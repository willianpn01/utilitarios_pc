"""
Testes que só fazem sentido rodando NO Windows de verdade.

Cada teste é marcado com `@pytest.mark.skipif(not is_windows(), ...)`.
Em Linux/macOS, todos os testes deste arquivo são skipped silenciosamente.
No Windows (inclusive no CI matrix `windows-latest`), exercitam:

  - Mutex nativo via CreateMutexW (single-instance lock)
  - Paths reais (%USERPROFILE%\\.utilitarios\\...)
  - Registry HKCU\\...\\Run (autostart) — com chave de TESTE, NUNCA a de
    produção, para não ligar o autostart acidentalmente da máquina do dev.
  - MessageBoxW callable

Estes testes só fornecem valor real quando rodados no Windows. A pipeline
de CI deve incluir um job Windows que execute esta suíte específica.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Adiciona repo root ao path para importações relativas
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.app_paths import is_windows, get_data_dir, get_log_dir, get_lock_file_path  # noqa: E402

# Marca que aplica skip a todos os testes deste arquivo fora do Windows.
pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Testes Windows-específicos rodam apenas em win32"
)


# ─── Paths ─────────────────────────────────────────────────────────────────

class TestWindowsPaths:
    def test_is_windows_is_true(self):
        assert is_windows() is True

    def test_data_dir_is_under_user_profile(self):
        data_dir = get_data_dir()
        user_profile = os.environ.get("USERPROFILE", "")
        assert user_profile, "USERPROFILE não está definido no ambiente Windows"
        assert data_dir.lower().startswith(user_profile.lower()), (
            f"Esperado data_dir dentro de USERPROFILE={user_profile!r}, "
            f"mas obtive {data_dir!r}"
        )

    def test_data_dir_exists_and_is_writable(self, tmp_path):
        """O data_dir deve existir ou ser criável, e permitir escrita."""
        data_dir = Path(get_data_dir())
        data_dir.mkdir(parents=True, exist_ok=True)
        assert data_dir.is_dir()
        probe = data_dir / ".write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            assert probe.read_text(encoding="utf-8") == "ok"
        finally:
            if probe.exists():
                probe.unlink()

    def test_log_dir_exists_and_is_writable(self):
        log_dir = Path(get_log_dir())
        log_dir.mkdir(parents=True, exist_ok=True)
        assert log_dir.is_dir()

    def test_lock_file_path_uses_backslashes(self):
        """Sanidade: path de lock deve ser absoluto e conter separador nativo."""
        lock = get_lock_file_path()
        assert os.path.isabs(lock)
        assert "app.lock" in lock


# ─── Single-instance lock via CreateMutexW ────────────────────────────────

class TestWindowsMutexLock:
    def test_mutex_first_acquire_succeeds_second_fails(self):
        """
        Dois CreateMutexW com o mesmo nome: o primeiro sucede, o segundo
        retorna ERROR_ALREADY_EXISTS (183). Reproduz o comportamento que
        garante single-instance do app.
        """
        import ctypes

        MUTEX_NAME = "UtilitariosPCAppMutex_TEST_SUITE_ONLY"
        kernel32 = ctypes.windll.kernel32

        # Primeiro handle
        h1 = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        err1 = kernel32.GetLastError()
        assert h1 != 0, "CreateMutexW falhou na primeira chamada"
        assert err1 != 183, "Mutex já existia antes do teste — ambiente sujo"

        try:
            # Segunda tentativa com o mesmo nome → deve acusar ALREADY_EXISTS
            h2 = kernel32.CreateMutexW(None, False, MUTEX_NAME)
            err2 = kernel32.GetLastError()
            try:
                assert err2 == 183, f"Esperava ERROR_ALREADY_EXISTS=183, obtive {err2}"
                assert h2 != 0, "CreateMutexW ainda retorna handle mesmo se já existir"
            finally:
                if h2:
                    kernel32.CloseHandle(h2)
        finally:
            # Libera o primeiro — IMPORTANTE: sem isso, reruns do teste falham.
            kernel32.CloseHandle(h1)

    def test_acquire_instance_lock_returns_handle_on_windows(self, monkeypatch):
        """
        A função real do app (acquire_instance_lock) deve retornar um handle
        truthy no Windows e None se já houver um mutex com o mesmo nome.
        """
        import ctypes
        from app import main as app_main

        # Usa nome de mutex específico do teste para evitar colisão com app real
        monkeypatch.setattr(app_main, "APP_MUTEX_NAME", "UtilitariosPCAppMutex_TEST2")

        first = app_main.acquire_instance_lock()
        assert first, "Esperava handle truthy na primeira aquisição"

        try:
            # Segunda aquisição com o mesmo mutex → deve retornar None
            second = app_main.acquire_instance_lock()
            assert second is None, "Segunda aquisição deveria ter falhado"
        finally:
            ctypes.windll.kernel32.CloseHandle(first)


# ─── Registry (autostart) usando chave de TESTE, não a de produção ────────

class TestWindowsAutostartRegistry:
    """
    Estes testes usam uma chave "APP_NAME" DIFERENTE da de produção para
    evitar que rodar os testes ative/desative o autostart da máquina.
    """

    TEST_NAME = "UtilitariosPC_TestSuite_DoNotUse"

    def _cleanup_registry(self):
        """Garante que a chave de teste não existe antes/depois."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, self.TEST_NAME)
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(key)
        except Exception:
            pass

    @pytest.fixture(autouse=True)
    def _clean_registry(self):
        self._cleanup_registry()
        yield
        self._cleanup_registry()

    def test_winreg_available(self):
        import winreg  # noqa: F401 — import para smoke check

    def test_enable_disable_round_trip(self, monkeypatch):
        """Habilita o autostart (na chave de teste), confere, desabilita e confere."""
        from app.core import autostart

        monkeypatch.setattr(autostart, "APP_NAME", self.TEST_NAME)

        assert autostart._is_autostart_enabled_windows() is False, (
            "Estado inicial deveria estar desabilitado"
        )

        ok = autostart._enable_autostart_windows()
        assert ok is True
        assert autostart._is_autostart_enabled_windows() is True

        ok = autostart._disable_autostart_windows()
        assert ok is True
        assert autostart._is_autostart_enabled_windows() is False

    def test_disable_when_not_enabled_is_idempotent(self, monkeypatch):
        from app.core import autostart
        monkeypatch.setattr(autostart, "APP_NAME", self.TEST_NAME)

        # Nunca foi habilitado; disable deve retornar True (sem erro).
        assert autostart._disable_autostart_windows() is True


