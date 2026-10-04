"""
Application and crawling configuration module.
Centralizes environment configuration and crawl defaults.
"""
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CrawlConfig(BaseModel):
    """
    Typed configuration contract for scraping jobs.
    Baseline defaults follow Section 6 of Technical Implementation Plan.
    """
    crawl_depth: int = Field(default=2, ge=0, description="Max depth of link traversal (0 = seed only)")
    recursive: bool = Field(default=True, description="Whether to discover and follow hyperlinks")
    javascript_fallback: bool = Field(default=True, description="Enable Playwright fallback for JS-rendered pages")
    robots_mode: Literal["respect", "ignore"] = Field(default="respect", description="Robots.txt compliance mode")
    timeout_seconds: int = Field(default=15, gt=0, le=120, description="Per-request HTTP timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts for transient errors")
    domain_rate_limit: float = Field(default=2.0, gt=0, description="Max requests per second per domain")
    max_concurrency: int = Field(default=3, gt=0, le=20, description="Global concurrency ceiling")


class Settings(BaseSettings):
    """
    Application-level settings loaded from environment or .env file.
    """
    app_env: str = Field(default="development", description="Application environment: development | testing | production")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/web_data_acq",
        description="PostgreSQL connection string. If postgresql:// is provided, it will be converted to postgresql+asyncpg://"
    )
    output_dir: str = Field(default="./output", description="Root directory for media files and JSON exports")
    log_level: str = Field(default="INFO", description="Logging level: DEBUG | INFO | WARNING | ERROR")

    # Default crawl parameters
    default_crawl_depth: int = 2
    default_recursive: bool = True
    default_javascript_fallback: bool = True
    default_robots_mode: Literal["respect", "ignore"] = "respect"
    default_timeout_seconds: int = 15
    default_max_retries: int = 3
    default_domain_rate_limit: float = 2.0
    default_max_concurrency: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_async_database_url(self) -> str:
        """
        Ensures the database connection URL is formatted for asyncpg.
        Converts standard postgresql:// to postgresql+asyncpg://.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    def get_default_crawl_config(self) -> CrawlConfig:
        """Returns the baseline CrawlConfig instance."""
        return CrawlConfig(
            crawl_depth=self.default_crawl_depth,
            recursive=self.default_recursive,
            javascript_fallback=self.default_javascript_fallback,
            robots_mode=self.default_robots_mode,
            timeout_seconds=self.default_timeout_seconds,
            max_retries=self.default_max_retries,
            domain_rate_limit=self.default_domain_rate_limit,
            max_concurrency=self.default_max_concurrency,
        )


settings = Settings()
