import os
import json
import datetime
from pathlib import Path

# Tentativa de importação híbrida
try:
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    print(" Usar langchain-chroma e langchain-huggingface (novos pacotes)")
except ImportError:
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import SentenceTransformerEmbeddings as HuggingFaceEmbeddings
    print(" A usar langchain_community (pacotes antigos)")

from langchain.chains import RetrievalQA
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAI

# Configs
PDF_FOLDER = Path("pdfs")
ORIGINAL_DB_FOLDER = Path("rag_files_original")
REFINED_DB_FOLDER = Path("rag_files_refined")
RESULTS_FILE = Path(f"rag_test_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

# API Key (set your key)
os.environ["GOOGLE_API_KEY"] = "AIzaSyDGxqunYqJmIgCS_sjRMkK7_9gS11c8Yw0"

# Embeddings
original_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
refined_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Gemini models
original_model = GoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
refined_model = GoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.4)

def build_vectorstore(db_folder, splitter, embeddings):
    if db_folder.exists() and any(db_folder.iterdir()):
        print(f"[INFO] Loading vectorstore from {db_folder}")
        return Chroma(persist_directory=str(db_folder), embedding_function=embeddings)
    else:
        print(f"[INFO] Creating vectorstore at {db_folder}")
        all_texts = []
        for pdf_file in PDF_FOLDER.glob("*.pdf"):
            print(f"[INFO] Loading {pdf_file.name}")
            loader = PyPDFLoader(str(pdf_file))
            data = loader.load()
            texts = splitter.split_documents(data)
            all_texts.extend(texts)

        db = Chroma.from_documents(all_texts, embeddings, persist_directory=str(db_folder))
        print("[INFO] Vectorstore created and saved.")
        return db

# Original pipeline setup
original_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
original_docsearch = build_vectorstore(ORIGINAL_DB_FOLDER, original_splitter, original_embeddings)
original_retriever = original_docsearch.as_retriever()
original_qa = RetrievalQA.from_chain_type(llm=original_model, chain_type="stuff", retriever=original_retriever)

# Refined pipeline setup
refined_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
refined_docsearch = build_vectorstore(REFINED_DB_FOLDER, refined_splitter, refined_embeddings)
refined_retriever = refined_docsearch.as_retriever(search_kwargs={"k": 5})
refined_qa = RetrievalQA.from_chain_type(llm=refined_model, chain_type="stuff", retriever=refined_retriever)

# Test questions
test_questions = [
    {
        "pdf": "Introdução a Realidade Virtual e Aumentada",
        "question": "O que é Realidade Aumentada (RA) e como difere da Realidade Virtual (RV)?"
    },
    {
        "pdf": "Introdução a Realidade Virtual e Aumentada",
        "question": "Quais foram os principais avanços tecnológicos na VR/AR nos anos 2000?"
    },
    {
        "pdf": "Introdução a Realidade Virtual e Aumentada",
        "question": "Quais frameworks e engines são recomendados para desenvolver experiências VR/AR?"
    },
    {
        "pdf": "Scala_1",
        "question": "O que significa 'Scalable Language' em Scala?"
    },
    {
        "pdf": "Scala_1",
        "question": "Explique o conceito de funções parciais em Scala."
    },
    {
        "pdf": "Scala_1",
        "question": "Quais as diferenças entre variáveis val e var e como isso se relaciona com programação funcional?"
    }
]

# Run tests
results = []
for idx, test in enumerate(test_questions):
    q = test["question"]
    print(f"[TEST {idx+1}] Question: {q}")

    try:
        original_answer = original_qa.invoke({"query": q})["result"]
    except Exception as e:
        original_answer = f"Error: {e}"

    try:
        refined_answer = refined_qa.invoke({"query": q})["result"]
    except Exception as e:
        refined_answer = f"Error: {e}"

    results.append({
        "pdf": test["pdf"],
        "question": q,
        "original_answer": original_answer,
        "refined_answer": refined_answer,
        "original_length": len(original_answer.split()),
        "refined_length": len(refined_answer.split())
    })

    print("[✔] Test completed\n")

# Save results to JSON
with open(RESULTS_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4, ensure_ascii=False)

print(f"[] All tests completed. Results saved to {RESULTS_FILE}")

# Simple analysis
print("\n Analysis Summary:")
for idx, res in enumerate(results):
    print(f"\n--- Test {idx+1} ---")
    print(f"Question: {res['question']}")
    print(f"Original answer length: {res['original_length']} words")
    print(f"Refined answer length:  {res['refined_length']} words")
    if res['refined_length'] > res['original_length']:
        print(" Refined RAG gave a longer, possibly more detailed answer.")
    elif res['refined_length'] < res['original_length']:
        print(" Refined RAG gave a shorter answer (check for context loss).")
    else:
        print("ℹ Both answers have the same length (check quality manually).")
