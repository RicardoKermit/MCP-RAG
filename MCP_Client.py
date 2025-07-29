import asyncio
import os
import json
import threading
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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
        'connect': 'Conectar',
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
        'please_provide_question': 'Por favor, forneça uma pergunta.'
    },
    'en': {
        'new_chat': 'New chat',
        'clear_history': 'Clear history',
        'connection': '🔗 Connection',
        'server_path_placeholder': 'MCP server path',
        'connect': 'Connect',
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
        'please_provide_question': 'Please provide a question.'
    }
}

# Modelos Gemini disponíveis
GEMINI_MODELS = {
    "gemini-1.5-flash": {
        "name": "Gemini 1.5 Flash",
        "description": "Modelo rápido e eficiente para tarefas gerais",
        "max_tokens": 8192
    },
    "gemini-1.5-pro": {
        "name": "Gemini 1.5 Pro", 
        "description": "Modelo avançado para tarefas complexas",
        "max_tokens": 32768
    },
    "gemini-1.0-pro": {
        "name": "Gemini 1.0 Pro",
        "description": "Modelo estável e confiável",
        "max_tokens": 32768
    },
    "gemini-pro": {
        "name": "Gemini Pro",
        "description": "Modelo versátil para diversas aplicações",
        "max_tokens": 32768
    },
    "gemini-2.0-flash-lite": {
        "name": "Gemini 2.0 Flash Lite",
        "description": "Modelo ultra-rápido e leve para tarefas simples",
        "max_tokens": 4096
    },
    "gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "description": "Modelo rápido da nova geração para tarefas gerais",
        "max_tokens": 8192
    },
    "gemini-2.5-flash-lite": {
        "name": "Gemini 2.5 Flash Lite",
        "description": "Versão lite do modelo mais recente, otimizada para velocidade",
        "max_tokens": 4096
    },
    "gemini-2.5-flash": {
        "name": "Gemini 2.5 Flash",
        "description": "Modelo mais recente e rápido para tarefas avançadas",
        "max_tokens": 8192
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro",
        "description": "Modelo mais avançado da nova geração para tarefas complexas",
        "max_tokens": 32768
    }
}

app = Flask(__name__, static_folder='templates/static')
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Event loop global
loop = None
loop_thread = None

def create_event_loop():
    """Cria e mantém um event loop em uma thread separada"""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()

def start_event_loop():
    """Inicia o event loop em uma thread separada"""
    global loop_thread
    loop_thread = threading.Thread(target=create_event_loop, daemon=True)
    loop_thread.start()

class MCPGeminiClient:
    def __init__(self):
        self.session = None
        self.stdio = None
        self.write = None
        self.tools = []
        self.stdio_cm = None
        self.session_cm = None
        self.is_connected = False
        self.current_model = "gemini-1.5-flash"  # Modelo padrão
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
    global loop
    if loop is None:
        start_event_loop()
        import time
        time.sleep(0.1)  # Pequena pausa para garantir que o loop iniciou
    
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

@app.route('/')
def index():
    return render_template('simple.html')

@app.route('/connect', methods=['POST'])
def connect():
    try:
        data = request.get_json()
        server_path = data.get('server_path', 'MCP_Server.py')
        
        success, result = run_async(mcp_client.connect_to_server(server_path))
        
        if success:
            return jsonify({
                'success': True,
                'tools': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/query', methods=['POST'])
def query():
    try:
        data = request.get_json()
        query_text = data.get('query', '')
        current_language = data.get('language', 'pt')  # Default to Portuguese
        
        if not query_text:
            error_msg = TRANSLATIONS.get(current_language, TRANSLATIONS['pt'])['please_provide_question']
            return jsonify({'response': error_msg})
        
        # Set the current language for this query
        mcp_client.set_language(current_language)
        
        response = run_async(mcp_client.process_query(query_text))
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'response': f'Erro ao processar a pergunta: {str(e)}'})

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 