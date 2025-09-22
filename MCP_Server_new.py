from mcp.server.fastmcp import FastMCP
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders.parsers import RapidOCRBlobParser
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate
try:
    # Prefer new split packages
    from langchain_chroma import Chroma
    CHROMA_IMPORTED_FROM = "langchain_chroma"
except ImportError:
    # Fallback to community package if needed
    from langchain_community.vectorstores import Chroma
    CHROMA_IMPORTED_FROM = "langchain_community.vectorstores"
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
import uuid
import tempfile
from typing import List
import time
from datetime import datetime
import logging
from langchain_openai import ChatOpenAI
import requests  # para chamar o Ollama via API HTTP
import re
import json



# PostgreSQL Logging System
from postgres_logger import PostgresLogger, OperationType

# Configuração de Logs
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
        f"logs/rag_server_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)
    
    # Log para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configurar logger principal
    logger = logging.getLogger('RAG_Server')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Inicializar logger
logger = setup_logging()

# Inicializar sistema de logs PostgreSQL
postgres_logger = PostgresLogger({
    'host': 'localhost',
    'port': 5432,
    'database': 'rag_system',
    'user': 'rag_user',
    'password': 'rag_password_secure_2024'
})

# Load .env
load_dotenv()


#ALL_MODELS=os.getenv("ALL_MODELS")

models_file = os.getenv("ALL_MODELS", "models.json")
with open(Path(__file__).parent / models_file, "r", encoding="utf-8") as f:
    ALL_MODELS = json.load(f)

QDRANT_COLLECTION_NAME=os.getenv("QDRANT_COLLECTION_NAME")
QDRANT_API_KEY=os.getenv("QDRANT_API_KEY")
QDRANT_URL=os.getenv("QDRANT_HOST")

# RAG backend selection
RAG_BACKEND=os.getenv("RAG_BACKEND").lower()  # "qdrant" or "chroma"
CHROMA_DIR=os.getenv("CHROMA_DIR")

MOODLE_URL=os.getenv("MOODLE_URL")
MOODLE_TOKEN=os.getenv("MOODLE_TOKEN")

# Pastas
PDF_FOLDER = "pdfs_test"

# MCP
mcp = FastMCP(name="RAG_pdf_Mul_RemoteQdrant")

"""Inicialização de embeddings e vectorstore, com suporte a Chroma (local) e Qdrant (cloud)."""
# Embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

if RAG_BACKEND == "qdrant":
    # Cliente Qdrant
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    if QDRANT_COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
        client.recreate_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )

    # Preparar textos a indexar (apenas se houver PDFs)
    all_texts = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
    for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
        loader = PyPDFLoader(
            file_path=str(pdf_file),
            extract_images=True,
            images_parser=RapidOCRBlobParser(),  # OCR para ler texto dentro das imagens
        )
        data = loader.load()
        texts = text_splitter.split_documents(data)
        all_texts.extend(texts)

    # Vectorstore Qdrant
    docsearch = Qdrant(
        client=client,
        collection_name=QDRANT_COLLECTION_NAME,
        embeddings=embeddings
    )
    if all_texts:
        docsearch.add_documents(all_texts)
else:

    print("Chroma local com persistência")
    # Chroma local com persistência
    if os.path.exists(CHROMA_DIR) and os.path.isdir(CHROMA_DIR) and len(os.listdir(CHROMA_DIR)) > 0:
        docsearch = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    else:
        print("ENTROU RAG")
        all_texts = []
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
        for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
            loader = PyPDFLoader(
            file_path=str(pdf_file),
            extract_images=True,
            images_parser=RapidOCRBlobParser(),  # OCR para ler texto dentro das imagens
        )
            data = loader.load()
            texts = text_splitter.split_documents(data)
            all_texts.extend(texts)
        docsearch = Chroma.from_documents(all_texts, embeddings, persist_directory=CHROMA_DIR)

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

