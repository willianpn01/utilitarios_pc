"""
Watcher Config - Persistência das configurações do monitoramento de pastas.

Salva e carrega configurações em arquivo JSON no diretório do usuário.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

from app.core.auto_organizer import default_mapping, parse_rules, OrganizeRule


@dataclass
class WatchConfig:
    """Configuração de uma pasta monitorada."""
    path: str
    rules_text: str  # Texto das regras no formato "Categoria: .ext1, .ext2"
    enabled: bool = True
    
    def get_rule(self) -> OrganizeRule:
        """Converte o texto das regras em OrganizeRule."""
        rule = parse_rules(self.rules_text)
        rule.recursive = False  # Watchdog não precisa de recursivo, monitora eventos
        return rule


def get_config_dir() -> str:
    """Retorna o diretório de configuração do aplicativo."""
    home = os.path.expanduser("~")
    config_dir = os.path.join(home, ".utilitarios")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_config_path() -> str:
    """Retorna o caminho do arquivo de configuração."""
    return os.path.join(get_config_dir(), "watcher_config.json")


@dataclass
class WatcherSettings:
    """Configurações globais do watcher."""
    watches: List[WatchConfig]
    minimize_to_tray: bool = True
    auto_start_monitoring: bool = False
    show_notifications: bool = True
    
    def to_dict(self) -> dict:
        """Converte para dicionário serializável."""
        return {
            "watches": [
                {
                    "path": w.path,
                    "rules_text": w.rules_text,
                    "enabled": w.enabled
                }
                for w in self.watches
            ],
            "minimize_to_tray": self.minimize_to_tray,
            "auto_start_monitoring": self.auto_start_monitoring,
            "show_notifications": self.show_notifications
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WatcherSettings":
        """Cria instância a partir de dicionário."""
        watches = []
        for w in data.get("watches", []):
            watches.append(WatchConfig(
                path=w.get("path", ""),
                rules_text=w.get("rules_text", ""),
                enabled=w.get("enabled", True)
            ))
        
        return cls(
            watches=watches,
            minimize_to_tray=data.get("minimize_to_tray", True),
            auto_start_monitoring=data.get("auto_start_monitoring", False),
            show_notifications=data.get("show_notifications", True)
        )


def get_default_rules_text() -> str:
    """Retorna texto das regras padrão."""
    mapping = default_mapping()
    lines = []
    for category, extensions in mapping.items():
        exts = ", ".join(extensions)
        lines.append(f"{category}: {exts}")
    return "\n".join(lines)


def load_settings() -> WatcherSettings:
    """Carrega configurações do arquivo."""
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        return WatcherSettings(watches=[])
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return WatcherSettings.from_dict(data)
    except (json.JSONDecodeError, IOError):
        return WatcherSettings(watches=[])


def save_settings(settings: WatcherSettings) -> bool:
    """Salva configurações no arquivo."""
    config_path = get_config_path()
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)
        return True
    except IOError:
        return False


def add_watch_config(path: str, rules_text: Optional[str] = None) -> WatcherSettings:
    """Adiciona uma nova pasta às configurações."""
    settings = load_settings()
    
    # Verificar se já existe
    for w in settings.watches:
        if os.path.normpath(w.path) == os.path.normpath(path):
            return settings
    
    # Usar regras padrão se não fornecidas
    if rules_text is None:
        rules_text = get_default_rules_text()
    
    settings.watches.append(WatchConfig(
        path=path,
        rules_text=rules_text,
        enabled=True
    ))
    
    save_settings(settings)
    return settings


def remove_watch_config(path: str) -> WatcherSettings:
    """Remove uma pasta das configurações."""
    settings = load_settings()
    
    settings.watches = [
        w for w in settings.watches
        if os.path.normpath(w.path) != os.path.normpath(path)
    ]
    
    save_settings(settings)
    return settings


def update_watch_config(
    path: str,
    enabled: Optional[bool] = None,
    rules_text: Optional[str] = None
) -> WatcherSettings:
    """Atualiza configuração de uma pasta."""
    settings = load_settings()
    
    for w in settings.watches:
        if os.path.normpath(w.path) == os.path.normpath(path):
            if enabled is not None:
                w.enabled = enabled
            if rules_text is not None:
                w.rules_text = rules_text
            break
    
    save_settings(settings)
    return settings
