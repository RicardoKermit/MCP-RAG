import asyncio
import os
import json
import threading
import time
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
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

# Instância global do sistema de logs PostgreSQL
postgres_logger = PostgresLogger({
    'host': 'localhost',
    'port': 5432,
    'database': 'rag_system',
    'user': 'rag_user',
    'password': 'rag_password_secure_2024'
})

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
 

def log_video_generation(prompt: str, duration: int, aspect_ratio: str, success: bool, generation_duration: float | None = None, error: str | None = None, user_id: str | None = None):
    gen_ms = int(generation_duration * 1000) if generation_duration else None
    # NEW: write to Postgres
    try:
        postgres_logger.log_operation(
            operation_type=OperationType.VIDEO_GENERATION,
            user_id=user_id,
            details={"prompt": prompt[:200], "video_duration_seconds": duration, "aspect_ratio": aspect_ratio, "generation_duration_ms": gen_ms, **({"error": error} if error else {})},
            status="success" if success else "error",
            error_message=error,
            duration_ms=gen_ms,
        )
        if gen_ms is not None:
            postgres_logger.update_operation_stats(OperationType.VIDEO_GENERATION.value, success, gen_ms)
    except Exception as e:
        logger.warning(f"Postgres log_video_generation failed: {e}")
    # keep existing file/console log
    logger.info(f"VIDEO_GENERATION | {duration}s | {aspect_ratio} | {success} | {generation_duration}s | {error}")
 

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

postgres_logger = PostgresLogger(db_config)

