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
    temperature: float = 0.2,
    max_tokens: int = 500
    ) -> str:
    """
    Sendet einen einzelnen Prompt an ChatGPT und gibt den Text zurück.
    Loggt dabei die genutzten Tokens zur Kostenkontrolle.
    """
    # Token-Länge prüfen
    count_tokens(prompt, model=model)

    # Neue V1-API-Syntax: client.chat.completions.create
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    )

    usage = response.usage
    print(f"ℹ️ Model: {model} | prompt_tokens={usage.prompt_tokens} | completion_tokens={usage.completion_tokens}")

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
        "Bitte sortiere die Erfahrungen zeitlich absteigend."
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

def estimate_match_score(job_description: str, experiences: list[str]) -> float | None:
    """
    Fragt das OpenAI-API, die Passgenauigkeit des Bewerbers für die Stelle
    auf einer Skala von 0–100 einzuschätzen, basierend auf der Stellenbeschreibung
    und den relevanten Erfahrungen. Berücksichtigt dabei u.a.:
      • Fachliche Übereinstimmung (Technologien, Methoden)
      • Führungskompetenz und Teamgröße
      • Branchenerfahrung
      • Erreichte Ergebnisse / Impact
      • Sprach- und Kulturkompetenz (z.B. Nearshore-Management)
    Gibt die Zahl (0–100) zurück oder None, wenn keine Zahl erkannt wurde.
    """
    # Baue den Prompt mit klareren Bewertungskriterien
    prompt = f"""Bitte bewerte auf einer Skala von 0 bis 100, wie gut der Bewerber
auf die folgende Stellenanzeige passt. Gehe dabei insbesondere auf diese Punkte ein:
  1. Fachliche Übereinstimmung: genutzte Technologien, Frameworks, Methoden
  2. Führungserfahrung: Teamgröße, Art der Verantwortung
  3. Branchen- und Domainwissen
  4. Nachweisbarer Impact / erzielte Ergebnisse
  5. Sprach-, Standort- oder Kulturkompetenz (z.B. Nearshore-Management)
  
Antworte bitte ganz kurz mit einer einzigen Zahl (z.B. `87`).  
  
Stellenanzeige:
{job_description}

Relevante Berufserfahrungen:
"""
    for idx, exp in enumerate(experiences, 1):
        prompt += f"{idx}. {exp}\n"
    prompt += "\nNur die Zahl zurückgeben, keine weiteren Erklärungen."

    # Anfrage an ChatGPT
    response = ask_chatgpt_single_prompt(prompt, model="gpt-3.5-turbo", temperature=0.0)

    # Extrahiere eine Zahl
    m = re.search(r"(\d{1,3}(?:\.\d+)?)", response)
    if not m:
        return None
    score = float(m.group(1))
    # Begrenze auf 0–100
    return max(0.0, min(100.0, score))

def refine_experiences_list(job_description, retrieved_docs, experiences_html):
    """
    Fragt bei ChatGPT nach, ob die drei HTML-Experience-Einträge 
    wirklich die relevantesten sind, basierend auf:
      - der Stellenanzeige (job_description)
      - den ursprünglichen Retrieval-Dokumenten (retrieved_docs)
      - der aktuellen HTML-Liste (experiences_html)
    Gibt immer eine HTML-Liste mit exakt drei <li> zurück.
    """
    # Roh-Dokumente aufzählen
    docs_text = "\n".join(f"{i+1}. {doc}" for i, doc in enumerate(retrieved_docs))

    prompt = f"""Du bist ein Bewerber-Matching-Experte.

    Stellenanzeige (reduziert):
    {job_description}

    Roh-Dokumente aus dem RAG (Top-5):
    {docs_text}

    Aktuelle Auswahl der Top-3 Berufserfahrungen als HTML-Liste:
    {experiences_html}

    1. Bewerte anhand der Stellenanzeige, ob diese drei Einträge wirklich die relevantesten sind.
    2. Falls ja, antworte nur mit der unveränderten HTML-Liste.
    3. Falls nein, wähle aus den obigen 5 Roh-Dokumenten die drei passendsten aus
    und liefere sie als neue HTML-Liste mit genau drei <li>…</li> zurück.
    4. Gib ausschließlich die endgültige HTML-Liste zurück (ohne Erklärung)."""

    return ask_chatgpt_single_prompt(prompt, model="gpt-3.5-turbo", temperature=0.0)

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
        print(f"🎯 Passgenauigkeit laut ChatGPT: {score:.1f}%")
    
    return response