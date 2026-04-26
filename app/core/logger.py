import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.app_paths import get_log_dir
from app.core.app_settings import load_setting, save_setting

ROOT_NAME = "UtilitariosPC"
_logger = None


def _qualified(name: str) -> str:
    """
    Garante que loggers filhos fiquem na hierarquia do logger raiz para
    herdarem handlers (file + console). `logging.getLogger("watcher")`
    seria um logger top-level sem nossos handlers — precisamos de
    `logging.getLogger("UtilitariosPC.watcher")`.
    """
    if not name or name == ROOT_NAME:
        return ROOT_NAME
    if name.startswith(ROOT_NAME + "."):
        return name
    return f"{ROOT_NAME}.{name}"


def get_logger(name: str = ROOT_NAME) -> logging.Logger:
    global _logger
    if _logger is None:
        log_dir = Path(get_log_dir())
        log_file = log_dir / 'app.log'

        _logger = logging.getLogger(ROOT_NAME)

        debug_mode = load_setting('debug_mode', False)
        _logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

        # Evita propagar para o root logger do Python (que não tem handlers
        # configurados) e impede mensagens duplicadas se algum lib externa
        # chamar logging.basicConfig.
        _logger.propagate = False

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'
        )

        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=2, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        _logger.addHandler(console_handler)

        _logger.info("====================================")
        _logger.info("Logger inicializado. Debug mode: %s", debug_mode)

    return logging.getLogger(_qualified(name))

def is_debug_mode() -> bool:
    return load_setting('debug_mode', False)

def set_debug_mode(enabled: bool):
    save_setting('debug_mode', enabled)
    if _logger:
        _logger.setLevel(logging.DEBUG if enabled else logging.INFO)
        _logger.info("Debug mode alterado para: %s", enabled)
