# ChromaDB vector store management for RAG
import os
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_CATALOGUE = "course_catalogue"
COLLECTION_UPLOADS = "student_uploads"


# Function to create the OpenAI embeddings model
def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model="text-embedding-3-small")


# Function to return the persistent course catalogue vector store
def get_catalogue_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_CATALOGUE,
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )


# Function to return the vector store for student-uploaded files
def get_upload_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_UPLOADS,
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )


# Function to add documents to a vector store
def add_documents(store: Chroma, docs: List[Document]):
    store.add_documents(docs)


# Function to run a similarity search and return top-k chunks
def similarity_search(store: Chroma, query: str, k: int = 5) -> List[Document]:
    return store.similarity_search(query, k=k)


# Function to build or rebuild the catalogue store from a list of documents
def build_catalogue_store(docs: List[Document]) -> Chroma:
    store = Chroma(
        collection_name=COLLECTION_CATALOGUE,
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )
    if docs:
        store.add_documents(docs)
    return store


# Function to wipe all documents from the upload collection
def clear_upload_store():
    store = get_upload_store()
    store.reset_collection()


# Function to return a LangChain retriever from a store, with optional metadata filter
def get_retriever(store: Chroma, k: int = 5, filter: Optional[dict] = None):
    search_kwargs: dict = {"k": k}
    if filter:
        search_kwargs["filter"] = filter
    return store.as_retriever(search_kwargs=search_kwargs)
