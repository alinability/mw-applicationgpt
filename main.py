#!/usr/bin/env python3

import os
import sys
from collections import OrderedDict

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
        process_pdf,
    )
    from app.rag_manager import (
        csv_to_db,
        get_docs,
    )
    from app.openai_client import (
        get_response,
    )
    from app.html_generator import generate_kurzprofil_html
    from app.prompt_utils import save_references_to_txt
except ImportError:
    from input_manager import (
        find_csv_and_pdf_files,
        process_pdf,
    )
    from rag_manager import (
        csv_to_db,
        get_docs,
    )
    from openai_client import (
        get_response,
    )
    from html_generator import generate_kurzprofil_html
    from prompt_utils import save_references_to_txt

# Versuch 1: Lokale Docker-Struktur
try:
    # Wir vermuten, dass “input/” existiert, wenn wir im Container sind
    if not os.path.isdir("input"):
        raise FileNotFoundError
    INPUT_FOLDER = "input"
    PERSIST_DIRECTORY = "chroma"
    TEMPLATE_PATH = "app/templates"
except FileNotFoundError:
    INPUT_FOLDER = "../input"
    PERSIST_DIRECTORY = "../chroma"
    TEMPLATE_PATH = "../app/templates"

def main():
    # 1. Dateien finden
    candidate_profiles, job_postings = find_csv_and_pdf_files(INPUT_FOLDER) 
    if not candidate_profiles:
        print("⚠️ Keine CSV-Dateien gefunden.")
        return
    if not job_postings:
        print("⚠️ Keine PDF-Dateien gefunden.")
        return

    # 2. Chroma-Collection erzeugen oder laden
    new_data = True # Ändern, fals neue Erfarungen aus der csv eingelesen werden sollen. 
    collection, _ = csv_to_db(candidate_profiles, PERSIST_DIRECTORY, new_data)

    # 3. Für jede PDF-Stellenanzeige
    for pdf_path in job_postings:
        job_title = os.path.basename(pdf_path).replace(".pdf", "")
        print(f"📨 Bearbeite Stellenanzeige: {job_title}")

        # 3.a PDF-Text extrahieren und reduzieren
        reduced_text = process_pdf(pdf_path) 
    
        # 3.b Daten aus dem RAG abrufen
        retrieved_docs = get_docs(collection, reduced_text)
        if retrieved_docs == False:
            break
        
        # 3.c Antwort bei ChatGPT abfragen 
        response = get_response(reduced_text, retrieved_docs)
        if response == False:
            break
            
        # nachdem Du reduced_text und retrieved_docs hast:
        save_references_to_txt(pdf_path, reduced_text, retrieved_docs, response, output_dir="output")
        
        # 3.d Statische Profildaten definieren
        #ToDo: Diese Daten tatäschlich aus dem Mittarbeiterprofil ziehen!
        static_info = {
            "name": "Marcel Russ",
            "title": "Teamleiter Mobile & Web",
            "skills": "Agile Softwareentwicklung, Teamführung, Mobile & Web, Nearshore-Management",
            "languages": "Deutsch (Muttersprache), Englisch (verhandlungssicher)"
        }

        # 3.e Kurzprofil HTML erzeugen
        generate_kurzprofil_html(
            static_info=static_info,
            experiences=response,
            template_path=TEMPLATE_PATH,
            output_dir="output",
            job_title=job_title
        )

if __name__ == "__main__":
    main()
