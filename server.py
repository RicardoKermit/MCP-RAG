from mcp.server.fastmcp import FastMCP
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.embeddings import SentenceTransformerEmbeddings  # Para embeddings locais
import os
from dotenv import load_dotenv

# 1. Configurar chave da API Gemini (diretamente no Python)
os.environ["GOOGLE_API_KEY"] = "AIzaSyDGxqunYqJmIgCS_sjRMkK7_9gS11c8Yw0"

# Criar MCP server
mcp = FastMCP(name="RAG")

# Carregar dados
loader = TextLoader("dummy.txt")
data = loader.load()

# Document Transformer
text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
texts = text_splitter.split_documents(data)

# Embeddings (podes trocar por outros se quiseres)
embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

# VectorDb
docsearch = Chroma.from_documents(texts, embeddings,persist_directory="db")
retriever = docsearch.as_retriever()

# Modelo LLM com Gemini
model = GoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)


# RetrievalQA
qa = RetrievalQA.from_chain_type(llm=model, chain_type="stuff", retriever=retriever)

@mcp.tool()
def retrive(prompt: str) -> str:
    """Get information using RAG"""
    return qa.run(prompt)

if __name__ == "__main__":
    mcp.run()