def _reinitialize_vectorstore(new_backend: str) -> str:
    """Reinicializa docsearch, retriever e qa com o backend indicado."""
    global RAG_BACKEND, docsearch, retriever, qa
    target_backend = (new_backend or RAG_BACKEND).lower()

    # Embeddings já inicializados globalmente
    if target_backend == "qdrant":
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        if QDRANT_COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
            client.recreate_collection(
                collection_name=QDRANT_COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
        # Não recarregar tudo obrigatoriamente; apenas garantir docsearch
        docsearch = Qdrant(
            client=client,
            collection_name=QDRANT_COLLECTION_NAME,
            embeddings=embeddings
        )
    elif target_backend == "chroma":
        # Reabrir Chroma do disco (se existir) ou criar vazio
        if os.path.exists(CHROMA_DIR) and os.path.isdir(CHROMA_DIR) and len(os.listdir(CHROMA_DIR)) > 0:
            docsearch = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
        else:
            # Base vazia
            docsearch = Chroma.from_documents([], embeddings, persist_directory=CHROMA_DIR)
    else:
        raise ValueError("Backend inválido. Use 'qdrant' ou 'chroma'.")

    retriever = docsearch.as_retriever(search_kwargs={"k": 5})
    qa = RetrievalQA.from_chain_type(
        llm=model,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": custom_prompt}
    )
    RAG_BACKEND = target_backend
    return RAG_BACKEND


def update_model(new_model_name: str) -> bool:
    """Atualiza o modelo Gemini ou OpenAI ou Ollama usado pelo servidor"""
    global model, qa, current_model_name
    if new_model_name not in ALL_MODELS:
        return False
    try:
        model_info = ALL_MODELS[new_model_name]
        if model_info["provider"] == "gemini":
            model = GoogleGenerativeAI(model=new_model_name, temperature=0.4)
        elif model_info["provider"] == "openai":
            model = ChatOpenAI(model=new_model_name, api_key=os.getenv("OPENAI_API_KEY"), temperature=0.4)
        elif model_info["provider"] == "ollama":
            from langchain_community.chat_models import ChatOllama
            model = ChatOllama(
                model=new_model_name,
                base_url="http://localhost:11434",
                temperature=0.4
            )

        # Reconstruir o QA pipeline
        qa = RetrievalQA.from_chain_type(
            llm=model,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": custom_prompt},
        )

        current_model_name = new_model_name
        return True
    except Exception as e:
        print(f"Erro ao atualizar modelo: {e}")
        return False

@mcp.tool()
def set_model(model_name: str) -> str:
    """
    Changes the current LLM model used by the server.
    Normally this tool should NOT be called by the assistant directly.
    Arguments:
      - model_name: the identifier of the model (e.g., "gemini-2.5-pro", "gpt-4o-mini").
    """
    if update_model(model_name):
        # Log em Postgres (sucesso)
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.API_CALL,
                details={"tool": "set_model", "model_name": model_name},
                status="success"
            )
        except Exception:
            pass
        return f"Modelo alterado para {ALL_MODELS[model_name]['name']}"
    else:
        # Log em Postgres (erro)
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.API_CALL,
                details={"tool": "set_model", "error": "invalid_model", "model_name": model_name},
                status="error",
                error_message="invalid model"
            )
        except Exception:
            pass
        return f"Erro: Modelo '{model_name}' não é válido"

@mcp.tool()
def get_current_model() -> dict:
    """
    Returns information about the current model in use and the list of available models.
    Use only when explicitly asked about the active model or supported models.
    """
    return {
        "current_model": current_model_name,
        "current_model_info": ALL_MODELS[current_model_name],
        "available_models": ALL_MODELS
    }

@mcp.tool()
def set_rag_backend(backend: str) -> dict:
    """
    Switches the active RAG backend (e.g., "chroma", "faiss", "weaviate").
    ONLY use this tool if the user explicitly asks to change the knowledge base backend.
    Arguments:
      - backend_name: the backend identifier.
    """
    try:
        new_backend = _reinitialize_vectorstore(backend)
        # Log em Postgres (sucesso)
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SYSTEM_MAINTENANCE,
                details={"tool": "set_rag_backend", "backend": new_backend},
                status="success"
            )
        except Exception:
            pass
        return {"success": True, "backend": new_backend}
    except Exception as e:
        # Log em Postgres (erro)
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SYSTEM_MAINTENANCE,
                details={"tool": "set_rag_backend", "backend": backend},
                status="error",
                error_message=str(e)
            )
        except Exception:
            pass
        return {"success": False, "error": str(e)}

@mcp.tool()
def get_rag_backend() -> dict:
    """
    Returns the name of the currently active RAG backend (e.g., "chroma", "faiss").
    ONLY use this tool if the user explicitly asks which backend is currently being used.
    Do not use it to answer knowledge questions.
    """
    #return {"backend": RAG_BACKEND, "options": ["qdrant", "chroma"], "chroma_dir": CHROMA_DIR, "qdrant_collection": QDRANT_COLLECTION_NAME}
    return RAG_BACKEND

@mcp.tool()
def retrieve(prompt: str) -> str:
    """
    Retrieves information directly from the knowledge base (indexed PDFs).
    ALWAYS use this tool whenever the user asks a question about the content of the PDFs.
    Arguments:
      - prompt: the user’s question.
    """
    start_time = time.time()
    try:
        # Log da operação (ficheiro/console)
        logger.info(f"RAG_RETRIEVE | Prompt: {prompt[:50]}... | Starting")
        
        result = qa.invoke({"query": prompt})
        response = result.get("result", "Não foi possível obter uma resposta.")
        
        # Calcular duração
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        
        # Log de sucesso (ficheiro/console)
        logger.info(f"RAG_RETRIEVE | Prompt: {prompt[:50]}... | Success | Duration: {duration:.2f}s")
        # Log em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.RAG_QUERY,
                details={"operation": "retrieve", "topic": prompt[:50], "duration_ms": duration_ms, "model": current_model_name},
                status="success",
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.RAG_QUERY.value, True, duration_ms)
        except Exception:
            pass
        
        return response
    except Exception as e:
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        error_msg = str(e)
        
        # Log de erro (ficheiro/console)
        logger.error(f"RAG_RETRIEVE | Prompt: {prompt[:50]}... | Error: {error_msg} | Duration: {duration:.2f}s")
        # Log em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.RAG_QUERY,
                details={"operation": "retrieve", "topic": prompt[:50]},
                status="error",
                error_message=error_msg,
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.RAG_QUERY.value, False, duration_ms)
        except Exception:
            pass
        
        return f"Erro ao processar a pergunta: {error_msg}"


