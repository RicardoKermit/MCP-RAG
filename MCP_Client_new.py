import asyncio
import os
import json
import threading
import time
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response,send_file,send_from_directory
from dotenv import load_dotenv
import google.generativeai as genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import re
import psutil
import gc
from collections import deque
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import sqlite3
from openai import OpenAI
import requests
from psycopg2.extras import RealDictCursor


# PostgreSQL Logging System
from postgres_logger import PostgresLogger, OperationType

# Configuração de Logs
import logging

def setup_logging():
    """Configura o sistema de logs"""
    # Criar diretório de logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configurar formato
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Log para ficheiro
    file_handler = logging.FileHandler(
        f"logs/rag_app_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)
    
    # Log para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configurar logger principal
    logger = logging.getLogger('RAG_App')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Inicializar logger
logger = setup_logging()

# Sistema de Estatísticas Baseado em Logs
class LogAnalyzer:
    """Analisador de logs para extrair estatísticas do sistema RAG"""
    
    def __init__(self):
        self.logs_dir = Path("logs")
        self.stats_db_path = "statistics.db"
        self.init_database()
    
    def init_database(self):
        """Inicializa a base de dados de estatísticas"""
        conn = sqlite3.connect(self.stats_db_path)
        cursor = conn.cursor()
        
        # Tabela para estatísticas de operações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                operation_type TEXT,
                success BOOLEAN,
                duration REAL,
                topic TEXT,
                language TEXT,
                user_id TEXT,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela para estatísticas de performance
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                cpu_percent REAL,
                memory_percent REAL,
                memory_used_mb REAL,
                disk_usage_percent REAL,
                active_connections INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela para estatísticas de utilização
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                total_queries INTEGER,
                successful_queries INTEGER,
                failed_queries INTEGER,
                total_quiz_generations INTEGER,
                successful_quiz_generations INTEGER,
                total_connections INTEGER,
                successful_connections INTEGER,
                avg_query_duration REAL,
                avg_quiz_duration REAL,
                avg_connection_duration REAL,
                unique_users INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Analisa uma linha de log e extrai informações relevantes"""
        try:
            # Padrão para extrair informações do log
            pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (\w+) - (.+)'
            match = re.match(pattern, line)
            
            if not match:
                return None
            
            timestamp_str, logger_name, level, message = match.groups()
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            
            # Extrair informações específicas baseadas no tipo de mensagem
            if 'USER_INTERACTION' in message:
                return self.parse_user_interaction(timestamp, message)
            elif 'RAG_OPERATION' in message:
                return self.parse_rag_operation(timestamp, message)
            elif 'QUIZ_GENERATION' in message:
                return self.parse_quiz_generation(timestamp, message)
            elif 'RAG_RETRIEVE' in message:
                return self.parse_rag_retrieve(timestamp, message)
            elif 'SYSTEM_ERROR' in message:
                return self.parse_system_error(timestamp, message)
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao analisar linha de log: {e}")
            return None
    
    def parse_user_interaction(self, timestamp: datetime, message: str) -> Dict[str, Any]:
        """Analisa mensagens de interação do utilizador"""
        try:
            # Extrair ação e detalhes
            action_match = re.search(r'Action: (\w+)', message)
            details_match = re.search(r'Details: ({.*})', message)
            
            action = action_match.group(1) if action_match else "unknown"
            details = {}
            
            if details_match:
                try:
                    details = eval(details_match.group(1))  # Converter string dict para dict
                except:
                    details = {}
            
            return {
                'timestamp': timestamp,
                'type': 'user_interaction',
                'action': action,
                'details': details,
                'language': details.get('language', 'unknown'),
                'query_length': details.get('query_length', 0),
                'query_preview': details.get('query_preview', '')
            }
        except Exception as e:
            logger.error(f"Erro ao analisar interação do utilizador: {e}")
            return {}
    
    def parse_rag_operation(self, timestamp: datetime, message: str) -> Dict[str, Any]:
        """Analisa operações RAG"""
        try:
            # Extrair informações da operação RAG
            operation_match = re.search(r'RAG_OPERATION \| (\w+) \| Topic: ([^|]+) \| Success: (\w+) \| Duration: ([\d.]+)s', message)
            
            if operation_match:
                operation_type, topic, success_str, duration_str = operation_match.groups()
                success = success_str.lower() == 'true'
                duration = float(duration_str)
                
                # Extrair erro se houver
                error_match = re.search(r'Error: ([^|]+)', message)
                error_message = error_match.group(1) if error_match else None
                
                return {
                    'timestamp': timestamp,
                    'type': 'rag_operation',
                    'operation_type': operation_type,
                    'topic': topic.strip(),
                    'success': success,
                    'duration': duration,
                    'error_message': error_message
                }
            
            return {}
        except Exception as e:
            logger.error(f"Erro ao analisar operação RAG: {e}")
            return {}
    
    def parse_quiz_generation(self, timestamp: datetime, message: str) -> Dict[str, Any]:
        """Analisa geração de questionários"""
        try:
            # Extrair informações da geração de questionários
            quiz_match = re.search(r'QUIZ_GENERATION \| Topic: ([^|]+) \| Questions: (\d+) \| Difficulty: ([^|]+) \| Success: (\w+) \| Duration: ([\d.]+)s', message)
            
            if quiz_match:
                topic, num_questions, difficulty, success_str, duration_str = quiz_match.groups()
                success = success_str.lower() == 'true'
                duration = float(duration_str)
                
                # Extrair erro se houver
                error_match = re.search(r'Error: ([^|]+)', message)
                error_message = error_match.group(1) if error_match else None
                
                return {
                    'timestamp': timestamp,
                    'type': 'quiz_generation',
                    'topic': topic.strip(),
                    'num_questions': int(num_questions),
                    'difficulty': difficulty.strip(),
                    'success': success,
                    'duration': duration,
                    'error_message': error_message
                }
            
            return {}
        except Exception as e:
            logger.error(f"Erro ao analisar geração de questionários: {e}")
            return {}
    
    def parse_rag_retrieve(self, timestamp: datetime, message: str) -> Dict[str, Any]:
        """Analisa operações de retrieve RAG"""
        try:
            # Extrair informações do retrieve
            retrieve_match = re.search(r'RAG_RETRIEVE \| Prompt: ([^|]+) \| (\w+) \| Duration: ([\d.]+)s', message)
            
            if retrieve_match:
                prompt, status, duration_str = retrieve_match.groups()
                duration = float(duration_str)
                
                # Extrair erro se houver
                error_match = re.search(r'Error: ([^|]+)', message)
                error_message = error_match.group(1) if error_match else None
                
                return {
                    'timestamp': timestamp,
                    'type': 'rag_retrieve',
                    'prompt': prompt.strip(),
                    'status': status,
                    'duration': duration,
                    'error_message': error_message
                }
            
            return {}
        except Exception as e:
            logger.error(f"Erro ao analisar retrieve RAG: {e}")
            return {}
    
    def parse_system_error(self, timestamp: datetime, message: str) -> Dict[str, Any]:
        """Analisa erros do sistema"""
        try:
            # Extrair informações do erro
            error_match = re.search(r'SYSTEM_ERROR \| Operation: ([^|]+) \| Error: ([^|]+)', message)
            
            if error_match:
                operation, error = error_match.groups()
                
                # Extrair contexto se houver
                context_match = re.search(r'Context: ({.*})', message)
                context = {}
                
                if context_match:
                    try:
                        context = eval(context_match.group(1))
                    except:
                        context = {}
                
                return {
                    'timestamp': timestamp,
                    'type': 'system_error',
                    'operation': operation.strip(),
                    'error': error.strip(),
                    'context': context
                }
            
            return {}
        except Exception as e:
            logger.error(f"Erro ao analisar erro do sistema: {e}")
            return {}
    
    def analyze_logs(self) -> Dict[str, Any]:
        """Analisa todos os ficheiros de log e extrai estatísticas"""
        stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'operations_by_type': {},
            'performance_metrics': {},
            'usage_patterns': {},
            'error_analysis': {},
            'language_usage': {},
            'topic_analysis': {},
            'time_analysis': {}
        }
        
        all_operations = []
        
        # Analisar todos os ficheiros de log
        for log_file in self.logs_dir.glob("*.log"):
            if log_file.name.startswith(('rag_app_', 'rag_server_')):
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            parsed = self.parse_log_line(line.strip())
                            if parsed:
                                all_operations.append(parsed)
                except Exception as e:
                    logger.error(f"Erro ao ler ficheiro {log_file}: {e}")
                    continue
        
        # Processar estatísticas
        if all_operations:
            stats = self.calculate_statistics(all_operations)
        
        return stats
    
    def calculate_statistics(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula estatísticas baseadas nas operações extraídas"""
        stats = {
            'total_operations': len(operations),
            'successful_operations': 0,
            'failed_operations': 0,
            'operations_by_type': {},
            'performance_metrics': {},
            'usage_patterns': {},
            'error_analysis': {},
            'language_usage': {},
            'topic_analysis': {},
            'time_analysis': {},
            'recent_activity': []
        }
        
        # Agrupar operações por tipo
        for op in operations:
            op_type = op.get('type', 'unknown')
            if op_type not in stats['operations_by_type']:
                stats['operations_by_type'][op_type] = {
                    'count': 0,
                    'successful': 0,
                    'failed': 0,
                    'total_duration': 0,
                    'avg_duration': 0
                }
            
            stats['operations_by_type'][op_type]['count'] += 1
            
            # Contar sucessos/falhas
            if op.get('success', False):
                stats['successful_operations'] += 1
                stats['operations_by_type'][op_type]['successful'] += 1
            else:
                stats['failed_operations'] += 1
                stats['operations_by_type'][op_type]['failed'] += 1
            
            # Calcular durações
            duration = op.get('duration', 0)
            if duration > 0:
                stats['operations_by_type'][op_type]['total_duration'] += duration
        
        # Calcular médias de duração
        for op_type, data in stats['operations_by_type'].items():
            if data['count'] > 0:
                data['avg_duration'] = data['total_duration'] / data['count']
        
        # Análise de linguagem
        for op in operations:
            if op.get('type') == 'user_interaction':
                language = op.get('language', 'unknown')
                if language not in stats['language_usage']:
                    stats['language_usage'][language] = 0
                stats['language_usage'][language] += 1
        
        # Análise de tópicos
        for op in operations:
            topic = op.get('topic', '')
            if topic and topic != 'MCP_Server.py':
                if topic not in stats['topic_analysis']:
                    stats['topic_analysis'][topic] = 0
                stats['topic_analysis'][topic] += 1
        
        # Análise temporal
        for op in operations:
            timestamp = op.get('timestamp')
            if timestamp:
                hour = timestamp.hour
                if hour not in stats['time_analysis']:
                    stats['time_analysis'][hour] = 0
                stats['time_analysis'][hour] += 1
        
        # Análise de erros
        for op in operations:
            if not op.get('success', True):
                error = op.get('error_message', 'Unknown error')
                if error not in stats['error_analysis']:
                    stats['error_analysis'][error] = 0
                stats['error_analysis'][error] += 1
        
        # Atividade recente (últimas 24 horas)
        now = datetime.now()
        recent_ops = [op for op in operations if op.get('timestamp') and (now - op['timestamp']).days < 1]
        stats['recent_activity'] = len(recent_ops)
        
        return stats
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Obtém métricas do sistema em tempo real"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024 * 1024),
                'memory_total_mb': memory.total / (1024 * 1024),
                'disk_usage_percent': disk.percent,
                'disk_free_gb': disk.free / (1024 * 1024 * 1024),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Erro ao obter métricas do sistema: {e}")
            return {}
    
    def save_statistics(self, stats: Dict[str, Any]):
        """Salva estatísticas na base de dados"""
        try:
            conn = sqlite3.connect(self.stats_db_path)
            cursor = conn.cursor()
            
            # Salvar métricas de performance
            system_metrics = self.get_system_metrics()
            if system_metrics:
                cursor.execute('''
                    INSERT INTO performance_stats 
                    (timestamp, cpu_percent, memory_percent, memory_used_mb, disk_usage_percent, active_connections)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(),
                    system_metrics.get('cpu_percent', 0),
                    system_metrics.get('memory_percent', 0),
                    system_metrics.get('memory_used_mb', 0),
                    system_metrics.get('disk_usage_percent', 0),
                    0  # TODO: Implementar contagem de conexões ativas
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Erro ao salvar estatísticas: {e}")

log_analyzer: LogAnalyzer = LogAnalyzer() 

def map_tool_to_operation(tool_name: str) -> OperationType:
    """Map a tool name to the corresponding OperationType enum."""
    if tool_name == "retrieve":
        return OperationType.RAG_QUERY
    elif tool_name == "generate_quiz_with_difficulty" or tool_name=="practice_quiz" :
        return OperationType.QUIZ_GENERATION
    elif tool_name == "study_plan_generator":
        return OperationType.STUDY_PLAN_GENERATION
    elif tool_name == "interactive_flashcards":
        return OperationType.FLASHCARD_GENERATION
    elif tool_name == "generate_test":
        return OperationType.TEST_GENERATION
    elif tool_name == "generate_dev_questions":
        return OperationType.OPEN_QUESTION
    elif tool_name == "generate_lesson_summary":
        return OperationType.SUMMARY_GENERATION
    elif tool_name == "recommend_reading_material":
        return OperationType.RECOMMEND_READING_MATERIAL
    elif tool_name == "analyze_student_queries":
        return OperationType.ANALYZE_STUDENT_QUERIES
    elif tool_name == "add_new_pdfs":
        return OperationType.FILE_UPLOAD
    elif tool_name == "recommend_reading_material":
        return OperationType.RECOMMEND_READING_MATERIAL
    else:
        return OperationType.API_CALL  # fallback

def log_rag_operation(operation: str, topic: str, success: bool, duration: float | None = None, error: str | None = None, user_id: str | None = None):
    duration_ms = int(duration * 1000) if duration else None
    # NEW: write to Postgres
    try:
        postgres_logger.log_operation(
            operation_type=OperationType.RAG_QUERY,
            user_id=user_id,
            details={"operation": operation, "topic": topic, "duration_ms": duration_ms, **({"error": error} if error else {})},
            status="success" if success else "error",
            error_message=error,
            duration_ms=duration_ms,
            ip_address=(request.remote_addr if "request" in globals() and request else None),
            user_agent=(request.headers.get("User-Agent") if "request" in globals() and request else None),
        )
        if duration_ms is not None:
            postgres_logger.update_operation_stats(OperationType.RAG_QUERY.value, success, duration_ms)
    except Exception as e:
        logger.warning(f"Postgres log_rag_operation failed: {e}")
    # keep existing file/console log
    logger.info(f"RAG_OPERATION | {operation} | Topic: {topic} | Success: {success} | Duration: {duration}s | Error: {error}")

def log_quiz_generation(topic: str, num_questions: int, difficulty: str, success: bool, duration: float | None = None, error: str | None = None, user_id: str | None = None):
    duration_ms = int(duration * 1000) if duration else None
    # NEW: write to Postgres
    try:
        postgres_logger.log_operation(
            operation_type=OperationType.QUIZ_GENERATION,
            user_id=user_id,
            details={"topic": topic, "num_questions": num_questions, "difficulty": difficulty, "duration_ms": duration_ms, **({"error": error} if error else {})},
            status="success" if success else "error",
            error_message=error,
            duration_ms=duration_ms,
        )
        if duration_ms is not None:
            postgres_logger.update_operation_stats(OperationType.QUIZ_GENERATION.value, success, duration_ms)
    except Exception as e:
        logger.warning(f"Postgres log_quiz_generation failed: {e}")
    # keep existing file/console log
    logger.info(f"QUIZ_GENERATION | {topic} | {num_questions} | {difficulty} | {success} | {duration}s | {error}")
  

def log_system_error(operation: str, error: str, context: dict | None = None, user_id: str | None = None):
    # NEW: write to Postgres
    try:
        postgres_logger.log_operation(
            operation_type="system_error",
            user_id=user_id,
            details={"operation": operation, "context": context or {}},
            status="error",
            error_message=error,
        )
    except Exception as e:
        logger.warning(f"Postgres log_system_error failed: {e}")
    # keep existing file/console log
    logger.error(f"SYSTEM_ERROR | Operation: {operation} | Error: {error} | Context: {context}")

def log_user_interaction(action: str, details: dict | None = None, user_id: str | None = None, session_id: str | None = None):
    # NEW: write to Postgres
    try:
        postgres_logger.log_user_interaction(user_id=user_id, action=action, details=details, session_id=session_id)
    except Exception as e:
        logger.warning(f"Postgres log_user_interaction failed: {e}")
    # keep existing file/console log
    logger.info(f"USER_INTERACTION | {action} | {details}")

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MOODLE_TOKEN=os.getenv("MOODLE_TOKEN")
MOODLE_URL=os.getenv("MOODLE_URL")

if not GEMINI_API_KEY:
    raise ValueError("GOOGLE_API_KEY não definido no .env")

genai.configure(api_key=GEMINI_API_KEY)

# --- ADD: Postgres logger init ---
db_config = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "database": os.getenv("PG_DATABASE", "rag_system"),
    "user": os.getenv("PG_USER", "rag_user"),
    "password": os.getenv("PG_PASSWORD", "rag_password_secure_2024"),
}

ROLE_PERMISSIONS = {
                    "Admin": os.getenv("ADMIN_TOOLS", "all").split(","),
                    "Professor": os.getenv("TEACHER_TOOLS", "").split(","),
                    "Aluno": os.getenv("STUDENT_TOOLS", "").split(","),
                }

ROLE_PROMPTS = {
    "Professor": os.getenv("PROMPT_PROFESSOR", ""),
    "Aluno": os.getenv("PROMPT_ALUNO", ""),
    "Admin": os.getenv("PROMPT_ADMIN", "")
}


postgres_logger = PostgresLogger(db_config)

# Dicionário de traduções
#TRANSLATIONS=os.getenv("TRANSLATIONS")

translations_file = os.getenv("TRANSLATIONS", "translations.json")
with open(Path(__file__).parent / translations_file, "r", encoding="utf-8") as f:
    TRANSLATIONS = json.load(f)

# Modelos Gemini disponíveis (ordenados por custo - menor para maior)
#ALL_MODELS=os.getenv("ALL_MODELS")

models_file = os.getenv("ALL_MODELS", "models.json")

with open(Path(__file__).parent / models_file, "r", encoding="utf-8") as f:
    ALL_MODELS = json.load(f)

app = Flask(__name__, static_folder='templates/static')


app.config['SECRET_KEY'] = 'your-secret-key-here'

# Event loop global
loop = None
loop_thread = None
event_loop = None

def create_event_loop():
    """Cria e mantém um event loop em uma thread separada"""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()

def start_event_loop():
    """Inicia o event loop em uma thread separada"""
    global loop_thread
    try:
        loop_thread = threading.Thread(target=create_event_loop, daemon=True)
        loop_thread.start()
        # Aguardar um pouco para garantir que o loop iniciou
        import time
        time.sleep(0.2)
    except Exception as e:
        print(f"❌ Erro ao iniciar event loop: {e}")

class MCPGeminiClient:
    def __init__(self):
        self.session = None
        self.stdio = None
        self.write = None
        self.tools = []
        self.stdio_cm = None
        self.session_cm = None
        self.is_connected = False
        self.current_model = "gemini-2.5-flash"  # Changed to the most economical model
        self.current_provider = ALL_MODELS[self.current_model]["provider"]
        self.current_language = "pt"  # Idioma padrão (Português)
        self.conversation_history = []  # Histórico da conversa
        

    def set_model(self, model_name):
        """Define o modelo a ser usado (Gemini ou OpenAI) e sincroniza com o servidor"""
        if model_name in ALL_MODELS:
            self.current_model = model_name
            self.current_provider = ALL_MODELS[model_name]["provider"]
            print(f"✅ Modelo definido: {model_name} (provider={self.current_provider})")
        
            # Se já estiver conectado ao servidor, sincroniza
            if self.is_connected:
                try:
                    # Chamar a ferramenta set_model do servidor
                    result = run_async(self.session.call_tool("set_model", {"model_name": model_name}))
                    print(f"🔄 Modelo sincronizado com servidor: {model_name}")
                except Exception as e:
                    print(f"⚠️ Erro ao sincronizar modelo com servidor: {e}")
            return True
        return False

    def get_current_model(self):
        return self.current_model

    def get_current_rag_backend(self):
        return self.current_rag_backend

    def get_rag_backend(self):
        """Obtém o backend RAG atual a partir do servidor MCP."""
        if not self.is_connected:
            return {"success": False, "error": "Not connected"}
        try:
            result = run_async(self.session.call_tool("get_rag_backend", {}))
            # Normalizar resultado (CallToolResult -> dict)
            try:
                # Alguns clientes retornam conteúdo em result.content (lista de partes)
                content = getattr(result, 'content', None)
                if isinstance(content, list) and content:
                    # Procurar parte de texto
                    for part in content:
                        text = getattr(part, 'text', None) or part.get('text') if isinstance(part, dict) else None
                        if text:
                            import json as _json
                            try:
                                return _json.loads(text)
                            except Exception:
                                return {"success": True, "data": text}
                # Se já for dict serializável
                if isinstance(result, dict):
                    return result
                # Fallback para string
                return {"success": True, "data": str(result)}
            except Exception:
                return {"success": True, "data": str(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_rag_backend(self, backend):
        """Define o backend RAG ("qdrant" ou "chroma") no servidor MCP."""
        if not self.is_connected:
            return {"success": False, "error": "Not connected"}
        try:
            result = run_async(self.session.call_tool("set_rag_backend", {"backend": backend}))
            # Normalizar resultado (CallToolResult -> dict)
            try:
                content = getattr(result, 'content', None)
                if isinstance(content, list) and content:
                    for part in content:
                        text = getattr(part, 'text', None) or part.get('text') if isinstance(part, dict) else None
                        if text:
                            import json as _json
                            try:
                                return _json.loads(text)
                            except Exception:
                                # Tentar inferir sucesso a partir do texto
                                return {"success": "sucesso" in text.lower(), "message": text}
                if isinstance(result, dict):
                    return result
                return {"success": True, "message": str(result)}
            except Exception:
                return {"success": True, "message": str(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_available_models(self):
        """Retorna a lista de modelos disponíveis"""
        return ALL_MODELS
    
    def set_language(self, language):
        """Define o idioma atual para as respostas"""
        if language in TRANSLATIONS:
            self.current_language = language
            print(f"🌐 Idioma alterado para: {language}")
            return True
        return False
    
    def clear_conversation_history(self):
        """Limpa o histórico da conversa"""
        self.conversation_history = []
        print("🗑️ Histórico da conversa limpo")



    async def connect_to_server(self, server_script_path):
        try:
            print(f"🔗 Tentando conectar ao servidor: {server_script_path}")
            
            # Verificar se o arquivo existe
            if not os.path.exists(server_script_path):
                print(f"❌ Arquivo não encontrado: {server_script_path}")
                return False, f"Arquivo não encontrado: {server_script_path}"
            
            is_python = server_script_path.endswith('.py')
            if not is_python:
                raise ValueError("Apenas servidores Python suportados neste exemplo.")
            
            print("📋 Configurando parâmetros do servidor...")
            server_params = StdioServerParameters(
                command="python",
                args=[server_script_path],
                env=None
            )
            
            print("🔌 Iniciando conexão stdio...")
            self.stdio_cm = stdio_client(server_params)
            self.stdio, self.write = await self.stdio_cm.__aenter__()
            
            print("🤝 Criando sessão MCP...")
            self.session_cm = ClientSession(self.stdio, self.write)
            self.session = await self.session_cm.__aenter__()
            
            print("🚀 Inicializando sessão...")
            await self.session.initialize()
            
            print("📋 Listando ferramentas...")
            response = await self.session.list_tools()
            self.tools = response.tools
            self.is_connected = True
            
            # Verificar modelo atual do servidor
            try:
                model_info = await self.session.call_tool("get_current_model", {})
                # Processar resposta do servidor
                if hasattr(model_info.content, 'text'):
                    import json
                    server_model_data = json.loads(model_info.content.text)
                    server_model = server_model_data.get(self.current_model, "gemini-2.5-flash")
                    if server_model != self.current_model:
                        print(f"🔄 Sincronizando modelo do servidor: {server_model}")
                        self.current_model = server_model
                elif hasattr(model_info.content, '__iter__'):
                    # Tentar processar como lista de conteúdos
                    for content in model_info.content:
                        if hasattr(content, 'text'):
                            import json
                            server_model_data = json.loads(content.text)
                            server_model = server_model_data.get(self.current_model, "gemini-2.5-flash")
                            if server_model != self.current_model:
                                print(f"🔄 Sincronizando modelo do servidor: {server_model}")
                                self.current_model = server_model
                            break
                else:
                    print("⚠️ Formato de resposta inesperado do servidor")
            except Exception as e:
                print(f"⚠️ Erro ao verificar modelo do servidor: {e}")
                print(f"⚠️ Tipo de resposta: {type(model_info.content)}")
                print(f"⚠️ Conteúdo: {model_info.content}")
            
            print(f"✅ Conectado com sucesso! Ferramentas: {[tool.name for tool in self.tools]}")
            return True, [tool.name for tool in self.tools]
        except Exception as e:
            print(f"❌ Erro ao conectar: {str(e)}")
            self.is_connected = False
            # Limpar recursos em caso de erro
            try:
                if hasattr(self, 'session_cm') and self.session_cm:
                    await self.session_cm.__aexit__(None, None, None)
                if hasattr(self, 'stdio_cm') and self.stdio_cm:
                    await self.stdio_cm.__aexit__(None, None, None)
            except:
                pass
            return False, str(e)

    async def process_query(self, query):
        if not self.is_connected:
            return "Erro: Cliente não está conectado ao servidor MCP."
    
        try: 
            
            usertype=os.getenv(session["role"])
            
            print(usertype)
            
            

            print(f"🤔 Processando pergunta: {query}")
            print(f"🤖 Usando modelo: {self.current_model} (provider={self.current_provider})")
        
            # Adicionar pergunta ao histórico
            self.conversation_history.append({"role": "user", "content": query})
        
            # Construir contexto da conversa
            conversation_context = ""
            if len(self.conversation_history) > 1:
                recent_history = self.conversation_history[-6:]
                conversation_context = "\n\nContexto da conversa anterior:\n"
                for msg in recent_history:
                    role = "Utilizador" if msg["role"] == "user" else "Assistente"
                    conversation_context += f"{role}: {msg['content']}\n"
        
            tool_descriptions = "\n".join(
                f"- {tool.name}: {tool.description}" for tool in self.tools
            )
        
            language_instructions = {
                "pt": "IMPORTANTE: Responde SEMPRE em português de Portugal. Usa termos e expressões apropriados para português europeu.",
                "en": "IMPORTANTE: Always respond in British English. Use appropriate British English terms and expressions."
            }

            few_shot_examples = """
                                Example 1:
                                Question: Who wrote The Lusiads?
                                TOOL: retrieve
                                ARGS: {"prompt": "The Lusiads author"}

                                Example 2:
                                Question: What are the rules of Monopoly?
                                TOOL: retrieve
                                ARGS: {"prompt": "Monopoly game rules"}

                                Example 3:
                                Question: What is the educational importance of LEGO?
                                TOOL: retrieve
                                ARGS: {"prompt": "Educational importance of LEGO"}

                                Example 4:
                                Question: Create 5 medium-difficulty questions about Artificial Intelligence. TOOL: generate_quiz_with_difficulty
                                ARGS: {"topic": "Artificial Intelligence", "num_questions": 5, "difficulty": "medium"}

                                Example 5:
                                Question: Create a quiz with 3 easy questions about computer networks.
                                TOOL: generate_quiz_with_difficulty
                                ARGS: {"topic": "Computer Networks", "num_questions": 3, "difficulty": "easy"}
                            """

        
            prompt = (
                        f"{conversation_context}\n"
                        f"Available tools:\n{tool_descriptions}\n"
                        f"{language_instructions.get(self.current_language, language_instructions['pt'])}\n"
                        "IMPORTANT: You must ALWAYS use a tool. NEVER answer directly.\n"
                        "For any question about PDF content, use the 'retrieve' tool.\n"
                        "For the 'retrieve' tool, always use 'prompt' as the argument key.\n"
                        "To generate quizzes with difficulty validation, use 'generate_quiz_with_difficulty'.\n"
                        "To add the pdfs to the rag, use 'add new_pfds'.\n"
                        "For analyses use 'analyze_student_queries'. Be as analytical as possible and try to discover patterns in what the student has researched.\n"
                        "ALWAYS answer in the format:\n"
                        "TOOL: <tool_name>\nARGS: <json_com_arguments>\n"
                        "Here are some examples:\n"
                        f"{few_shot_examples}\n"
                        f"---\n"
                        f"Current user question: {query}\n"
                        f"User type: {usertype}\n"
                    )
        
            # --- PRIMEIRA GERAÇÃO ---
            if self.current_provider == "gemini":
                model = genai.GenerativeModel(self.current_model)
                response = model.generate_content(prompt)
                text = response.text.strip()

            elif self.current_provider == "openai":
                response = openai_client.chat.completions.create(
                    model=self.current_model,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.choices[0].message.content.strip()

            elif self.current_provider == "ollama":
                import requests
                try:
                    r = requests.post(
                        "http://localhost:11434/api/chat",
                        json={
                            "model": self.current_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False
                        },
                        timeout=60
                    )
                    data = r.json()
                    if "message" in data and "content" in data["message"]:
                        text = data["message"]["content"].strip()
                    elif "content" in data:
                        text = data["content"].strip()
                    else:
                        text = str(data)
                except Exception as e:
                    text = f"Erro ao chamar Ollama local: {e}"

            else:
                raise ValueError(f"Provider desconhecido: {self.current_provider}")

            print(f"📝 Resposta inicial do modelo: {text}...")

            # --- PARSER VIA REGEX ---
            match = re.search(r"TOOL:\s*(\w+)\s*ARGS:\s*(\{.*\})", text, re.DOTALL)
            if match:
                # Extrair TOOL e ARGS
                #lines = text.splitlines()
                #tool_name = lines[0].replace("TOOL:", "").strip()
                #args_line = next((l for l in lines if l.startswith("ARGS:")), None)
                #tool_args = json.loads(args_line.replace("ARGS:", "").strip()) if args_line else {}
                
                tool_name = match.group(1).strip()
                try:
                    tool_args = json.loads(match.group(2))
                except Exception:
                    tool_args = {}


                def get_allowed_tools():
                    if session["role"] == "Professor":
                       return  ROLE_PERMISSIONS["Professor"]
                    elif session["role"] == "Admin":
                        return ROLE_PERMISSIONS["Admin"]
                    else:
                        return ROLE_PERMISSIONS["Aluno"]
          
                # Lista de ferramentas válidas
                #allowed_tools = ["retrieve", "generate_quiz_with_difficulty", "generate_video_with_veo", "generate_dev_questions","study_plan_generator","generate_lesson_summary","interactive_flashcards","generate_test"]
                allowed_tools=get_allowed_tools()


                print(allowed_tools)
                
                if tool_name not in allowed_tools:
                    print(f"⚠️ Ferramenta inválida sugerida: {tool_name}, forçando 'retrieve'")
                    tool_name = "retrieve"
                    tool_args = {"prompt": query}

                print(f"🔧 Chamando ferramenta: {tool_name} com args: {tool_args}")

                if tool_name == "retrieve":
                    if "query" in tool_args:
                        tool_args["prompt"] = tool_args.pop("query")
                    if not tool_args.get("prompt"):
                        tool_args["prompt"] = query

                result = await self.session.call_tool(tool_name, tool_args)

                print("Results: ", result)
                
                raw_response = ""
                details = {}

                try:
                    # Caso o server tenha devolvido JSON válido dentro do TextContent
                    if hasattr(result, 'content') and result.content:
                        # pode ser lista de TextContent
                        content_list = list(result.content)
                        if content_list and hasattr(content_list[0], 'text'):
                            parsed = json.loads(content_list[0].text)
                            raw_response = parsed.get("response", "")
                            details = parsed.get("details", {})
                            download_url =parsed.get("download_url", {})
                            
                        else:
                            raw_response = str(result.content)
                    else:
                        raw_response = str(result)

                except Exception as e:
                    print("⚠️ Falha ao parsear resposta JSON:", e)
                    raw_response = str(result)
                    details = {}
                    download_url= None

                print("DETAILS: ",details)
                print("download_url: ",download_url)


                print(f"📄 Resposta bruta da ferramenta: {raw_response}...")

                final_language_instructions = {
                    "pt": "IMPORTANTE: Responde SEMPRE em português de Portugal. Usa termos e expressões apropriados para português europeu.",
                    "en": "IMPORTANTE: Always respond in British English. Use appropriate British English terms and expressions."
                }

                if tool_name == "recommend_reading_material":
                    follow_up_prompt = f"""
    The user requested reading recommendations on ** {query} **. 

Recovered Context of Documents (PDFs):
{raw_response}

Type of User: {usertype}

From this context, it generates a clear and structured list with:
- ** Books ** (Title + Author)
- ** Articles/Papers ** (Title + Source or where it can be found)
- ** Videos ** (YouTube channels, documentaries, relevant audiovisual resources)

{final_language_instructions.get (self.current_language, final_language_instructions ['pt'])}

Format in Markdown:
- USA ** Bold ** for categories (books, articles, videos)
- Use lists with * or - for items
- Includes short descriptions (1–2 sentences) to contextualize each recommendation
- Maintains the pedagogical tone, organized and easy to follow
- Provides links if so possible
    """
                else:
                    follow_up_prompt = f"""
    Original question: {query}

    Information found:
    {raw_response}

    Type of user: {usertype}

    {final_language_instructions.get(self.current_language, final_language_instructions['pt'])}

    Please present this information in a clear, well-structured, and easy-to-read format.
    Use Markdown formatting to organize your answer:

    - Use **bold** for headings and important points
    - Use lists with * or - to organize information
    - Use paragraphs to separate ideas
    - Use > for important quotes
    - Organize your answer in a logical and structured way
    - Highlight important points with **bold**
    - Use line breaks for better readability
    """


                print("🔄 Gerando resposta final...")

                # --- SEGUNDA GERAÇÃO (follow_up) ---
                if self.current_provider == "gemini":
                    follow_up_response = model.generate_content(follow_up_prompt)
                    final_response = follow_up_response.text.strip()

                elif self.current_provider == "openai":
                    follow_up_response = openai_client.chat.completions.create(
                        model=self.current_model,
                        messages=[{"role": "user", "content": follow_up_prompt}]
                    )
                    final_response = follow_up_response.choices[0].message.content.strip()

                elif self.current_provider == "ollama":
                    try:
                        r = requests.post(
                            "http://localhost:11434/api/chat",
                            json={
                                "model": self.current_model,
                                "messages": [{"role": "user", "content": follow_up_prompt}],
                                "stream": False
                            },
                            timeout=60
                        )
                        data = r.json()
                        if "message" in data and "content" in data["message"]:
                            final_response = data["message"]["content"].strip()
                        elif "content" in data:
                            final_response = data["content"].strip()
                        else:
                            final_response = str(data)
                    except Exception as e:
                        final_response = f"Erro ao gerar resposta final com Ollama: {e}"

                else:
                    raise ValueError(f"Provider desconhecido: {self.current_provider}")

                print(f"✅ Resposta final: {final_response[:100]}...")
                self.conversation_history.append({"role": "assistant", "content": final_response})
                return final_response, tool_name, details,download_url

            else:
                print(f"⚠️ Resposta não contém TOOL: {text}")
                return text

        except Exception as e:
            error_msg = f"Erro ao processar a pergunta: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

    async def cleanup(self):
        if hasattr(self, "session_cm") and self.session_cm:
            await self.session_cm.__aexit__(None, None, None)
        if hasattr(self, "stdio_cm") and self.stdio_cm:
            await self.stdio_cm.__aexit__(None, None, None)

# Instância global do cliente
mcp_client = MCPGeminiClient()

def run_async(coro):
    """Executa uma corotina no event loop global"""
    try:
        global loop, event_loop
        if loop is None:
            start_event_loop()
            import time
            time.sleep(0.1)  # Pequena pausa para garantir que o loop iniciou
        
        # Usar loop como event_loop
        event_loop = loop
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    except Exception as e:
        print(f"❌ Erro ao executar corotina: {e}")
        return f"Erro: {str(e)}"

@app.route('/')
def index():
    # Check if user is authenticated
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    # Add headers to prevent caching
    response = make_response(render_template('simple.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/login', methods=['GET', 'POST'])
def login():
    def get_role_from_username(username: str) -> str:
        """Determina o role pelo primeiro caracter do username/email."""
        if not username:
            return "Aluno"
        first_char = username[0]
        if first_char.isalpha():
            return "Professor"
        elif first_char.isdigit():
            return "Aluno"
        return "Aluno"

    def get_or_create_user(username: str, email: str = None, full_name: str = None,moodle_id: int = None):
        """Verifica se o user existe, senão cria com role atribuído automaticamente."""
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, role FROM users WHERE username = %s AND is_active = %s",(username, True))
                row = cur.fetchone()
                
                if row:
                    return str(row[0]), row[1]  # id, role

                # Se não existir → criar
                role = get_role_from_username(username)
                cur.execute(
                    """
                    INSERT INTO users (username, email, courses, role,moodle_user_id)
                    VALUES (%s, %s, %s, %s,%s)
                    RETURNING id
                    """,
                     (username, email, full_name, role,moodle_id)
                )
                new_id = cur.fetchone()[0]
                conn.commit()
                return str(new_id), role

    if request.method == 'GET':
        if session.get('authenticated'):
            return redirect(url_for('index'))

        response = make_response(render_template('login.html'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    elif request.method == 'POST':
        try:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return jsonify({'success': False, 'error': 'Nome de utilizador e palavra-passe são obrigatórios'})

            # Autenticação no Moodle
            auth_url = "http://localhost/login/token.php"
            params = {
                'username': username,
                'password': password,
                'service': 'moodle_mobile_app'
            }

            params2 = {
                "wstoken": MOODLE_TOKEN,
                "wsfunction": "core_user_get_users",
                "moodlewsrestformat": "json",
                "criteria[0][key]": "email",
                "criteria[0][value]": username
            }

           
            print("params2----> ", params2)
            
            
            with httpx.Client() as client:
                response = client.get(auth_url, params=params)
                response2 = client.get(MOODLE_URL, params=params2)
                dados = response2.json()
                print("response2----> ", dados)
                print("\n\ndados['users'][0]['id']----> ", dados['users'][0]['id'])
                
                if response.status_code == 200:


                    user_id = dados['users'][0]['id']
                    params3 = {
                        "wstoken": MOODLE_TOKEN,
                        "wsfunction": "core_enrol_get_users_courses",
                        "moodlewsrestformat": "json",
                        "userid": dados['users'][0]['id'],
                    }
                    response3 = client.get(MOODLE_URL, params=params3)
                    dados2 = response3.json()
                    print("response3----> ", dados2)
                    
                    # extrair só os nomes completos
                    fullnames = [c['fullname'] for c in dados2]

                    print("fullnames----> ", fullnames)
                    
                    
                    
                    try:
                        auth_data = response.json()
                        if 'token' in auth_data and auth_data['token']:
                            # Autenticação válida
                            session['authenticated'] = True
                            session['username'] = username
                            session['moodle_token'] = auth_data['token']

                            # Criar ou obter utilizador na BD
                            user_id, role = get_or_create_user(username, email=username,full_name=fullnames,moodle_id=dados['users'][0]['id'])
                            session['user_id'] = user_id  # 🔑 agora guardamos o ID
                            session['role'] = role
                            session['moodle_id'] = dados['users'][0]['id']
                            session['courses'] = fullnames

                            print("session----> ", session)

                            # Log opcional
                            postgres_logger.log_operation(
                                operation_type="user_login",
                                details={"username": username, "role": role},
                                status="success"
                            )

                            return jsonify({'success': True, 'role': role, 'user_id': user_id})
                        else:
                            return jsonify({'success': False, 'error': 'Credenciais inválidas'})
                    except json.JSONDecodeError:
                        return jsonify({'success': False, 'error': 'Resposta inválida do servidor Moodle'})
                else:
                    return jsonify({'success': False, 'error': 'Erro na autenticação com Moodle'})
                    
        except Exception as e:
            postgres_logger.log_operation(
                operation_type="user_login",
                details={"username": username},
                status="error",
                error_message=str(e)
            )
            return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'})


@app.route('/logout')
def logout():
    # Clear session
    session.clear()
    return redirect(url_for('login'))

@app.route('/connect', methods=['POST'])
def connect():
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    start_time = time.time()
    try:
        data = request.get_json()
        server_path = data.get('server_path', 'MCP_Server_new.py')
        
        # Log da tentativa de conexão
        log_user_interaction("connect", {
            "server_path": server_path
        })
        
        print(f"🔄 Tentando conectar ao servidor: {server_path}")
        
        # Verificar se o arquivo existe
        if not os.path.exists(server_path):
            log_system_error("connect", f"Arquivo não encontrado: {server_path}")
            return jsonify({
                'success': False,
                'error': f'Arquivo não encontrado: {server_path}'
            })
        
        success, result = run_async(mcp_client.connect_to_server(server_path))
        
        # Calcular duração
        duration = time.time() - start_time
        
        if success:
            print(f"✅ Conectado com sucesso! Ferramentas: {result}")
            log_rag_operation("connect", server_path, True, duration)
            return jsonify({
                'success': True,
                'tools': result
            })
        else:
            print(f"❌ Falha na conexão: {result}")
            log_rag_operation("connect", server_path, False, duration, result)
            return jsonify({
                'success': False,
                'error': result
            })
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        print(f"❌ Erro na rota de conexão: {error_msg}")
        log_system_error("connect", error_msg, {
            "server_path": server_path,
            "duration": duration
        })
        return jsonify({
            'success': False,
            'error': f'Erro interno: {error_msg}'
        })

@app.route('/query', methods=['POST'])
def query():
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401

    start_time = time.time()
    query_text = None
    tool = None
    details = {}

    try:
        data = request.get_json()
        query_text = data.get('query', '')
        current_language = data.get('language', 'pt')

        if not query_text:
            return jsonify({'response': '⚠️ Pergunta vazia.'})

        mcp_client.set_language(current_language)

        response, tool, details, download_url = run_async(mcp_client.process_query(query_text))

        print("📦 DETAILS RECEBIDOS:", details)
        print("TOOL: ",tool)
       

        duration_ms = int((time.time() - start_time) * 1000)
        op_type = map_tool_to_operation(tool)

        postgres_logger.log_operation(
            operation_type=op_type,
            user_id=session.get("user_id"),
            details=details,
            status="success",
            duration_ms=duration_ms
        )
        postgres_logger.update_operation_stats(op_type.value, True, duration_ms)

        return jsonify({'response': response,'download_url': download_url})

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        op_type = map_tool_to_operation(tool if tool else "unknown")

        postgres_logger.log_operation(
            operation_type=op_type,
            user_id=session.get("user_id"),
            details=details if details else {"query": query_text[:50] if query_text else ""},
            status="error",
            error_message=error_msg,
            duration_ms=duration_ms
        )
        postgres_logger.update_operation_stats(op_type.value, False, duration_ms)

        return jsonify({'response': f'Erro ao processar a pergunta: {error_msg}'})


@app.route('/clear-history', methods=['POST'])
def clear_history():
    """Limpa o histórico da conversa"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        mcp_client.clear_conversation_history()
        return jsonify({'success': True, 'message': 'Histórico limpo com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/status')
def status():
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'connected': mcp_client.is_connected,
        'tools': [tool.name for tool in mcp_client.tools] if mcp_client.is_connected else [],
        'current_model': mcp_client.current_model,
        'available_models': mcp_client.get_available_models()
    })

@app.route('/models', methods=['GET'])
def get_models():
    """Retorna a lista de modelos disponíveis"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'models': mcp_client.get_available_models(),
        'current_model': mcp_client.current_model
    })

@app.route('/set-model', methods=['POST'])
def set_model():
    """Define o modelo Gemini a ser usado"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        model_name = data.get('model')
        
        if mcp_client.set_model(model_name):
            return jsonify({
                'success': True,
                'message': f'Modelo alterado para {ALL_MODELS[model_name]["name"]}',
                'current_model': model_name
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Modelo inválido'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/rag-backend', methods=['GET'])
def get_rag_backend_route():
    """Retorna o backend RAG atual (qdrant/chroma) em JSON limpo."""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401

    raw = mcp_client.get_rag_backend()
    print("RAW RAGBACK:", raw)

    backend_data = None

    if isinstance(raw, dict) and "backend" in raw:
        backend_data = raw

    elif isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], str):
        data_str = raw["data"]

        try:
            start = data_str.find("text='") + len("text='")
            end = data_str.find("}', annotations=") + 1  # inclui a chaveta final
            if start > -1 and end > -1:
                json_str = data_str[start:end]

                # remover escapes de barras
                json_str = json_str.encode("utf-8").decode("unicode_escape")

                backend_data = json.loads(json_str)
        except Exception as e:
            print("❌ Erro a parsear JSON do backend:", e)

    if not backend_data:
        return jsonify({'success': False, 'error': 'Invalid response', 'raw': raw}), 500

    return jsonify({'success': True, **backend_data})

@app.route('/set-rag-backend', methods=['POST'])
def set_rag_backend_route():
    """Altera o backend RAG (qdrant/chroma) em tempo de execução."""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        backend = data.get('backend', '').lower()
        result = mcp_client.set_rag_backend(backend)
        return jsonify({"success": True, "backend": backend})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/translations/<language>', methods=['GET'])
def get_translations(language):
    """Retorna as traduções para o idioma especificado"""
    if language in TRANSLATIONS:
        return jsonify({
            'success': True,
            'translations': TRANSLATIONS[language]
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Idioma não suportado'
        })

@app.route('/languages', methods=['GET'])
def get_languages():
    """Retorna a lista de idiomas disponíveis"""
    return jsonify({
        'languages': {
            'pt': 'Português',
            'en': 'English'
        }
    })

@app.route('/test')
def test():
    return jsonify({'message': 'API funcionando!'})

@app.route('/generate-quiz', methods=['POST'])
def generate_quiz():
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    start_time = time.time()
    try:
        data = request.get_json()
        topic = data.get('topic', '')
        question_type = data.get('questionType', 'multiple_choice')
        num_questions = data.get('numQuestions', 5)
        difficulty = data.get('difficulty', 'mixed')
        
        # Log da tentativa de geração
        log_user_interaction("generate_quiz", {
            "topic": topic,
            "question_type": question_type,
            "num_questions": num_questions,
            "difficulty": difficulty
        })
        
        if not topic:
            log_system_error("generate_quiz", "Tópico vazio")
            return jsonify({'error': 'Tópico é obrigatório'})
        
        # Construir prompt para geração de questionário
        prompt = f"Gera {num_questions} perguntas de {question_type} sobre {topic} com nível de dificuldade {difficulty}"
        
        # Executar no servidor MCP
        result = run_async(mcp_client.process_query(prompt))
        
        # Calcular duração
        duration = time.time() - start_time
        
        # Log de sucesso
        log_quiz_generation(topic, num_questions, difficulty, True, duration)
        
        return jsonify({'success': True, 'result': result})
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        log_quiz_generation(topic, num_questions, difficulty, False, duration, error_msg)
        return jsonify({'error': f'Erro ao gerar questionário: {error_msg}'})

@app.route('/statistics-page')
def statistics_page():
    """Renderiza a página de estatísticas"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return redirect('/login')
    
    return render_template('statistics.html')

@app.route('/settings-page')
def settings_page():
    """Renderiza a página de estatísticas"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return redirect('/login')
    if not session["role"] =="Admin":
        return render_template('simple.html')
    
    return render_template('settings.html')

@app.route('/api/statistics')
def get_statistics():
    """API para obter estatísticas baseadas nos logs"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Analisar logs e obter estatísticas
        stats = log_analyzer.analyze_logs()
        
        # Adicionar métricas do sistema em tempo real
        system_metrics = postgres_logger.get_system_metrics()
        stats['current_system_metrics'] = system_metrics
        
        # Salvar estatísticas na base de dados
        postgres_logger.log_system_metrics(stats)
        
        return jsonify({
            'success': True,
            'statistics': stats,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/statistics/detailed')
def get_detailed_statistics():
    """API para obter estatísticas detalhadas"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Analisar logs
        stats = log_analyzer.analyze_logs()
        
        # Calcular estatísticas adicionais
        detailed_stats = {
            'summary': {
                'total_operations': stats.get('total_operations', 0),
                'success_rate': (stats.get('successful_operations', 0) / max(stats.get('total_operations', 1), 1)) * 100,
                'recent_activity': stats.get('recent_activity', 0),
                'unique_topics': len(stats.get('topic_analysis', {})),
                'languages_used': len(stats.get('language_usage', {}))
            },
            'performance': {
                'avg_query_duration': 0,
                'avg_quiz_duration': 0,
                'avg_connection_duration': 0,
                'peak_hours': [],
                'system_metrics': postgres_logger.get_system_metrics()
            },
            'usage_analysis': {
                'top_topics': sorted(stats.get('topic_analysis', {}).items(), key=lambda x: x[1], reverse=True)[:10],
                'language_distribution': stats.get('language_usage', {}),
                'hourly_activity': stats.get('time_analysis', {}),
                'error_frequency': stats.get('error_analysis', {})
            },
            'operations_breakdown': stats.get('operations_by_type', {})
        }
        
        # Calcular médias de duração
        operations = stats.get('operations_by_type', {})
        if 'rag_operation' in operations:
            detailed_stats['performance']['avg_query_duration'] = operations['rag_operation'].get('avg_duration', 0)
        if 'quiz_generation' in operations:
            detailed_stats['performance']['avg_quiz_duration'] = operations['quiz_generation'].get('avg_duration', 0)
        if 'user_interaction' in operations:
            detailed_stats['performance']['avg_connection_duration'] = operations['user_interaction'].get('avg_duration', 0)
        
        # Encontrar horas de pico
        hourly_activity = stats.get('time_analysis', {})
        if hourly_activity:
            peak_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[:3]
            detailed_stats['performance']['peak_hours'] = [{'hour': int(h), 'count': c} for h, c in peak_hours]
        
        return jsonify({
            'success': True,
            'detailed_statistics': detailed_stats,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas detalhadas: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route("/export-stats")
def export_stats():
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT operation_type, status, duration_ms, created_at, user_id
                    FROM operation_log
                    ORDER BY created_at DESC
                    LIMIT 1000
                """)
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]

        # Gerar CSV na memória
        def generate():
            yield ",".join(colnames) + "\n"
            for row in rows:
                yield ",".join([str(x) for x in row]) + "\n"

        return Response(generate(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment;filename=stats.csv"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/whoami')
def whoami():
    if not session.get('authenticated'):
        return jsonify({"error": "Não autenticado"})
    return jsonify({
        "username": session['username'],
        "role": session['role']
    })

# ========================
# Conversas
# ========================

# Listar conversas do utilizador autenticado
@app.route("/conversations", methods=["GET"])
def get_conversations():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "Não autenticado"}), 401

        with postgres_logger.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, title, model_used, created_at, updated_at, is_archived
                    FROM conversations
                    WHERE is_archived = FALSE AND user_id = %s
                    ORDER BY updated_at DESC
                """, (user_id,))
                rows = cur.fetchall()

        return jsonify({"success": True, "conversations": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Criar conversa
@app.route("/conversations", methods=["POST"])
def create_conversation():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "Não autenticado"}), 401

        data = request.json
        title = data.get("title", "Nova conversa")
        model_used = data.get("model", "default")

        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO conversations (user_id, title, model_used)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (user_id, title, model_used))
                new_id = cur.fetchone()[0]
                conn.commit()

        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/conversations/<uuid:conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    """Apaga uma conversa"""
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversations WHERE id = %s", (str(conv_id),))
                conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================
# Mensagens
# ========================

# Listar mensagens de uma conversa
@app.route("/conversations/<uuid:conv_id>/messages", methods=["GET"])
def get_messages(conv_id):
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "Não autenticado"}), 401

        with postgres_logger.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # garantir que a conversa pertence ao utilizador
                cur.execute("SELECT id FROM conversations WHERE id = %s AND user_id = %s", (str(conv_id), user_id))
                if not cur.fetchone():
                    return jsonify({"success": False, "error": "Acesso negado"}), 403

                cur.execute("""
                    SELECT id, role, content, tokens_used, created_at
                    FROM conversation_messages
                    WHERE conversation_id = %s
                    ORDER BY created_at ASC
                """, (str(conv_id),))
                rows = cur.fetchall()

        return jsonify({"success": True, "messages": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Adicionar mensagem a uma conversa
@app.route("/conversations/<uuid:conv_id>/messages", methods=["POST"])
def add_message(conv_id):
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "Não autenticado"}), 401

        data = request.json
        role = data.get("role")
        content = data.get("content")

        if not role or not content:
            return jsonify({"success": False, "error": "role e content são obrigatórios"}), 400

        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                # garantir que a conversa pertence ao utilizador
                cur.execute("SELECT id FROM conversations WHERE id = %s AND user_id = %s", (str(conv_id), user_id))
                if not cur.fetchone():
                    return jsonify({"success": False, "error": "Acesso negado"}), 403

                cur.execute("""
                    INSERT INTO conversation_messages (conversation_id, role, content)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (str(conv_id), role, content))
                new_id = cur.fetchone()[0]
                conn.commit()

        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/conversations/<uuid:conv_id>", methods=["PUT"])
def update_conversation(conv_id):
    try:
        data = request.json
        title = data.get("title")

        if not title:
            return jsonify({"success": False, "error": "title é obrigatório"}), 400

        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s",
                    (title, str(conv_id))
                )
                conn.commit()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/model", methods=["GET"])
def get_model():
    # devolve o modelo atual configurado no servidor
    return jsonify({"success": True, "model": "gpt-4o-mini"})  

# ========================
# Estatísticas
# ========================

@app.route('/stats/technical')
def stats_technical():
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                # Totais globais
                cur.execute("""
                    SELECT SUM(total_count) AS total,
                           SUM(success_count) AS success,
                           SUM(error_count) AS errors
                    FROM operation_stats
                    WHERE date > CURRENT_DATE - INTERVAL '7 days'
                """)
                total_ops = cur.fetchone()

                # Por tipo
                cur.execute("""
                    SELECT operation_type,
                           SUM(total_count) AS total,
                           SUM(success_count) AS success,
                           SUM(error_count) AS errors,
                           ROUND(AVG(avg_duration_ms)::numeric,2) AS avg_duration
                    FROM operation_stats
                    WHERE date > CURRENT_DATE - INTERVAL '7 days'
                    GROUP BY operation_type
                    ORDER BY total DESC
                """)
                per_type = [
                    {
                        "operation_type": r[0],
                        "total": r[1],
                        "success": r[2],
                        "errors": r[3],
                        "avg_duration": float(r[4]) if r[4] is not None else None
                    }
                    for r in cur.fetchall()
                ]

        return jsonify({
            "success": True,
            "data": {
                "total": total_ops[0],
                "success": total_ops[1],
                "errors": total_ops[2],
                "per_type": per_type
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/educational')
def stats_educational():
    """Métricas educacionais (últimos 14 dias)."""
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT date, operation_type, SUM(total_count) AS total
                    FROM operation_stats
                    WHERE date > CURRENT_DATE - INTERVAL '14 days'
                      
                    GROUP BY date, operation_type
                    ORDER BY date
                """)
                rows = cur.fetchall()

        data = [
            {"date": str(r[0]), "operation_type": r[1], "total": r[2]}
            for r in rows
        ]

        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/performance')
def stats_performance():
    """Métricas de performance (durations) por tipo de operação."""
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT operation_type,
                           ROUND(AVG(avg_duration_ms)::numeric,2) AS avg_duration,
                           MIN(min_duration_ms) AS min_duration,
                           MAX(max_duration_ms) AS max_duration
                    FROM operation_stats
                    WHERE date > CURRENT_DATE - INTERVAL '14 days'
                    GROUP BY operation_type
                    ORDER BY avg_duration DESC
                """)
                rows = cur.fetchall()

        data = [
            {
                "operation_type": r[0],
                "avg_duration": float(r[1]) if r[1] is not None else None,
                "min_duration": r[2],
                "max_duration": r[3]
            }
            for r in rows
        ]

        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/system')
def stats_system():
    """Últimas métricas do sistema + evolução (30 dias)."""
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                # Último snapshot de cada métrica
                cur.execute("""
                    SELECT DISTINCT ON (metric_name)
                           metric_name, metric_value, metric_unit, date
                    FROM performance_stats
                    ORDER BY metric_name, created_at DESC
                """)
                snapshot_rows = cur.fetchall()

                # Evolução do uso de disco (30 dias)
                cur.execute("""
                    SELECT date, metric_value
                    FROM performance_stats
                    WHERE metric_name = 'disk_usage_percent'
                      AND date > CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY date
                """)
                disk_usage_rows = cur.fetchall()

                # Evolução da memória total
                cur.execute("""
                    SELECT date, metric_value
                    FROM performance_stats
                    WHERE metric_name = 'memory_total_mb'
                    ORDER BY date
                """)
                memory_rows = cur.fetchall()

        snapshot = [
            {
                "metric_name": r[0],
                "metric_value": float(r[1]),
                "metric_unit": r[2] or "",
                "date": str(r[3])
            }
            for r in snapshot_rows
        ]

        disk_usage = [{"date": str(r[0]), "value": float(r[1])} for r in disk_usage_rows]
        memory = [{"date": str(r[0]), "value": float(r[1])} for r in memory_rows]

        return jsonify({
            "success": True,
            "snapshot": snapshot,
            "disk_usage": disk_usage,
            "memory": memory
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/models')
def stats_models():
    """Modelos mais usados nas últimas 24h + operações sem modelo (em separado)."""
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(operation_details->>'model', 'sem_modelo') AS modelo,
                           COUNT(*) AS total
                    FROM operation_logs
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY modelo
                    ORDER BY total DESC
                """)
                rows = cur.fetchall()

        models_data = []
        system_count = 0
        for r in rows:
            if r[0] == "sem_modelo":
                system_count = r[1]  # separa operações do sistema
            else:
                models_data.append({"model": r[0], "total": r[1]})

        return jsonify({"success": True, "models": models_data, "system": system_count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/statistics-page-new')
def statistics_page_new():
    """Renderiza a página de estatísticas"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return redirect('/login')

    # Apenas Professores ou Admin podem aceder às estatísticas
    if session["role"] not in ["Professor", "Admin"]:
        return render_template('simple.html')

    return render_template('statistics2.html')

# 1. Ranking de utilizadores mais ativos
@app.route('/stats/top-users')
def stats_top_users():
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT l.user_id, u.username, COUNT(*) AS total
                    FROM operation_logs l
                    JOIN users u ON l.user_id = u.id
                    WHERE l.created_at > NOW() - INTERVAL '7 days'
                    GROUP BY l.user_id, u.username
                    ORDER BY total DESC
                    LIMIT 10
                """)
                rows = cur.fetchall()

        data = [{"user_id": r[0], "username": r[1], "total": r[2]} for r in rows]
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# 2. Distribuição por role
@app.route('/stats/roles')
def stats_roles():
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.role, COUNT(*) AS total
                    FROM operation_logs l
                    JOIN users u ON l.user_id = u.id
                    WHERE l.created_at > NOW() - INTERVAL '7 days'
                    GROUP BY u.role
                """)
                rows = cur.fetchall()

        data = [{"role": r[0], "total": r[1]} for r in rows]
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/errors-by-role')
def stats_errors_by_role():
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.role,
                           COUNT(*) FILTER (WHERE l.status = 'success') AS success,
                           COUNT(*) FILTER (WHERE l.status = 'error')   AS errors,
                           COUNT(*) AS total
                    FROM operation_logs l
                    JOIN users u ON l.user_id = u.id
                    WHERE l.created_at > NOW() - INTERVAL '7 days'
                    GROUP BY u.role
                """)
                rows = cur.fetchall()

        data = [
            {
                "role": r[0],
                "success": r[1],
                "errors": r[2],
                "total": r[3],
                "error_rate": round((r[2] / r[3]) * 100, 2) if r[3] > 0 else 0
            }
            for r in rows
        ]
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/errors')
def stats_errors_by_model():
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT l.operation_details->>'model' AS modelo,
                           COUNT(*) FILTER (WHERE l.status = 'success') AS success,
                           COUNT(*) FILTER (WHERE l.status = 'error')   AS errors,
                           COUNT(*) AS total
                    FROM operation_logs l
                    WHERE l.created_at > NOW() - INTERVAL '7 days'
                      AND l.operation_details->>'model' IS NOT NULL
                    GROUP BY modelo
                    ORDER BY total DESC
                """)
                rows = cur.fetchall()

        data = [
            {
                "model": r[0],
                "success": r[1],
                "errors": r[2],
                "total": r[3],
                "error_rate": round((r[2] / r[3]) * 100, 2) if r[3] > 0 else 0
            }
            for r in rows
        ]
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/stats/latency-by-model')
def stats_latency_by_model():
    try:
        with postgres_logger.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT l.operation_details->>'model' AS modelo,
                           ROUND(AVG(l.duration_ms), 2) AS avg_latency,
                           MIN(l.duration_ms) AS min_latency,
                           MAX(l.duration_ms) AS max_latency
                    FROM operation_logs l
                    WHERE l.created_at > NOW() - INTERVAL '7 days'
                      AND l.operation_details->>'model' IS NOT NULL
                      AND l.duration_ms IS NOT NULL
                    GROUP BY modelo
                    ORDER BY avg_latency ASC
                """)
                rows = cur.fetchall()

        data = [
            {
                "model": r[0],
                "avg_latency": float(r[1]),
                "min_latency": r[2],
                "max_latency": r[3]
            }
            for r in rows
        ]
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ========================
# Estatísticas
# ========================



@app.route('/download-quiz/<filename>')
def download_quiz(filename):
    """Permite descarregar quizzes gerados em formato .gift"""
    try:
        filepath = os.path.join("exports", filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        return jsonify({"error": "Ficheiro não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# vai buscar a pasta definida no .env ou usa "pdfs" por defeito
PDF_FOLDER = os.getenv("PDF_FOLDER", "pdfs")

@app.route('/upload-temp', methods=['POST'])
def upload_temp():
    if not session.get('authenticated'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum ficheiro enviado'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nome de ficheiro inválido'}), 400

    os.makedirs(PDF_FOLDER, exist_ok=True)
    save_path = os.path.join(PDF_FOLDER, file.filename)
    file.save(save_path)

    return jsonify({
        "success": True,
        "filename": file.filename,
        "message": f"📎 PDF '{file.filename}' carregado. Escreve 'adicionar PDFs' para indexar ao RAG."
    })

@app.route("/download-logs/<filename>")
def download_logs(filename):
    return send_from_directory("exports", filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 