### Einlesen CSV

import os
import pandas as pd
import re
import pdfplumber
import hashlib
import os
import re
import pdfplumber
import ocrmypdf
import tempfile

try:
    from app.openai_client import ask_chatgpt_single_prompt, validate_prompt_length
    from app.prompt_utils import count_tokens, chunk_text_by_tokens
except ImportError:
    from openai_client import ask_chatgpt_single_prompt, validate_prompt_length
    from prompt_utils import count_tokens, chunk_text_by_tokens

CACHE_DIR = "./data/cache"

def find_csv_and_pdf_files(path: str) -> tuple[list[str], list[str]]:
    """
    Sucht nach allen CSV- und PDF-Dateien in einem Verzeichnis und gibt deren Pfade zurück.
    Gibt zusätzlich Feedback zur Anzahl der gefundenen Dateien.
    """
    if not os.path.isdir(path):
        raise NotADirectoryError(f"❌ Der Pfad ist kein gültiges Verzeichnis: {path}")

    files = os.listdir(path)
    
    if not files:
        raise FileNotFoundError("❌ Keine Dateien im angegebenen Verzeichnis gefunden.")

    csv_files = [os.path.join(path, f) for f in files if f.lower().endswith(".csv")]
    pdf_files = [os.path.join(path, f) for f in files if f.lower().endswith(".pdf")]

    print(f"📄 Gefundene CSV-Dateien: {len(csv_files)}")
    print(f"📄 Gefundene PDF-Dateien: {len(pdf_files)}")

    if not pdf_files:
        raise FileNotFoundError("❌ Keine PDF-Datei gefunden. Bitte stelle sicher, dass mindestens eine PDF im Ordner liegt.")

    return csv_files, pdf_files

def detect_separator(filepath: str) -> str:
    """
    Erkennt automatisch das Trennzeichen in der ersten Zeile der Datei.
    Unterstützt ',', ';' und Tabulator ('\\t').
    """
    with open(filepath, encoding="utf-8") as f:
        first_line = f.readline()

    # Zähle Vorkommen möglicher Trenner
    candidates = {",": first_line.count(","), ";": first_line.count(";"), "\t": first_line.count("\t")}

    # Wähle den Trenner mit den meisten Vorkommen
    best = max(candidates, key=candidates.get)

    # Warnung, falls alles gleich 0 ist (z. B. eine leere oder ungewöhnliche Datei)
    if candidates[best] == 0:
        print("⚠️ Kein gängiges Trennzeichen erkannt, Standardwert ',' wird verwendet.")
        return ","

    return best

def parse_date_string(date_str: str) -> pd.Timestamp | None:
    """Konvertiert Strings wie '2010', 'heute', 'today' in ein Datum, sonst None."""
    date_str = date_str.strip().lower()
    today = pd.Timestamp.today().normalize()

    if date_str in {"heute", "today"}:
        return today

    try:
        return pd.to_datetime(date_str, errors="raise", dayfirst=True)
    except Exception:
        return None
    
