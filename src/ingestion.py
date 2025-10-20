import os
import yaml # To parse the OpenAPI YAML file
from dotenv import load_dotenv

# --- LangChain Components ---
# Document Loaders for different file types
from langchain_community.document_loaders import TextLoader, DirectoryLoader
# Text Splitter for chunking documents
from langchain.text_splitter import RecursiveCharacterTextSplitter
# Google's Embedding Model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
# Vector Store (ChromaDB)
from langchain_community.vectorstores import Chroma

# --- Configuration ---
# Load API Key from .env file
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file. Please add it.")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY # Ensure environment variable is set for LangChain

# Define paths
DOCS_PATH = "../docs" # Path to your documentation folder (relative to this script)
CHROMA_PERSIST_DIR = "../chroma_db" # Where to save the vector database

# --- Helper Function for OpenAPI/YAML ---
def load_openapi_spec_to_text(file_path):
    """Loads an OpenAPI YAML file and converts relevant parts to text."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading or parsing YAML file {file_path}: {e}")
        return None

    # Extract key information into a text format RAG can understand
    text_content = ""
    info = spec.get('info', {})
    text_content += f"# API Title: {info.get('title', 'N/A')}\n\n"
    text_content += f"## Description:\n{info.get('description', 'No description provided.')}\n\n"

    paths = spec.get('paths', {})
    text_content += "## API Endpoints:\n\n"
    for path, methods in paths.items():
        for method, details in methods.items():
            text_content += f"### {method.upper()} {path}\n"
            text_content += f"Summary: {details.get('summary', 'No summary')}\n"
            # Add more details as needed (parameters, responses, etc.)
            # For simplicity, we keep it concise here. In production, you'd extract more.
            text_content += "---\n" # Separator

    return text_content


# --- Main Ingestion Function ---
def ingest_documents():
    """Loads, splits, embeds, and stores documents in ChromaDB."""
    print("Starting document ingestion...")

    # 1. Load Documents
    print(f"Loading documents from: {DOCS_PATH}")
    markdown_loader = DirectoryLoader(DOCS_PATH, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'}, recursive=True)
    md_docs = markdown_loader.load()
    print(f"Loaded {len(md_docs)} Markdown documents.")

    # Load and process the OpenAPI YAML file separately
    openapi_file = os.path.join(DOCS_PATH, "openapi.yaml")
    openapi_text = load_openapi_spec_to_text(openapi_file)
    openapi_docs = []
    if openapi_text:
        # Create a LangChain Document object for the processed YAML content
        from langchain_core.documents import Document
        openapi_docs = [Document(page_content=openapi_text, metadata={"source": "openapi.yaml"})]
        print("Loaded and processed OpenAPI spec.")
    else:
        print("Skipping OpenAPI spec due to loading error.")

    all_docs = md_docs + openapi_docs
    if not all_docs:
        print("No documents loaded. Exiting.")
        return

    # 2. Split Documents into Chunks
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, # Max characters per chunk
        chunk_overlap=100  # Characters overlap between chunks
    )
    chunks = text_splitter.split_documents(all_docs)
    print(f"Split documents into {len(chunks)} chunks.")

    # 3. Initialize Embedding Model
    print("Initializing embedding model (models/text-embedding-004)...")
    embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

    # 4. Create or Load Vector Store (ChromaDB) and Add Chunks
    print(f"Creating/updating vector store at: {CHROMA_PERSIST_DIR}")
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=CHROMA_PERSIST_DIR # Save to this directory
    )

    # Persist the database to disk
    vector_store.persist()
    print("Vector store created and data persisted.")
    print("--- Ingestion Complete ---")

# --- Run the Ingestion ---
if __name__ == "__main__":
    ingest_documents()