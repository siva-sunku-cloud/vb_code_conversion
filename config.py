import os
from dotenv import load_dotenv

load_dotenv()
# Some comment


# Default models per provider — override any of these via .env
_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {
        "agent": "claude-sonnet-4-6",
        "hub":   "claude-opus-4-7",
    },
    "openai": {
        "agent": "gpt-4o",
        "hub":   "gpt-4o",
    },
    "gemini": {
        "agent": "gemini/gemini-1.5-pro",
        "hub":   "gemini/gemini-1.5-pro",
    },
    # GitHub Copilot — uses GITHUB_TOKEN, model names are prefixed with "github/"
    "copilot": {
        "agent": "github/gpt-4o",
        "hub":   "github/gpt-4o",
    },
    # Azure OpenAI — model names are prefixed with "azure/<deployment-name>"
    "azure": {
        "agent": "azure/gpt-4o",
        "hub":   "azure/gpt-4o",
    },
}


class Config:
    # ── LLM provider ──────────────────────────────────────────────────────────
    # Set LLM_PROVIDER to: anthropic | openai | gemini | copilot
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic").lower()

    # API keys — only the one matching LLM_PROVIDER needs to be set
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str    = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str    = os.getenv("GEMINI_API_KEY", "")
    GITHUB_COPILOT_TOKEN: str = os.getenv("GITHUB_COPILOT_TOKEN", "")

    # Custom endpoint — set when using a company proxy instead of the provider's default URL.
    # LiteLLM passes this as api_base; leave empty to use the provider's standard endpoint.
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "")

    # Azure OpenAI — populated by setup when LLM_PROVIDER=azure
    AZURE_API_BASE: str    = os.getenv("AZURE_API_BASE", "")
    AZURE_DEPLOYMENT: str  = os.getenv("AZURE_DEPLOYMENT", "")
    AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")

    # Ollama — used only for vectordb embeddings (translation memory)
    OLLAMA_BASE_URL: str    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "")  # empty = hash fallback

    # Models — defaults come from the table above; override per-agent in .env
    AGENT_MODEL: str = os.getenv(
        "AGENT_MODEL", _DEFAULTS.get(os.getenv("LLM_PROVIDER", "anthropic").lower(), _DEFAULTS["anthropic"])["agent"]
    )
    HUB_MODEL: str = os.getenv(
        "HUB_MODEL", _DEFAULTS.get(os.getenv("LLM_PROVIDER", "anthropic").lower(), _DEFAULTS["anthropic"])["hub"]
    )

    # ── Folders ───────────────────────────────────────────────────────────────
    DATA_FOLDER: str = os.path.expanduser(os.getenv("DATA_FOLDER", "~/data_code_conversion"))
    LOG_FOLDER:  str = os.path.expanduser(os.getenv("LOG_FOLDER",  "~/data_code_conversion/logs"))

    # ── Logging ───────────────────────────────────────────────────────────────
    # Set LOG_LEVEL to DEBUG | INFO | WARNING | ERROR | CRITICAL
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG").upper()

    # ── Pipeline ──────────────────────────────────────────────────────────────
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_URL: str        = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str    = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = "java_python_patterns"

    # ── GitHub ────────────────────────────────────────────────────────────────
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str  = os.getenv("GITHUB_REPO", "")
