# 🤖 RAG System with MCP, Qdrant and Gemini - Interface Web

Um sistema de **Retrieval-Augmented Generation (RAG)** avançado que combina:
- **MCP (Model Context Protocol)** para comunicação cliente-servidor
- **Qdrant Cloud** como vectorstore remoto
- **Google Gemini** como modelo de linguagem
- **Integração com Moodle** para download automático de PDFs
- **Interface Web Moderna** com Flask e SocketIO

## 🚀 Características

### Sistema RAG
- **Busca semântica** em documentos PDF
- **Integração com Moodle** para download automático de materiais
- **Vectorstore remoto** com Qdrant Cloud
- **Interface MCP** para fácil integração
- **Suporte a múltiplos formatos** de documentos
- **Processamento assíncrono** de documentos

### Interface Web
- **Interface Moderno**: Design responsivo e elegante com gradientes e animações
- **Chat em Tempo Real**: Comunicação em tempo real com WebSocket
- **Conexão Dinâmica**: Conecte-se a diferentes servidores MCP
- **Indicador de Status**: Visualização clara do estado da conexão
- **Lista de Ferramentas**: Mostra as ferramentas disponíveis no servidor
- **Responsivo**: Funciona perfeitamente em desktop e mobile
- **Gestão de Conversas**: Sistema de conversas múltiplas
- **Seleção de Modelos**: Suporte a múltiplos modelos Gemini
- **Internacionalização**: Suporte a português e inglês

## 📋 Pré-requisitos

