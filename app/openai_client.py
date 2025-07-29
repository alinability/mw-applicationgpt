from dotenv import load_dotenv, find_dotenv
# Lade Umgebungsvariablen aus .env
load_dotenv(find_dotenv())

import os
import re
from openai import OpenAI
from prompt_utils import count_tokens, DEFAULT_MODEL
import yaml
from pathlib import Path

PROMPTS = yaml.safe_load(
    (Path(__file__).parent / "prompts.yml")
    .read_text(encoding="utf-8")
)

# API-Key aus Umgebungsvariable
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ Kein OpenAI API-Key gefunden. Bitte .env prüfen.")

# `client` kann als Alias verwendet werden, falls gewünscht
client = OpenAI(api_key=api_key)

def ask_chatgpt_single_prompt(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 4096
    ) -> str:
    """
    Sendet einen einzelnen Prompt an ChatGPT und gibt den Text zurück.
    Loggt dabei die genutzten Tokens zur Kostenkontrolle.
    """
    
    # Neue V1-API-Syntax: client.chat.completions.create
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    )

    usage = response.usage
    #print(f"ℹ️ Model: {model} | prompt_tokens={usage.prompt_tokens} | completion_tokens={usage.completion_tokens}")

    # Extrahiere und returniere den Content
    return response.choices[0].message.content.strip()

def validate_prompt_length(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096
    ):
    """Prüft, ob der Prompt die maximale Token-Länge überschreitet."""
    token_count = count_tokens(prompt, model=model)
    if token_count > max_tokens:
        return False
    return True

def build_prompt(
    job_text: str,
    experiences: list[str],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096
) -> str:
    """
    Baut einen Prompt zur Auswahl der 3 relevantesten Erfahrungen
    und zur Rückgabe im HTML-Format, basierend auf dem Template
    'get_3_experiences' in prompts.yml.
    """
    job_text = job_text.strip()
    # 1) rohes Template aus YAML holen
    template: str = PROMPTS["get_3_experiences"]
    # 2) Liste der Erfahrungen in eine string-Repräsentation umwandeln
    #    (falls das Template eine Bullet-Liste erwartet)
    ex_list = "\n".join(f"- {e}" for e in experiences)
    # 3) Template befüllen
    filled_prompt = template.format(
        job_description=job_text,
        experiences=ex_list
    )
    # 4) Prompt-Länge prüfen
    if not validate_prompt_length(filled_prompt, model=model, max_tokens=max_tokens):
        raise ValueError(
            f"Prompt für 'get_3_experiences' ist zu lang ({max_tokens} Token max)."
        )
    return filled_prompt

def is_wrapped_with_same_tag(html: str) -> bool:
    """
    Prüft, ob `html` mit <tag>…</tag> umschlossen ist, wobei 'tag' an beiden Stellen identisch sein muss.
    """
    html = html.strip()
    m = re.match(r'^<\s*([A-Za-z0-9]+)(?:\s+[^>]*)?>', html)
    if not m:
        return False
    tag = m.group(1)
    return bool(re.search(rf'</\s*{re.escape(tag)}\s*>$', html))

def validate_html_list(response: str) -> bool:
    """
    Prüft, ob `response` eine HTML-Liste (<ul> oder <ol>) mit genau drei nicht-leeren <li>-Einträgen ist.
    Gibt True zurück, wenn alles passt, sonst False und druckt die gefundenen Fehler.
    """

    # 1) Entferne mögliche Markdown-Codefences
    
    # html → Zeilenumbruch
    clean = re.sub(r'html', '\n', response)
    
    # am Zeilenanfang oder -ende beliebig viele ' löschen
    clean = re.sub(r"(\s)*(`)+(\n)*", "", clean)

    # 2) Entferne komplett leere Zeilen oder solche mit nur Whitespace
    #    (?m) aktiviert den Multiline-Mode, sodass ^/$ auf Zeilenanfang/-ende abzielen
    clean = re.sub(r'(?m)^[ \t]*\n', '', clean)

    # 3) Überprüfe, ob die Liste richtig mit <ul>…</ul> oder <ol>…</ol> umschlossen ist
    if bool(is_wrapped_with_same_tag(clean)) == False:
        print("❌ Keine korrekt formatierte HTML-Liste gefunden (fehlende umschließenden <il>/<ul>/<ol>-Tags).")
        #print(clean)
        return False

    # 4) Finde alle <li>…</li>
    items = re.findall(r'<li\b[^>]*>(.*?)</li>', clean, flags=re.DOTALL | re.IGNORECASE)
    if len(items) != 3:
        print(f"❌ Liste enthält {len(items)} Einträge, erwartet werden genau 3.")
        print(response)
        return False

    # 5) Prüfe, dass jeder Eintrag nicht nur aus Tags besteht, sondern echten Text enthält
    for idx, inner in enumerate(items, start=1):
        text = re.sub(r'<[^>]+>', '', inner).strip()
        if not text:
            print(f"❌ Listeneintrag {idx} ist leer.")
            return False
        
    return clean

