MW ApplicationGPT

Eine command-line Anwendung, die mithilfe von RAG (Retrieval-Augmented Generation) und OpenAI-ChatGPT automatisiert Kurzprofile erstellt.

Features
	•	Liest ausschließlich CSV- und PDF-Dateien aus dem input-Verzeichnis ein.
	•	Verarbeitet Lebenslauf-Daten aus CSVs und Stellenbeschreibungen aus PDFs.
	•	Legt die CSV-Daten in eine ChromaDB-Collection (RAG) ab.
	•	Fragt relevante Berufserfahrungen zur Stellenanzeige ab.
	•	Nutzt ChatGPT, um die Top-3 Berufserfahrungen auszuwählen und in HTML-Format zu bringen.
	•	Generiert ein HTML-Kurzprofil mit statischen Profildaten und den ausgewählten Erfahrungen.

Voraussetzungen
	•	Python 3.11+
	•	Ein gültiger OPENAI_API_KEY in der .env-Datei
	•	Docker & Docker Compose (optional, für Container-Betrieb)

Installation
	1.	Repository klonen und ins Verzeichnis wechseln:

git clone <repo-url>
cd mw-applicationgpt


	2.	Virtuelle Umgebung erstellen und aktivieren:

python3 -m venv .venv
source .venv/bin/activate


	3.	Abhängigkeiten installieren:

pip install -r requirements.txt


	4.	Kopiere .env.example nach .env und trage deinen OpenAI-API-Key ein:

cp .env.example .env
# dann .env mit EDITOR öffnen und OPENAI_API_KEY setzen



Konfiguration
	•	INPUT_FOLDER: Standardmäßig input (nur CSV- und PDF-Dateien).
	•	OUTPUT_FOLDER: Standardmäßig output.
	•	PERSIST_DIRECTORY: Standardmäßig data/chroma für die ChromaDB.
	•	new_data: Auf True setzen, damit neu hinzugefügte CSV-Dateien erneut eingelesen werden.

Nutzung

Lokal

python main.py

Mit Docker Compose

docker-compose up --build

Das Programm führt folgende Schritte aus:
	1.	Liest CSV- und PDF-Dateien aus input.
	2.	Initialisiert bzw. lädt die ChromaDB.
	3.	Importiert CSV-Zeilen als Dokumente in die RAG-Collection.
	4.	Für jede PDF-Stellenbeschreibung:
	•	Extrahiert PDF-Text und reduziert ihn mit ChatGPT.
	•	Fragt relevante Erfahrungen aus der RAG ab (mit bis zu 3 Versuchen).
	•	Baut einen Prompt und erhält eine HTML-Liste der Top-3 Erfahrungen (ebenfalls bis zu 3 Versuche).
	•	Erzeugt ein HTML-Kurzprofil im output-Verzeichnis.

Ordnerstruktur

├── app/                  # Quellcode der Anwendung
│   ├── input_manager.py  # PDF/CSV-Parser und -Reducer
│   ├── rag_manager.py    # ChromaDB-Integration
│   ├── openai_client.py  # Wrapper für OpenAI-API
│   ├── html_generator.py # HTML-Rendering der Ergebnisse
│   └── templates/        # Jinja2-Templates
├── data/                 # ChromaDB-Datenbank (persistiert)
├── input/                # Eingabedateien (CSV & PDF)
├── output/               # Generierte HTML-Profile
├── main.py               # Einstiegspunkt
├── requirements.txt
└── docker-compose.yml

Lizenz

MIT License