# Application settings and configuration

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: List[str] = ["http://localhost:8080", "http://127.0.0.1:8080"]

    # Rembg model
    rembg_model: str = "isnet-general-use"

    # Image processing limits
    max_image_size_mb: int = 15

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()