@mcp.tool()
def add_new_pdfs() -> str:
    """
    Adds new PDF documents to the knowledge base (RAG).
    ONLY use this tool when the user explicitly provides new files to be added.
    Do not use it for general questions.
    """
    new_files_added = False
    added_count = 0

    try:
        if RAG_BACKEND == "qdrant":
            # Obter fontes já indexadas via busca vazia (limite alto)
            existing_ids = set([d.metadata.get("source") for d in docsearch.similarity_search("", k=1000)])
            for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
                file_path = str(pdf_file.resolve())
                if file_path not in existing_ids:
                    loader = PyPDFLoader(
                                        file_path=file_path,
                                        extract_images=True,
                                        images_parser=RapidOCRBlobParser(),  # OCR para ler texto dentro das imagens
                            )
                    data = loader.load()
                    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
                    texts = text_splitter.split_documents(data)
                    docsearch.add_documents(texts)
                    new_files_added = True
                    added_count += 1
        else:
            # Chroma: ler metadados existentes
            existing_metadatas = docsearch.get(include=["metadatas"]).get("metadatas", [])
            existing_sources = set()
            for meta_list in existing_metadatas:
                for meta in meta_list:
                    if isinstance(meta, dict):
                        src = meta.get("source")
                        if src:
                            existing_sources.add(src)
            for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
                file_path = str(pdf_file.resolve())
                if file_path not in existing_sources:
                    loader = PyPDFLoader(
                                        file_path=file_path,
                                        extract_images=True,
                                        images_parser=RapidOCRBlobParser(),  # OCR para ler texto dentro das imagens
                            )
                    data = loader.load()
                    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
                    texts = text_splitter.split_documents(data)
                    docsearch.add_documents(texts)
                    new_files_added = True
                    added_count += 1
            if new_files_added:
                try:
                    docsearch.persist()
                except Exception:
                    pass

        msg = "PDFs adicionados." if new_files_added else "Nenhum PDF novo para adicionar."
    except Exception as e:
        msg = f"Erro ao adicionar PDFs: {e}"
    # Log em Postgres (resumo da operação)
    try:
        postgres_logger.log_operation(
            operation_type=OperationType.FILE_UPLOAD,
            details={"operation": "add_new_pdfs", "added_count": added_count},
            status="success"
        )
    except Exception:
        pass
    return msg

@mcp.tool()
def download_and_add_pdf(file_url: str) -> str:
    """
    Downloads a PDF from the given URL and adds it to the knowledge base (RAG).
    ALWAYS use this tool when the user provides a valid file URL and explicitly asks to add that PDF.
    Arguments:
      - file_url: direct link to the PDF file to be downloaded and indexed.
    """
    try:
        url_path = file_url.lower().split("?")[0]
        if not url_path.endswith(".pdf"):
            # Log erro em Postgres
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.FILE_DOWNLOAD,
                    details={"operation": "download_and_add_pdf", "file_url": file_url},
                    status="error",
                    error_message="URL não é PDF"
                )
            except Exception:
                pass
            return "URL não é PDF."
        response = requests.get(file_url)
        if response.status_code != 200:
            # Log erro em Postgres
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.FILE_DOWNLOAD,
                    details={"operation": "download_and_add_pdf", "file_url": file_url, "http_status": response.status_code},
                    status="error",
                    error_message=f"HTTP {response.status_code}"
                )
            except Exception:
                pass
            return f"Erro HTTP {response.status_code}"
        filename = url_path.split("/")[-1]
        pdf_path = Path(PDF_FOLDER) / filename
        with open(pdf_path, "wb") as f:
            f.write(response.content)
        loader = PyPDFLoader(
                            file_path=pdf_path,
                            extract_images=True,
                            images_parser=RapidOCRBlobParser(),  # OCR para ler texto dentro das imagens
                            )
        data = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(data)
        docsearch.add_documents(texts)
        # Log sucesso em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.FILE_UPLOAD,
                details={"operation": "download_and_add_pdf", "filename": filename},
                status="success"
            )
        except Exception:
            pass
        return f"'{filename}' adicionado com sucesso."
    except Exception as e:
        # Log erro em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.FILE_DOWNLOAD,
                details={"operation": "download_and_add_pdf", "file_url": file_url},
                status="error",
                error_message=str(e)
            )
        except Exception:
            pass
        return f"Erro: {e}"

