"""
Autostart Manager - Gerencia início automático com o Windows.

Adiciona/remove entrada no registro do Windows para iniciar o app automaticamente.
"""
from __future__ import annotations

import os
import sys
import platform


def get_app_path() -> str:
    """Retorna o caminho do executável ou script principal."""
    if getattr(sys, 'frozen', False):
        # Executável compilado (PyInstaller)
        return sys.executable
    else:
        # Script Python
        return os.path.abspath(sys.argv[0])


def get_startup_command() -> str:
    """Retorna o comando para iniciar o aplicativo."""
    app_path = get_app_path()
    
    if app_path.endswith('.py'):
        # Se for script Python, usar o interpretador
        python_exe = sys.executable
        return f'"{python_exe}" "{app_path}" --minimized'
    else:
        # Executável direto
        return f'"{app_path}" --minimized'


def is_windows() -> bool:
    """Verifica se está rodando no Windows."""
    return platform.system() == 'Windows'


def is_autostart_enabled() -> bool:
    """Verifica se o autostart está habilitado."""
    if not is_windows():
        return False
    
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "UtilitariosPC"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return bool(value)
        except FileNotFoundError:
            return False
        except WindowsError:
            return False
    except ImportError:
        return False


def enable_autostart() -> bool:
    """Habilita início automático com o Windows."""
    if not is_windows():
        return False
    
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "UtilitariosPC"
        command = get_startup_command()
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return True
        except WindowsError as e:
            print(f"Erro ao habilitar autostart: {e}")
            return False
    except ImportError:
        return False


def disable_autostart() -> bool:
    """Desabilita início automático com o Windows."""
    if not is_windows():
        return False
    
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "UtilitariosPC"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            # Já não existe
            return True
        except WindowsError as e:
            print(f"Erro ao desabilitar autostart: {e}")
            return False
    except ImportError:
        return False


def set_autostart(enabled: bool) -> bool:
    """Define se o autostart está habilitado ou não."""
    if enabled:
        return enable_autostart()
    else:
        return disable_autostart()
