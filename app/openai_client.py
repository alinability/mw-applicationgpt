import os
from dotenv import load_dotenv, find_dotenv
# Lade Umgebungsvariablen aus .env
load_dotenv(find_dotenv())

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