@mcp.tool()
def get_courses_by_field(field: str, value: str) -> dict:
    """
    Retrieves courses that match a given field and value.
    ONLY use this tool when the user explicitly asks to search for courses.
    Arguments:
      - field: the field to filter courses.
      - value: the value to match in that field.
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
        data = response.json()
        # Log sucesso em Postgres (opcional)
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.API_CALL,
                details={"tool": "get_courses_by_field", "field": field, "value": value},
                status="success"
            )
        except Exception:
            pass
        return data
    except Exception as e:
        # Log erro em Postgres (opcional)
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.API_CALL,
                details={"tool": "get_courses_by_field", "field": field, "value": value},
                status="error",
                error_message=str(e)
            )
        except Exception:
            pass
        return {"error": str(e)}

@mcp.tool()
def download_pdfs_from_course(course_fullname: str) -> dict:
    """
    Downloads all PDF resources from a given course and adds them to the knowledge base (RAG).
    ALWAYS use this tool when the user requests to add PDFs from a specific course.
    Arguments:
      - course_fullname: the exact name of the course.
    """
    downloaded, skipped, failed = [], [], []
    courses_resp = get_courses_by_field(field="", value="")
    if "error" in courses_resp:
        # Log erro em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.API_CALL,
                details={"tool": "download_pdfs_from_course", "course": course_fullname},
                status="error",
                error_message=f"Erro: {courses_resp['error']}"
            )
        except Exception:
            pass
        return {"error": f"Erro: {courses_resp['error']}"}
    courses = courses_resp.get("courses", [])
    course = next((c for c in courses if c.get("fullname") == course_fullname), None)
    if not course:
        # Log erro em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.API_CALL,
                details={"tool": "download_pdfs_from_course", "course": course_fullname},
                status="error",
                error_message="Curso não encontrado"
            )
        except Exception:
            pass
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
        # Log erro em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.API_CALL,
                details={"tool": "download_pdfs_from_course", "course": course_fullname},
                status="error",
                error_message=f"Erro ao obter conteúdo: {str(e)}"
            )
        except Exception:
            pass
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
    # Log resumo em Postgres
    try:
        postgres_logger.log_operation(
            operation_type=OperationType.FILE_DOWNLOAD,
            details={
                "tool": "download_pdfs_from_course",
                "course": course_fullname,
                "downloaded": downloaded,
                "skipped": skipped,
                "failed": failed,
                "rag_result": rag_result
            },
            status="success" if not failed else "warning",
            error_message=None if not failed else f"{len(failed)} ficheiros falharam"
        )
    except Exception:
        pass
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
    Limpa completamente o vectorstore, conforme o backend selecionado.
    - Qdrant: apaga a coleção remota
    - Chroma: remove a pasta de persistência local
    """
    try:
        if RAG_BACKEND == "qdrant":
            client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
            result_msg = "Vectorstore (Qdrant) limpo."
        else:
            if os.path.exists(CHROMA_DIR):
                shutil.rmtree(CHROMA_DIR)
            result_msg = "Vectorstore (Chroma) limpo."
        # Log sucesso em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SYSTEM_MAINTENANCE,
                details={"operation": "clear_rag", "backend": RAG_BACKEND},
                status="success"
            )
        except Exception:
            pass
        return result_msg
    except Exception as e:
        # Log erro em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SYSTEM_MAINTENANCE,
                details={"operation": "clear_rag", "backend": RAG_BACKEND},
                status="error",
                error_message=str(e)
            )
        except Exception:
            pass
        return f"Erro ao apagar vectorstore: {e}"

@mcp.tool()
def generate_quiz_with_difficulty(topic: str, num_questions: int = 5, difficulty: str = "mixed") -> dict:
    """
    Generates a quiz based on a specific topic.
    ALWAYS use this tool whenever the user asks for questions, quizzes, true/false, or multiple-choice exercises, not mock tests.
    Arguments:
      - topic: the subject of the quiz.
      - num_questions: number of questions to generate.
      - difficulty: difficulty level ("easy", "medium", "hard", or "mixed").
      - question_type: type of question ("multiple_choice" or "true_false").
    """
    start_time = time.time()
    try:
        # Log da operação
        logger.info(f"QUIZ_GENERATION | Topic: {topic} | Questions: {num_questions} | Difficulty: {difficulty} | Starting")
        
        # 1. Buscar conteúdo sobre o tópico
        difficulty_prompt = f"""
        Generates {num_questions} questions about {topic} with difficulty {difficulty}.

        IMPORTANT:
        - Uses only information from available PDFs
        - Generates ONLY the requested question type (multiple choice OR true/false)
        - For multiple choice: each question must have 4 options (a, b, c, d)
        - For true/false: each question must have 2 options (a) True, b) False)
        - Always indicates the correct answer
        - Format: Question + options + "Answer: X"
        - Difficulty {difficulty}: adjusts question complexity
        """
        
        quiz_content = retrieve(difficulty_prompt)
        
        # Calcular duração
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)

        
        
        if not quiz_content or "não foi possível" in quiz_content.lower():
            logger.warning(f"QUIZ_GENERATION | Topic: {topic} | Questions: {num_questions} | Difficulty: {difficulty} | No content found | Duration: {duration:.2f}s")
            # Log em Postgres (sem conteúdo relevante)
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.QUIZ_GENERATION,
                    details={"topic": topic, "num_questions": num_questions, "difficulty": difficulty},
                    status="error",
                    error_message="Sem conteúdo relevante",
                    duration_ms=duration_ms
                )
                postgres_logger.update_operation_stats(OperationType.QUIZ_GENERATION.value, False, duration_ms)
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Não foi possível encontrar conteúdo relevante sobre '{topic}'"
            }
        
        # Log de sucesso
        logger.info(f"QUIZ_GENERATION | Topic: {topic} | Questions: {num_questions} | Difficulty: {difficulty} | Success | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.QUIZ_GENERATION,
                details={"topic": topic, "num_questions": num_questions, "difficulty": difficulty, "duration_ms": duration_ms},
                status="success",
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.QUIZ_GENERATION.value, True, duration_ms)
        except Exception:
            pass
        
        return {
            "success": True,
            "quiz": quiz_content,
            "message": f"Questionário gerado com sucesso sobre {topic}",
            "topic": topic,
            "difficulty": difficulty
        }
        
    except Exception as e:
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        error_msg = str(e)
        
        # Log de erro
        logger.error(f"QUIZ_GENERATION | Topic: {topic} | Questions: {num_questions} | Difficulty: {difficulty} | Error: {error_msg} | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.QUIZ_GENERATION,
                details={"topic": topic, "num_questions": num_questions, "difficulty": difficulty},
                status="error",
                error_message=error_msg,
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.QUIZ_GENERATION.value, False, duration_ms)
        except Exception:
            pass
        
        return {
            "success": False,
            "message": f"Erro ao gerar questionário: {error_msg}"
        }

