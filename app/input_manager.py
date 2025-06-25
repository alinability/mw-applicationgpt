### Einlesen CSV

import os
import pandas as pd
import datetime as dt
import re
import pdfplumber

def find_csv_and_pdf(path: str) -> tuple[str, str]:
    """
    Sucht in einem Verzeichnis nach genau einer CSV- und einer PDF-Datei.
    
    Gibt eine verständliche Fehlermeldung zurück, wenn:
    - keine Dateien vorhanden sind
    - unerwartete Formate auftauchen
    - mehr oder weniger als je eine CSV und PDF vorhanden sind

    Rückgabe:
        Tuple[str, str]: (Pfad zur CSV-Datei, Pfad zur PDF-Datei)
    """
    if not os.path.isdir(path):
        raise NotADirectoryError(f"❌ Der Pfad ist kein gültiges Verzeichnis: {path}")

    files = os.listdir(path)

    if not files:
        raise FileNotFoundError("❌ Es wurden keine Dateien im angegebenen Verzeichnis gefunden.")

    # Filtere nur csv und pdf
    csv_files = [os.path.join(path, f) for f in files if f.lower().endswith(".csv")]
    pdf_files = [os.path.join(path, f) for f in files if f.lower().endswith(".pdf")]
    other_files = [f for f in files if not f.lower().endswith((".csv", ".pdf"))]

    if len(csv_files) == 0:
        raise FileNotFoundError("❌ Es wurde keine CSV-Datei gefunden.")
    if len(csv_files) > 1:
        raise FileNotFoundError(f"❌ Es wurden mehrere CSV-Dateien gefunden: {len(csv_files)}") # ToDo: ggf Anpassung für mehrere Datein. So, dass sowohl meherere Stellenanzeigen als auch Projektlisten genutzt werden können.

    if len(pdf_files) == 0:
        raise FileNotFoundError("❌ Es wurde keine PDF-Datei gefunden.")
    if len(pdf_files) > 1:
        raise FileNotFoundError(f"❌ Es wurden mehrere PDF-Dateien gefunden: {len(pdf_files)}")
    return csv_files[0], pdf_files[0]

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
    
    Vorteile gegenüber PyPDF2:
    - Bessere Textstruktur
    - Weniger Layout-Müll
    - Keine zerrissenen Wörter oder Duplikate
    
    Rückgabe:
        str: Bereinigter Text der PDF
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            raw_text = " ".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        raise ValueError(f"❌ Fehler beim Öffnen oder Lesen der PDF-Datei: {e}")

    # Text bereinigen
    cleaned_text = normalize_pdf_text(raw_text)

    if not cleaned_text.strip():
        raise ValueError("❌ Es konnte kein sinnvoller Text aus der PDF extrahiert werden. Möglicherweise enthält die Datei nur Bilder.")
    
    print("✅ Die Stellenauschreibung wurde erkannt.")

    return cleaned_text

