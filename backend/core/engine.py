import os
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    ServiceContext,
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.llama_cpp import LlamaCPP
from llama_index.llms.llama_cpp.llama_utils import (
    messages_to_prompt,
    completion_to_prompt,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

# --- Configuration ---
MODEL_PATH = "./models"  # Folder for LLaMA GGUF model
DOCUMENTS_PATH = "./documents"  # Folder for your PDF
VECTOR_STORE_PATH = "./vector_store"  # Folder for the vector database
EMBED_MODEL_ID = "BAAI/bge-small-en-v1.5"

def get_chat_engine():
    """Initializes and returns a chat engine for the chatbot."""

    # Find the LLaMA model file
    try:
        model_file = [f for f in os.listdir(MODEL_PATH) if f.endswith(".gguf")][0]
        model_url = os.path.join(MODEL_PATH, model_file)
    except IndexError:
        raise FileNotFoundError(f"No GGUF model file found in the '{MODEL_PATH}' directory.")

    # Initialize the LLaMA CPP model
    llm = LlamaCPP(
        model_url=model_url,
        model_path=None,
        temperature=0.1,
        max_new_tokens=2048,
        context_window=3900,
        generate_kwargs={},
        model_kwargs={"n_gpu_layers": -1},  # Offload all layers to GPU if available
        messages_to_prompt=messages_to_prompt,
        completion_to_prompt=completion_to_prompt,
        verbose=True,
    )

    # Initialize the embedding model
    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_ID)

    # Initialize the ChromaDB vector store
    db = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    chroma_collection = db.get_or_create_collection("pdf_chatbot_store")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    service_context = ServiceContext.from_defaults(
        llm=llm, embed_model=embed_model, chunk_size=1024
    )

    # Check if the vector store is empty to decide whether to load documents
    if chroma_collection.count() == 0:
        print("Vector store is empty. Loading and indexing documents...")
        if not os.path.exists(DOCUMENTS_PATH) or not os.listdir(DOCUMENTS_PATH):
             raise FileNotFoundError(f"No documents found in the '{DOCUMENTS_PATH}' directory. Please add your PDF.")
        
        # Load documents from the specified path
        documents = SimpleDirectoryReader(DOCUMENTS_PATH).load_data()
        
        # Create the index and persist it
        index = VectorStoreIndex.from_documents(
            documents, service_context=service_context, storage_context=storage_context
        )
        print("Documents indexed successfully.")
    else:
        print("Loading existing index from vector store...")
        index = VectorStoreIndex.from_vector_store(
            vector_store, service_context=service_context
        )
        print("Index loaded successfully.")

    # Create the chat engine with a specific system prompt
    chat_engine = index.as_chat_engine(
        chat_mode="context",
        system_prompt=(
            "You are a helpful and expert Q&A assistant. Your goal is to answer questions "
            "as accurately as possible, based ONLY on the text provided in the context. "
            "If the context does not contain the answer, you MUST state that you cannot find the answer in the document. "
            "Do not use any outside knowledge."
        ),
    )

    return chat_engine
