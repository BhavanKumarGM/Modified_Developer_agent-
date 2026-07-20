from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5-coder:7b"
    fallback_model: str = "qwen2.5-coder:7b"
    ollama_timeout: int = 120

    # Local embeddings for semantic search (SearchAgent). Requires
    # `ollama pull nomic-embed-text` — if it's not pulled, SearchAgent falls
    # back to keyword/glob search only (see search_agent.py).
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768

    # App
    app_name: str = "WebForge AI"
    debug: bool = False

    # Server bind address — defaults to loopback-only. This is a single-user,
    # unauthenticated local tool: binding 0.0.0.0 exposes it to the network
    # with no auth, so it must be an explicit opt-in via HOST, never the default.
    host: str = "127.0.0.1"
    port: int = 8000

    # Chat abuse limits
    max_message_length: int = 20_000
    chat_rate_limit_per_minute: int = 30

    # Minimum ReviewAgent score (0-10) required before generated/edited
    # files are written to disk. Below this, changes are held back and the
    # issues are surfaced to the user instead.
    review_score_threshold: int = 5

    # Storage
    projects_dir: Path = Path("../projects")
    db_url: str = "sqlite+aiosqlite:///./webforge.db"

    # Preview server ports range
    preview_port_start: int = 3100
    preview_port_end: int = 3200

    # File upload limits
    max_zip_size_mb: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
settings.projects_dir.mkdir(parents=True, exist_ok=True)
