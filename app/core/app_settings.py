"""
Utilitários PC — Gerenciamento de configurações persistentes.

As configurações são salvas em JSON no diretório de dados do aplicativo:
  ~/.utilitarios/settings.json
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from app.core.app_paths import get_settings_path


def _settings_path() -> Path:
    return Path(get_settings_path())


def _load_all() -> dict:
    p = _settings_path()
    if not p.exists():
        return {}
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def load_setting(key: str, default: Any = None) -> Any:
    """Carrega uma configuração pelo nome da chave."""
    return _load_all().get(key, default)


def save_setting(key: str, value: Any) -> None:
    """Persiste uma configuração pelo nome da chave."""
    settings = _load_all()
    settings[key] = value
    p = _settings_path()
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except OSError:
        pass  # Falha silenciosa — sem acesso a disco não deve travar a UI
