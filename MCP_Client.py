import asyncio
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GOOGLE_API_KEY não definido no .env")

genai.configure(api_key=GEMINI_API_KEY)

class MCPGeminiClient:
    def __init__(self):
        self.session = None
        self.stdio = None
        self.write = None
        self.tools = []
        self.stdio_cm = None
        self.session_cm = None

    async def connect_to_server(self, server_script_path):
        is_python = server_script_path.endswith('.py')
        if not is_python:
            raise ValueError("Apenas servidores Python suportados neste exemplo.")
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )
        # CORREÇÃO: usa o context manager manualmente
        self.stdio_cm = stdio_client(server_params)
        self.stdio, self.write = await self.stdio_cm.__aenter__()
        self.session_cm = ClientSession(self.stdio, self.write)
        self.session = await self.session_cm.__aenter__()
        await self.session.initialize()
        response = await self.session.list_tools()
        self.tools = response.tools
        print("Ferramentas disponíveis:", [tool.name for tool in self.tools])

    async def process_query(self, query):
        # Gemini não suporta tool-calling nativo como Claude, então fazemos manualmente:
        # 1. Mostramos as ferramentas disponíveis ao Gemini
        # 2. Gemini sugere qual ferramenta usar e com que argumentos
        tool_descriptions = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self.tools
        )
        prompt = (
            f"Pergunta do utilizador: {query}\n"
            f"Ferramentas disponíveis:\n{tool_descriptions}\n"
            "Tens sempre de usar uma ferramenta, responde no formato:\n"
            "TOOL: <nome_da_ferramenta>\nARGS: <json_com_argumentos>\n"
        )
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("TOOL:"):
            # Parse tool name and args
            lines = text.splitlines()
            tool_name = lines[0].replace("TOOL:", "").strip()
            args_line = next((l for l in lines if l.startswith("ARGS:")), None)
            import json
            tool_args = json.loads(args_line.replace("ARGS:", "").strip()) if args_line else {}
            # Corrige o nome do argumento se necessário
            if tool_name == "retrieve":
                # Se vier 'query', converte para 'prompt'
                if "query" in tool_args:
                    tool_args["prompt"] = tool_args.pop("query")
                # Se vier vazio, tenta preencher com a pergunta original
                if not tool_args.get("prompt"):
                    tool_args["prompt"] = query
            result = await self.session.call_tool(tool_name, tool_args)
            
            # Extrai apenas o texto da resposta
            if hasattr(result.content, 'text'):
                raw_response = result.content.text
            else:
                # Se for uma string, remove as informações técnicas
                content_str = str(result.content)
                if '[TextContent(type=\'text\', text=\'' in content_str:
                    # Remove o início e fim das informações técnicas
                    start = content_str.find('[TextContent(type=\'text\', text=\'') + len('[TextContent(type=\'text\', text=\'')
                    end = content_str.find('\', annotations=None, meta=None)]')
                    if end != -1:
                        raw_response = content_str[start:end]
                    else:
                        raw_response = content_str
                else:
                    raw_response = content_str
            
            # Usa o Gemini para fazer um follow-up e apresentar a informação de forma melhor
            follow_up_prompt = f"""
Pergunta original: {query}

Informação encontrada:
{raw_response}

Por favor, apresenta esta informação de forma clara, bem estruturada e fácil de ler. 
Organiza a resposta de forma lógica, usa formatação adequada para listas e destaca pontos importantes.
Responde de forma natural e direta, como se estivesses a explicar a alguém.
"""
            
            follow_up_response = model.generate_content(follow_up_prompt)
            return follow_up_response.text.strip()
        else:
            return text

    async def chat_loop(self):
        print("Cliente MCP com Gemini iniciado! Escreve 'quit' para sair.")
        while True:
            query = input("\nPergunta: ").strip()
            if query.lower() == "quit":
                break
            try:
                resposta = await self.process_query(query)
                print("\n" + resposta)
            except Exception as e:
                print("Erro:", e)

    async def cleanup(self):
        if hasattr(self, "session_cm") and self.session_cm:
            await self.session_cm.__aexit__(None, None, None)
        if hasattr(self, "stdio_cm") and self.stdio_cm:
            await self.stdio_cm.__aexit__(None, None, None)

async def main():
    if len(sys.argv) < 2:
        print("Uso: python client_gemini.py <caminho_para_server.py>")
        sys.exit(1)
    client = MCPGeminiClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())