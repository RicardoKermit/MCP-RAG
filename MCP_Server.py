from mcp.server.fastmcp import FastMCP
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_huggingface import HuggingFaceEmbeddings

import os
from dotenv import load_dotenv
from pathlib import Path
import requests
import httpx
import shutil
import gc
# Load .env
load_dotenv()

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

QDRANT_COLLECTION_NAME=os.getenv("QDRANT_COLLECTION_NAME")
QDRANT_API_KEY=os.getenv("QDRANT_API_KEY")
QDRANT_URL=os.getenv("QDRANT_HOST")

MOODLE_URL=os.getenv("MOODLE_URL")
MOODLE_TOKEN=os.getenv("MOODLE_TOKEN")

# Pastas
PDF_FOLDER = "pdfs"

# MCP
mcp = FastMCP(name="RAG_pdf_Mul_RemoteQdrant")

# Embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Cliente Qdrant
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
if QDRANT_COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
    client.recreate_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )

# Vectorstore
all_texts = []
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
    loader = PyPDFLoader(str(pdf_file))
    data = loader.load()
    texts = text_splitter.split_documents(data)
    all_texts.extend(texts)

docsearch = Qdrant(
    client=client,
    collection_name=QDRANT_COLLECTION_NAME,
    embeddings=embeddings
)

if all_texts:
    docsearch.add_documents(all_texts)

retriever = docsearch.as_retriever(search_kwargs={"k": 5})

# Modelo atual (será alterado dinamicamente)
current_model_name = "gemini-1.5-flash-8b"  # Changed to the most economical model
model = GoogleGenerativeAI(model=current_model_name, temperature=0.4)

custom_prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        "Responde sempre em português. Se não souber a resposta, diz claramente. "
        "Contexto: {context}\n\nPergunta: {question}\nResposta:"
    ),
)

qa = RetrievalQA.from_chain_type(
    llm=model,
    chain_type="stuff",
    retriever=retriever,
    chain_type_kwargs={"prompt": custom_prompt}
)

def update_model(new_model_name: str) -> bool:
    """Atualiza o modelo Gemini usado pelo servidor"""
    global model, qa, current_model_name
    
    if new_model_name not in GEMINI_MODELS:
        return False
    
    try:
        current_model_name = new_model_name
        model = GoogleGenerativeAI(model=current_model_name, temperature=0.4)
        qa = RetrievalQA.from_chain_type(
            llm=model,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": custom_prompt}
        )
        return True
    except Exception as e:
        print(f"Erro ao atualizar modelo: {e}")
        return False

@mcp.tool()
def set_model(model_name: str) -> str:
    """
    Define o modelo Gemini a ser usado pelo servidor MCP.
    
    Permite alterar dinamicamente o modelo Gemini usado para geração de respostas,
    sem necessidade de reiniciar o servidor. Útil para otimizar custos ou performance.
    
    Args:
        model_name (str): Nome do modelo Gemini a usar. Deve ser uma das chaves
                         do dicionário GEMINI_MODELS (ex: "gemini-1.5-flash-8b")
    
    Returns:
        str: Mensagem de confirmação com o nome do modelo alterado, ou erro se
             o modelo não for válido.
    
    Examples:
        >>> set_model("gemini-1.5-flash-8b")
        "Modelo alterado para Gemini 1.5 Flash 8B"
        
        >>> set_model("gemini-2.0-pro")
        "Modelo alterado para Gemini 2.0 Pro"
        
        >>> set_model("invalid-model")
        "Erro: Modelo 'invalid-model' não é válido"
    
    Notes:
        - A alteração afeta todas as operações subsequentes (retrieve, generate_quiz, etc.)
        - Modelos mais caros (Pro) têm melhor performance mas custo maior
        - Modelos mais baratos (Flash) são ideais para uso prolongado
    """
    if update_model(model_name):
        return f"Modelo alterado para {GEMINI_MODELS[model_name]['name']}"
    else:
        return f"Erro: Modelo '{model_name}' não é válido"