def parse_period_string(entry: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """
    Erkennt entweder:
    - Einzelzeitpunkt wie '2010', 'heute' → Start = End
    - Zeitraum wie '2010 - 2015' → Start, End
    Gibt: (start, end) oder None
    """
    entry = entry.strip()

    # Trenne Bereich
    split_match = re.split(r"\s*[-–bis]+\s*", entry, maxsplit=1)
    if len(split_match) == 1:
        date = parse_date_string(split_match[0])
        return (date, date) if date else None
    elif len(split_match) == 2:
        start = parse_date_string(split_match[0])
        end = parse_date_string(split_match[1])
        return (start, end) if start and end else None
    return None

def quality_check(df: pd.DataFrame, time_column: str = 'Timeline') -> bool:
    """
    Prüft ob:
    - Zeitspalte vorhanden
    - mind. 4 gültige Einträge (einzelne Zeitpunkte oder Zeiträume)
    - Gesamtzeitraum >= 1 Jahr
    """
    if time_column not in df.columns:
        print(f"❌ Zeitspalte '{time_column}' nicht gefunden.")
        return False

    if len(df) < 4:
        print(f"❌ Der DataFrame enthält nur {len(df)} Zeilen (mindestens 4 erforderlich).")
        return False

    df = df.copy()
    periods = df[time_column].astype(str).apply(parse_period_string)
    valid_periods = [p for p in periods if p is not None]

    if len(valid_periods) < 4:
        print(f"❌ Nur {len(valid_periods)} gültige Zeitangaben erkannt (mindestens 4 erforderlich).")
        return False

    starts, ends = zip(*valid_periods)
    overall_start = min(starts)
    overall_end = max(ends)
    duration = overall_end - overall_start

    if duration < pd.Timedelta(days=365):
        print(f"❌ Zeitraum ist zu kurz: nur {duration.days} Tage (mind. 1 Jahr erforderlich).")
        return False

    print(f"✅ Es wurden {len(df)} Berufserfahrungen erkannt. Der Zeitraum erstreckt sich von {overall_start.strftime('%B %Y')} bis {overall_end.strftime('%B %Y')} ({(overall_end - overall_start).days} Tage).")
    print("✅ Qualitätsprüfung bestanden.")
    return True

def load_resume_data(filepath: str) -> pd.DataFrame:
    
    sep = detect_separator(filepath)

    try:
        # Korrektur: Header ist in Zeile 0
        df = pd.read_csv(filepath, sep=sep, header=0)
    except Exception as e:
        raise ValueError(f"❌ Fehler beim Einlesen der CSV: {e}")

    # Leere Spalten entfernen
    df = df.drop(columns=[col for col in df.columns if col.startswith("Unnamed")], errors="ignore")

    # Leere Zeilen entfernen
    df = df.dropna(how="all")

    # Whitespace aus Spaltennamen entfernen
    df.columns = [col.strip() for col in df.columns]

    # ToDo: Hier noch einen Qualitätscheck einfügen. z.B. Datensatz nach Relevanz filtern --> vorgeschriebene Spalten oder mit Chatgpt Spaltennamen nach Relevanz auswerten
    quality_check(df) 
    return df

### Einlesen PDF

def normalize_pdf_text(text: str) -> str:
    """
    Bereinigt gestreckten, duplizierten oder zerschossenen Text aus PDF-Scans.
    - Fasst Buchstabenwiederholungen wie 'TTTeeecccchhhh' zu 'Tech' zusammen
    - Entfernt mehrfach wiederholte Wörter oder Blöcke
    - Vereinheitlicht Leerzeichen
    """

    # 1. Einzelne Buchstaben-Wiederholungen reduzieren (z.B. SSSoooffftttwwwaaarrreee → Software)
    text = re.sub(r'(.)\1{2,}', r'\1', text)

    # 2. Überlange Wortwiederholungen zusammenfassen
    text = re.sub(r'\b(\w{3,})\s+\1\b', r'\1', text)

    # 3. Whitespace bereinigen
    text = re.sub(r'\s+', ' ', text)

    # 4. Erste Buchstaben wieder groß schreiben (optional)
    text = re.sub(r'(^|\.\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)

    # 5. Trim
    text = text.strip()

    return text

def extract_clean_text_from_pdf(pdf_path: str) -> str:
    """
    Extrahiert und bereinigt den Text aus einer PDF-Datei mit pdfplumber.
    Falls dabei kein Text herauskommt, wird OCR nachgeladen und erneut extrahiert.
    
    Vorteile gegenüber PyPDF2:
    - Bessere Textstruktur
    - Weniger Layout-Müll
    - Keine zerrissenen Wörter oder Duplikate
    
    Rückgabe:
        str: Bereinigter Text der PDF
    """
    def _read_pdf(path: str) -> str:
        with pdfplumber.open(path) as pdf:
            return " ".join(page.extract_text() or "" for page in pdf.pages)

    # 1) Erster Versuch ohne OCR
    try:
        raw_text = _read_pdf(pdf_path)
    except Exception as e:
        raise ValueError(f"❌ Fehler beim Öffnen oder Lesen der PDF-Datei: {e}")

    cleaned_text = normalize_pdf_text(raw_text)

    # 2) Falls kein sinnvoller Text, OCR-Fallback
    ocr_pdf_path = False
    pattern = re.compile(r'^(?:\b\w+\b\W+){49}\b\w+\b', flags=re.UNICODE)
    if not bool(pattern.match(cleaned_text.strip())):
    #if not cleaned_text.strip():
        print("ℹ️ Kein Text gefunden, führe OCR nach ...")
        fd, ocr_pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            # force_ocr sorgt dafür, dass auch textbasierte PDFs verarbeitet werden
           ocrmypdf.ocr(
                pdf_path,
                ocr_pdf_path,
                output_type="pdf",
                force_ocr=True,
                skip_text=False,
                redo_ocr=False
            )
           raw_text = _read_pdf(ocr_pdf_path)
           cleaned_text = normalize_pdf_text(raw_text)
           if cleaned_text.strip():
                print("✅ OCR erfolgreich, Text extrahiert.")
           else:
               print("⚠️ Auch nach OCR konnte kein Text extrahiert werden.")

        except Exception as oe:
            raise ValueError(f"❌ OCR-Fehler: {oe}")

    if not cleaned_text.strip():
        raise ValueError("❌ Es konnte kein sinnvoller Text aus der PDF extrahiert werden.")
    
    print("✅ Die Stellenausschreibung wurde erkannt.")
    return cleaned_text, ocr_pdf_path

def _get_cache_path(key: str) -> str:
        return os.path.join(CACHE_DIR, f"{key}.txt")

def load_cached_reduction(key: str) -> str | None:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = _get_cache_path(key)
        if os.path.exists(path):
            print("🔄 Verwende gecachte Reduktion.")
            return open(path, "r", encoding="utf-8").read()
        return None

def save_cached_reduction(key: str, text: str):
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_get_cache_path(key), "w", encoding="utf-8") as f:
            f.write(text)

def make_key_from_file(pdf_path: str) -> str:
    buf = open(pdf_path, "rb").read()
    return hashlib.sha256(buf).hexdigest()

def reduce_pdf_to_essentials(text: str, pdf_path : str, cache_key: str) -> str:
    """
    Reduziert den PDF-Text auf das Wesentliche via ChatGPT, mit einfachem Cache.
    """
    prompt = (
        "Ich gebe dir eine Stellenanzeige:\n\n"
        f"{text}\n\n"
        "Bitte fasse diesen Text präzise zusammen und hebe **besonders** die technischen Anforderungen hervor, "
        "insbesondere:\n"
        "- Programmiersprachen und Versionen\n"
        "- Frameworks und Bibliotheken\n"
        "- Tools und Plattformen\n"
        "- Schnittstellen oder APIs und Protokolle\n"
        "- Tätigkeitsbereich des Unternehmens\n\n"
        "Die Zusammenfassung soll in Stichpunkten erfolgen."
    )

    prompt_length_bool = validate_prompt_length(text)
    
    if not prompt_length_bool:
        chunks = chunk_text_by_tokens(text)
        for chunk in chunks:
            reduced = ""
            prompt = (
            f"Ich gebe dir einen Auszug aus einer Stellenanzeige:\n\n"
            f"{chunk}\n\n"
            "Bitte fasse diesen Text präzise zusammen und hebe **besonders** die technischen Anforderungen hervor, "
            "insbesondere:\n"
            "- Programmiersprachen und Versionen\n"
            "- Frameworks und Bibliotheken\n"
            "- Tools und Plattformen\n"
            "- Schnittstellen oder APIs und Protokolle\n"
            "- Tätigkeitsbereich des Unternehmens\n\n"
            "Die Zusammenfassung soll in Stichpunkten erfolgen."
        )
            chunk_reduced = ask_chatgpt_single_prompt(prompt)
            reduced = reduced + " " + chunk_reduced

            save_cached_reduction(cache_key, reduced)

            print("✅ PDF-Inhalt wurde erfolgreich reduziert.")
            return reduced

    reduced = ask_chatgpt_single_prompt(prompt)

    save_cached_reduction(cache_key, reduced)

    print("✅ PDF-Inhalt wurde erfolgreich reduziert.")
    return reduced

def get_pdf_page_count(pdf_path: str) -> int:
    """Zählt die Seiten einer PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)

def extract_headings_from_pdf(pdf_path: str) -> list[str]:
    """
    Liest jede Seite mit pdfplumber ein, splittet sie in Zeilen
    und sammelt alle Zeilen, die mit „Zahl. Text“ beginnen.
    """
    headings: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                clean = line.strip()
                # Regex: Zeilenanfang, Zahl+, optional weitere .Ziffern, Punkt, mindestens ein Leerzeichen, dann Text
                if re.match(r'^\d+(?:\.\d+)*\.\s+\S+', clean):
                    headings.append(clean)
    return headings

def select_best_heading(headings):
    """
    Fragt ChatGPT, welche Heading(s) am relevantesten für die Stellenanzeige sind.
    Liefert eine ganz normale Python-Liste von Kapitel-Titeln zurück.
    """
    # 1) Inhaltsverzeichnis als Bullet-Point-Liste für den Prompt aufbauen
    toc = "\n".join(f"- {h}" for h in headings)
    prompt = (
        "Die PDF enthält folgende Kapitelüberschriften:\n"
        f"{toc}\n\n"
        "Welche dieser Überschriften sind essentiell für die Anforderungen und Qualifikation des "
        "Personals im Projekt? Bitte antworte **nur** mit den exakten Kapitel-Titeln, jeder Titel "
        "in einer neuen Zeile. Du darfst dafür '-' voranstellen oder weglassen."
    )

    # 2) ChatGPT fragen
    raw = ask_chatgpt_single_prompt(prompt).strip()

    # 3) Antwort in Zeilen splitten und leerzeilen herausfiltern
    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    # 4) führendes "- " entfernen (falls vorhanden) und saubere Liste sammeln
    result = []
    for line in lines:
        if line.startswith("-"):
            result.append(line.lstrip("- ").strip())
        else:
            result.append(line)
    return result

def extract_chapter_text(full_text, chosen, all_headings):
    """
    Schneidet aus full_text nur den Abschnitt heraus, der zu `chosen` gehört.
    Wenn `chosen` eine Liste von Überschriften ist, werden alle entsprechenden
    Abschnitte extrahiert und hintereinander gehängt.
    """
    def _extract_one(text, heading, headings):
        # Split vor der gewählten Überschrift
        parts = re.split(rf'(?m)^{re.escape(heading)}.*$', text, maxsplit=1)
        if len(parts) < 2:
            return ""
        after = parts[1]
        # Finde Position der nächsten Überschrift
        others = [h for h in headings if h != heading]
        if others:
            nxt_pattern = rf'(?m)^({"|".join(re.escape(h) for h in others)})'
            m = re.search(nxt_pattern, after)
            if m:
                return after[:m.start()].strip()
        return after.strip()

    # Handle list of headings
    if isinstance(chosen, (list, tuple)):
        sections = []
        for heading in chosen:
            sec = _extract_one(full_text, heading, all_headings)
            if sec:
                sections.append(sec)
        return "\n\n".join(sections)

    # Single heading
    return _extract_one(full_text, chosen, all_headings)

def process_pdf(pdf_path: str) -> str:
    """
    - Nutzt Cache, sofern vorhanden.
    - Liest PDF, falls ≤3 Seiten: Volltext → reduce.
    - Falls >3 Seiten: sucht Kapitel, fragt ChatGPT, extrahiert bestes Kapitel → reduce.
    """
    # 1) Cache-Key prüfen
    key = make_key_from_file(pdf_path)
    cached = load_cached_reduction(key)
    if cached is not None:
        return cached

    # 2) PDF öffnen und Volltext sammeln
    full_text, ocr_pdf_path = extract_clean_text_from_pdf(pdf_path)
    token_count = count_tokens(full_text)
    
    # 3) Bei kurzen PDFs: direkt reduzieren
    if token_count <= 2000:
        reduced = reduce_pdf_to_essentials(full_text, pdf_path, cache_key=key)
        save_cached_reduction(key, reduced)
        return reduced

    # 4) Bei langen PDFs: Kapitel-Handling
    if ocr_pdf_path:
        headings = extract_headings_from_pdf(ocr_pdf_path)
    else:
        headings = extract_headings_from_pdf(pdf_path)

    if not headings:
        # Falls keine Kapitel gefunden: wie Kurz-PDF behandeln
        reduced = reduce_pdf_to_essentials(full_text, pdf_path, cache_key=key)
        
    if headings:
        best = select_best_heading(headings)
        #print(f"ℹ️ Wähle Kapitel „{best}“ für Reduktion.")
        full_text = extract_chapter_text(full_text, best, headings)
        reduced = reduce_pdf_to_essentials(full_text, pdf_path, cache_key=key)
    
    # 5) Dieses Kapitel reduzieren und cachen
    save_cached_reduction(key, reduced)
    return reduced

