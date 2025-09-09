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
import uuid
import tempfile
from typing import List
import time
from datetime import datetime
import logging

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
        return f"Modelo alterado para {GEMINI_MODELS[model_name]['name']}"
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
    Retorna informações sobre o modelo Gemini atual e lista todos os modelos disponíveis.
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
    Adiciona novos PDFs da pasta 'pdfs' ao vectorstore (Qdrant).
    """
    existing_ids = set([d.metadata.get("source") for d in docsearch.similarity_search("", k=1000)])
    new_files_added = False
    added_count = 0
    for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
        file_path = str(pdf_file.resolve())
        if file_path not in existing_ids:
            loader = PyPDFLoader(file_path)
            data = loader.load()
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            texts = text_splitter.split_documents(data)
            docsearch.add_documents(texts)
            new_files_added = True
            added_count += 1
    msg = "PDFs adicionados." if new_files_added else "Nenhum PDF novo para adicionar."
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
    Faz download de um PDF a partir de uma URL e adiciona-o ao vectorstore.
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
        loader = PyPDFLoader(str(pdf_path))
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
    Busca cursos no Moodle usando critérios específicos.
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
    Faz download de todos os PDFs de um curso específico do Moodle.
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
    Limpa completamente o vectorstore (Qdrant) removendo todos os documentos.
    """
    try:
        client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
        # Log sucesso em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SYSTEM_MAINTENANCE,
                details={"operation": "clear_rag", "collection": QDRANT_COLLECTION_NAME},
                status="success"
            )
        except Exception:
            pass
        return "Vectorstore (Qdrant) limpo."
    except Exception as e:
        # Log erro em Postgres
        try:
            postgres_logger.log_operation(
                operation_type=OperationType.SYSTEM_MAINTENANCE,
                details={"operation": "clear_rag", "collection": QDRANT_COLLECTION_NAME},
                status="error",
                error_message=str(e)
            )
        except Exception:
            pass
        return f"Erro ao apagar vectorstore: {e}"

@mcp.tool()
def generate_quiz_with_difficulty(topic: str, num_questions: int = 5, difficulty: str = "mixed") -> dict:
    """
    Gera questionários com validação de dificuldade baseados no conteúdo dos PDFs.
    """
    start_time = time.time()
    try:
        # Log da operação
        logger.info(f"QUIZ_GENERATION | Topic: {topic} | Questions: {num_questions} | Difficulty: {difficulty} | Starting")
        
        # 1. Buscar conteúdo sobre o tópico
        difficulty_prompt = f"""
        Gera {num_questions} perguntas sobre {topic} com dificuldade {difficulty}.
        
        IMPORTANTE:
        - Usa apenas informação dos PDFs disponíveis
        - Gera APENAS o tipo de pergunta solicitado (escolha múltipla OU verdadeiro/falso)
        - Para escolha múltipla: cada pergunta deve ter 4 opções (a, b, c, d)
        - Para verdadeiro/falso: cada pergunta deve ter 2 opções (a) Verdadeiro, b) Falso)
        - Indica sempre a resposta correta
        - Formato: Pergunta + opções + "Resposta: X"
        - Dificuldade {difficulty}: ajusta complexidade das perguntas
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
def generate_video_with_veo(prompt: str, duration_seconds: int = 8, aspect_ratio: str = "16:9") -> dict:
    """
    Gera vídeo usando Gemini Veo (IA generativa de vídeo).
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
