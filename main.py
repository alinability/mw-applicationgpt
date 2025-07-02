import os
import sys

# Stelle sicher, dass das Verzeichnis "app" im Pfad ist
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

# Flexibler Import für beide Umgebungen (Notebook vs Docker-Ausführung)
try:
    from app.input_manager import (
        find_csv_and_pdf_files,
        load_resume_data,
        extract_clean_text_from_pdf,
        reduce_pdf_to_essentials,
    )
    from app.rag_manager import (
        create_collection,
        add_dataframe_to_chroma,
        query_relevant_entries,
    )
    from app.openai_client import (
        ask_chatgpt_single_prompt,
        build_prompt,
    )
except ImportError:
    from input_manager import (
        find_csv_and_pdf_files,
        load_resume_data,
        extract_clean_text_from_pdf,
        reduce_pdf_to_essentials,
    )
    from rag_manager import (
        create_collection,
        add_dataframe_to_chroma,
        query_relevant_entries,
    )
    from openai_client import (
        ask_chatgpt_single_prompt,
        build_prompt,
    )

INPUT_FOLDER = "data/input"

def main():
    # Suche nach Dateien
    csv_files, pdf_files = find_csv_and_pdf_files(INPUT_FOLDER)

    if not csv_files:
        print("⚠️ Keine CSV-Dateien gefunden.")
        return

    if not pdf_files:
        print("⚠️ Keine PDF-Dateien gefunden.")
        return

    # Verwende nur die erste PDF für das Stellenprofil
    pdf_path = pdf_files[0]
    pdf_text = extract_clean_text_from_pdf(pdf_path)
    reduced_text = reduce_pdf_to_essentials(pdf_text)

    # Erstelle oder hole Collection
    collection = create_collection(name="bewerbung")

    # Füge CSV-Dateien ins RAG ein
    for csv_path in csv_files:
        df = load_resume_data(csv_path)
        add_dataframe_to_chroma(df, collection, source_id=os.path.basename(csv_path))

    print("✅ PDF und CSV-Dateien erfolgreich verarbeitet und ins RAG eingefügt.")

    # Relevante Berufserfahrungen abfragen
    retrieved_docs = query_relevant_entries(collection, reduced_text, n_results=5)

    # Prompt generieren
    final_prompt = build_prompt(reduced_text, retrieved_docs)

    #print("\n📨 Finaler Prompt zur Übergabe an ChatGPT:")
    #print(final_prompt)

    # Anfrage an ChatGPT senden
    #print("\n🤖 Sende Prompt an ChatGPT...")
    response = ask_chatgpt_single_prompt(final_prompt)

    print("\n🎯 Antwort von ChatGPT:")
    print(response)