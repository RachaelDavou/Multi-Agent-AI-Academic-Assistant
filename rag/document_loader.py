# Document loading utilities — supports PDF, DOCX, and TXT files
import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Chunk settings for splitting documents before embedding
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# Function to load a single file and return split Document chunks
def load_file(file_path: str, source_label: str = "") -> List[Document]:
    path = Path(file_path)
    ext = path.suffix.lower()
    label = source_label or path.name

    # Pick the right loader based on file extension
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext in (".docx", ".doc"):
        loader = Docx2txtLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    raw_docs = loader.load()

    # Tag each chunk with the source label for metadata filtering later
    for doc in raw_docs:
        doc.metadata["source"] = label
        doc.metadata["file_name"] = path.name

    return _splitter.split_documents(raw_docs)


# Function to load all supported files from a directory
def load_directory(directory: str) -> List[Document]:
    docs = []
    supported = {".pdf", ".docx", ".doc", ".txt"}
    for file_path in Path(directory).rglob("*"):
        if file_path.suffix.lower() in supported:
            try:
                docs.extend(load_file(str(file_path)))
            except Exception as e:
                print(f"Warning: could not load {file_path.name}: {e}")
    return docs
