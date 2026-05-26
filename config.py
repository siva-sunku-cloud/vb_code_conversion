import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Models
    HUB_MODEL: str = os.getenv("HUB_MODEL", "claude-opus-4-7")
    AGENT_MODEL: str = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")

    # Pipeline
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    COMPLEXITY_THRESHOLD: float = float(os.getenv("COMPLEXITY_THRESHOLD", "0.7"))

    # Qdrant
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = "vb_python_patterns"

    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")
