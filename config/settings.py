"""
AquaFlora Stock Sync - Configuration Settings
Pydantic Settings for type-safe configuration from .env
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # WooCommerce API
    woo_url: str = Field(default="https://aquafloragroshop.com.br")
    woo_consumer_key: str = Field(default="")
    woo_consumer_secret: str = Field(default="")
    
    # Paths
    input_dir: Path = Field(default=Path("./data/input"))
    output_dir: Path = Field(default=Path("./data/output"))
    db_path: Path = Field(default=Path("./products.db"))
    
    # Processing
    sync_enabled: bool = Field(default=True)
    dry_run: bool = Field(default=False)
    include_zero_stock: bool = Field(default=True)
    min_price: float = Field(default=0.01)
    
    # Safety
    price_guard_max_variation: float = Field(default=40.0)
    zero_ghost_stock: bool = Field(default=False)  # DANGEROUS! Only enable if file contains ALL products
    
    # Notifications
    discord_webhook_url: Optional[str] = Field(default=None)
    telegram_webhook_url: Optional[str] = Field(default=None)
    
    # Discord Bot
    discord_bot_token: Optional[str] = Field(default=None)
    discord_channel_id: Optional[str] = Field(default=None)
    
    # Logging
    log_level: str = Field(default="INFO")
    log_rotation_mb: int = Field(default=10)
    log_json_format: bool = Field(default=False)  # Enable JSON logs for production
    
    # Dashboard Authentication
    dashboard_username: str = Field(default="admin")
    dashboard_password: str = Field(default="")  # Empty = no auth required
    dashboard_auth_enabled: bool = Field(default=False)
    
    # Backup
    backup_enabled: bool = Field(default=False)
    backup_rclone_remote: str = Field(default="gdrive:aquaflora-backup")
    backup_retention_days: int = Field(default=7)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Allow extra env vars like GOOGLE_API_KEY
    
    @property
    def woo_configured(self) -> bool:
        """Check if WooCommerce credentials are configured."""
        return bool(self.woo_consumer_key and self.woo_consumer_secret)
    
    @property
    def discord_webhook_configured(self) -> bool:
        """Check if Discord webhook is configured."""
        return bool(self.discord_webhook_url)
    
    @property
    def discord_bot_configured(self) -> bool:
        """Check if Discord bot is configured."""
        return bool(self.discord_bot_token)
    
    @property
    def backup_configured(self) -> bool:
        """Check if backup is enabled and configured."""
        return self.backup_enabled and bool(self.backup_rclone_remote)


# Singleton instance
settings = Settings()