- Python 3.13 ou superior
- [uv](https://docs.astral.sh/uv/) instalado
- Conta no [Google AI Studio](https://aistudio.google.com/) (para Gemini API)
- Conta no [Qdrant Cloud](https://cloud.qdrant.io/) (opcional, para vectorstore remoto)
- Servidor Moodle (opcional, para integração)

## 🛠️ Instalação

1. **Clone o repositório:**
   ```bash
   git clone <url-do-seu-repositorio>
   cd rag
   ```

2. **Instale as dependências com uv:**
   ```bash
   # Instalar todas as dependências principais
   uv sync
   
   # Ou se preferir instalar manualmente:
   uv add "mcp[cli]>=1.10.1"
   uv add "langchain>=0.3.26"
   uv add "langchain-community>=0.3.27"
   uv add "chromadb>=1.0.15"
   uv add "langchain-qdrant>=0.1.0"
   uv add "qdrant-client>=1.7.0"
   uv add "langchain-huggingface>=0.1.0"
   uv add "sentence-transformers>=2.2.0"
   uv add "langchain-google-genai>=2.0.0"
   uv add "google-generativeai>=0.3.0"
   uv add "langchain-ollama>=0.3.3"
   uv add "PyPDF2>=3.0.0"
   uv add "pypdf>=3.17.0"
   uv add "httpx>=0.25.0"
   uv add "requests>=2.31.0"
   uv add "python-dotenv>=1.0.0"
   uv add "pathlib2>=2.3.7"
   uv add "flask>=3.0.0"
   uv add "flask-socketio>=5.3.0"
   
   # Para dependências de desenvolvimento (opcional):
   uv add --dev "pytest>=7.4.0"
   uv add --dev "pytest-asyncio>=0.21.0"
   ```

## 🔑 Configuração das APIs

### 1. Google Gemini API

1. **Aceda ao Google AI Studio:**
   - Vá para [https://aistudio.google.com/](https://aistudio.google.com/)
   - Faça login com a sua conta Google

2. **Obtenha a API Key:**
   - Clique em "Get API key" no canto superior direito
   - Selecione "Create API key"
   - Copie a chave gerada

3. **Configure no projeto:**
   ```env
   GOOGLE_API_KEY=sua_chave_api_gemini_aqui
   ```

### 2. Qdrant Cloud

1. **Crie uma conta no Qdrant Cloud:**
   - Vá para [https://cloud.qdrant.io/](https://cloud.qdrant.io/)
   - Registe-se com email ou GitHub

2. **Crie um cluster:**
   - Clique em "Create cluster"
   - Escolha um nome para o cluster
   - Selecione a região mais próxima
   - Escolha o plano (Free tier disponível)

3. **Obtenha as credenciais:**
   - No dashboard do cluster, vá para "API Keys"
   - Clique em "Create API key"
   - Copie a API key
   - Anote a URL do cluster (ex: `https://seu-cluster.qdrant.io`)

4. **Configure no projeto:**
   ```env
   QDRANT_HOST=https://seu-cluster.qdrant.io
   QDRANT_API_KEY=sua_chave_api_qdrant_aqui
   QDRANT_COLLECTION_NAME=rag_documents
   ```

### 3. Moodle (Opcional)

1. **Instale o Moodle:**
   - Baixe o Moodle de [https://download.moodle.org/](https://download.moodle.org/)
   - Instale num servidor web (Apache/Nginx + MySQL/PostgreSQL)
   - Configure o site durante a instalação

2. **Ative os Web Services:**
   - Faça login como administrador
   - Vá para **Site administration** > **Plugins** > **Web services** > **Overview**
   - Clique em "Enable web services"
   - Vá para **External services** e clique em "Add"
   - Configure o serviço com as funções necessárias

3. **Crie um Token:**
   - Vá para **Site administration** > **Plugins** > **Web services** > **Manage tokens**
   - Clique em "Add"
   - Selecione o utilizador e serviço
   - Copie o token gerado

4. **Configure no projeto:**
   ```env
   MOODLE_URL=http://seu-moodle/webservice/rest/server.php
   MOODLE_TOKEN=seu_token_moodle_aqui
   ```

### 4. Arquivo .env Completo

Crie um arquivo `.env` na raiz do projeto com todas as configurações:

```env
# Google Gemini API
GOOGLE_API_KEY=sua_chave_api_gemini_aqui

# Qdrant Cloud
QDRANT_HOST=https://seu-cluster.qdrant.io
QDRANT_API_KEY=sua_chave_api_qdrant_aqui
QDRANT_COLLECTION_NAME=rag_documents

# Moodle (Opcional)
MOODLE_URL=http://seu-moodle/webservice/rest/server.php
MOODLE_TOKEN=seu_token_moodle_aqui
```

## 🏗️ Estrutura do Projeto

```
rag/
├── MCP_Server.py          # Servidor MCP principal
├── MCP_Client.py          # Cliente MCP com Gemini
├── server.py              # Servidor RAG básico
├── server_pdf.py          # Servidor RAG com PDFs
├── server_MulPDF.py       # Servidor RAG multi-PDF
├── main.py                # Servidor RAG com Ollama
├── pyproject.toml         # Configuração de dependências
├── templates/             # Templates da interface web
│   ├── simple.html        # Interface principal
│   └── static/            # Ficheiros estáticos
│       ├── css/
│       │   └── style.css  # Estilos da interface
│       └── js/
│           └── app.js     # JavaScript da interface
├── pdfs/                  # Pasta com documentos PDF
├── db/                    # Vectorstore local (Chroma)
├── db_pdf/                # Vectorstore para PDFs
└── README.md              # Este arquivo
```

## 🚀 Como Usar

### Interface Web (Recomendado)

Para usar a interface web moderna:

```bash
# Iniciar o servidor MCP
uv run python MCP_Server.py

# Em outro terminal, iniciar a interface web
uv run python MCP_Client.py
```

Depois aceda a `http://localhost:5000` no seu navegador.

### Execução Completa (CLI)

Para executar tanto o servidor como o cliente de uma vez:

```bash
uv run python MCP_Client.py MCP_Server.py
```

Este comando inicia automaticamente o servidor MCP e o cliente, permitindo-te fazer perguntas diretamente.

### Execução Separada

#### 1. Servidor MCP Principal

O servidor principal oferece as seguintes ferramentas:

- `retrieve` - Busca semântica e geração de resposta
- `add_new_pdfs` - Adiciona novos PDFs da pasta
- `download_and_add_pdf` - Download e indexação de PDF via URL
- `get_courses_by_field` - Busca cursos no Moodle
- `download_pdfs_from_course` - Download de PDFs de um curso
- `clear_rag` - Limpa o vectorstore

**Executar o servidor:**
```bash
uv run python MCP_Server.py
```

#### 2. Cliente MCP

**Executar o cliente:**
```bash
uv run python MCP_Client.py MCP_Server.py
```

### 3. Exemplos de Uso

#### Busca semântica:
```
Pergunta: O que é realidade virtual?
```

#### Download de PDF de um curso Moodle:
```
Pergunta: Baixa os PDFs do curso "Introdução à IA"
```

#### Adicionar novo PDF:
```
Pergunta: Adiciona o PDF do URL https://exemplo.com/documento.pdf
```

## 🎨 Interface Web

### Características da Interface

- **Design Moderno**: Interface inspirada no ChatGPT com tema escuro
- **Responsivo**: Funciona perfeitamente em desktop e mobile
- **Gestão de Conversas**: Sistema de conversas múltiplas com histórico
- **Seleção de Modelos**: Suporte a múltiplos modelos Gemini
- **Internacionalização**: Suporte a português e inglês
- **Modo Escuro/Claro**: Toggle entre temas
- **Menu Mobile**: Menu hambúrguer para dispositivos móveis

### Estados Visuais

- **Desconectado**: Botão azul "Conectar ao servidor"
- **Conectando**: Botão laranja com animação de loading
- **Conectado**: Botão verde "Conectado"
- **Input Desabilitado**: Campo de texto bloqueado quando desconectado
- **Geração de Resposta**: Botão de stop durante geração

## 🔧 Configuração Avançada

### Configuração MCP no Claude Desktop

Para usar o servidor MCP no Claude Desktop, adicione a seguinte configuração ao arquivo `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "RAG": {
      "command": "uv",
      "args": [
        "--directory",
        "/caminho/para/seu/projeto/rag",
        "run",
        "python",
        "MCP_Server.py"
      ]
    }
  }
}
```

**Para Windows:**
```json
{
  "mcpServers": {
    "RAG": {
      "command": "C:\\Users\\seu-usuario\\.local\\bin\\uv.EXE",
      "args": [
        "--directory",
        "C:\\caminho\\para\\seu\\projeto\\rag",
        "run",
        "python",
        "MCP_Server.py"
      ]
    }
  }
}
```

**Para macOS/Linux:**
```json
{
  "mcpServers": {
    "RAG": {
      "command": "uv",
      "args": [
        "--directory",
        "/caminho/para/seu/projeto/rag",
        "run",
        "python",
        "MCP_Server.py"
      ]
    }
  }
}
```

**Localização do arquivo de configuração:**
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

**Após adicionar a configuração:**
1. Reinicie o Claude Desktop
2. O servidor RAG estará disponível como ferramenta
3. Pode fazer perguntas como: "Busca informação sobre realidade virtual nos meus documentos"

### Qdrant Cloud

Para usar Qdrant Cloud como vectorstore remoto:

1. Crie uma conta em [Qdrant Cloud](https://cloud.qdrant.io/)
2. Crie um cluster
3. Configure as variáveis de ambiente:
   ```env
   QDRANT_HOST=https://seu-cluster.qdrant.io
   QDRANT_API_KEY=sua_chave_api
   ```

### Integração Moodle

Para integrar com um servidor Moodle:

1. Configure o webservice no Moodle
2. Gere um token de acesso
3. Configure as variáveis de ambiente:
   ```env
   MOODLE_URL=http://seu-moodle/webservice/rest/server.php
   MOODLE_TOKEN=seu_token
   ```

## 📊 Modelos Gemini

O sistema suporta múltiplos modelos Gemini, ordenados por custo (do mais económico ao mais caro):

### 🟢 Económicos (Baixo Custo)
- **Gemini 1.5 Flash 8B** (Padrão) - Modelo mais barato, ideal para uso prolongado
- **Gemini 2.0 Flash Lite** - Leve e rápido para tarefas simples
- **Gemini 2.5 Flash Lite** - Versão otimizada e recente do Flash Lite
- **Gemini 1.5 Flash** - Eficiente para tarefas gerais com bom custo/benefício
- **Gemini 2.0 Flash** - Geração seguinte do Flash com suporte multimodal
- **Gemini 2.5 Flash** - Mais rápido e versátil para aplicações em tempo real

### 🔴 Avançados (Alto Custo)
- **Gemini 2.0 Pro** - Modelo Pro com bom desempenho mas preço elevado
- **Gemini 1.5 Pro** - Popular para tarefas complexas com contexto grande
- **Gemini 1.0 Pro** - Primeiro Pro lançado, ainda competente
- **Gemini Pro** - Modelo base Pro com desempenho genérico
- **Gemini 2.5 Pro** - Topo de gama da Google, multimodal e muito caro

**Nota:** O sistema inicia por padrão com o **Gemini 1.5 Flash 8B** (modelo mais económico) para minimizar custos.

Para alterar o modelo padrão:
```python
# Em MCP_Client.py e MCP_Server.py
current_model = "gemini-2.0-flash-lite"  # Modelo mais económico
```

### Modelos de Embeddings

O sistema usa por padrão `sentence-transformers/all-MiniLM-L6-v2`. Para alterar:

```python
# Em MCP_Server.py
embeddings = HuggingFaceEmbeddings(model_name="outro-modelo")
```

### Configuração da Interface Web

#### Alterar Porta
Edite o arquivo `MCP_Client.py` na linha final:
```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

#### Personalizar Design
Edite o CSS no arquivo `templates/static/css/style.css` para personalizar cores, fontes e layout.

## 🧪 Testes e Verificação

### Testes Automatizados

Para executar os testes:

```bash
uv sync --extra dev
uv run pytest
```

### Verificação Manual da Configuração

1. **Teste da API Gemini:**
   ```bash
   # Execute o cliente para testar a conexão
   uv run python MCP_Client.py
   ```
   Se não houver erros, a API Gemini está configurada corretamente.

2. **Teste do Qdrant:**
   ```bash
   # Execute o servidor para testar a conexão Qdrant
   uv run python MCP_Server.py
   ```
   Se não houver erros de conexão, o Qdrant está configurado corretamente.

3. **Teste da Interface Web:**
   ```bash
   # Inicie o servidor e cliente
   uv run python MCP_Server.py
   # Em outro terminal:
   uv run python MCP_Client.py
   ```
   Aceda a `http://localhost:5000` e teste a conexão.

### Verificação das Variáveis de Ambiente

Para verificar se todas as variáveis estão configuradas:

```bash
# No Python
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

required_vars = ['GOOGLE_API_KEY', 'QDRANT_HOST', 'QDRANT_API_KEY']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f'Variáveis em falta: {missing_vars}')
else:
    print('Todas as variáveis estão configuradas!')
"
```

## 📦 Dependências

### Principais:
- `mcp[cli]` - Framework MCP
- `langchain` - Framework RAG
- `langchain-qdrant` - Integração Qdrant
- `langchain-google-genai` - Integração Gemini
- `sentence-transformers` - Embeddings
- `qdrant-client` - Cliente Qdrant
- `flask` - Framework web
- `flask-socketio` - WebSocket para comunicação em tempo real

### Desenvolvimento:
- `pytest` - Framework de testes
- `pytest-asyncio` - Testes assíncronos

## 🔍 Troubleshooting

### Erro de API Key
```
ValueError: GOOGLE_API_KEY não definido no .env
```
**Solução:** Configure a variável `GOOGLE_API_KEY` no arquivo `.env`

### Erro de conexão Qdrant
```
ConnectionError: Unable to connect to Qdrant
```
**Solução:** Verifique as configurações de `QDRANT_HOST` e `QDRANT_API_KEY`

### Erro de PDF
```
PDFReadError: Unable to read PDF
```
**Solução:** Verifique se o PDF não está corrompido e se tem permissões de leitura

### Erro de Build Hatch
```
ValueError: Unable to determine which files to ship inside the wheel
```
**Solução:** O `pyproject.toml` já está configurado corretamente. Se ainda tiver problemas:
1. Limpe o cache do uv: `uv cache clean`
2. Reinstale as dependências: `uv sync --reinstall`
3. Execute novamente: `uv run python MCP_Server.py`

### Problemas da Interface Web

#### Erro de Conexão
- Verifique se o servidor MCP está acessível
- Confirme que o caminho do servidor está correto
- Verifique se todas as dependências estão instaladas

#### Erro de WebSocket
- Verifique se a porta 5000 está livre
- Confirme que o firewall não está bloqueando a conexão

#### Problemas de Responsividade
- Verifique se está a usar um navegador moderno
- Teste em diferentes tamanhos de ecrã

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 📞 Suporte

Para suporte, abra uma issue no GitHub ou contacte através do email.

## ⚡ Comandos Rápidos

### Instalação Completa (Recomendado)
```bash
# Clone e instale tudo de uma vez
git clone <url-do-seu-repositorio>
cd rag
uv sync
```

### Comandos de Execução
```bash
# Interface Web (Recomendado)
uv run python MCP_Server.py
uv run python MCP_Client.py

# Execução completa (CLI)
uv run python MCP_Client.py MCP_Server.py

# Servidor MCP principal
uv run python MCP_Server.py

# Cliente MCP
uv run python MCP_Client.py MCP_Server.py

# Servidor RAG básico
uv run python server.py

# Servidor RAG com PDFs
uv run python server_pdf.py

# Servidor RAG multi-PDF
uv run python server_MulPDF.py

# Servidor RAG com Ollama
uv run python main.py
```

### Comandos de Desenvolvimento
```bash
# Instalar dependências de desenvolvimento
uv sync --extra dev

# Executar testes
uv run pytest

# Adicionar nova dependência
uv add nome-do-pacote

# Adicionar dependência de desenvolvimento
uv add --dev nome-do-pacote

# Limpar cache e reinstalar (se houver problemas)
uv cache clean
uv sync --reinstall
```

---

**Desenvolvido com ❤️ usando MCP, LangChain, Gemini, Flask e SocketIO**
