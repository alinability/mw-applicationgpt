#!/usr/bin/env python3

import os
import sys

class TelemetryStderrFilter:
    def __init__(self, stderr):
        self.stderr = stderr

    def write(self, data):
        # alle Telemetrie-Fehlerzeilen überspringen
        if "Failed to send telemetry event" in data:
            return
        self.stderr.write(data)

    def flush(self):
        self.stderr.flush()

# sys.stderr umschalten
sys.stderr = TelemetryStderrFilter(sys.stderr)

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
    from app.html_generator import generate_kurzprofil_html
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
    from html_generator import generate_kurzprofil_html

INPUT_FOLDER = "input"
PERSIST_DIRECTORY = "data/chroma"

def main():
    # 1. Dateien finden
    csv_files, pdf_files = find_csv_and_pdf_files(INPUT_FOLDER)
    if not csv_files:
        print("⚠️ Keine CSV-Dateien gefunden.")
        return
    if not pdf_files:
        print("⚠️ Keine PDF-Dateien gefunden.")
        return

    # 2. Chroma-Collection erzeugen (Telemetrie ausgeschaltet in rag_manager)
    collection = create_collection(
    name="bewerbung",
    persist_directory=PERSIST_DIRECTORY
)

    # 3. CSVs ins RAG laden
    for csv_path in csv_files:
        df = load_resume_data(csv_path)
        # old signature: df, collection, source_id
        add_dataframe_to_chroma(df, collection, source_id=os.path.basename(csv_path))
    
    print("✅ PDF und CSV-Dateien erfolgreich verarbeitet und ins RAG eingefügt.")

    # 4. PDF-Text extrahieren und reduzieren
    for pdf_path in pdf_files:
        job_title = pdf_path.split('/')[-1].replace('.pdf','')
        pdf_text = extract_clean_text_from_pdf(pdf_path)
        reduced_text = reduce_pdf_to_essentials(pdf_text)

        # 5. Relevante Einträge abfragen
        retrieved_docs = query_relevant_entries(
            collection=collection,
            query_text=reduced_text,
            n_results=5
        )

        # 6. Prompt bauen und an ChatGPT senden
        final_prompt = build_prompt(reduced_text, retrieved_docs)
        response = ask_chatgpt_single_prompt(final_prompt)

        # 7. Statische Profildaten
        static_info = {
            "name": "Marcel Russ",
            "title": "Teamleiter Mobile & Web",
            "skills": "Agile Softwareentwicklung, Teamführung, Mobile & Web, Nearshore-Management",
            "languages": "Deutsch (Muttersprache), Englisch (verhandlungssicher)"
        }
        
        # 8. ChatGPT-Response parsen und HTML generieren
        
        generate_kurzprofil_html(
        static_info=static_info,
        experiences=response,
        template_path="app/templates",
        output_dir="output",
        job_title = job_title
    )

if __name__ == "__main__":
    main()