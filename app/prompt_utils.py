import tiktoken
import os

DEFAULT_MODEL = "gpt-3.5-turbo"

def count_tokens(text: str, model: str = DEFAULT_MODEL) -> int:
    """
    Zählt die Tokens eines Strings basierend auf dem Modell.
    """
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def save_references_to_txt(pdf_path, reduced_text, retrieved_docs, response, output_dir="output"):
    """
    Speichert reduced_text und retrieved_docs in einer TXT-Datei im output-Verzeichnis.
    Die Datei heißt <pdf_basename>_references.txt.

    :param pdf_path: Pfad zur Stellenanzeigen-PDF
    :param reduced_text: Das bereits reduzierte PDF-Text-Snippet
    :param retrieved_docs: Liste der aus dem RAG abgefragten Dokumente (Strings)
    :param output_dir: Zielordner (wird angelegt, falls nicht vorhanden)
    :return: Pfad zur erzeugten TXT-Datei
    """
    # 1. Output-Verzeichnis anlegen
    os.makedirs(output_dir, exist_ok=True)

    # 2. Basisname der PDF (ohne Extension) ermitteln
    base = os.path.basename(pdf_path)
    name, _ = os.path.splitext(base)
    filename = f"{name}_references.txt"
    output_path = os.path.join(output_dir, filename)

    # 3. In die Datei schreiben
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=== Reduced Text ===\n")
        f.write(reduced_text.strip() + "\n\n")
        f.write("=== Retrieved Documents ===\n")
        if retrieved_docs:
            for i, doc in enumerate(retrieved_docs, start=1):
                f.write(f"{i}. {doc.strip()}\n\n")
        else:
            f.write("Keine Dokumente abgerufen.\n")
        f.write("=== Response ===\n")
        f.write(response + "\n\n")

    print(f"✅ Referenzen gespeichert unter: {output_path}")
    return output_path