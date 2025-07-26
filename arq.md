# Arquitetura do Projeto RAG com MCP, Qdrant e Gemini

## Visão Geral

O projeto implementa um sistema de **chatbot inteligente** que combina:
- **MCP (Model Context Protocol)** para comunicação cliente-servidor
- **RAG (Retrieval-Augmented Generation)** para busca semântica em documentos PDF
- **Qdrant Cloud** como vectorstore remoto
- **Google Gemini** como modelo de linguagem
- **Integração com Moodle** para download automático de PDFs

---

## Componentes Principais

### 1. Servidor MCP (`MCP_Server.py`)

**Função:** Servidor FastMCP que expõe ferramentas RAG via protocolo MCP

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP_Server.py                            │
├─────────────────────────────────────────────────────────────┤
│  FastMCP Framework                                          │
│  ├── Tool Registry                                          │
│  │   ├── retrieve()                                         │
│  │   ├── add_new_pdfs()                                     │
│  │   ├── download_and_add_pdf()                             │
│  │   ├── get_courses_by_field()                             │
│  │   ├── download_pdfs_from_course()                        │
│  │   └── clear_rag()                                        │
│  └── MCP Protocol Handler                                   │
├─────────────────────────────────────────────────────────────┤
│  RAG Pipeline                                               │
│  ├── Document Processing                                    │
│  │   ├── PyPDFLoader                                        │
│  │   ├── RecursiveCharacterTextSplitter                     │
│  │   └── CharacterTextSplitter                              │
│  ├── Embeddings                                             │
│  │   └── HuggingFaceEmbeddings (all-MiniLM-L6-v2)           │
│  ├── Vectorstore                                            │
│  │   └── Qdrant (Cloud)                                     │
│  └── LLM Chain                                              │
│      ├── GoogleGenerativeAI (gemini-2.0-flash)              │
│      ├── RetrievalQA                                        │
│      └── Custom Prompt Template                             │
├─────────────────────────────────────────────────────────────┤
│  External Integrations                                      │
│  ├── Moodle API Integration                                 │
│  │   ├── Course Discovery                                   │
│  │   ├── Content Retrieval                                  │
│  │   └── PDF Download                                       │
│  └── HTTP Client (httpx)                                    │
└─────────────────────────────────────────────────────────────┘
```

**Fluxo de processamento:**
1. Inicialização: Carrega PDFs da pasta `pdfs/`, processa e indexa no Qdrant
2. Query Processing: Recebe queries via MCP, busca documentos relevantes, gera respostas
3. Document Management: Permite adicionar novos PDFs e sincronizar com Moodle

---

### 2. Cliente MCP (`MCP_Client.py`)

**Função:** Cliente que se conecta ao servidor MCP e usa Gemini para interpretar queries

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP_Client.py                            │
├─────────────────────────────────────────────────────────────┤
│  MCP Client Layer                                           │
│  ├── ClientSession                                          │
│  ├── StdioServerParameters                                  │
│  └── Tool Discovery                                         │
├─────────────────────────────────────────────────────────────┤
│  Gemini Integration                                         │
│  ├── GenerativeModel (gemini-1.5-flash)                     │
│  ├── Tool Selection Logic                                   │
│  └── Response Formatting                                    │
├─────────────────────────────────────────────────────────────┤
│  User Interface                                             │
│  ├── Interactive Chat Loop                                  │
│  ├── Query Processing                                       │
│  └── Error Handling                                         │
└─────────────────────────────────────────────────────────────┘
```

**Fluxo de comunicação:**
1. Connection: Estabelece conexão stdio com o servidor MCP
2. Tool Discovery: Lista ferramentas disponíveis no servidor
3. Query Processing: Usa Gemini para decidir qual ferramenta chamar
4. Tool Execution: Chama ferramentas via MCP e retorna resultados

---

