from mcp.server.fastmcp import FastMCP
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter
try:
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    print("A usar langchain-chroma e langchain-huggingface (novos pacotes)")
except ImportError:
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import SentenceTransformerEmbeddings as HuggingFaceEmbeddings
    print("A usar langchain_community (pacotes antigos)")

from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv
from pathlib import Path
import requests
import httpx
import shutil
import gc

# Configuração do Moodle (edite conforme necessário)
MOODLE_URL = "http://localhost/webservice/rest/server.php"
MOODLE_TOKEN = "c27f3ee4c459f64400855077479f2d61"

# Load environment variables
load_dotenv()

# Set Gemini API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyDGxqunYqJmIgCS_sjRMkK7_9gS11c8Yw0"

# Directories
PDF_FOLDER = "pdfs"
DB_FOLDER = "rag_files"

# Create MCP server
mcp = FastMCP(name="RAG_pdf_Mul_Improved")

# Embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Load or create vectorstore
if os.path.exists(DB_FOLDER) and len(os.listdir(DB_FOLDER)) > 0:
    print("Loading existing vectorstore...")
    docsearch = Chroma(persist_directory=DB_FOLDER, embedding_function=embeddings)
else:
    print("Creating vectorstore from PDFs...")
    all_texts = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
    for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
        print(f"Loading {pdf_file.name}")
        loader = PyPDFLoader(str(pdf_file))
        data = loader.load()
        texts = text_splitter.split_documents(data)
        all_texts.extend(texts)

    docsearch = Chroma.from_documents(all_texts, embeddings, persist_directory=DB_FOLDER)
    print("Vectorstore created and saved.")

# Create retriever
retriever = docsearch.as_retriever(search_kwargs={"k": 5})

# Gemini model
model = GoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.4)

# Prompt template forcing Portuguese
custom_prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        "Responde sempre em português. Se não souber a resposta, diz claramente. "
        "Contexto: {context}\n\nPergunta: {question}\nResposta:"
    ),
)

# RetrievalQA
qa = RetrievalQA.from_chain_type(
    llm=model,
    chain_type="stuff",
    retriever=retriever,
    chain_type_kwargs={"prompt": custom_prompt}
)

@mcp.tool()
def retrieve(prompt: str) -> str:
    """Retrieve information using RAG"""
    try:
        result = qa.invoke({"query": prompt})
        return result.get("result", "Não foi possível obter uma resposta.")
    except Exception as e:
        return f"Erro ao processar a pergunta: {e}"




@mcp.tool()
def add_new_pdfs() -> str:
    """
    Adds new PDFs from the 'pdfs' directory to the existing vectorstore.
    """
    # Get existing metadata from the vectorstore
    existing_metadatas = docsearch.get(include=["metadatas"])["metadatas"]
    existing_sources = set()
    for meta_list in existing_metadatas:
        for meta in meta_list:
            if isinstance(meta, dict):
                source = meta.get('source')
                if source:
                    existing_sources.add(source)

    new_files_added = False
    for pdf_file in Path(PDF_FOLDER).glob("*.pdf"):
        file_path = str(pdf_file.resolve())
        if file_path not in existing_sources:
            print(f"Adding {pdf_file.name} to the vectorstore...")
            loader = PyPDFLoader(file_path)
            data = loader.load()
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            texts = text_splitter.split_documents(data)
            docsearch.add_documents(texts)
            new_files_added = True

    if new_files_added:
        docsearch.persist()
        return "New PDFs successfully added to the vectorstore."
    else:
        return "No new PDFs found to add."


@mcp.tool()
def download_and_add_pdf(file_url: str) -> str:
    """
    Downloads a PDF from a URL and adds it to the vectorstore (RAG).

    Args:
        file_url (str): Full URL to the PDF file (including authentication token).

    Returns:
        str: Success or error message.
    """
    try:
        # Fix PDF extension check
        url_path = file_url.lower().split("?")[0]
        if not url_path.endswith(".pdf"):
            return "The provided URL does not point to a PDF file."

        # Download the file
        response = requests.get(file_url)
        if response.status_code != 200:
            return f"Failed to download PDF: HTTP {response.status_code}"

        # Extract filename before '?'
        filename = url_path.split("/")[-1]
        pdf_path = Path(PDF_FOLDER) / filename
        with open(pdf_path, "wb") as f:
            f.write(response.content)
        print(f"File saved as {pdf_path}")

        # Load the PDF into the vectorstore
        loader = PyPDFLoader(str(pdf_path))
        data = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(data)
        docsearch.add_documents(texts)
        docsearch.persist()
        print(f"File {filename} added to the vectorstore.")

        return f"The file '{filename}' was successfully downloaded and added to the vectorstore."
    
    except Exception as e:
        print(f"Error: {e}")
        return f"An error occurred while processing the file: {e}"

    
