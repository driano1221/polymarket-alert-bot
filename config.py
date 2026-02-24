import os
from dotenv import load_dotenv

load_dotenv()


def _int(key: str, default: int = 0) -> int:
    """Lê variável como int; retorna default se estiver ausente ou inválida."""
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _float(key: str, default: float = 0.0) -> float:
    """Lê variável como float; retorna default se estiver ausente ou inválida."""
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


# Telegram - Fontes
TELEGRAM_API_ID   = _int("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE    = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_SOURCE_CHANNELS = [
    c.strip()
    for c in os.getenv("TELEGRAM_SOURCE_CHANNELS", "").split(",")
    if c.strip()
]

# Telegram - Alertas
TELEGRAM_BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALERT_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID", "")

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")

# Bot config
MIN_EDGE_THRESHOLD = _float("MIN_EDGE_THRESHOLD", 0.07)
CHECK_INTERVAL     = _int("CHECK_INTERVAL", 60)