@mcp.tool()
def generate_dev_questions(topic: str, num_questions: int = 3, language: str = "en") -> dict:
    """
    Generates open end questions about a given topic.
    ALWAYS use this tool when the user asks for questions that should include both the question and the answer.

    Arguments:
      - topic: the  subject (e.g., "Scala", "Python", "Docker").
      - num_questions: number of questions to generate (default: 3).
      - language: language of the output ("en" for English, "pt" for Portuguese).
    """
    start_time = time.time()
    try:
        logger.info(f"DEV_QUESTIONS | Topic: {topic} | Questions: {num_questions} | Language: {language} | Starting")

        # Prompt para o LLM
        dev_prompt = f"""
        Generate {num_questions} open ended questions about "{topic}".
        For each question, also provide the answer immediately below.

        Format strictly as:
        Question: <question>
        Answer: <answer>

        Language of the output: {language}.
        """

        # Chamada à função retrieve (podes trocar por chamada direta ao modelo se preferires)
        dev_content = retrieve(dev_prompt)

        # Calcular duração
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)

        if not dev_content or "não foi possível" in dev_content.lower():
            logger.warning(f"DEV_QUESTIONS | Topic: {topic} | No content found | Duration: {duration:.2f}s")
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.QUIZ_GENERATION,  # podes criar um novo tipo se quiseres (DEV_QUESTIONS)
                    details={"topic": topic, "num_questions": num_questions, "language": language},
                    status="error",
                    error_message="No relevant content",
                    duration_ms=duration_ms
                )
                postgres_logger.update_operation_stats(OperationType.QUIZ_GENERATION.value, False, duration_ms)
            except Exception:
                pass
            return {
                "success": False,
                "message": f"No relevant content found about '{topic}'"
            }

        logger.info(f"DEV_QUESTIONS | Topic: {topic} | Questions: {num_questions} | Success | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.QUIZ_GENERATION,
                details={"topic": topic, "num_questions": num_questions, "language": language, "duration_ms": duration_ms},
                status="success",
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.QUIZ_GENERATION.value, True, duration_ms)
        except Exception:
            pass

        return {
            "success": True,
            "questions": dev_content,
            "message": f"Development questions successfully generated about {topic}",
            "topic": topic,
            "language": language
        }

    except Exception as e:
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        error_msg = str(e)

        logger.error(f"DEV_QUESTIONS | Topic: {topic} | Error: {error_msg} | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.QUIZ_GENERATION,
                details={"topic": topic, "num_questions": num_questions, "language": language},
                status="error",
                error_message=error_msg,
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.QUIZ_GENERATION.value, False, duration_ms)
        except Exception:
            pass

        return {
            "success": False,
            "message": f"Error while generating development questions: {error_msg}"
        }

