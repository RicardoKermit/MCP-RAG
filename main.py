from mcp.server.fastmcp import FastMCP
from langchain.chains import RetrievalQA
from langchain.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.document_loaders import TextLoader
from langchain_ollama.llms import OllamaLLM
from langchain.embeddings import OllamaEmbeddings

#Create MCP server
mcp = FastMCP(name="RAG")

embeddings = OllamaEmbeddings(model="nomic-embed-text:latest",base_url="http://127.0.0.1:11434")

model = OllamaLLM(model="qwen2.5",base_url="http://127.0.0.1:11434")

loader = TextLoader("dummy.txt")
data=loader.load()

#Document Transformer
text_splitter = CharacterTextSplitter(chunk_size=1000,chunk_overlap=0)
texts = text_splitter.split_documents(data)

#VectorDb
docsearch = Chroma.from_documents(texts,embeddings)

#RetrievalQA

qa = RetrievalQA.from_chain_type(llm=model,chain_type="stuff",retriever=docsearch.as_retriever())

@mcp.tool()
def retrive(prompt: str) -> str:
    """Get information using rag"""
    return qa.run(prompt)

if __name__ == "__main__":
    mcp.run()