# Dicionário de traduções
TRANSLATIONS = {
    'pt': {
        'new_chat': 'Nova conversa',
        'clear_history': 'Limpar histórico',
        'clear_history_title': 'Limpar histórico',
        'connection': '🔗 Conexão',
        'server_path_placeholder': 'Caminho do servidor MCP',
        'connect': 'Conectar ao servidor',
        'connected': 'Conectado',
        'connecting': 'Conectando...',
        'disconnected': 'Desconectado',
        'gemini_model': '🤖 Modelo Gemini',
        'tools': '🔧 Ferramentas',
        'language': '🌐 Idioma',
        'portuguese': 'Português',
        'english': 'English',
        'welcome_message': 'Olá! Sou o seu assistente MCP. Conecte-se ao servidor para começar a fazer perguntas.',
        'input_placeholder': 'Digite a sua mensagem...',
        'send': 'Enviar',
        'clear_history_success': 'Histórico limpo com sucesso',
        'model_changed': 'Modelo alterado para',
        'invalid_model': 'Modelo inválido',
        'connection_success': 'Conectado com sucesso',
        'connection_error': 'Erro de conexão',
        'sync_with_server': 'sincronizado com servidor',
        'dark_mode': 'Alternar modo escuro',
        'logout_title': 'Terminar sessão',
        'menu_title': 'Menu',
        'help_title': 'Ajuda',
        'statistics': 'Estatísticas',
        'new_chat_welcome': 'Nova conversa iniciada. Como posso ajudá-lo hoje?',
        'error_processing': 'Erro ao processar a pergunta:',
        'history_cleared': 'Histórico limpo com sucesso',
        'error_clearing_history': 'Erro ao limpar histórico:',
        'please_provide_question': 'Por favor, forneça uma pergunta.',
        'input_placeholder': 'Digite a sua pergunta...',
        'connect_first': 'Conecte-se primeiro ao servidor...',
        'quiz_topic_placeholder': 'Tópico...',
        'quiz_num_questions_placeholder': 'Nº Perguntas',
        'video_prompt_placeholder': 'Descrição detalhada do vídeo (ex: Tutorial sobre Scala com código na tela)',
        'generation_cancelled': 'Geração cancelada pelo utilizador.',
        'conversations': '💬 Conversas',
        'quiz_section': '📝 Questionários',
        'video_ai_section': '🤖 Vídeos com IA (Gemini Veo)',
        'model_description': 'Descrição dos modelos',
        'model_description_fast': 'Modelo rápido e eficiente para tarefas gerais',
        'model_description_advanced': 'Modelo avançado para tarefas complexas',
        'model_description_stable': 'Modelo estável e confiável',
        'model_description_versatile': 'Modelo versátil para diversas aplicações',
        'model_description_ultra_fast': 'Modelo ultra-rápido e leve para tarefas simples',
        'model_description_next_gen': 'Modelo rápido da nova geração para tarefas gerais',
        'model_description_optimized': 'Versão optimizada e recente do Flash Lite. Mais rápida e estável, mantendo baixo custo.',
        'model_description_latest': 'Modelo mais recente e rápido para tarefas avançadas',
        'model_description_less_used': 'Modelo menos usado da linha Pro, com bom desempenho mas preço já mais elevado.',
        'model_description_popular': 'Modelo Pro popular para tarefas complexas com contexto grande. Mais caro que os Flash.',
        'model_description_first': 'Primeiro Pro lançado. Já ultrapassado, mas ainda competente para aplicações estáveis.',
        'model_description_base': 'Modelo base Pro, com desempenho genérico e preço elevado face aos mais recentes.',
        'model_description_top': 'Topo de gama da Google. Multimodal, com capacidades avançadas e contexto alargado. Muito caro.',
        'generate_quiz': 'Gerar Questionário',
        'generate_video_ai': 'Gerar Vídeo com IA',
        'multiple_choice': 'Escolha Múltipla',
        'true_false': 'Verdadeiro/Falso',
        'markdown': 'Markdown',
        'text': 'Texto Simples',
        'mixed': 'Misturado',
        'easy': 'Fácil',
        'medium': 'Médio',
        'hard': 'Difícil',
        'seconds': 'segundos',
        'widescreen': '16:9 (Widescreen)',
        'desktop': '16:10 (Desktop)',
        'mcp_client_interface': 'MCP Client - Interface Web',
        'available_tools': '🔧 Ferramentas Disponíveis',
        'logout_modal_title': '🚪 Terminar Sessão',
        'logout_confirm_message': 'Tem a certeza que pretende terminar a sessão?',
        'logout_redirect_message': 'Será redirecionado para a página de login.',
        'cancel': 'Cancelar',
        'confirm_logout': 'Terminar Sessão'
    },
    'en': {
        'new_chat': 'New chat',
        'clear_history': 'Clear history',
        'clear_history_title': 'Clear history',
        'connection': '🔗 Connection',
        'server_path_placeholder': 'MCP server path',
        'connect': 'Connect to server',
        'connected': 'Connected',
        'connecting': 'Connecting...',
        'disconnected': 'Disconnected',
        'gemini_model': '🤖 Gemini Model',
        'tools': '🔧 Tools',
        'language': '🌐 Language',
        'portuguese': 'Português',
        'english': 'English',
        'welcome_message': 'Hello! I\'m your MCP assistant. Connect to the server to start asking questions.',
        'input_placeholder': 'Type your message...',
        'send': 'Send',
        'clear_history_success': 'History cleared successfully',
        'model_changed': 'Model changed to',
        'invalid_model': 'Invalid model',
        'connection_success': 'Connected successfully',
        'connection_error': 'Connection error',
        'sync_with_server': 'synchronized with server',
        'dark_mode': 'Toggle dark mode',
        'logout_title': 'End session',
        'menu_title': 'Menu',
        'help_title': 'Help',
        'statistics': 'Statistics',
        'new_chat_welcome': 'New chat started. How can I help you today?',
        'error_processing': 'Error processing question:',
        'history_cleared': 'History cleared successfully',
        'error_clearing_history': 'Error clearing history:',
        'please_provide_question': 'Please provide a question.',
        'input_placeholder': 'Type your question...',
        'connect_first': 'Connect to server first...',
        'quiz_topic_placeholder': 'Topic...',
        'quiz_num_questions_placeholder': 'Nº Questions',
        'video_prompt_placeholder': 'Detailed video description (ex: Tutorial about Scala with code on screen)',
        'generation_cancelled': 'Generation cancelled by user.',
        'conversations': '💬 Conversations',
        'quiz_section': '📝 Quizzes',
        'video_ai_section': '🤖 AI Videos (Gemini Veo)',
        'model_description': 'Model descriptions',
        'model_description_fast': 'Fast and efficient model for general tasks',
        'model_description_advanced': 'Advanced model for complex tasks',
        'model_description_stable': 'Stable and reliable model',
        'model_description_versatile': 'Versatile model for various applications',
        'model_description_ultra_fast': 'Ultra-fast and lightweight model for simple tasks',
        'model_description_next_gen': 'Next generation fast model for general tasks',
        'model_description_optimized': 'Recent optimized version of Flash Lite. Faster and more stable, maintaining low cost.',
        'model_description_latest': 'Most recent and fast model for advanced tasks',
        'model_description_less_used': 'Less used model from Pro line, with good performance but already higher price.',
        'model_description_popular': 'Popular Pro model for complex tasks with large context. More expensive than Flash models.',
        'model_description_first': 'First Pro released. Already outdated, but still competent for stable applications.',
        'model_description_base': 'Base Pro model, with generic performance and high price compared to newer ones.',
        'model_description_top': 'Google\'s top of the line. Multimodal, with advanced capabilities and extended context. Very expensive.',
        'generate_quiz': 'Generate Quiz',
        'generate_video_ai': 'Generate AI Video',
        'multiple_choice': 'Multiple Choice',
        'true_false': 'True/False',
        'markdown': 'Markdown',
        'text': 'Plain Text',
        'mixed': 'Mixed',
        'easy': 'Easy',
        'medium': 'Medium',
        'hard': 'Hard',
        'seconds': 'seconds',
        'widescreen': '16:9 (Widescreen)',
        'desktop': '16:10 (Desktop)',
        'mcp_client_interface': 'MCP Client - Web Interface',
        'available_tools': '🔧 Available Tools',
        'logout_modal_title': '🚪 End Session',
        'logout_confirm_message': 'Are you sure you want to end the session?',
        'logout_redirect_message': 'You will be redirected to the login page.',
        'cancel': 'Cancel',
        'confirm_logout': 'End Session'
    }
}

