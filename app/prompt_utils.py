import tiktoken

DEFAULT_MODEL = "gpt-4o"

def count_tokens(text: str, model: str = DEFAULT_MODEL) -> int:
    """
    Zählt die Tokens eines Strings basierend auf dem Modell.
    """
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))