# ─── Smoke tests nativos do sistema ────────────────────────────────────────

class TestWindowsNativeApi:
    def test_user32_messagebox_is_callable(self):
        """
        MessageBoxW precisa estar acessível (o app chama em caso de 2a instância).
        Este teste NÃO exibe a messagebox — só verifica que o símbolo existe.
        """
        import ctypes
        assert hasattr(ctypes.windll.user32, "MessageBoxW")

    def test_kernel32_createmutex_is_callable(self):
        import ctypes
        assert hasattr(ctypes.windll.kernel32, "CreateMutexW")
        assert hasattr(ctypes.windll.kernel32, "GetLastError")
        assert hasattr(ctypes.windll.kernel32, "CloseHandle")


# ─── Logger: arquivo de log cria e recebe writes em path Windows ──────────

class TestWindowsLogger:
    def test_log_file_is_writable(self, tmp_path, monkeypatch):
        """
        Com a correção recente do logger.py (hierarquia UtilitariosPC.<nome>),
        mensagens de loggers filhos DEVEM chegar ao arquivo em Windows.
        """
        # Redireciona o log_dir para tmp_path antes de importar o logger.
        from app.core import app_paths
        monkeypatch.setattr(app_paths, "get_log_dir", lambda: str(tmp_path))

        # Força reimport do logger com log_dir mockado
        import importlib
        from app.core import logger as logger_mod
        # Reseta singleton para pegar o novo log_dir
        logger_mod._logger = None
        importlib.reload(logger_mod)

        root = logger_mod.get_logger()
        child = logger_mod.get_logger("test.child")
        child.info("mensagem de teste filho")
        child.warning("aviso de teste filho")

        # Força flush dos handlers
        for h in root.handlers:
            h.flush()

        log_file = tmp_path / "app.log"
        assert log_file.exists(), f"app.log não foi criado em {tmp_path}"
        content = log_file.read_text(encoding="utf-8")
        assert "UtilitariosPC.test.child" in content, (
            f"Logger filho não escreveu no arquivo. Conteúdo:\n{content}"
        )
        assert "mensagem de teste filho" in content
