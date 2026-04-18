"""
App Paths - Gerenciamento centralizado de caminhos do aplicativo.

Este módulo centraliza todos os caminhos usados pelo aplicativo,
facilitando a configuração para instaladores e desinstaladores.
Suporta Windows, Linux e macOS.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

# Nome do aplicativo (usado em vários lugares)
APP_NAME = "UtilitariosPC"
APP_ORG = "Projeto Utilitarios"
APP_DISPLAY_NAME = "Utilitários PC"

# Registro do Windows (usado apenas no Windows)
REGISTRY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_SETTINGS_KEY = rf"Software\{APP_ORG}\{APP_DISPLAY_NAME}"


# ── Helpers de Plataforma ─────────────────────────────────────────────────────

def is_windows() -> bool:
    """Retorna True se estiver rodando no Windows."""
    return sys.platform.startswith('win')


def is_linux() -> bool:
    """Retorna True se estiver rodando no Linux."""
    return sys.platform.startswith('linux')


def is_macos() -> bool:
    """Retorna True se estiver rodando no macOS."""
    return sys.platform == 'darwin'


# ── Diretórios de Dados ───────────────────────────────────────────────────────

def get_data_dir() -> str:
    """
    Retorna o diretório principal de dados do aplicativo.
    
    Padrão: ~/.utilitarios/
    
    Pode ser sobrescrito pela variável de ambiente UTILITARIOS_DATA_DIR.
    """
    # Verificar variável de ambiente para customização
    custom = os.environ.get('UTILITARIOS_DATA_DIR')
    if custom and os.path.isabs(custom):
        os.makedirs(custom, exist_ok=True)
        return custom
    
    # Padrão: ~/.utilitarios/
    home = os.path.expanduser("~")
    data_dir = os.path.join(home, ".utilitarios")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_config_dir() -> str:
    """Retorna o diretório de configurações do aplicativo."""
    config_dir = os.path.join(get_data_dir(), "config")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_log_dir() -> str:
    """Retorna o diretório de logs do aplicativo."""
    log_dir = os.path.join(get_data_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_undo_history_dir() -> str:
    """Retorna o diretório de histórico de undo."""
    undo_dir = os.path.join(get_data_dir(), "undo_history")
    os.makedirs(undo_dir, exist_ok=True)
    return undo_dir


def get_watcher_config_path() -> str:
    """Retorna o caminho do arquivo de configuração do watcher."""
    return os.path.join(get_data_dir(), "watcher_config.json")


def get_clipboard_db_path() -> str:
    """Retorna o caminho do banco de dados do histórico de clipboard."""
    return os.path.join(get_data_dir(), "clipboard_history.db")


def get_lock_file_path() -> str:
    """Retorna o caminho do arquivo de lock para instância única."""
    return os.path.join(get_data_dir(), "app.lock")


def get_settings_path() -> str:
    """Retorna o caminho do arquivo de configurações."""
    return os.path.join(get_data_dir(), "settings.json")


def get_all_data_paths() -> dict:
    """
    Retorna um dicionário com todos os caminhos de dados do aplicativo.
    
    Útil para instaladores/desinstaladores.
    """
    return {
        "data_dir": get_data_dir(),
        "config_dir": get_config_dir(),
        "log_dir": get_log_dir(),
        "undo_history": get_undo_history_dir(),
        "watcher_config": get_watcher_config_path(),
        "clipboard_db": get_clipboard_db_path(),
        "settings": get_settings_path(),
        "lock_file": get_lock_file_path(),
    }


def get_registry_paths() -> dict:
    """
    Retorna caminhos do registro do Windows usados pelo aplicativo.
    
    Útil para desinstaladores removerem entradas do registro.
    Retorna dicionário vazio em sistemas não-Windows.
    """
    if not is_windows():
        return {}
    
    return {
        "autostart": {
            "key": REGISTRY_RUN_KEY,
            "value_name": APP_NAME,
            "hive": "HKEY_CURRENT_USER"
        },
        "settings": {
            "key": REGISTRY_SETTINGS_KEY,
            "hive": "HKEY_CURRENT_USER"
        }
    }


def remove_all_data() -> dict:
    """
    Remove todos os dados do aplicativo.
    
    CUIDADO: Esta função remove permanentemente todos os dados do usuário!
    
    Retorna um dicionário com o resultado de cada operação.
    """
    import shutil
    results = {}
    
    # Remover diretório de dados
    data_dir = get_data_dir()
    try:
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)
            results["data_dir"] = "removed"
        else:
            results["data_dir"] = "not_found"
    except Exception as e:
        results["data_dir"] = f"error: {e}"
    
    # Remover entradas do registro (Windows)
    if is_windows():
        try:
            import winreg
            
            # Remover autostart
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_RUN_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, APP_NAME)
                winreg.CloseKey(key)
                results["registry_autostart"] = "removed"
            except FileNotFoundError:
                results["registry_autostart"] = "not_found"
            except Exception as e:
                results["registry_autostart"] = f"error: {e}"
            
            # Remover configurações
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY_SETTINGS_KEY)
                results["registry_settings"] = "removed"
            except FileNotFoundError:
                results["registry_settings"] = "not_found"
            except Exception as e:
                results["registry_settings"] = f"error: {e}"
                
        except ImportError:
            results["registry"] = "winreg not available"
    
    # Remover autostart no Linux
    if is_linux():
        desktop_file = os.path.expanduser("~/.config/autostart/utilitarios-pc.desktop")
        try:
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
                results["linux_autostart"] = "removed"
            else:
                results["linux_autostart"] = "not_found"
        except Exception as e:
            results["linux_autostart"] = f"error: {e}"
    
    # Remover autostart no macOS
    if is_macos():
        plist_file = os.path.expanduser("~/Library/LaunchAgents/com.utilitarios.pc.plist")
        try:
            if os.path.exists(plist_file):
                os.remove(plist_file)
                results["macos_autostart"] = "removed"
            else:
                results["macos_autostart"] = "not_found"
        except Exception as e:
            results["macos_autostart"] = f"error: {e}"
    
    return results


def print_data_locations():
    """Imprime todos os locais de dados (útil para debug)."""
    print("=" * 50)
    print(f"Dados do {APP_DISPLAY_NAME}")
    print("=" * 50)
    
    # Plataforma
    platform_name = "Windows" if is_windows() else ("Linux" if is_linux() else ("macOS" if is_macos() else "Desconhecido"))
    print(f"  Plataforma: {platform_name}")
    print()
    
    paths = get_all_data_paths()
    for name, path in paths.items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  [{exists}] {name}: {path}")
    
    if is_windows():
        print()
        print("Registro do Windows:")
        registry = get_registry_paths()
        for name, info in registry.items():
            print(f"  - {name}: {info['hive']}\\{info['key']}")
    
    if is_linux():
        print()
        desktop_file = os.path.expanduser("~/.config/autostart/utilitarios-pc.desktop")
        exists = "✓" if os.path.exists(desktop_file) else "✗"
        print(f"  [{exists}] Autostart (XDG): {desktop_file}")
    
    print("=" * 50)


if __name__ == "__main__":
    # Se executado diretamente, mostra informações
    print_data_locations()