@mcp.tool()
def study_plan_generator(student_id: str, goals: list, weaknesses: list, hours_per_week: int = 5, weeks: int = 4) -> dict:
    """
    Generates a personalized study plan based on PDFs (core content) 
    plus additional external multimedia resources.

    Arguments:
      - student_id: unique identifier for the student.
      - goals: list of main learning goals.
      - weaknesses: list of topics where the student struggles.
      - hours_per_week: number of hours available per week.
      - weeks: duration of the plan in weeks.
    """
    start_time = time.time()
    try:
        logger.info(
            f"STUDY_PLAN | Student: {student_id} | Goals: {goals} | Weaknesses: {weaknesses} | "
            f"Hours/week: {hours_per_week} | Weeks: {weeks} | Starting"
        )

        # Prompt atualizado
        plan_prompt = f"""
        Create a personalized study plan in Portuguese (Portugal).

        Inputs:
        - Student ID: {student_id}
        - Learning goals: {goals}
        - Weaknesses: {weaknesses}
        - Hours available per week: {hours_per_week}
        - Duration: {weeks} weeks

        REQUIREMENTS:
        1. Base the study plan structure and weekly topics primarily on the retrieved PDFs.
        2. Divide the plan by weeks. For each week, include:
           - Total study hours
           - Suggested number of sessions and hours per session
           - Focus topics (aligned with goals and weaknesses)
           - Activities (theory, exercises, small projects)
           - Evaluation criteria (how to measure progress that week)
        3. At the end, include ONE final integrative project combining all major topics.
        4. After the main plan, add a separate section titled "Recursos adicionais".
           - List 3–5 external resources (e.g. YouTube videos, online courses, official docs)
           - Prefer resources in Portuguese, but English is acceptable if high quality.
        5. Output must be structured Markdown with headings and bullet points.
        6. Be specific, avoid generic advice.
        """

        # Invocar retriever com RAG
        plan_content = retrieve(plan_prompt)

        duration = time.time() - start_time
        duration_ms = int(duration * 1000)

        if not plan_content or "sem conteúdo relevante" in plan_content.lower():
            logger.warning(f"STUDY_PLAN | Student: {student_id} | No content found | Duration: {duration:.2f}s")
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.STUDY_PLAN_GENERATION,
                    details={"student_id": student_id, "goals": goals, "weeks": weeks},
                    status="error",
                    error_message="Sem conteúdo relevante",
                    duration_ms=duration_ms
                )
                postgres_logger.update_operation_stats(OperationType.STUDY_PLAN_GENERATION.value, False, duration_ms)
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Não foi possível gerar um plano de estudos para '{student_id}'"
            }

        # Log de sucesso
        logger.info(f"STUDY_PLAN | Student: {student_id} | Success | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.STUDY_PLAN_GENERATION,
                details={
                    "student_id": student_id,
                    "goals": goals,
                    "weaknesses": weaknesses,
                    "hours_per_week": hours_per_week,
                    "weeks": weeks,
                    "duration_ms": duration_ms
                },
                status="success",
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.STUDY_PLAN_GENERATION.value, True, duration_ms)
        except Exception:
            pass

        return {
            "success": True,
            "plan": plan_content,
            "message": f"Plano de estudos gerado com sucesso para {student_id}",
            "student_id": student_id,
            "weeks": weeks
        }

    except Exception as e:
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        error_msg = str(e)

        logger.error(f"STUDY_PLAN | Student: {student_id} | Error: {error_msg} | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.STUDY_PLAN_GENERATION,
                details={"student_id": student_id, "goals": goals, "weeks": weeks},
                status="error",
                error_message=error_msg,
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.STUDY_PLAN_GENERATION.value, False, duration_ms)
        except Exception:
            pass

        return {
            "success": False,
            "message": f"Erro ao gerar plano de estudos: {error_msg}"
        }

@mcp.tool()
def generate_lesson_summary(topic: str, detail_level: str = "detailed") -> dict:
    """
    Generates a contextualized lesson summary about a specific topic.
    ALWAYS use this tool whenever the user asks for summaries, overviews, or syntheses of content.

    Arguments:
      - topic: the subject of the summary.
      - detail_level: "brief" for short summaries, "detailed" for in-depth summaries.
    """
    start_time = time.time()
    try:
        logger.info(f"LESSON_SUMMARY | Topic: {topic} | Detail: {detail_level} | Starting")

        # 1. Construção do prompt
        summary_prompt = f"""
        Generate a {detail_level} summary about the topic: {topic}.

        IMPORTANT:
        - Use only information from the available PDFs
        - If no relevant content is found, say explicitly "Sem conteúdo relevante encontrado"
        - The summary must be coherent, structured in paragraphs
        - Highlight key concepts, definitions and examples
        - For 'detailed', provide extended explanations and subtopics
        - For 'brief', keep the text concise (max 3 paragraphs)
        """

        # 2. Invocar RAG retriever
        summary_content = retrieve(summary_prompt)

        duration = time.time() - start_time
        duration_ms = int(duration * 1000)

        if not summary_content or "sem conteúdo relevante" in summary_content.lower():
            logger.warning(f"LESSON_SUMMARY | Topic: {topic} | No content found | Duration: {duration:.2f}s")
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.SUMMARY_GENERATION,
                    details={"topic": topic, "detail_level": detail_level},
                    status="error",
                    error_message="Sem conteúdo relevante",
                    duration_ms=duration_ms
                )
                postgres_logger.update_operation_stats(OperationType.SUMMARY_GENERATION.value, False, duration_ms)
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Não foi possível encontrar conteúdo relevante sobre '{topic}'"
            }

        # Log de sucesso
        logger.info(f"LESSON_SUMMARY | Topic: {topic} | Success | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SUMMARY_GENERATION,
                details={"topic": topic, "detail_level": detail_level, "duration_ms": duration_ms},
                status="success",
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.SUMMARY_GENERATION.value, True, duration_ms)
        except Exception:
            pass

        return {
            "success": True,
            "summary": summary_content,
            "message": f"Resumo gerado com sucesso sobre {topic}",
            "topic": topic,
            "detail_level": detail_level
        }

    except Exception as e:
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        error_msg = str(e)

        logger.error(f"LESSON_SUMMARY | Topic: {topic} | Error: {error_msg} | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SUMMARY_GENERATION,
                details={"topic": topic, "detail_level": detail_level},
                status="error",
                error_message=error_msg,
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.SUMMARY_GENERATION.value, False, duration_ms)
        except Exception:
            pass

        return {
            "success": False,
            "message": f"Erro ao gerar resumo: {error_msg}"
        }

