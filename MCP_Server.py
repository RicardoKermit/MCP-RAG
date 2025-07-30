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
    """Define o modelo Gemini a ser usado pelo servidor"""
    if update_model(model_name):
        return f"Modelo alterado para {GEMINI_MODELS[model_name]['name']}"
    else:
        return f"Erro: Modelo '{model_name}' não é válido"

@mcp.tool()
def get_current_model() -> dict:
    """Retorna o modelo atual e lista de modelos disponíveis"""
    return {
        "current_model": current_model_name,
        "current_model_info": GEMINI_MODELS[current_model_name],
        "available_models": GEMINI_MODELS
    }

@mcp.tool()
def retrieve(prompt: str) -> str:
    try:
        result = qa.invoke({"query": prompt})
        return result.get("result", "Não foi possível obter uma resposta.")
    except Exception as e:
        return f"Erro ao processar a pergunta: {e}"

@mcp.tool()
def add_new_pdfs() -> str:
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
    try:
        client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
        return "Vectorstore (Qdrant) limpo."
    except Exception as e:
        return f"Erro ao apagar vectorstore: {e}"

if __name__ == "__main__":
    mcp.run()