## Fluxo de Dados Completo

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│   Usuário   │───▶│ MCP_Client   │───▶│ MCP_Server  │───▶│   Qdrant    │
│             │    │              │    │             │    │    Cloud    │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
       ▲                   │                   │                   │
       │                   │                   │                   │
       │                   ▼                   ▼                   │
       │            ┌──────────────┐    ┌─────────────┐            │
       │            │   Gemini     │    │   Gemini    │            │
       │            │ (Tool Select)│    │ (Response   │            │
       │            │              │    │ Generation) │            │
       │            └──────────────┘    └─────────────┘            │
       │                   │                   │                   │
       └───────────────────┼───────────────────┼───────────────────┘
                           │                   │
                           ▼                   ▼
                   ┌──────────────┐    ┌─────────────┐
                   │   Moodle     │    │   PDFs/     │
                   │   API        │    │   Folder    │
                   └──────────────┘    └─────────────┘
```

---

## Características Técnicas Detalhadas

### 1. Processamento de Documentos
- **Loader:** `PyPDFLoader` para extrair texto de PDFs
- **Splitting:**
  - `RecursiveCharacterTextSplitter` (chunk_size=800, overlap=200) para indexação inicial
  - `CharacterTextSplitter` (chunk_size=1000, overlap=100) para novos documentos
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensões)

### 2. Vectorstore (Qdrant Cloud)
- **Configuração:** Cloud-hosted com API key
- **Collection:** `MCP_RAG`
- **Distance Metric:** Cosine similarity
- **Vector Size:** 384 (compatível com o modelo de embeddings)

### 3. Modelo de Linguagem
- **Primary:** Google Gemini 2.0 Flash (temperature=0.4)
- **Secondary:** Google Gemini 1.5 Flash (para seleção de ferramentas)
- **Prompt Template:** Customizado para português com contexto

### 4. Integração Moodle
- **API Endpoint:** `http://localhost/webservice/rest/server.php`
- **Authentication:** Token-based (`c27f3ee4c459f64400855077479f2d61`)
- **Functions:**
  - `core_course_get_courses_by_field`: Lista cursos
  - `core_course_get_contents`: Obtém conteúdo de cursos
- **PDF Download:** Automático com autenticação via token

### 5. Ferramentas MCP Disponíveis

| Ferramenta                  | Função                                 | Parâmetros                        |
|-----------------------------|----------------------------------------|-----------------------------------|
| `retrieve`                  | Busca semântica e geração de resposta  | `prompt: str`                     |
| `add_new_pdfs`              | Adiciona novos PDFs da pasta           | Nenhum                            |
| `download_and_add_pdf`      | Download e indexação de PDF via URL    | `file_url: str`                   |
| `get_courses_by_field`      | Busca cursos no Moodle                 | `field: str, value: str`          |
| `download_pdfs_from_course` | Download de PDFs de um curso           | `course_fullname: str`            |
| `clear_rag`                 | Limpa o vectorstore                    | Nenhum                            |

---

## Vantagens da Arquitetura

### 1. Modularidade
- Separação clara entre cliente e servidor
- Protocolo MCP permite troca fácil de implementações
- Ferramentas independentes e reutilizáveis

### 2. Escalabilidade
- Qdrant Cloud permite escalabilidade horizontal
- Processamento assíncrono de documentos
- Cache de embeddings no vectorstore

### 3. Flexibilidade
- Suporte a múltiplos formatos de entrada (PDF, URLs, Moodle)
- Integração com sistemas externos (Moodle)
- Configuração via variáveis de ambiente

### 4. Robustez
- Tratamento de erros em cada camada
- Fallback para respostas quando não há contexto
- Validação de entrada e saída

---

## Limitações e Considerações

### 1. Dependências Externas
- Qdrant Cloud (requer conectividade)
- Google Gemini API (requer quota)
- Moodle server (para funcionalidades de curso)

### 2. Performance
- Embeddings locais podem ser lentos
- Processamento de PDFs é CPU-intensive
- Latência de rede para Qdrant Cloud

### 3. Segurança
- API keys expostas no código
- Token do Moodle hardcoded
- Sem autenticação de utilizadores

---

Esta arquitetura representa um sistema RAG moderno e bem estruturado, adequado para aplicações educacionais com integração a LMS (Learning Management Systems). 