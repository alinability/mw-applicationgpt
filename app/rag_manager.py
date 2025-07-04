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

from input_manager import load_resume_data

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
    Fügt jede Zeile des DataFrames als eigenes Dokument in die Chroma-Collection ein.
    Dabei wird der komplette Zeileninhalt (alle Spalten) zu einem Text zusammengeführt.
    """

    # Bereits in der Collection gespeicherte Dokumente holen
    existing = collection.get(include=["documents"])
    existing_docs = set(doc.strip() for doc in existing.get("documents", []))

    documents, metadatas, ids = [], [], []
    for idx, row in df.iterrows():
        # 1) Werte aller Spalten in Liste sammeln (wird übersprungen, falls NaN)
        parts = []
        for col in df.columns:
            val = row[col]
            if pd.notnull(val):
                text = str(val).strip()
                if text:
                    parts.append(text)

        # 2) Ganzen Zeilentext zusammenfügen
        full_text = " ".join(parts)
        if not full_text:
            continue

        uid = f"{source_id}_{idx}"
        # 3) Duplikat-Prüfung anhand des kompletten Textes
        if full_text in existing_docs:
            #print(f"⚠️ Überspringe Duplikat: {uid}")
            continue

        documents.append(full_text)
        metadatas.append({"source": source_id})
        ids.append(uid)

    # DEBUG: Was wird hinzugefügt?
    for doc in documents:
        snippet = doc.replace("\n", " ")
        print("  →", (snippet[:80] + "…") if len(snippet) > 80 else snippet)

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ {len(documents)} neue Dokumente zur Collection hinzugefügt.")
    else:
        print("⚠️ Keine neuen Dokumente hinzugefügt (alle bereits vorhanden?).")


def query_relevant_entries(collection, query: str, n_results: int = 5) -> list[str]:
    """
    Fragt die Chroma-Collection nach den relevantesten Dokumenten zur gegebenen Anfrage ab.
    """
    # DEBUG: Anzahl aller gespeicherten Dokumente
    all_objs = collection.get(include=["documents"])
    total = len(all_objs.get("documents", []))
    if total == 0:
        print("DEBUG: Collection ist leer, keine Abfrage möglich.")
        return []

    # eigentliche Suche
    results = collection.query(query_texts=[query], n_results=n_results)
    docs = results.get("documents", [[]])[0]
    unique_docs = list(dict.fromkeys(doc.strip() for doc in docs if doc.strip()))
    return unique_docs

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

def validate_retrieved_docs(docs):
    """
    Prüft, ob `docs` eine Liste mit genau drei nicht-leeren Strings ist.
    Gibt True zurück, wenn alles OK ist, sonst False.
    """
    # 1) Liste?
    if not isinstance(docs, list):
        return False

    # 2) Jeder Eintrag muss ein nicht-leerer String sein
    for entry in docs:
        if not isinstance(entry, str):
            return False
        if not entry.strip():
            return False

    return True

def csv_to_db(csv_files: list, persist_dir: str = persist_dir):
    # Chroma-Collection erzeugen
    collection = create_collection(
        name="bewerbung",
        persist_directory=persist_dir
    )

    # CSVs ins RAG laden
    for csv_path in csv_files:
        df = load_resume_data(csv_path)
        add_dataframe_to_chroma(
            df,
            collection,
            source_id=os.path.basename(csv_path)
        )
        print("✅ PDF und CSV-Dateien erfolgreich verarbeitet und ins RAG eingefügt.")
    return collection

def get_docs(collection: chromadb.api.models.Collection.Collection, reduced_text: str):
    quality_check_docs = False
    n = 0
    while quality_check_docs == False and n <= 2:
        # Relevante Einträge abfragen
        retrieved_docs = query_relevant_entries(
            collection=collection,
            query=reduced_text,
            n_results=5
        )  # rag_manager
        quality_check_docs = validate_retrieved_docs(retrieved_docs)
        n += 1
    
    if quality_check_docs == False:
        print("❌ Kein Daten aus der DB abrufbar.")
    
    return retrieved_docs
    
    