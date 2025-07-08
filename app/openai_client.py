from dotenv import load_dotenv, find_dotenv
# Lade Umgebungsvariablen aus .env
load_dotenv(find_dotenv())

import os
import re
from openai import OpenAI
from prompt_utils import count_tokens, DEFAULT_MODEL

# API-Key aus Umgebungsvariable
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ Kein OpenAI API-Key gefunden. Bitte .env prüfen.")

# `client` kann als Alias verwendet werden, falls gewünscht
client = OpenAI(api_key=api_key)


def ask_chatgpt_single_prompt(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2
) -> str:
    """Sendet einen einfachen Prompt an ChatGPT und gibt die Antwort als Text zurück."""
    # Token-Länge prüfen
    count_tokens(prompt, model=model)

    # Neue V1-API-Syntax: client.chat.completions.create
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}]
    )

    # Extrahiere und returniere den Content
    return response.choices[0].message.content.strip()


def validate_prompt_length(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096
) -> None:
    """Prüft, ob der Prompt die maximale Token-Länge überschreitet."""
    token_count = count_tokens(prompt, model=model)
    if token_count > max_tokens:
        raise ValueError(
            f"Prompt zu lang: {token_count} Tokens, erlaubt sind {max_tokens} Tokens."
        )

def build_prompt(job_text: str, experiences: list[str], model: str = DEFAULT_MODEL, max_tokens: int = 8000) -> str:
    """
    Baut einen Prompt zur Auswahl der 3 relevantesten Erfahrungen und zur Rückgabe im HTML-Format.
    """
    intro = (
        "Du bist ein Karrierecoach. Deine Aufgabe ist es, aus den folgenden Berufserfahrungen "
        "die drei relevantesten für die unten stehende Stellenanzeige auszuwählen.\n\n"
        "Bitte gib die drei Erfahrungen exakt im folgenden HTML-Format zurück:\n\n"
        "<li>\n"
        "  <strong>[Titel der Erfahrung]</strong><br>\n"
        "  <em>[Zeitraum]</em><br>\n"
        "  [Beschreibung in max. 2 Sätzen]\n"
        "</li>\n\n"
        "⚠️ Gib nur die drei HTML-Elemente zurück – ohne Einleitung oder zusätzliche Erläuterungen."
    )

    job_section = f"\n\n📌 **Stellenanzeige**:\n{job_text.strip()}"
    exp_section = "\n\n📚 **Berufserfahrungen**:\n" + "\n---\n".join(experiences)

    full_prompt = f"{intro}{job_section}{exp_section}"

    validate_prompt_length(full_prompt, model=model, max_tokens=max_tokens)
    return full_prompt

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
        print(clean)
        return False

    # 4) Finde alle <li>…</li>
    items = re.findall(r'<li\b[^>]*>(.*?)</li>', clean, flags=re.DOTALL | re.IGNORECASE)
    if len(items) != 3:
        print(f"❌ Liste enthält {len(items)} Einträge, erwartet werden genau 3.")
        return False

    # 5) Prüfe, dass jeder Eintrag nicht nur aus Tags besteht, sondern echten Text enthält
    for idx, inner in enumerate(items, start=1):
        text = re.sub(r'<[^>]+>', '', inner).strip()
        if not text:
            print(f"❌ Listeneintrag {idx} ist leer.")
            return False
        
    return clean

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
        print(response)
    
    return response


