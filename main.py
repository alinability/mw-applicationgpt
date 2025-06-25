from app.input_manager import load_resume_data, extract_clean_text_from_pdf, find_csv_and_pdf

def main():
    try:
        csv_path, pdf_path = find_csv_and_pdf("/input")
        df = load_resume_data(csv_path)
        text = extract_clean_text_from_pdf(pdf_path)

        print(df)
        print(text[:1000])

    except Exception as e:
        print(f"❌ Fehler: {e}")

if __name__ == "__main__":
    main()