from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5-coder:7b"
    fallback_model: str = "qwen2.5-coder:7b"
    ollama_timeout: int = 120

    # App
    app_name: str = "WebForge AI"
    debug: bool = False

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
