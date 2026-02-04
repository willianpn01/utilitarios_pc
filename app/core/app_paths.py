"""
App Paths - Gerenciamento centralizado de caminhos do aplicativo.

Este módulo centraliza todos os caminhos usados pelo aplicativo,
facilitando a configuração para instaladores e desinstaladores.
"""
from __future__ import annotations

import os
import platform
from typing import Optional

# Nome do aplicativo (usado em vários lugares)
APP_NAME = "UtilitariosPC"
APP_ORG = "Projeto Utilitarios"
APP_DISPLAY_NAME = "Utilitários PC"

# Registro do Windows
REGISTRY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_SETTINGS_KEY = rf"Software\{APP_ORG}\{APP_DISPLAY_NAME}"


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


def get_all_data_paths() -> dict:
    """
    Retorna um dicionário com todos os caminhos de dados do aplicativo.
    
    Útil para instaladores/desinstaladores.
    """
    return {
        "data_dir": get_data_dir(),
        "undo_history": get_undo_history_dir(),
        "watcher_config": get_watcher_config_path(),
        "clipboard_db": get_clipboard_db_path(),
    }


def get_registry_paths() -> dict:
    """
    Retorna caminhos do registro do Windows usados pelo aplicativo.
    
    Útil para desinstaladores removerem entradas do registro.
    """
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
    if platform.system() == 'Windows':
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
    
    return results


def print_data_locations():
    """Imprime todos os locais de dados (útil para debug)."""
    print("=" * 50)
    print(f"Dados do {APP_DISPLAY_NAME}")
    print("=" * 50)
    
    paths = get_all_data_paths()
    for name, path in paths.items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  [{exists}] {name}: {path}")
    
    print()
    print("Registro do Windows:")
    registry = get_registry_paths()
    for name, info in registry.items():
        print(f"  - {name}: {info['hive']}\\{info['key']}")
    
    print("=" * 50)


if __name__ == "__main__":
    # Se executado diretamente, mostra informações
    print_data_locations()
