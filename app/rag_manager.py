from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chromadb.api.models import Collection
import os
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

def get_collection(client, name: str = "experience_db", embedding_function=None):
    """
    Gibt die gewünschte Collection zurück, legt sie ggf. an.
    Optional: eigene Embedding-Funktion übergeben.
    """
    if embedding_function is None:
        embedding_function = OpenAIEmbeddingFunction()
    return client.get_or_create_collection(name=name, embedding_function=embedding_function)

def add_dataframe_to_chroma(df: pd.DataFrame, collection, source_id: str = "resume") -> None:
    documents, metadatas, ids = [], [], []

    # Bestehende IDs laden
    existing_ids = set(collection.get(include=["documents"])["ids"])

    for i, row in df.iterrows():
        text = row.get("Erfahrung", "")
        if not text or not isinstance(text, str):
            continue

        uid = f"{source_id}_{i}"
        if uid in existing_ids:
            print(f"⚠️ Überspringe Duplikat: {uid}")
            continue

        documents.append(text.strip())
        metadatas.append({"source": source_id})
        ids.append(uid)

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ {len(documents)} neue Dokumente zur Collection hinzugefügt.")
    else:
        print("⚠️ Keine neuen Dokumente hinzugefügt (alle bereits vorhanden?).")

def create_collection(name: str = "bewerbung") -> Collection:
    db = init_chroma_db()
    embedding_function = create_openai_embedding_function()
    return get_collection(db, name=name, embedding_function=embedding_function)

def create_openai_embedding_function() -> OpenAIEmbeddingFunction:
    """
    Erstellt eine OpenAIEmbeddingFunction unter Verwendung des API-Keys aus der Umgebung.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("❌ Kein OpenAI API-Key gefunden. Bitte .env prüfen.")
    return OpenAIEmbeddingFunction(api_key=api_key)

def query_relevant_entries(collection, query: str, n_results: int = 5) -> list[str]:
    """
    Fragt die Chroma-Collection nach den relevantesten Dokumenten zur gegebenen Anfrage ab.

    Args:
        collection: Die ChromaDB-Collection.
        query: Die Textanfrage (z. B. Stellenanzeige).
        n_results: Anzahl der zurückgegebenen Ergebnisse.

    Returns:
        Eine Liste relevanter Dokument-Texte (Strings).
    """
    results = collection.query(query_texts=[query], n_results=n_results)
    return results.get("documents", [[]])[0] #ToDo: Anpassen für mehrere Ausschreibungen auf einmal. 