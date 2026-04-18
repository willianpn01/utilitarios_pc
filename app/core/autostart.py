"""
Autostart Manager - Gerencia início automático com o sistema operacional.

Suporta:
- Windows: Registro do Windows (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)
- Linux: Arquivo .desktop em ~/.config/autostart/ (padrão XDG)
- macOS: LaunchAgent plist em ~/Library/LaunchAgents/
"""
from __future__ import annotations

import os
import sys

from app.core.app_paths import is_windows, is_linux, is_macos, APP_NAME, APP_DISPLAY_NAME


def get_app_path() -> str:
    """Retorna o caminho do executável ou script principal."""
    if getattr(sys, 'frozen', False):
        # Executável compilado (PyInstaller/Nuitka)
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


# ── Windows ──────────────────────────────────────────────────────────────────

def _is_autostart_enabled_windows() -> bool:
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return bool(value)
        except FileNotFoundError:
            return False
        except OSError:
            return False
    except ImportError:
        return False


def _enable_autostart_windows() -> bool:
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        command = get_startup_command()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return True
        except OSError as e:
            print(f"Erro ao habilitar autostart (Windows): {e}")
            return False
    except ImportError:
        return False


def _disable_autostart_windows() -> bool:
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return True  # Já não existe
        except OSError as e:
            print(f"Erro ao desabilitar autostart (Windows): {e}")
            return False
    except ImportError:
        return False


# ── Linux (XDG Autostart) ────────────────────────────────────────────────────

_DESKTOP_FILENAME = "utilitarios-pc.desktop"


def _get_autostart_dir_linux() -> str:
    """Retorna o diretório de autostart do XDG."""
    xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    autostart_dir = os.path.join(xdg_config, 'autostart')
    return autostart_dir


def _get_desktop_file_path() -> str:
    return os.path.join(_get_autostart_dir_linux(), _DESKTOP_FILENAME)


def _generate_desktop_entry() -> str:
    """Gera o conteúdo do arquivo .desktop para autostart."""
    command = get_startup_command()
    app_path = get_app_path()
    
    # Tentar encontrar o ícone
    icon_path = ""
    possible_icons = [
        os.path.join(os.path.dirname(app_path), "app", "icone.ico"),
        os.path.join(os.path.dirname(app_path), "icone.ico"),
        os.path.join(os.path.dirname(os.path.dirname(app_path)), "app", "icone.ico"),
    ]
    for p in possible_icons:
        if os.path.exists(p):
            icon_path = p
            break
    
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={APP_DISPLAY_NAME}",
        f"Comment=Suite de utilitários para organização de arquivos e produtividade",
        f"Exec={command}",
        f"Icon={icon_path}" if icon_path else "Icon=utilities-file-archiver",
        "Terminal=false",
        "Categories=Utility;FileTools;",
        "StartupNotify=false",
        f"X-GNOME-Autostart-enabled=true",
    ]
    return "\n".join(lines) + "\n"


def _is_autostart_enabled_linux() -> bool:
    desktop_path = _get_desktop_file_path()
    if not os.path.exists(desktop_path):
        return False
    # Verificar se não está desabilitado dentro do arquivo
    try:
        with open(desktop_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Procurar X-GNOME-Autostart-enabled=false ou Hidden=true
        for line in content.splitlines():
            line = line.strip()
            if line.lower() == 'x-gnome-autostart-enabled=false':
                return False
            if line.lower() == 'hidden=true':
                return False
        return True
    except OSError:
        return False


def _enable_autostart_linux() -> bool:
    try:
        autostart_dir = _get_autostart_dir_linux()
        os.makedirs(autostart_dir, exist_ok=True)
        
        desktop_path = _get_desktop_file_path()
        content = _generate_desktop_entry()
        
        with open(desktop_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Tornar executável (embora não seja estritamente necessário para .desktop)
        os.chmod(desktop_path, 0o644)
        return True
    except OSError as e:
        print(f"Erro ao habilitar autostart (Linux): {e}")
        return False


def _disable_autostart_linux() -> bool:
    try:
        desktop_path = _get_desktop_file_path()
        if os.path.exists(desktop_path):
            os.remove(desktop_path)
        return True
    except OSError as e:
        print(f"Erro ao desabilitar autostart (Linux): {e}")
        return False


# ── macOS (LaunchAgent) ──────────────────────────────────────────────────────

_PLIST_FILENAME = "com.utilitarios.pc.plist"


def _get_plist_path() -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{_PLIST_FILENAME}")


def _generate_plist() -> str:
    """Gera o conteúdo do plist para LaunchAgent."""
    app_path = get_app_path()
    
    if app_path.endswith('.py'):
        program_args = f"""    <array>
        <string>{sys.executable}</string>
        <string>{app_path}</string>
        <string>--minimized</string>
    </array>"""
    else:
        program_args = f"""    <array>
        <string>{app_path}</string>
        <string>--minimized</string>
    </array>"""
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.utilitarios.pc</string>
    <key>ProgramArguments</key>
{program_args}
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""


def _is_autostart_enabled_macos() -> bool:
    return os.path.exists(_get_plist_path())


def _enable_autostart_macos() -> bool:
    try:
        plist_path = _get_plist_path()
        os.makedirs(os.path.dirname(plist_path), exist_ok=True)
        
        content = _generate_plist()
        with open(plist_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except OSError as e:
        print(f"Erro ao habilitar autostart (macOS): {e}")
        return False


def _disable_autostart_macos() -> bool:
    try:
        plist_path = _get_plist_path()
        if os.path.exists(plist_path):
            os.remove(plist_path)
        return True
    except OSError as e:
        print(f"Erro ao desabilitar autostart (macOS): {e}")
        return False


# ── API Pública ──────────────────────────────────────────────────────────────

def is_autostart_enabled() -> bool:
    """Verifica se o autostart está habilitado no sistema operacional atual."""
    if is_windows():
        return _is_autostart_enabled_windows()
    elif is_linux():
        return _is_autostart_enabled_linux()
    elif is_macos():
        return _is_autostart_enabled_macos()
    return False


def enable_autostart() -> bool:
    """Habilita início automático com o sistema operacional."""
    if is_windows():
        return _enable_autostart_windows()
    elif is_linux():
        return _enable_autostart_linux()
    elif is_macos():
        return _enable_autostart_macos()
    return False


def disable_autostart() -> bool:
    """Desabilita início automático com o sistema operacional."""
    if is_windows():
        return _disable_autostart_windows()
    elif is_linux():
        return _disable_autostart_linux()
    elif is_macos():
        return _disable_autostart_macos()
    return False


def set_autostart(enabled: bool) -> bool:
    """Define se o autostart está habilitado ou não."""
    if enabled:
        return enable_autostart()
    else:
        return disable_autostart()


def is_autostart_supported() -> bool:
    """Retorna True se o autostart é suportado no sistema operacional atual."""
    return is_windows() or is_linux() or is_macos()
