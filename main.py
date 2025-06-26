from app.input_manager import find_csv_and_pdf_files, load_resume_data, extract_clean_text_from_pdf

INPUT_FOLDER = "input"

def main():
    # Suche nach Dateien
    csv_files, pdf_files = find_csv_and_pdf_files(INPUT_FOLDER)

    # ToDo: Prüfen welche Files neu sind 

    # Aktuell: Verwende nur die erste PDF für das Stellenprofil
    pdf_path = pdf_files[0]
    pdf_text = extract_clean_text_from_pdf(pdf_path)

    # Mehrere CSVs könnten später einzeln ins RAG gespeichert werden
    for csv_path in csv_files:
        df = load_resume_data(csv_path)
        # ToDo: Übergabe an rag_manager folgt

    # ToDo: Übergabe an Prompt-Generator + RAG
    print("✅ PDF und CSV-Dateien erfolgreich verarbeitet.")

if __name__ == "__main__":
    main()