@mcp.tool()
def get_current_model() -> dict:
    """
    Retorna informações sobre o modelo Gemini atual e lista todos os modelos disponíveis.
    
    Fornece informações detalhadas sobre o modelo em uso e todos os modelos
    Gemini disponíveis, incluindo descrições, capacidades e custos relativos.
    
    Returns:
        dict: Dicionário com as seguintes chaves:
            - "current_model": Nome do modelo atualmente em uso
            - "current_model_info": Informações detalhadas do modelo atual
            - "available_models": Dicionário completo com todos os modelos disponíveis
    
    Examples:
        >>> get_current_model()
        {
            "current_model": "gemini-1.5-flash-8b",
            "current_model_info": {
                "name": "Gemini 1.5 Flash 8B",
                "description": "Modelo mais barato da família Gemini...",
                "max_tokens": 4096,
                "cost_rank": 1
            },
            "available_models": {
                "gemini-1.5-flash-8b": {...},
                "gemini-2.0-flash-lite": {...},
                ...
            }
        }
    
    Notes:
        - Útil para verificar qual modelo está ativo antes de alterá-lo
        - Permite comparar diferentes modelos antes de fazer a troca
        - Inclui informações de custo para ajudar na escolha do modelo
    """
    return {
        "current_model": current_model_name,
        "current_model_info": GEMINI_MODELS[current_model_name],
        "available_models": GEMINI_MODELS
    }

@mcp.tool()
def retrieve(prompt: str) -> str:
    """
    Busca e gera respostas baseadas no conteúdo dos PDFs armazenados no vectorstore.
    
    Esta função utiliza o sistema RAG (Retrieval Augmented Generation) para:
    1. Buscar documentos relevantes no vectorstore (Qdrant)
    2. Combinar o contexto encontrado com o prompt do utilizador
    3. Gerar uma resposta usando o modelo Gemini configurado
    
    Args:
        prompt (str): A pergunta ou instrução do utilizador. Pode ser uma pergunta direta,
                     uma instrução para gerar conteúdo, ou qualquer texto que precise
                     de resposta baseada nos documentos disponíveis.
    
    Returns:
        str: Resposta gerada baseada no conteúdo dos PDFs. Se não conseguir encontrar
             informação relevante ou ocorrer um erro, retorna uma mensagem explicativa.
    
    Examples:
        >>> retrieve("Quais são as regras do Monopoly?")
        "Baseado nos documentos disponíveis, as regras do Monopoly incluem..."
        
        >>> retrieve("Gera 5 perguntas sobre Scala")
        "## Perguntas sobre Scala\n\n1. O que é Scala?\n..."
        
        >>> retrieve("Explica o conceito de certificados")
        "Um certificado é um documento digital que..."
    
    Notes:
        - A função usa o modelo Gemini configurado (atualmente gemini-1.5-flash-8b)
        - Busca os 5 documentos mais relevantes do vectorstore
        - Responde sempre em português
        - Se não encontrar informação relevante, indica claramente
    """
    try:
        result = qa.invoke({"query": prompt})
        return result.get("result", "Não foi possível obter uma resposta.")
    except Exception as e:
        return f"Erro ao processar a pergunta: {e}"

@mcp.tool()
def add_new_pdfs() -> str:
    """
    Adiciona novos PDFs da pasta 'pdfs' ao vectorstore (Qdrant).
    
    Verifica a pasta 'pdfs' em busca de novos arquivos PDF que ainda não foram
    processados e adicionados ao vectorstore. Útil para atualizar o conhecimento
    do sistema sem reiniciar o servidor.
    
    Returns:
        str: Mensagem indicando se novos PDFs foram adicionados ou se não há
             novos arquivos para processar.
    
    Examples:
        >>> add_new_pdfs()
        "PDFs adicionados."
        
        >>> add_new_pdfs()
        "Nenhum PDF novo para adicionar."
    
    Notes:
        - Verifica apenas arquivos .pdf na pasta 'pdfs'
        - Evita duplicação comparando com documentos já existentes
        - Processa automaticamente o texto e cria embeddings
        - Não requer reinicialização do servidor
    """
    existing_ids = set([d.metadata.get("source") for d in docsearch.similarity_search("", k=1000)])
    new_files_added = False
    for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
        file_path = str(pdf_file.resolve())
        if file_path not in existing_ids:
            loader = PyPDFLoader(file_path)
            data = loader.load()
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            texts = text_splitter.split_documents(data)
            docsearch.add_documents(texts)
            new_files_added = True
    return "PDFs adicionados." if new_files_added else "Nenhum PDF novo para adicionar."