@mcp.tool()
def get_courses_by_field(field: str, value: str) -> dict:
    """
    Searches for Moodle courses by a specific field and value.
    
    Required Arguments:
        field (str): The course field to search by. Common options include 'id', 'shortname', 'idnumber', or 'category' or "" to view all courses.
        value (str): The value to match for the specified field.
    Optional Arguments:
        None. All arguments are required.
    
    Returns:
        dict: A dictionary containing the list of matching courses or an error message. The response structure follows Moodle's 'core_course_get_courses_by_field' API.
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
    Downloads all PDFs from a Moodle course and updates the vectorstore (RAG).

    Args:
        course_fullname (str): Full name of the Moodle course.

    Returns:
        dict: Summary with downloaded files, skipped files, errors, and the RAG update result.
    """
    downloaded_files = []
    skipped_files = []
    failed_downloads = []

    # 1. Get the list of courses and search for the given fullname
    courses_resp = get_courses_by_field(field="", value="")

    if "error" in courses_resp:
        return {"error": f"Failed to fetch courses: {courses_resp['error']}"}

    courses = courses_resp.get("courses", [])
    course = next((c for c in courses if c.get("fullname") == course_fullname), None)

    if not course:
        return {"error": f"Course with name '{course_fullname}' not found."}

    courseid = course["id"]

    # 2. Get course contents
    params = {
        "wstoken": MOODLE_TOKEN,
        "wsfunction": "core_course_get_contents",
        "moodlewsrestformat": "json",
        "courseid": courseid
    }

    try:
        response = httpx.get(MOODLE_URL, params=params, timeout=30.0)
        response.raise_for_status()
        contents = response.json()
    except Exception as e:
        return {"error": f"Failed to fetch course contents: {str(e)}"}

    # 3. Search for and download PDFs
    for section in contents:
        for module in section.get("modules", []):
            if module.get("modname") == "resource":
                for item in module.get("contents", []):
                    if item.get("type") == "file" and item.get("filename", "").lower().endswith(".pdf"):
                        file_name = item["filename"]
                        file_path = Path(PDF_FOLDER) / file_name

                        # Check if file already exists
                        if file_path.exists():
                            skipped_files.append(file_name)
                            continue

                        # Build the download URL with token
                        file_url = item["fileurl"]
                        separator = "&" if "?" in file_url else "?"
                        download_url = f"{file_url}{separator}token={MOODLE_TOKEN}"

                        try:
                            file_response = httpx.get(download_url, timeout=60.0)
                            file_response.raise_for_status()

                            with open(file_path, "wb") as f:
                                f.write(file_response.content)
                            downloaded_files.append(file_name)
                        except Exception as e:
                            failed_downloads.append({"filename": file_name, "error": str(e)})

    # 4. Update the RAG using the existing tool
    rag_result = add_new_pdfs()

    # 5. Build the response
    return {
        "course": course_fullname,
        "pdfs_downloaded": downloaded_files,
        "pdfs_skipped": skipped_files,
        "pdfs_failed": failed_downloads,
        "rag_result": rag_result
    }

@mcp.tool()
def download_pdfs_from_all_courses() -> dict:
    """
    Downloads all PDFs from all Moodle courses and updates the vectorstore (RAG).

    Returns:
        dict: Summary with downloaded files, skipped files, errors, and the RAG update result.
    """
    summary = {
        "courses_processed": 0,
        "total_pdfs_downloaded": 0,
        "total_pdfs_skipped": 0,
        "total_pdfs_failed": 0,
        "details": []
    }

    # 1. Get all courses
    courses_resp = get_courses_by_field(field="", value="")

    if "error" in courses_resp:
        return {"error": f"Failed to fetch courses: {courses_resp['error']}"}

    courses = courses_resp.get("courses", [])
    summary["courses_processed"] = len(courses)

    # 2. Process each course
    for course in courses:
        course_fullname = course.get("fullname")
        courseid = course.get("id")

        course_result = {
            "course": course_fullname,
            "pdfs_downloaded": [],
            "pdfs_skipped": [],
            "pdfs_failed": []
        }

        # Fetch course contents
        params = {
            "wstoken": MOODLE_TOKEN,
            "wsfunction": "core_course_get_contents",
            "moodlewsrestformat": "json",
            "courseid": courseid
        }

        try:
            response = httpx.get(MOODLE_URL, params=params, timeout=30.0)
            response.raise_for_status()
            contents = response.json()
        except Exception as e:
            course_result["error"] = f"Failed to fetch course contents: {str(e)}"
            summary["details"].append(course_result)
            continue

        # Search for and download PDFs
        for section in contents:
            for module in section.get("modules", []):
                if module.get("modname") == "resource":
                    for item in module.get("contents", []):
                        if item.get("type") == "file" and item.get("filename", "").lower().endswith(".pdf"):
                            file_name = item["filename"]
                            file_path = Path(PDF_FOLDER) / file_name

                            if file_path.exists():
                                course_result["pdfs_skipped"].append(file_name)
                                summary["total_pdfs_skipped"] += 1
                                continue

                            file_url = item["fileurl"]
                            separator = "&" if "?" in file_url else "?"
                            download_url = f"{file_url}{separator}token={MOODLE_TOKEN}"

                            try:
                                file_response = httpx.get(download_url, timeout=60.0)
                                file_response.raise_for_status()

                                with open(file_path, "wb") as f:
                                    f.write(file_response.content)

                                course_result["pdfs_downloaded"].append(file_name)
                                summary["total_pdfs_downloaded"] += 1
                            except Exception as e:
                                course_result["pdfs_failed"].append({
                                    "filename": file_name,
                                    "error": str(e)
                                })
                                summary["total_pdfs_failed"] += 1

        summary["details"].append(course_result)

    # 3. Update the RAG using the existing tool
    rag_result = add_new_pdfs()

    summary["rag_update_result"] = rag_result
    return summary


@mcp.tool()
def clear_rag() -> str:
    """
    Deletes the entire vectorstore (RAG) directory if it exists.
    """
    try:
        if os.path.exists(DB_FOLDER):
            shutil.rmtree(DB_FOLDER)
            print(f"Deleted vectorstore directory: {DB_FOLDER}")
            return "Vectorstore (RAG) has been successfully cleared."
        else:
            return "Vectorstore directory does not exist. Nothing to clear."
    except Exception as e:
        print(f"Error while deleting vectorstore: {e}")
        return f"Failed to clear the vectorstore: {e}"


if __name__ == "__main__":
    mcp.run()
