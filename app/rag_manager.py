from chromadb import PersistentClient
from chromadb import Collection
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import os
from typing import Any
import pandas as pd
import uuid

persist_dir = "./data/chroma"

def init_chroma_db(persist_directory: str = persist_dir) -> PersistentClient:
    """Initialisiert oder lädt die Chroma-Datenbank aus dem persistierten Verzeichnis."""
    if not os.path.exists(persist_directory):
        os.makedirs(persist_directory)
        print("🆕 Chroma-Verzeichnis erstellt.")
    else:
        print("📂 Chroma-Verzeichnis gefunden. Vorhandene Daten werden geladen.")
    return PersistentClient(path=persist_directory)

def get_collection(client, name: str = "experience_db"):
    """Gibt die gewünschte Collection zurück, legt sie ggf. an."""
    embedding_function = OpenAIEmbeddingFunction()
    return client.get_or_create_collection(name=name, embedding_function=embedding_function)

def add_dataframe_to_chroma(df: pd.DataFrame, collection: Collection, source_id: str = "default") -> None:
    """
    Fügt jede Zeile des DataFrames als Dokument in eine ChromaDB-Collection ein.
    """
    documents = []
    metadatas = []
    ids = []

    for idx, row in df.iterrows():
        # Füge z. B. alle Spalten als Text zusammen
        text = "\n".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
        documents.append(text)

        # Optionale Metadaten: z. B. Index oder Quelle
        metadatas.append({"row_index": idx, "source": source_id})
        ids.append(f"{source_id}_{uuid.uuid4()}")

    # Schreibe in ChromaDB
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    print(f"✅ {len(documents)} Dokumente zur Collection hinzugefügt.")