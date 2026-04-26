"""
Testes de comportamento Windows-específico usando mocks.

Rodam em QUALQUER sistema operacional. Mockam `sys.platform` e os módulos
nativos do Windows (winreg, ctypes) para exercitar os branches de código
que só executam no Windows em produção.

Cobrem:
  - Seleção correta de backend de autostart (winreg vs .desktop vs plist)
  - Seleção correta de backend de single-instance lock
  - Construção do comando de startup

Para testes que exigem o SO real (winreg vivo, mutex nativo), ver
`test_windows_specific.py`.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ─── Autostart ─────────────────────────────────────────────────────────────

def test_autostart_uses_windows_backend_when_is_windows_true(monkeypatch):
    """is_autostart_enabled() deve delegar para o backend Windows quando is_windows()=True."""
    from app.core import autostart

    with patch.object(autostart, "is_windows", return_value=True), \
         patch.object(autostart, "is_linux", return_value=False), \
         patch.object(autostart, "is_macos", return_value=False), \
         patch.object(autostart, "_is_autostart_enabled_windows", return_value=True) as m_win, \
         patch.object(autostart, "_is_autostart_enabled_linux") as m_lin, \
         patch.object(autostart, "_is_autostart_enabled_macos") as m_mac:
        assert autostart.is_autostart_enabled() is True
        m_win.assert_called_once()
        m_lin.assert_not_called()
        m_mac.assert_not_called()


def test_autostart_enable_routes_to_windows_backend():
    from app.core import autostart

    with patch.object(autostart, "is_windows", return_value=True), \
         patch.object(autostart, "is_linux", return_value=False), \
         patch.object(autostart, "is_macos", return_value=False), \
         patch.object(autostart, "_enable_autostart_windows", return_value=True) as m:
        assert autostart.enable_autostart() is True
        m.assert_called_once()


def test_autostart_disable_routes_to_windows_backend():
    from app.core import autostart

    with patch.object(autostart, "is_windows", return_value=True), \
         patch.object(autostart, "is_linux", return_value=False), \
         patch.object(autostart, "is_macos", return_value=False), \
         patch.object(autostart, "_disable_autostart_windows", return_value=True) as m:
        assert autostart.disable_autostart() is True
        m.assert_called_once()


def test_autostart_windows_uses_registry_api_correctly():
    """Valida que o backend Windows chama winreg com a chave CORRETA."""
    from app.core import autostart

    fake_winreg = MagicMock()
    fake_winreg.HKEY_CURRENT_USER = "HKCU_FAKE"
    fake_winreg.KEY_SET_VALUE = 2
    fake_winreg.REG_SZ = 1
    fake_key = MagicMock()
    fake_winreg.OpenKey.return_value = fake_key

    with patch.dict(sys.modules, {"winreg": fake_winreg}):
        ok = autostart._enable_autostart_windows()

    assert ok is True
    # Deve ter aberto a chave correta
    fake_winreg.OpenKey.assert_called_once()
    args, _ = fake_winreg.OpenKey.call_args
    assert args[0] == "HKCU_FAKE"
    assert args[1] == r"Software\Microsoft\Windows\CurrentVersion\Run"
    # Deve ter gravado um valor
    fake_winreg.SetValueEx.assert_called_once()
    name_arg = fake_winreg.SetValueEx.call_args[0][1]
    assert name_arg == autostart.APP_NAME
    fake_winreg.CloseKey.assert_called_once_with(fake_key)


def test_autostart_windows_disable_handles_missing_key_as_success():
    """Desabilitar quando a entrada não existe deve retornar True (já não está habilitado)."""
    from app.core import autostart

    fake_winreg = MagicMock()
    fake_key = MagicMock()
    fake_winreg.OpenKey.return_value = fake_key
    fake_winreg.DeleteValue.side_effect = FileNotFoundError()

    with patch.dict(sys.modules, {"winreg": fake_winreg}):
        assert autostart._disable_autostart_windows() is True


def test_autostart_enabled_windows_returns_false_when_key_missing():
    from app.core import autostart

    fake_winreg = MagicMock()
    fake_winreg.OpenKey.side_effect = FileNotFoundError()

    with patch.dict(sys.modules, {"winreg": fake_winreg}):
        assert autostart._is_autostart_enabled_windows() is False


def test_startup_command_quotes_path_with_spaces(monkeypatch, tmp_path):
    """
    Em Windows, o path do executável pode ter espaços ('C:\\Program Files\\...').
    O comando de startup DEVE estar entre aspas, senão o Windows quebra.
    """
    from app.core import autostart

    # Simula um executável congelado (PyInstaller) com path contendo espaço
    fake_exe = tmp_path / "Program Files" / "Utilitarios.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    cmd = autostart.get_startup_command()
    assert cmd.startswith('"'), f"Comando não começa com aspas: {cmd}"
    assert str(fake_exe) in cmd
    assert "--minimized" in cmd


# ─── Paths ─────────────────────────────────────────────────────────────────

def test_app_paths_detect_windows_platform():
    """is_windows() deve refletir corretamente sys.platform='win32'."""
    from app.core import app_paths
    with patch.object(sys, "platform", "win32"):
        # Recarrega o cache se necessário — algumas implementações calculam no import
        assert app_paths.is_windows() is True
        assert app_paths.is_linux() is False
        assert app_paths.is_macos() is False


def test_app_paths_detect_linux_platform():
    from app.core import app_paths
    with patch.object(sys, "platform", "linux"):
        assert app_paths.is_linux() is True
        assert app_paths.is_windows() is False
        assert app_paths.is_macos() is False


# ─── Smoke imports específicos do Windows ──────────────────────────────────

def test_autostart_module_imports_without_winreg():
    """
    autostart.py deve importar limpo em Linux/macOS (onde winreg não existe).
    O import de winreg é feito lazy, dentro das funções Windows-specific.
    """
    import importlib
    from app.core import autostart
    importlib.reload(autostart)
    # Se chegou aqui, importou sem erro.
    assert hasattr(autostart, "is_autostart_enabled")
    assert hasattr(autostart, "enable_autostart")
    assert hasattr(autostart, "disable_autostart")
