import os
from openai import OpenAI
from openai.types.chat import ChatCompletion
from openai.types.completion_usage import CompletionUsage
from prompt_utils import count_tokens, DEFAULT_MODEL

# Client initialisieren – API-Key wird über Umgebungsvariable erwartet
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_chatgpt_single_prompt(prompt: str, model: str = "gpt-4", temperature: float = 0.2) -> str:
    """Sendet einen einfachen Prompt an ChatGPT und gibt die Antwort als Text zurück."""
    try:
        response: ChatCompletion = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"❌ Fehler bei der Anfrage an ChatGPT: {e}")

def validate_prompt_length(prompt: str, model: str = "gpt-4", max_tokens: int = 8192):
    """Warnung, wenn der Prompt zu lang ist für das angegebene Modell."""
    word_count = len(prompt.split())
    char_count = len(prompt)

    if word_count > 3000 or char_count > max_tokens * 4:
        raise ValueError(
            f"⚠️ Prompt möglicherweise zu lang ({word_count} Wörter, {char_count} Zeichen) "
            f"für {model} mit max. {max_tokens} Tokens. Bitte prüfen oder kürzen."
        )

def build_prompt(job_text: str, experiences: list[str], model: str = DEFAULT_MODEL, max_tokens: int = 8000) -> str:
    """
    Baut einen Prompt zur Auswahl der 3 relevantesten Erfahrungen aus der Liste.
    """
    # Einleitung + Systeminstruktion
    intro = (
        "Du bist ein Karrierecoach. Deine Aufgabe ist es, aus den folgenden Berufserfahrungen die "
        "drei relevantesten für die unten stehende Stellenanzeige auszuwählen.\n"
        "Gib sie als strukturierte Liste mit Stichpunkten zurück. Jede Erfahrung soll einen Titel, "
        "eine kurze Beschreibung (max. 2 Sätze) und die Dauer enthalten."
    )

    job_section = f"\n\n📌 **Stellenanzeige**:\n{job_text.strip()}"
    exp_section = "\n\n📚 **Berufserfahrungen**:\n" + "\n---\n".join(experiences)

    full_prompt = f"{intro}{job_section}{exp_section}"

    # Token-Länge prüfen
    validate_prompt_length(full_prompt, model=model, max_tokens=max_tokens)
    return full_prompt