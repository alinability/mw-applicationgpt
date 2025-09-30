from dotenv import load_dotenv, find_dotenv
# Lade Umgebungsvariablen aus .env
load_dotenv(find_dotenv())

import os
import re
from openai import OpenAI
from prompt_utils import count_tokens, DEFAULT_MODEL, DEFAULT_MODEL_TOKEN_LIMIT, DEFAULT_LARGE_MODEL, DEFAULT_LARGE_MODEL_TOKEN_LIMIT
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
    prompt: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MODEL_TOKEN_LIMIT
    ) -> str:
    """
    Sendet einen einzelnen Prompt an ChatGPT und gibt den Text zurück.
    Loggt dabei die genutzten Tokens zur Kostenkontrolle.
    """
    
    # Neue V1-API-Syntax: client.chat.completions.create
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=prompt,
        max_tokens=max_tokens
    )

    usage = response.usage
    #print(f"ℹ️ Model: {model} | prompt_tokens={usage.prompt_tokens} | completion_tokens={usage.completion_tokens}")

    # Extrahiere und returniere den Content
    return response.choices[0].message.content.strip()

def validate_prompt_length(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MODEL_TOKEN_LIMIT
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
    max_tokens: int = DEFAULT_MODEL_TOKEN_LIMIT
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
        if validate_prompt_length(filled_prompt, model=DEFAULT_LARGE_MODEL, max_tokens=DEFAULT_LARGE_MODEL_TOKEN_LIMIT):
            model = DEFAULT_LARGE_MODEL
        else:
            raise ValueError(
                f"Prompt für 'get_3_experiences' ist zu lang ({max_tokens} Token max)."
            )
    return filled_prompt, model

def is_wrapped_with_same_tag(html: str) -> bool:
    """
    Prüft, ob das HTML korrekt verschachtelte und abgeschlossene Tags enthält.
    Es wird geprüft, ob jede öffnende Tag in der richtigen Reihenfolge wieder geschlossen wird.
    """
    html = html.strip()
    void_elements = {
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "source", "track", "wbr"
    }
    tag_stack = []
    tag_pattern = re.compile(r'<(\/)*(\w+)>')

    for element in re.findall(tag_pattern,html):
        if element[1] in void_elements:
                continue
        elif element[0] == '':
            tag_stack.append(element[1])
        elif element[0] == "/":
            if element[1] == tag_stack[-1]:
                tag_stack.pop()
            else:
                return False
    return html

def validate_html_list(response: str) -> bool:
    """
    Prüft, ob `response` eine HTML-Liste (<ul> oder <ol>) mit genau drei nicht-leeren <li>-Einträgen ist.
    Gibt True zurück, wenn alles passt, sonst False und druckt die gefundenen Fehler.
    """

    # 1) Entferne mögliche Markdown-Codefences
    
    # Entferne alle ```html und ``` Codefence-Blöcke, egal wo sie stehen
    clean = re.sub(r"```html\s*", "", response, flags=re.IGNORECASE)
    clean = re.sub(r"```", "", clean)

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
    items = re.findall(r'<(li)>', clean, flags=re.DOTALL | re.IGNORECASE)
    if len(items) != 3:
        print(f"❌ Liste enthält {len(items)} Einträge, erwartet werden genau 3.")


    # 5) Prüfe, dass jeder Eintrag nicht nur aus Tags besteht, sondern echten Text enthält
    for idx, inner in enumerate(items, start=1):
        text = re.sub(r'<[^>]+>', '', inner).strip()
        if not text:
            print(f"❌ Listeneintrag {idx} ist leer.")
            return False
        
    #print(f"✅ Validierte HTML-Liste:\n{clean[:300]}")
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
    if not validate_prompt_length(filled, model=DEFAULT_MODEL, max_tokens=128000):
        raise ValueError("Prompt für 'estimate_match_score' überschreitet das Token-Limit.")

    # 5) Anfrage an ChatGPT
    system_prompt = "Du bist ein äußerst strenger Bewerber-Matcher mit Fokus auf technische Details."
    messages = [{"role": "system", "content": system_prompt},{"role": "user",   "content": filled}]
    response = ask_chatgpt_single_prompt(messages, model="gpt-4o", temperature=0.0)

    # 6) Zahl extrahieren
    m = re.search(r"(\d{1,3}(?:\.\d+)?)", response)
    if not m:
        print(f"⚠️ Keine gültige Zahl in der Antwort: {response!r}")
        return None

    score = int(max(0, min(100, float(m.group(1)))))
    return score

def refine_experiences_list(
    job_description: str,
    retrieved_docs: list[str],
    experiences_html: str
) -> str:
    """
    Verfeinert eine gegebene HTML-Liste (<li>) mit genau drei Einträgen.
    Nutzt eine strikte System-Message und temperature=0 für deterministische Ergebnisse.

    Args:
        job_description: Der Text der Stellenanzeige.
        retrieved_docs: Liste der ursprünglichen Retrieval-Dokumente.
        experiences_html: Aktuelle HTML-Liste mit <li>-Einträgen.

    Returns:
        Eine HTML-<ul> mit exakt drei <li>, die die relevantesten Erfahrungen repräsentieren.
    """
    # 1) Dokumente nummerieren
    docs_text = "\n".join(f"{i+1}. {doc}" for i, doc in enumerate(retrieved_docs, start=0))

    # 2) Template aus PROMPTS laden
    template: str = PROMPTS["refine_experiences"]

    # Safety: ensure experiences_html is a string
    if isinstance(experiences_html, str):
        exp_html_str = experiences_html.strip()
    else:
        print("❌ refine_experiences_list: Kein gültiger HTML-String erhalten.")
        return False

    # 3) Prompt befüllen
    user_content = template.format(
        job_description=job_description.strip(),
        docs_text=docs_text,
        experiences_html=exp_html_str
    )
    
    # 4) Prompt-Länge validieren (optional erweitertes Kontext-Modell)
    model = DEFAULT_MODEL
    if not validate_prompt_length(user_content, model=DEFAULT_MODEL, max_tokens=DEFAULT_MODEL_TOKEN_LIMIT):
        model = DEFAULT_LARGE_MODEL #TODO: alle Modelle in eine config Datei schreiben
        if not validate_prompt_length(user_content, model=model, max_tokens=DEFAULT_LARGE_MODEL_TOKEN_LIMIT):
            raise ValueError("Prompt für 'refine_experiences' überschreitet das Token-Limit.")

    # 5) Anfrage mit System-Message
    system_prompt = "Du bist ein äußerst strenger Bewerber-Matcher mit Fokus auf technische Details."
    messages = [{"role": "system", "content": system_prompt},{"role": "user",   "content": user_content}]
    response = ask_chatgpt_single_prompt(messages, model=model, temperature=0.0)

    return response.strip()

def get_response(reduced_text: str, retrieved_docs: str):
    quality_check_rensponse = False
    n = 0
    
    # Prompt bauen und an ChatGPT senden
    while quality_check_rensponse == False and n <= 2:
        final_prompt, model = build_prompt(reduced_text, retrieved_docs)  
        system_prompt = "Du bist ein äußerst strenger Bewerber-Matcher mit Fokus auf technische Details."
        messages = [{"role": "system", "content": system_prompt},{"role": "user",   "content": final_prompt}]
        response = ask_chatgpt_single_prompt(messages, model=model, temperature=0.0)
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