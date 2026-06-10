from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    bot_token: str
    bot_username: str
    admin_ids: str = ""

    @property
    def admins(self) -> set[int]:
        if not self.admin_ids:
            return set()
        return {int(x.strip()) for x in self.admin_ids.split(",") if x.strip().isdigit()}

    # DB / Redis
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    download_dir: Path = Path("./storage/downloads")
    max_filesize_mb: int = 48
    max_duration_seconds: int = 3600

    # Logging
    log_level: str = "INFO"


settings = Settings()
settings.download_dir.mkdir(parents=True, exist_ok=True)
