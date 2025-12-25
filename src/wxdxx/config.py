"""Configuration management for WxDXX."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration with defaults."""

    tracked_wfos: list[str] = Field(default_factory=list)
    refresh_interval: int = Field(default=60, ge=10, le=600)

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the config file path."""
        return Path.home() / ".config" / "wxdxx" / "config.toml"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from file, returning defaults if not found."""
        config_path = cls.get_config_path()

        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            return cls.model_validate(data)
        except Exception:
            # Graceful fallback to defaults on corrupt config
            return cls()

    def save(self) -> None:
        """Save config to file, creating directory if needed."""
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("# WxDXX Configuration")
        lines.append("")
        lines.append(f"refresh_interval = {self.refresh_interval}")
        lines.append("")

        if self.tracked_wfos:
            wfos_str = ", ".join(f'"{wfo}"' for wfo in self.tracked_wfos)
            lines.append(f"tracked_wfos = [{wfos_str}]")
        else:
            lines.append("tracked_wfos = []")

        lines.append("")

        config_path.write_text("\n".join(lines))
