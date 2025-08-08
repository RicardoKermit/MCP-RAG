import asyncio
import os
import json
import threading
import time
import httpx
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
import google.generativeai as genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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

# Funções de Log Específicas
def log_rag_operation(operation: str, topic: str, success: bool, duration: float = None, error: str = None):
    """Log para operações RAG (retrieve, add_pdfs)"""
    log_msg = f"RAG_OPERATION | {operation} | Topic: {topic} | Success: {success}"
    if duration:
        log_msg += f" | Duration: {duration:.2f}s"
    if error:
        log_msg += f" | Error: {error}"
    logger.info(log_msg)

def log_quiz_generation(topic: str, num_questions: int, difficulty: str, success: bool, duration: float = None, error: str = None):
    """Log para geração de questionários"""
    log_msg = f"QUIZ_GENERATION | Topic: {topic} | Questions: {num_questions} | Difficulty: {difficulty} | Success: {success}"
    if duration:
        log_msg += f" | Duration: {duration:.2f}s"
    if error:
        log_msg += f" | Error: {error}"
    logger.info(log_msg)

def log_video_generation(prompt: str, duration: int, aspect_ratio: str, success: bool, generation_duration: float = None, error: str = None):
    """Log para geração de vídeos"""
    log_msg = f"VIDEO_GENERATION | Prompt: {prompt[:50]}... | Duration: {duration}s | Aspect: {aspect_ratio} | Success: {success}"
    if generation_duration:
        log_msg += f" | GenerationTime: {generation_duration:.2f}s"
    if error:
        log_msg += f" | Error: {error}"
    logger.info(log_msg)

def log_system_error(operation: str, error: str, context: dict = None):
    """Log para erros do sistema"""
    log_msg = f"SYSTEM_ERROR | Operation: {operation} | Error: {error}"
    if context:
        log_msg += f" | Context: {context}"
    logger.error(log_msg)

def log_user_interaction(action: str, details: dict = None):
    """Log para interações do utilizador"""
    log_msg = f"USER_INTERACTION | Action: {action}"
    if details:
        log_msg += f" | Details: {details}"
    logger.info(log_msg)

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GOOGLE_API_KEY não definido no .env")

genai.configure(api_key=GEMINI_API_KEY)

# Dicionário de traduções
TRANSLATIONS = {
    'pt': {
        'new_chat': 'Nova conversa',
        'clear_history': 'Limpar histórico',
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
        'new_chat_welcome': 'Nova conversa iniciada. Como posso ajudá-lo hoje?',
        'error_processing': 'Erro ao processar a pergunta:',
        'history_cleared': 'Histórico limpo com sucesso',
        'error_clearing_history': 'Erro ao limpar histórico:',
        'please_provide_question': 'Por favor, forneça uma pergunta.',
        'input_placeholder': 'Digite a sua pergunta...',
        'connect_first': 'Conecte-se primeiro ao servidor...',
        'generation_cancelled': 'Geração cancelada pelo utilizador.'
    },
    'en': {
        'new_chat': 'New chat',
        'clear_history': 'Clear history',
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
        'new_chat_welcome': 'New chat started. How can I help you today?',
        'error_processing': 'Error processing question:',
        'history_cleared': 'History cleared successfully',
        'error_clearing_history': 'Error clearing history:',
        'please_provide_question': 'Please provide a question.',
        'input_placeholder': 'Type your question...',
        'connect_first': 'Connect to server first...',
        'generation_cancelled': 'Generation cancelled by user.'
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
Pergunta original: {query}

Informação encontrada:
{raw_response}

{final_language_instructions.get(self.current_language, final_language_instructions['pt'])}

Por favor, apresenta esta informação de forma clara, bem estruturada e fácil de ler. 
Usa formatação markdown para organizar a resposta:

- Usa **negrito** para títulos e pontos importantes
- Usa listas com * ou - para organizar informações
- Usa parágrafos para separar ideias
- Usa > para citações importantes
- Organiza a resposta de forma lógica e estruturada
- Destaca pontos importantes com **negrito**
- Usa quebras de linha para melhor legibilidade

**IMPORTANTE:** 
- Se a pergunta pedir especificamente para criar perguntas de escolha múltipla, cria o número de perguntas solicitado baseadas no conteúdo encontrado, com o número de opções apropriado (geralmente 4 opções a, b, c, d) e indica a resposta correta
- Se a pergunta pedir especificamente para criar perguntas de verdadeiro/falso, cria o número de perguntas solicitado baseadas no conteúdo encontrado, cada uma com as opções "Verdadeiro" e "Falso" e indica a resposta correta
- Para todas as outras perguntas, responde naturalmente com a informação encontrada

Responde de forma natural e direta, como se estivesses a explicar a alguém.
Certifica-te de que a resposta está bem formatada e fácil de ler.
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
    return render_template('simple.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # If already authenticated, redirect to main page
        if session.get('authenticated'):
            return redirect(url_for('index'))
        return render_template('login.html')
    
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
    start_time = time.time()
    try:
        data = request.get_json()
        server_path = data.get('server_path', 'MCP_Server.py')
        
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
    try:
        mcp_client.clear_conversation_history()
        return jsonify({'success': True, 'message': 'Histórico limpo com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/status')
def status():
    return jsonify({
        'connected': mcp_client.is_connected,
        'tools': [tool.name for tool in mcp_client.tools] if mcp_client.is_connected else [],
        'current_model': mcp_client.current_model,
        'available_models': mcp_client.get_available_models()
    })

@app.route('/models', methods=['GET'])
def get_models():
    """Retorna a lista de modelos disponíveis"""
    return jsonify({
        'models': mcp_client.get_available_models(),
        'current_model': mcp_client.current_model
    })

@app.route('/set-model', methods=['POST'])
def set_model():
    """Define o modelo Gemini a ser usado"""
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



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 