@mcp.tool()
def interactive_flashcards(topic: str, num_cards: int = 10) -> dict:
    """
    Generates flashcards in plain text style based on a specific topic.
    Each flashcard is returned as simple Q/A text, easy to read or copy.
    
    Arguments:
      - topic: subject of the flashcards
      - num_cards: number of flashcards to generate
    """
    start_time = time.time()
    try:
        logger.info(f"FLASHCARD_GENERATION | Topic: {topic} | Cards: {num_cards} | Starting")

        # Prompt para gerar flashcards em texto
        flashcard_prompt = f"""
        Generate {num_cards} flashcards about {topic}.

        IMPORTANT:
        - Use only information from the available PDFs
        - Return the flashcards as plain text in Portuguese (Portugal)
        - Format each card as:

          Flashcard X
          Q: ...
          A: ...

        - Do not return JSON or any extra commentary.
        """

        # Invocar o modelo (podes usar retrieve ou qa.invoke → ambos devolvem texto)
        #flashcards_text = retrieve(flashcard_prompt)
        res = qa.invoke({"query": flashcard_prompt})
        if isinstance(res, dict):
            flashcards_text = res.get("result", "")
        else:
            flashcards_text = str(res)

        duration = time.time() - start_time
        duration_ms = int(duration * 1000)

        if not flashcards_text or "não foi possível" in flashcards_text.lower():
            logger.warning(f"FLASHCARD_GENERATION | Topic: {topic} | No content found | Duration: {duration:.2f}s")
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.FLASHCARD_GENERATION,
                    details={"topic": topic, "num_cards": num_cards},
                    status="error",
                    error_message="Sem conteúdo relevante",
                    duration_ms=duration_ms
                )
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Não foi possível gerar flashcards sobre '{topic}'"
            }

        # Log de sucesso
        logger.info(f"FLASHCARD_GENERATION | Topic: {topic} | Success | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.FLASHCARD_GENERATION,
                details={"topic": topic, "num_cards": num_cards, "duration_ms": duration_ms},
                status="success",
                duration_ms=duration_ms
            )
        except Exception:
            pass

        return {
            "success": True,
            "flashcards": flashcards_text,
            "message": f"Flashcards gerados com sucesso sobre {topic}",
            "topic": topic
        }

    except Exception as e:
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        error_msg = str(e)

        logger.error(f"FLASHCARD_GENERATION | Topic: {topic} | Error: {error_msg} | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.FLASHCARD_GENERATION,
                details={"topic": topic, "num_cards": num_cards},
                status="error",
                error_message=error_msg,
                duration_ms=duration_ms
            )
        except Exception:
            pass

        return {
            "success": False,
            "message": f"Erro ao gerar flashcards: {error_msg}"
        }

@mcp.tool()
def generate_test(topic: str, num_questions: int = 10) -> dict:
    """
    Generates a mixed test (mock exam) about a given topic.
    The test includes multiple-choice, true/false, and open-ended questions.
    
    Arguments:
      - topic: subject of the test
      - num_questions: total number of questions
    """
    start_time = time.time()
    try:
        logger.info(f"TEST_GENERATION | Topic: {topic} | Questions: {num_questions} | Starting")

        test_prompt = f"""
        Generate a test with {num_questions} questions about {topic}.

        REQUIREMENTS:
        - Use only information from the available PDFs
        - Mix question types: multiple choice, true/false, and open-ended
        - For multiple choice:
          * Provide 4 options (a, b, c, d)
          * Indicate the correct option
        - For true/false:
          * Provide statement + answer (True/False)
        - For open-ended:
          * Provide the question and a short "expected answer"
        - Format the output in Markdown like this:

        ### Question 1 (Multiple Choice)
        Text...
        a) ...
        b) ...
        c) ...
        d) ...
        Answer: X

        ### Question 2 (True/False)
        Statement...
        Answer: True

        ### Question 3 (Open-ended)
        Question text...
        Expected answer: ...
        """

        test_content = retrieve(test_prompt)

        duration = time.time() - start_time
        duration_ms = int(duration * 1000)

        if not test_content or "não foi possível" in test_content.lower():
            logger.warning(f"TEST_GENERATION | Topic: {topic} | No content found | Duration: {duration:.2f}s")
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.TEST_GENERATION,
                    details={"topic": topic, "num_questions": num_questions},
                    status="error",
                    error_message="Sem conteúdo relevante",
                    duration_ms=duration_ms
                )
            except Exception:
                pass
            return {
                "success": False,
                "message": f"Não foi possível gerar teste sobre '{topic}'"
            }

        logger.info(f"TEST_GENERATION | Topic: {topic} | Questions: {num_questions} | Success | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.TEST_GENERATION,
                details={"topic": topic, "num_questions": num_questions, "duration_ms": duration_ms},
                status="success",
                duration_ms=duration_ms
            )
        except Exception:
            pass

        return {
            "success": True,
            "test": test_content,
            "message": f"Teste gerado com sucesso sobre {topic}",
            "topic": topic
        }

    except Exception as e:
        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        error_msg = str(e)

        logger.error(f"TEST_GENERATION | Topic: {topic} | Error: {error_msg} | Duration: {duration:.2f}s")
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.TEST_GENERATION,
                details={"topic": topic, "num_questions": num_questions},
                status="error",
                error_message=error_msg,
                duration_ms=duration_ms
            )
        except Exception:
            pass

        return {
            "success": False,
            "message": f"Erro ao gerar teste: {error_msg}"
        }