def estimate_match_score(job_description: str, experiences: list[str]) -> int | None:
    """
    Fragt das OpenAI-API, die Passgenauigkeit des Bewerbers für die Stelle
    auf einer Skala von 0–100 einzuschätzen, basierend auf:
      • Stellenbeschreibung
      • den relevanten Erfahrungen (nummeriert)
    Gibt die Zahl (0–100) zurück oder None, wenn keine Zahl erkannt wurde.
    Und gibt das Ergebnis im Terminal aus.
    """
    # 1) Liste der Erfahrungen in nummerierten Block umwandeln
    exp_block = "\n".join(f"{idx}. {exp}" for idx, exp in enumerate(experiences, start=1))

    # 2) Roh-Template aus YAML holen
    template: str = PROMPTS["estimate_match_score"]
    # 3) Prompt befüllen
    filled = template.format(
        job_description=job_description.strip(),
        experiences=exp_block
    )

    # 4) Prompt-Länge validieren
    if not validate_prompt_length(filled, model=DEFAULT_MODEL, max_tokens=4096):
        raise ValueError("Prompt für 'estimate_match_score' überschreitet das Token-Limit.")

    # 5) Anfrage an ChatGPT
    response = ask_chatgpt_single_prompt(filled, model=DEFAULT_MODEL, temperature=0.0).strip()

    # 6) Zahl extrahieren
    m = re.search(r"(\d{1,3}(?:\.\d+)?)", response)
    if not m:
        print(f"⚠️ Keine gültige Zahl in der Antwort: {response!r}")
        return None

    score = int(max(0, min(100, float(m.group(1)))))
    return score

def refine_experiences_list(job_description: str,
                            retrieved_docs: list[str],
                            experiences_html: str) -> str:
    """
    Fragt bei ChatGPT nach, ob die drei HTML-Experience-Einträge 
    wirklich die relevantesten sind, basierend auf:
      - der Stellenanzeige (job_description)
      - den ursprünglichen Retrieval-Dokumenten (retrieved_docs)
      - der aktuellen HTML-Liste (experiences_html)
    Gibt immer eine HTML-Liste mit exakt drei <li> zurück.
    """
    # 1) Dokumente nummerieren
    docs_text = "\n".join(f"{i+1}. {doc}" for i, doc in enumerate(retrieved_docs, start=1))

    # 2) Template aus der YAML-Datei laden
    template: str = PROMPTS["refine_experiences"]

    # 3) Prompt befüllen
    prompt = template.format(
        job_description=job_description.strip(),
        docs_text=docs_text,
        experiences_html=experiences_html.strip()
    )

    # 4) Prompt-Länge validieren
    if not validate_prompt_length(prompt, model=DEFAULT_MODEL, max_tokens=4096):
        if validate_prompt_length(prompt, model=DEFAULT_MODEL, max_tokens=128000):
            model = "gpt‑4o‑mini"
        if not validate_prompt_length(prompt, model=DEFAULT_MODEL, max_tokens=128000):
            raise ValueError("Prompt für 'refine_experiences' überschreitet das Token-Limit.")

    # 5) Anfrage an ChatGPT
    response = ask_chatgpt_single_prompt(
        prompt,
        model=DEFAULT_MODEL,
        temperature=0.0
    ).strip()

    return response

def get_response(reduced_text: str, retrieved_docs: str):
    quality_check_rensponse = False
    n = 0
    
    # Prompt bauen und an ChatGPT senden
    while quality_check_rensponse == False and n <= 2:
        
        final_prompt = build_prompt(reduced_text, retrieved_docs)  
        response = ask_chatgpt_single_prompt(final_prompt)
        response = validate_html_list(response)
        n += 1
    
    if response == False:
        print("❌ ChatGPT Anfrage nicht wie erwartet.")

    response = refine_experiences_list(reduced_text, retrieved_docs, response)   

    if response == False:
        print("❌ ChatGPT Anfrage nicht wie erwartet.")

    score = estimate_match_score(reduced_text, retrieved_docs)
    if score is None:
        print("⚠️ Konnte keine Passgenauigkeitszahl aus der Antwort extrahieren.")
    else:
        print(f"🎯 Passgenauigkeit laut ChatGPT: {score}%")
    
    return response