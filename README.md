# RAG System with MCP, Qdrant and Gemini

Um sistema de **Retrieval-Augmented Generation (RAG)** avançado que combina:
- **MCP (Model Context Protocol)** para comunicação cliente-servidor
- **Qdrant Cloud** como vectorstore remoto
- **Google Gemini** como modelo de linguagem
- **Integração com Moodle** para download automático de PDFs

## 🚀 Características

- **Busca semântica** em documentos PDF
- **Integração com Moodle** para download automático de materiais
- **Vectorstore remoto** com Qdrant Cloud
- **Interface MCP** para fácil integração
- **Suporte a múltiplos formatos** de documentos
- **Processamento assíncrono** de documentos

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
   
   # Para dependências de desenvolvimento (opcional):
   uv add --dev "pytest>=7.4.0"
   uv add --dev "pytest-asyncio>=0.21.0"
   ```

3. **Configure as variáveis de ambiente:**
   Crie um arquivo `.env` na raiz do projeto:
   ```env
   GOOGLE_API_KEY=sua_chave_api_gemini_aqui
   QDRANT_HOST=https://seu-cluster.qdrant.io
   QDRANT_API_KEY=sua_chave_api_qdrant_aqui
   MOODLE_URL=http://localhost/webservice/rest/server.php
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
├── pdfs/                  # Pasta com documentos PDF
├── db/                    # Vectorstore local (Chroma)
├── db_pdf/                # Vectorstore para PDFs
└── README.md              # Este arquivo
```

## 🚀 Como Usar

### Execução Completa (Recomendado)

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

### Modelos de Embeddings

O sistema usa por padrão `sentence-transformers/all-MiniLM-L6-v2`. Para alterar:

```python
# Em MCP_Server.py
embeddings = HuggingFaceEmbeddings(model_name="outro-modelo")
```

## 🧪 Testes

Para executar os testes:

```bash
uv sync --extra dev
uv run pytest
```

## 📦 Dependências

### Principais:
- `mcp[cli]` - Framework MCP
- `langchain` - Framework RAG
- `langchain-qdrant` - Integração Qdrant
- `langchain-google-genai` - Integração Gemini
- `sentence-transformers` - Embeddings
- `qdrant-client` - Cliente Qdrant

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
# Execução completa (Recomendado)
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

**Desenvolvido com ❤️ usando MCP, LangChain e Gemini**