@mcp.tool()
def download_and_add_pdf(file_url: str) -> str:
    """
    Faz download de um PDF a partir de uma URL e adiciona-o ao vectorstore.
    
    Baixa um arquivo PDF de uma URL remota, salva-o na pasta 'pdfs' e
    processa-o automaticamente para adicionar ao sistema RAG. Útil para
    incorporar documentos externos sem intervenção manual.
    
    Args:
        file_url (str): URL completa do arquivo PDF a baixar. Deve ser uma URL
                        válida que aponte diretamente para um arquivo PDF.
    
    Returns:
        str: Mensagem de sucesso com o nome do arquivo baixado, ou mensagem
             de erro se a operação falhar.
    
    Examples:
        >>> download_and_add_pdf("https://example.com/document.pdf")
        "'document.pdf' adicionado com sucesso."
        
        >>> download_and_add_pdf("https://example.com/image.jpg")
        "URL não é PDF."
        
        >>> download_and_add_pdf("https://invalid-url.com/file.pdf")
        "Erro: Connection timeout"
    
    Notes:
        - Valida se a URL termina com extensão .pdf
        - Faz download usando requests com timeout
        - Salva automaticamente na pasta 'pdfs'
        - Processa e adiciona ao vectorstore imediatamente
        - Trata erros de rede e arquivos inválidos
    """
    try:
        url_path = file_url.lower().split("?")[0]
        if not url_path.endswith(".pdf"):
            return "URL não é PDF."
        response = requests.get(file_url)
        if response.status_code != 200:
            return f"Erro HTTP {response.status_code}"
        filename = url_path.split("/")[-1]
        pdf_path = Path(PDF_FOLDER) / filename
        with open(pdf_path, "wb") as f:
            f.write(response.content)
        loader = PyPDFLoader(str(pdf_path))
        data = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(data)
        docsearch.add_documents(texts)
        return f"'{filename}' adicionado com sucesso."
    except Exception as e:
        return f"Erro: {e}"

