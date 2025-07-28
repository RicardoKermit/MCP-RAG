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
            tool_descriptions = "\n".join(
                f"- {tool.name}: {tool.description}" for tool in self.tools
            )
            prompt = (
                f"Pergunta do utilizador: {query}\n"
                f"Ferramentas disponíveis:\n{tool_descriptions}\n"
                "IMPORTANTE: Tens SEMPRE de usar uma ferramenta. NUNCA respondas diretamente.\n"
                "Para qualquer pergunta sobre conteúdo dos PDFs, usa a ferramenta 'retrieve'.\n"
                "Para a ferramenta 'retrieve', usa sempre 'prompt' como chave do argumento.\n"
                "Responde SEMPRE no formato:\n"
                "TOOL: <nome_da_ferramenta>\nARGS: <json_com_argumentos>\n"
            )
            
            print("🤖 Gerando resposta com Gemini...")
            model = genai.GenerativeModel("gemini-1.5-flash")
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
                
                follow_up_prompt = f"""
Pergunta original: {query}

Informação encontrada:
{raw_response}

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
        raise RuntimeError("Event loop não está inicializado")
    
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

@app.route('/')
def index():
    return render_template('simple.html')

@app.route('/connect', methods=['POST'])
def connect():
    print("🔗 Endpoint /connect chamado")
    data = request.get_json()
    server_path = data.get('server_path', 'MCP_Server.py')
    print(f"📁 Caminho do servidor: {server_path}")
    
    try:
        success, result = run_async(mcp_client.connect_to_server(server_path))
        print(f"📊 Resultado da conexão: success={success}, result={result}")
        return jsonify({
            'success': success,
            'tools': result if success else [],
            'error': result if not success else None
        })
    except Exception as e:
        print(f"❌ Erro no endpoint /connect: {str(e)}")
        return jsonify({
            'success': False,
            'tools': [],
            'error': str(e)
        })

@app.route('/query', methods=['POST'])
def query():
    print("❓ Endpoint /query chamado")
    data = request.get_json()
    user_query = data.get('query', '')
    print(f"💬 Pergunta: {user_query}")
    
    try:
        response = run_async(mcp_client.process_query(user_query))
        print(f"📝 Resposta: {response[:100]}...")
        return jsonify({'response': response})
    except Exception as e:
        error_msg = f"Erro ao processar pergunta: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({'response': error_msg})

@app.route('/status')
def status():
    print("📊 Endpoint /status chamado")
    status_data = {
        'connected': mcp_client.is_connected,
        'tools': [tool.name for tool in mcp_client.tools] if mcp_client.is_connected else []
    }
    print(f"📊 Status: {status_data}")
    return jsonify(status_data)

@app.route('/test')
def test():
    return jsonify({
        'message': 'Aplicação funcionando!',
        'connected': mcp_client.is_connected,
        'tools_count': len(mcp_client.tools)
    })

if __name__ == '__main__':
    print("🚀 Iniciando MCP Client Web Interface (Fixed Event Loop)")
    print("📱 A interface estará disponível em: http://localhost:5000")
    print("🔄 Pressione Ctrl+C para parar o servidor")
    print("=" * 50)
    
    # Inicia o event loop em uma thread separada
    start_event_loop()
    
    # Aguarda um pouco para o event loop inicializar
    import time
    time.sleep(1)
    
    app.run(debug=True, host='0.0.0.0', port=5000) 