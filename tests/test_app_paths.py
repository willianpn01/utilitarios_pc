"""Testes para app.core.app_paths — helpers de plataforma e caminhos."""
import os
import sys
import pytest

# Garantir que o projeto esteja no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.app_paths import (
    is_windows, is_linux, is_macos,
    get_data_dir, get_config_dir, get_log_dir,
    get_undo_history_dir, get_watcher_config_path,
    get_clipboard_db_path, get_lock_file_path,
    get_settings_path, get_all_data_paths,
    APP_NAME, APP_DISPLAY_NAME,
)


class TestPlatformHelpers:
    """Testa os helpers de detecção de plataforma."""
    
    def test_exactly_one_platform(self):
        """Deve detectar exatamente uma plataforma (ou nenhuma em sistemas exóticos)."""
        platforms = [is_windows(), is_linux(), is_macos()]
        assert sum(platforms) <= 1, "Mais de uma plataforma detectada simultaneamente"
    
    def test_current_platform_detected(self):
        """Pelo menos uma plataforma deve ser detectada em sistemas comuns."""
        if sys.platform.startswith(('win', 'linux', 'darwin')):
            assert any([is_windows(), is_linux(), is_macos()])
    
    def test_is_windows_matches_sys_platform(self):
        assert is_windows() == sys.platform.startswith('win')
    
    def test_is_linux_matches_sys_platform(self):
        assert is_linux() == sys.platform.startswith('linux')
    
    def test_is_macos_matches_sys_platform(self):
        assert is_macos() == (sys.platform == 'darwin')


class TestDataPaths:
    """Testa os caminhos de dados do aplicativo."""
    
    def test_data_dir_exists(self):
        """get_data_dir() deve criar e retornar um diretório existente."""
        data_dir = get_data_dir()
        assert os.path.isdir(data_dir)
    
    def test_data_dir_under_home(self):
        """Diretório de dados deve estar sob o home do usuário (sem UTILITARIOS_DATA_DIR)."""
        # Salvar e limpar variável de ambiente
        original = os.environ.pop('UTILITARIOS_DATA_DIR', None)
        try:
            data_dir = get_data_dir()
            home = os.path.expanduser("~")
            assert data_dir.startswith(home)
        finally:
            if original:
                os.environ['UTILITARIOS_DATA_DIR'] = original
    
    def test_data_dir_custom_env(self, tmp_path):
        """UTILITARIOS_DATA_DIR deve sobrescrever o diretório padrão."""
        custom = str(tmp_path / "custom_data")
        original = os.environ.get('UTILITARIOS_DATA_DIR')
        os.environ['UTILITARIOS_DATA_DIR'] = custom
        try:
            assert get_data_dir() == custom
            assert os.path.isdir(custom)
        finally:
            if original:
                os.environ['UTILITARIOS_DATA_DIR'] = original
            else:
                del os.environ['UTILITARIOS_DATA_DIR']
    
    def test_subdirectories_exist(self):
        """Subdiretórios devem ser criados automaticamente."""
        assert os.path.isdir(get_config_dir())
        assert os.path.isdir(get_log_dir())
        assert os.path.isdir(get_undo_history_dir())
    
    def test_config_dir_under_data_dir(self):
        assert get_config_dir().startswith(get_data_dir())
    
    def test_log_dir_under_data_dir(self):
        assert get_log_dir().startswith(get_data_dir())
    
    def test_file_paths_are_strings(self):
        """Caminhos de arquivos devem ser strings válidas."""
        assert isinstance(get_watcher_config_path(), str)
        assert isinstance(get_clipboard_db_path(), str)
        assert isinstance(get_lock_file_path(), str)
        assert isinstance(get_settings_path(), str)
    
    def test_file_paths_under_data_dir(self):
        data_dir = get_data_dir()
        assert get_watcher_config_path().startswith(data_dir)
        assert get_clipboard_db_path().startswith(data_dir)
        assert get_lock_file_path().startswith(data_dir)
        assert get_settings_path().startswith(data_dir)
    
    def test_all_data_paths_dict(self):
        """get_all_data_paths() deve retornar todas as chaves esperadas."""
        paths = get_all_data_paths()
        expected_keys = {
            'data_dir', 'config_dir', 'log_dir', 'undo_history',
            'watcher_config', 'clipboard_db', 'settings', 'lock_file'
        }
        assert set(paths.keys()) == expected_keys


class TestAppConstants:
    def test_app_name_not_empty(self):
        assert APP_NAME
        assert APP_DISPLAY_NAME
    
    def test_app_name_is_ascii(self):
        """APP_NAME (usado em caminhos/registro) deve ser ASCII."""
        assert APP_NAME.isascii()
