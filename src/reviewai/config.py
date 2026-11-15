"""Runtime configuration with explicit demo/live isolation."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("REVIEWAI_DATA_DIR", "./data")))
    gemini_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    embedding_model: str = field(default_factory=lambda: os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"))
    openalex_key: str = field(default_factory=lambda: os.getenv("OPENALEX_API_KEY", ""))
    openalex_email: str = field(default_factory=lambda: os.getenv("OPENALEX_EMAIL", ""))
    max_papers: int = field(default_factory=lambda: int(os.getenv("REVIEWAI_MAX_PAPERS", "12")))
    timeout: int = field(default_factory=lambda: int(os.getenv("REVIEWAI_REQUEST_TIMEOUT", "20")))

    def __post_init__(self):
        if not 1 <= self.max_papers <= 100:
            raise ValueError("REVIEWAI_MAX_PAPERS must be between 1 and 100")
        if not 3 <= self.timeout <= 120:
            raise ValueError("REVIEWAI_REQUEST_TIMEOUT must be between 3 and 120")