@mcp.tool()
def get_courses_by_field(field: str, value: str) -> dict:
    """
    Busca cursos no Moodle usando critérios específicos.
    
    Utiliza a API do Moodle para buscar cursos baseado em diferentes campos
    como ID, nome curto, número de identificação ou categoria. Útil para
    integrar com plataformas Moodle existentes.
    
    Args:
        field (str): Campo de busca do curso. Opções válidas:
            - "id": Busca por ID do curso
            - "shortname": Busca por nome curto do curso
            - "idnumber": Busca por número de identificação
            - "category": Busca por categoria
            - "": Retorna todos os cursos (vazio)
        value (str): Valor a procurar no campo especificado. Se field for vazio,
                    este valor é ignorado.
    
    Returns:
        dict: Resposta da API do Moodle com lista de cursos encontrados, ou
              dicionário com chave "error" se ocorrer algum erro.
    
    Examples:
        >>> get_courses_by_field("shortname", "CS101")
        {"courses": [{"id": 123, "shortname": "CS101", "fullname": "Computer Science 101"}]}
        
        >>> get_courses_by_field("", "")
        {"courses": [{"id": 1, "shortname": "MATH101", "fullname": "Mathematics"}]}
        
        >>> get_courses_by_field("id", "999")
        {"error": "Course not found"}
    
    Notes:
        - Requer configuração válida de MOODLE_URL e MOODLE_TOKEN
        - Usa timeout de 30 segundos para evitar travamentos
        - Retorna dados no formato JSON do Moodle
        - Útil para integração com sistemas educacionais existentes
    """
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "core_course_get_courses_by_field",
        "moodlewsrestformat": "json",
        "field": field,
        "value": value
    }
    try:
        response = httpx.post(MOODLE_URL, data=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def download_pdfs_from_course(course_fullname: str) -> dict:
    """
    Faz download de todos os PDFs de um curso específico do Moodle.
    
    Busca um curso no Moodle pelo nome completo, obtém todos os recursos PDF
    disponíveis no curso e faz download automático para a pasta local. Ideal
    para sincronizar materiais educacionais de plataformas Moodle existentes.
    
    Args:
        course_fullname (str): Nome completo do curso no Moodle (ex: "Computer Science 101")
    
    Returns:
        dict: Resumo da operação com as seguintes chaves:
            - "course": Nome do curso processado
            - "pdfs_downloaded": Lista de PDFs baixados com sucesso
            - "pdfs_skipped": Lista de PDFs que já existiam localmente
            - "pdfs_failed": Lista de PDFs que falharam no download
            - "rag_result": Resultado da adição ao vectorstore
    
    Examples:
        >>> download_pdfs_from_course("Computer Science 101")
        {
            "course": "Computer Science 101",
            "pdfs_downloaded": ["lecture1.pdf", "assignment1.pdf"],
            "pdfs_skipped": ["syllabus.pdf"],
            "pdfs_failed": [],
            "rag_result": "PDFs adicionados."
        }
        
        >>> download_pdfs_from_course("Non-existent Course")
        {"error": "Curso 'Non-existent Course' não encontrado."}
    
    Notes:
        - Requer configuração válida de MOODLE_URL e MOODLE_TOKEN
        - Evita duplicação verificando arquivos já existentes
        - Processa automaticamente os PDFs para o vectorstore
        - Trata erros de rede e arquivos corrompidos
        - Usa autenticação token para aceder aos recursos protegidos
    """
    downloaded, skipped, failed = [], [], []
    courses_resp = get_courses_by_field(field="", value="")
    if "error" in courses_resp:
        return {"error": f"Erro: {courses_resp['error']}"}
    courses = courses_resp.get("courses", [])
    course = next((c for c in courses if c.get("fullname") == course_fullname), None)
    if not course:
        return {"error": f"Curso '{course_fullname}' não encontrado."}
    courseid = course["id"]
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "core_course_get_contents",
        "moodlewsrestformat": "json",
        "courseid": courseid
    }
    try:
        response = httpx.get(MOODLE_URL, params=params, timeout=30)
        response.raise_for_status()
        contents = response.json()
    except Exception as e:
        return {"error": f"Erro ao obter conteúdo: {str(e)}"}

    for section in contents:
        for module in section.get("modules", []):
            if module.get("modname") == "resource":
                for item in module.get("contents", []):
                    if item.get("type") == "file" and item.get("filename", "").lower().endswith(".pdf"):
                        file_name = item["filename"]
                        file_path = Path(PDF_FOLDER) / file_name
                        if file_path.exists():
                            skipped.append(file_name)
                            continue
                        file_url = item["fileurl"]
                        sep = "&" if "?" in file_url else "?"
                        download_url = f"{file_url}{sep}token={MOODLE_TOKEN}"
                        try:
                            file_resp = httpx.get(download_url, timeout=60)
                            file_resp.raise_for_status()
                            with open(file_path, "wb") as f:
                                f.write(file_resp.content)
                            downloaded.append(file_name)
                        except Exception as e:
                            failed.append({"filename": file_name, "error": str(e)})

    rag_result = add_new_pdfs()
    return {
        "course": course_fullname,
        "pdfs_downloaded": downloaded,
        "pdfs_skipped": skipped,
        "pdfs_failed": failed,
        "rag_result": rag_result
    }

@mcp.tool()
def clear_rag() -> str:
    """
    Limpa completamente o vectorstore (Qdrant) removendo todos os documentos.
    
    Apaga toda a coleção de documentos do Qdrant, efetivamente resetando
    o conhecimento do sistema RAG. Útil para limpeza completa ou reset
    do sistema quando necessário.
    
    Returns:
        str: Mensagem de confirmação se a operação foi bem-sucedida, ou
             mensagem de erro se ocorrer algum problema.
    
    Examples:
        >>> clear_rag()
        "Vectorstore (Qdrant) limpo."
        
        >>> clear_rag()
        "Erro ao apagar vectorstore: Connection timeout"
    
    Notes:
        - Remove permanentemente todos os documentos do vectorstore
        - Requer nova adição de PDFs para restaurar o conhecimento
        - Útil para reset completo do sistema
        - Operação irreversível - use com cuidado
    """
    try:
        client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
        return "Vectorstore (Qdrant) limpo."
    except Exception as e:
        return f"Erro ao apagar vectorstore: {e}"

if __name__ == "__main__":
    mcp.run()