@mcp.tool()
def generate_video_with_veo(prompt: str, duration_seconds: int = 8, aspect_ratio: str = "16:9") -> dict:
    """
    Generates a video using the Gemini Veo API based on a textual description.
    ALWAYS use this tool whenever the user asks to create or generate a video.
    Arguments:
      - description: a textual description of the video.
      - style: the style of the video (default: "realistic").
      - duration: duration of the video in seconds (default: 30).
    """
    try:
        from google import genai
        from google.genai import types
        import time
        
        # Verificar se a API key está configurada
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            # Log erro em Postgres
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.VIDEO_GENERATION,
                    details={"prompt": prompt[:200], "duration_seconds": duration_seconds, "aspect_ratio": aspect_ratio},
                    status="error",
                    error_message="API key não configurada"
                )
            except Exception:
                pass
            return {
                "success": False,
                "message": "API key do Gemini não configurada. Configure a variável GEMINI_API_KEY."
            }
        
        # Configurar cliente Gemini
        client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=api_key,
        )
        
        # Configuração do vídeo
        video_config = types.GenerateVideosConfig(
            person_generation="dont_allow",  # Não permitir pessoas
            aspect_ratio=aspect_ratio,
            number_of_videos=1,
            duration_seconds=duration_seconds,
        )
        
        # Melhorar o prompt para ser mais descritivo
        enhanced_prompt = f"""
        Cria um vídeo educativo sobre: {prompt}
        
        Requisitos:
        - Estilo educativo e profissional
        - Visual limpo e moderno
        - Incluir elementos visuais relevantes
        - Texto claro e legível
        - Cores contrastantes para boa visibilidade
        - Animação suave e profissional
        """
        
        print(f"Iniciando geracao de video com Gemini Veo...")
        print(f"Prompt: {enhanced_prompt}")
        
        start_time = time.time()
        # Gerar vídeo
        operation = client.models.generate_videos(
            model="veo-2.0-generate-001",
            prompt=enhanced_prompt,
            config=video_config,
        )
        
        # Aguardar conclusão
        print("Aguardando geracao do video...")
        while not operation.done:
            print("Video ainda nao foi gerado. Verificando em 10 segundos...")
            time.sleep(10)
            operation = client.operations.get(operation)
        
        result = operation.result
        if not result:
            # Log erro em Postgres
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.VIDEO_GENERATION,
                    details={"prompt": prompt[:200], "duration_seconds": duration_seconds, "aspect_ratio": aspect_ratio},
                    status="error",
                    error_message="Resultado vazio do Gemini Veo"
                )
            except Exception:
                pass
            return {
                "success": False,
                "message": "Erro durante a geração do vídeo com Gemini Veo"
            }
        
        generated_videos = result.generated_videos
        if not generated_videos:
            # Log erro em Postgres
            try:
                postgres_logger.log_operation(
                    operation_type=OperationType.VIDEO_GENERATION,
                    details={"prompt": prompt[:200], "duration_seconds": duration_seconds, "aspect_ratio": aspect_ratio},
                    status="error",
                    error_message="Nenhum vídeo gerado"
                )
            except Exception:
                pass
            return {
                "success": False,
                "message": "Nenhum vídeo foi gerado pelo Gemini Veo"
            }
        
        # Baixar o vídeo gerado
        generated_video = generated_videos[0]
        video_filename = f"video_veo_{uuid.uuid4().hex[:8]}.mp4"
        
        print(f"Baixando video: {generated_video.video.uri}")
        client.files.download(file=generated_video.video)
        generated_video.video.save(video_filename)
        
        print(f"Video gerado com sucesso: {video_filename}")
        
        # Log sucesso em Postgres
        try:
            duration_ms = int((time.time() - start_time) * 1000)
            postgres_logger.log_operation(
                operation_type=OperationType.VIDEO_GENERATION,
                details={"prompt": prompt[:200], "duration_seconds": duration_seconds, "aspect_ratio": aspect_ratio, "video_path": video_filename, "generation_duration_ms": duration_ms},
                status="success",
                duration_ms=duration_ms
            )
            postgres_logger.update_operation_stats(OperationType.VIDEO_GENERATION.value, True, duration_ms)
        except Exception:
            pass
        
        return {
            "success": True,
            "video_path": video_filename,
            "message": f"Vídeo gerado com sucesso usando Gemini Veo: {video_filename}",
            "duration": duration_seconds
        }
        
    except Exception as e:
        error_msg = str(e)
        # Remover caracteres especiais que podem causar problemas de codificação
        error_msg = error_msg.encode('ascii', 'ignore').decode('ascii')
        # Log erro em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.VIDEO_GENERATION,
                details={"prompt": prompt[:200], "duration_seconds": duration_seconds, "aspect_ratio": aspect_ratio},
                status="error",
                error_message=error_msg
            )
        except Exception:
            pass
        return {
            "success": False,
            "message": f"Erro ao gerar video com Gemini Veo: {error_msg}"
        }

if __name__ == "__main__":
    mcp.run()
