# rag_manager.py

import chromadb.telemetry
# ─── Telemetrie-Events unterdrücken ─────────────────────────────────────────────
chromadb.telemetry.capture = lambda *args, **kwargs: None

import os
import pandas as pd
from chromadb.config import Settings
from chromadb import PersistentClient
from chromadb.api.models import Collection
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Standard-Persistenzverzeichnis
persist_dir = "./data/chroma"

def init_chroma_db(persist_directory: str = persist_dir) -> PersistentClient:
    """
    Initialisiert oder lädt die Chroma-Datenbank aus dem persistierten Verzeichnis.
    """
    if not os.path.exists(persist_directory):
        os.makedirs(persist_directory)
        print("🆕 Chroma-Verzeichnis erstellt.")
    else:
        print("📂 Chroma-Verzeichnis gefunden. Vorhandene Daten werden geladen.")
    settings = Settings(anonymized_telemetry=False)
    return PersistentClient(path=persist_directory, settings=settings)

def get_collection(client, name: str = "experience_db", embedding_function=None) -> Collection:
    """
    Gibt die gewünschte Collection zurück, legt sie ggf. an.
    """
    if embedding_function is None:
        embedding_function = OpenAIEmbeddingFunction()
    return client.get_or_create_collection(name=name, embedding_function=embedding_function)

def add_dataframe_to_chroma(df: pd.DataFrame, collection, source_id: str = "resume") -> None:
    """
    Fügt Zeilen eines DataFrame als Dokumente zur Collection hinzu, prüft auf Duplikate.
    """
    documents, metadatas, ids = [], [], []
    existing = collection.get(include=["documents"])
    existing_ids = set(existing.get("ids", []))
    existing_docs = set(doc.strip() for doc in existing.get("documents", []))

    for i, row in df.iterrows():
        text = row.get("Erfahrung", "")
        if not text or not isinstance(text, str):
            continue
        cleaned_text = text.strip()
        uid = f"{source_id}_{i}"
        if uid in existing_ids or cleaned_text in existing_docs:
            print(f"⚠️ Überspringe Duplikat: {uid}")
            continue
        documents.append(cleaned_text)
        metadatas.append({"source": source_id})
        ids.append(uid)

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ {len(documents)} neue Dokumente zur Collection hinzugefügt.")
    else:
        print("⚠️ Keine neuen Dokumente hinzugefügt (alle bereits vorhanden?).")

def create_openai_embedding_function() -> OpenAIEmbeddingFunction:
    """
    Erstellt eine OpenAIEmbeddingFunction unter Verwendung des API-Keys aus der Umgebung.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("❌ Kein OpenAI API-Key gefunden. Bitte .env prüfen.")
    return OpenAIEmbeddingFunction(api_key=api_key)

def create_collection(name: str = "bewerbung",
                      persist_directory: str = persist_dir) -> Collection:
    """
    Erzeugt oder lädt die Collection mit ausgeschalteter Telemetrie.
    """
    client = init_chroma_db(persist_directory)
    embedding_function = create_openai_embedding_function()
    return get_collection(client, name=name, embedding_function=embedding_function)

def query_relevant_entries(collection,
                           query_text: str,
                           n_results: int = 5) -> list[str]:
    """
    Fragt die Chroma-Collection nach den relevantesten Dokumenten zur gegebenen Anfrage ab.
    """
    results = collection.query(query_texts=[query_text], n_results=n_results)
    docs = results.get("documents", [[]])[0]
    unique_docs = list(dict.fromkeys(doc.strip() for doc in docs if doc.strip()))
    return unique_docs