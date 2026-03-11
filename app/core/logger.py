import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.app_settings import load_setting, save_setting

_logger = None

def get_logger(name="UtilitariosPC"):
    global _logger
    if _logger is not None:
        return logging.getLogger(name)
    
    appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    log_dir = Path(appdata) / 'UtilitariosPC' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / 'app.log'
    
    _logger = logging.getLogger("UtilitariosPC")
    
    debug_mode = load_setting('debug_mode', False)
    _logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s')
    
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    _logger.addHandler(console_handler)
    
    _logger.info("====================================")
    _logger.info("Logger inicializado. Debug mode: %s", debug_mode)
    
    return logging.getLogger(name)

def is_debug_mode() -> bool:
    return load_setting('debug_mode', False)

def set_debug_mode(enabled: bool):
    save_setting('debug_mode', enabled)
    if _logger:
        _logger.setLevel(logging.DEBUG if enabled else logging.INFO)
        _logger.info("Debug mode alterado para: %s", enabled)