# Modelos Gemini disponíveis (ordenados por custo - menor para maior)
GEMINI_MODELS = {
    "gemini-1.5-flash-8b": {
        "name": "Gemini 1.5 Flash 8B",
        "description": "Modelo mais barato da família Gemini, ideal para uso prolongado com baixo custo. Desempenho básico.",
        "max_tokens": 4096,
        "cost_rank": 1
    },
    "gemini-2.0-flash-lite": {
        "name": "Gemini 2.0 Flash Lite",
        "description": "Modelo leve e rápido, bom para tarefas simples com excelente relação custo/eficiência.",
        "max_tokens": 4096,
        "cost_rank": 2
    },
    "gemini-2.5-flash-lite": {
        "name": "Gemini 2.5 Flash Lite",
        "description": "Versão optimizada e recente do Flash Lite. Mais rápida e estável, mantendo baixo custo.",
        "max_tokens": 4096,
        "cost_rank": 3
    },
    "gemini-1.5-flash": {
        "name": "Gemini 1.5 Flash",
        "description": "Modelo eficiente para tarefas gerais com bom custo/benefício e suporte a contexto maior.",
        "max_tokens": 8192,
        "cost_rank": 4
    },
    "gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "description": "Geração seguinte do Flash com melhor suporte multimodal. Um pouco mais caro.",
        "max_tokens": 8192,
        "cost_rank": 5
    },
    "gemini-2.5-flash": {
        "name": "Gemini 2.5 Flash",
        "description": "Mais rápido e versátil que os anteriores. Ideal para aplicações em tempo real com contexto médio.",
        "max_tokens": 8192,
        "cost_rank": 6
    },
    "gemini-2.0-pro": {
        "name": "Gemini 2.0 Pro",
        "description": "Modelo menos usado da linha Pro, com bom desempenho mas preço já mais elevado.",
        "max_tokens": 32768,
        "cost_rank": 7
    },
    "gemini-1.5-pro": {
        "name": "Gemini 1.5 Pro",
        "description": "Modelo Pro popular para tarefas complexas com contexto grande. Mais caro que os Flash.",
        "max_tokens": 32768,
        "cost_rank": 8
    },
    "gemini-1.0-pro": {
        "name": "Gemini 1.0 Pro",
        "description": "Primeiro Pro lançado. Já ultrapassado, mas ainda competente para aplicações estáveis.",
        "max_tokens": 32768,
        "cost_rank": 9
    },
    "gemini-pro": {
        "name": "Gemini Pro",
        "description": "Modelo base Pro, com desempenho genérico e preço elevado face aos mais recentes.",
        "max_tokens": 32768,
        "cost_rank": 10
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro",
        "description": "Topo de gama da Google. Multimodal, com capacidades avançadas e contexto alargado. Muito caro.",
        "max_tokens": 32768,
        "cost_rank": 11
    }
}

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
        self.current_model = "gemini-1.5-flash-8b"  # Changed to the most economical model
        self.current_language = "pt"  # Idioma padrão (Português)
        self.conversation_history = []  # Histórico da conversa

    def set_model(self, model_name):
        """Define o modelo Gemini a ser usado"""
        if model_name in GEMINI_MODELS:
            self.current_model = model_name
            # Sincronizar com o servidor se estiver conectado
            if self.is_connected:
                try:
                    # Chamar a ferramenta set_model do servidor
                    result = run_async(self.session.call_tool("set_model", {"model_name": model_name}))
                    print(f"🔄 Modelo sincronizado com servidor: {model_name}")
                except Exception as e:
                    print(f"⚠️ Erro ao sincronizar modelo com servidor: {e}")
            return True
        return False

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
        return GEMINI_MODELS
    
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
                    server_model = server_model_data.get("current_model", "gemini-1.5-flash")
                    if server_model != self.current_model:
                        print(f"🔄 Sincronizando modelo do servidor: {server_model}")
                        self.current_model = server_model
                elif hasattr(model_info.content, '__iter__'):
                    # Tentar processar como lista de conteúdos
                    for content in model_info.content:
                        if hasattr(content, 'text'):
                            import json
                            server_model_data = json.loads(content.text)
                            server_model = server_model_data.get("current_model", "gemini-1.5-flash")
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
            print(f"🤔 Processando pergunta: {query}")
            print(f"🤖 Usando modelo: {self.current_model}")
            
            # Adicionar pergunta ao histórico
            self.conversation_history.append({"role": "user", "content": query})
            
            # Construir contexto da conversa
            conversation_context = ""
            if len(self.conversation_history) > 1:
                # Incluir as últimas 3 trocas de mensagens para contexto
                recent_history = self.conversation_history[-6:]  # 3 pares de user/assistant
                conversation_context = "\n\nContexto da conversa anterior:\n"
                for msg in recent_history:
                    role = "Utilizador" if msg["role"] == "user" else "Assistente"
                    conversation_context += f"{role}: {msg['content']}\n"
            
            tool_descriptions = "\n".join(
                f"- {tool.name}: {tool.description}" for tool in self.tools
            )
            
            # Instruções de idioma baseadas no idioma atual
            language_instructions = {
                "pt": "IMPORTANTE: Responde SEMPRE em português de Portugal. Usa termos e expressões apropriados para português europeu.",
                "en": "IMPORTANTE: Always respond in British English. Use appropriate British English terms and expressions."
            }
            
            prompt = (
                f"{conversation_context}\n"
                f"Pergunta atual do utilizador: {query}\n"
                f"Ferramentas disponíveis:\n{tool_descriptions}\n"
                f"{language_instructions.get(self.current_language, language_instructions['pt'])}\n"
                "IMPORTANTE: Tens SEMPRE de usar uma ferramenta. NUNCA respondas diretamente.\n"
                "Para qualquer pergunta sobre conteúdo dos PDFs, usa a ferramenta 'retrieve'.\n"
                "Para a ferramenta 'retrieve', usa sempre 'prompt' como chave do argumento.\n"
                "Para gerar questionários com validação de dificuldade, usa 'generate_quiz_with_difficulty'.\n"
    
                "Para gerar vídeos com IA (Gemini Veo), usa 'generate_video_with_veo'.\n"
                "Responde SEMPRE no formato:\n"
                "TOOL: <nome_da_ferramenta>\nARGS: <json_com_argumentos>\n"
            )
            
            print("🤖 Gerando resposta com Gemini...")
            model = genai.GenerativeModel(self.current_model)
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            print(f"📝 Resposta do Gemini: {text[:100]}...")
            
            if text.startswith("TOOL:"):
                lines = text.splitlines()
                tool_name = lines[0].replace("TOOL:", "").strip()
                args_line = next((l for l in lines if l.startswith("ARGS:")), None)
                tool_args = json.loads(args_line.replace("ARGS:", "").strip()) if args_line else {}
                
                print(f"🔧 Chamando ferramenta: {tool_name} com args: {tool_args}")
                
                if tool_name == "retrieve":
                    if "query" in tool_args:
                        tool_args["prompt"] = tool_args.pop("query")
                    if not tool_args.get("prompt"):
                        tool_args["prompt"] = query
                
                result = await self.session.call_tool(tool_name, tool_args)
                
                if hasattr(result.content, 'text'):
                    raw_response = result.content.text
                elif hasattr(result.content, '__iter__'):
                    # Tentar processar como lista de conteúdos
                    content_list = list(result.content)
                    if content_list:
                        raw_response = content_list[0].text if hasattr(content_list[0], 'text') else str(content_list[0])
                    else:
                        raw_response = str(result.content)
                else:
                    content_str = str(result.content)
                    if '[TextContent(type=\'text\', text=\'' in content_str:
                        start = content_str.find('[TextContent(type=\'text\', text=\'') + len('[TextContent(type=\'text\', text=\'')
                        end = content_str.find('\', annotations=None, meta=None)]')
                        if end != -1:
                            raw_response = content_str[start:end]
                        else:
                            raw_response = content_str
                    else:
                        raw_response = content_str
                
                print(f"📄 Resposta bruta: {raw_response[:100]}...")
                
                # Instruções de idioma para a resposta final
                final_language_instructions = {
                    "pt": "IMPORTANTE: Responde SEMPRE em português de Portugal. Usa termos e expressões apropriados para português europeu.",
                    "en": "IMPORTANTE: Always respond in British English. Use appropriate British English terms and expressions."
                }
                
                follow_up_prompt = f"""
Original question: {query}

Information found:
{raw_response}

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

**IMPORTANT:**
- If the question specifically asks you to create multiple-choice questions, create the requested number of questions based on the content found, with the appropriate number of options (usually 4 options a, b, c, d) and indicate the correct answer.
- If the question specifically asks you to create true/false questions, create the requested number of questions based on the content found, each with the options "True" and "False" and indicate the correct answer.
- For all other questions, answer naturally with the information found.

Answer naturally and directly, as if you were explaining it to someone. Make sure your response is well formatted and easy to read.
"""
                
                print("🔄 Gerando resposta final...")
                follow_up_response = model.generate_content(follow_up_prompt)
                final_response = follow_up_response.text.strip()
                print(f"✅ Resposta final: {final_response[:100]}...")
                
                # Adicionar resposta ao histórico
                self.conversation_history.append({"role": "assistant", "content": final_response})
                
                return final_response
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
    if request.method == 'GET':
        # If already authenticated, redirect to main page
        if session.get('authenticated'):
            return redirect(url_for('index'))
        
        # Add headers to prevent caching
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
            
            # Call Moodle authentication endpoint
            auth_url = "http://localhost/login/token.php"
            params = {
                'username': username,
                'password': password,
                'service': 'moodle_mobile_app'
            }
            
            # Make the request to Moodle
            with httpx.Client() as client:
                response = client.get(auth_url, params=params)
                
                if response.status_code == 200:
                    try:
                        auth_data = response.json()
                        if 'token' in auth_data and auth_data['token']:
                            # Authentication successful
                            session['authenticated'] = True
                            session['username'] = username
                            session['moodle_token'] = auth_data['token']
                            return jsonify({'success': True})
                        else:
                            return jsonify({'success': False, 'error': 'Credenciais inválidas'})
                    except json.JSONDecodeError:
                        return jsonify({'success': False, 'error': 'Resposta inválida do servidor'})
                else:
                    return jsonify({'success': False, 'error': 'Erro na autenticação'})
                    
        except Exception as e:
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
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    start_time = time.time()
    try:
        data = request.get_json()
        query_text = data.get('query', '')
        current_language = data.get('language', 'pt')  # Default to Portuguese
        
        # Log da interação do utilizador
        log_user_interaction("query", {
            "query_length": len(query_text),
            "language": current_language,
            "query_preview": query_text[:100]
        })
        
        if not query_text:
            log_system_error("query", "Query vazia")
            error_msg = TRANSLATIONS.get(current_language, TRANSLATIONS['pt'])['please_provide_question']
            return jsonify({'response': error_msg})
        
        # Set the current language for this query
        mcp_client.set_language(current_language)
        
        response = run_async(mcp_client.process_query(query_text))
        
        # Calcular duração
        duration = time.time() - start_time
        
        # Log de sucesso
        log_rag_operation("query", query_text[:50], True, duration)
        
        return jsonify({'response': response})
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        log_system_error("query", error_msg, {
            "query": query_text,
            "duration": duration
        })
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
                'message': f'Modelo alterado para {GEMINI_MODELS[model_name]["name"]}',
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
    """Retorna o backend RAG atual (qdrant/chroma)."""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    result = mcp_client.get_rag_backend()
    return jsonify(result)

@app.route('/set-rag-backend', methods=['POST'])
def set_rag_backend_route():
    """Altera o backend RAG (qdrant/chroma) em tempo de execução."""
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        backend = data.get('backend', '').lower()
        result = mcp_client.set_rag_backend(backend)
        return jsonify(result)
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

@app.route('/api/statistics/export')
def export_statistics():
    """API para exportar estatísticas em formato JSON"""
    # Check if user is authenticated
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Obter estatísticas completas
        stats = log_analyzer.analyze_logs()
        system_metrics = postgres_logger.get_system_metrics()
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'statistics': stats,
            'system_metrics': system_metrics,
            'export_info': {
                'total_log_files': len(list(log_analyzer.logs_dir.glob("*.log"))),
                'analysis_period': 'All available logs',
                'generated_by': 'RAG System Statistics'
            }
        }
        
        # Criar resposta com headers para download
        response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=rag_statistics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao exportar estatísticas: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 