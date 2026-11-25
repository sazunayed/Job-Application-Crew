import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OUTPUT_DIR = ROOT / "backend" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = ROOT / "frontend"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def _with_provider(model: str) -> str:
    """LiteLLM needs a provider prefix. Groq model ids such as 'qwen/qwen3-32b' or
    'llama-3.3-70b-versatile' are therefore sent as 'groq/<id>'."""
    model = model.strip()
    other_providers = ("openai/", "anthropic/", "gemini/", "ollama/", "openrouter/", "together_ai/", "azure/")
    if model.startswith("groq/") or model.startswith(other_providers):
        return model
    return f"groq/{model}"


# LLM_MODEL is the preferred name; GROQ_MODEL still works for older .env files.
GROQ_MODEL = _with_provider(os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# The key that matches the chosen model: openrouter/... models use the OpenRouter key, everything else Groq's.
API_KEY = OPENROUTER_API_KEY if GROQ_MODEL.startswith("openrouter/") else GROQ_API_KEY
KEY_NAME = "OPENROUTER_API_KEY" if GROQ_MODEL.startswith("openrouter/") else "GROQ_API_KEY"
IS_OPENROUTER = GROQ_MODEL.startswith("openrouter/")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Output tokens per answer. Lower it if your model has a small per-minute output limit.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "3500"))
# Automatic retries on rate limits (LiteLLM waits for the time Groq asks for, up to 60s each).
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "6"))

# Keep scraped text small so we stay inside Groq token limits
MAX_JOB_CHARS = 6000
MAX_GITHUB_CHARS = 5000
MAX_RESUME_CHARS = 6000
# Pause (seconds) after each agent finishes. Helps on models with a small tokens-per-minute limit
# (e.g. 8000 TPM): 15-25 usually lets the per-minute window recover. 0 = no pause.
LLM_COOLDOWN_SECONDS = int(os.getenv("LLM_COOLDOWN_SECONDS", "0"))
# A scraped job page shorter than this is treated as "no real content" (JS-rendered or blocked page).
MIN_JOB_CHARS = 300
