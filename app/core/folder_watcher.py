"""
Folder Watcher - Monitoramento automático de pastas para organização de arquivos.

Usa a biblioteca watchdog para detectar novos arquivos e organizá-los
automaticamente de acordo com regras configuradas.
"""
from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

from app.core.auto_organizer import parse_rules, OrganizeRule, resolve_collision
from app.core.logger import get_logger

if TYPE_CHECKING:
    from app.core.watcher_config import WatchConfig

_log = get_logger("watcher")


@dataclass
class WatchEvent:
    """Registro de um evento de organização."""
    timestamp: datetime
    source: str
    destination: str
    category: str
    success: bool
    error: str = ""


class OrganizeHandler(FileSystemEventHandler):
    """Handler para eventos de sistema de arquivos."""
    
    def __init__(
        self,
        config: WatchConfig,
        on_file_organized: Optional[Callable[[WatchEvent], None]] = None,
        delay_seconds: float = 1.0
    ):
        super().__init__()
        self.config = config
        self.on_file_organized = on_file_organized
        self.delay_seconds = delay_seconds
        self._pending_files: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
    
    def _get_category_for_file(self, filepath: str) -> Optional[str]:
        """Retorna a categoria para um arquivo baseado nas regras."""
        rule = self.config.get_rule()
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        
        for category, extensions in rule.mapping.items():
            if ext in extensions:
                return category
        return None
    
    def _organize_file(self, filepath: str) -> None:
        """Organiza um arquivo movendo-o para a pasta da categoria."""
        with self._lock:
            if filepath in self._pending_files:
                del self._pending_files[filepath]
        
        if not os.path.exists(filepath):
            return
        
        # Ignorar pastas e arquivos temporários
        if os.path.isdir(filepath):
            return
        
        basename = os.path.basename(filepath)
        if basename.startswith('.') or basename.endswith('.tmp') or basename.endswith('.crdownload'):
            return
        
        category = self._get_category_for_file(filepath)
        if not category:
            return
        
        # Calcular destino
        watch_dir = self.config.path
        dest_dir = os.path.join(watch_dir, category)
        dest_path = os.path.join(dest_dir, basename)
        
        # Verificar se já está na pasta correta
        file_dir = os.path.dirname(filepath)
        if os.path.normpath(file_dir) == os.path.normpath(dest_dir):
            return
        
        event = WatchEvent(
            timestamp=datetime.now(),
            source=filepath,
            destination=dest_path,
            category=category,
            success=False
        )
        
        try:
            os.makedirs(dest_dir, exist_ok=True)

            # Resolve colisão: se o destino já existe, gerar nome único.
            dest_path = resolve_collision(dest_path)
            event.destination = dest_path

            # Mover arquivo
            import shutil
            shutil.move(filepath, dest_path)
            event.success = True
            _log.info("Arquivo organizado: %s -> %s (categoria=%s)",
                      filepath, dest_path, category)

        except Exception as e:
            event.error = str(e)
            _log.exception("Falha ao organizar %s -> %s", filepath, dest_path)

        if self.on_file_organized:
            self.on_file_organized(event)
    
    def _schedule_organize(self, filepath: str) -> None:
        """Agenda organização com delay para evitar arquivos incompletos."""
        with self._lock:
            # Cancelar timer anterior se existir
            if filepath in self._pending_files:
                self._pending_files[filepath].cancel()
            
            # Agendar nova organização
            timer = threading.Timer(self.delay_seconds, self._organize_file, args=[filepath])
            self._pending_files[filepath] = timer
            timer.start()
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Chamado quando um arquivo é criado."""
        if event.is_directory:
            return
        self._schedule_organize(event.src_path)
    
    def on_moved(self, event: FileMovedEvent) -> None:
        """Chamado quando um arquivo é movido para a pasta."""
        if event.is_directory:
            return
        self._schedule_organize(event.dest_path)


class FolderWatcher:
    """Gerenciador principal do serviço de monitoramento."""
    
    def __init__(self):
        self._observers: Dict[str, Observer] = {}
        self._configs: Dict[str, WatchConfig] = {}
        self._handlers: Dict[str, OrganizeHandler] = {}
        self._running = False
        self._on_file_organized: Optional[Callable[[WatchEvent], None]] = None
        self._on_status_changed: Optional[Callable[[str, bool], None]] = None
        self._events: List[WatchEvent] = []
        self._lock = threading.Lock()
    
    @property
    def is_running(self) -> bool:
        """Retorna se o watcher está ativo."""
        return self._running
    
    @property
    def watched_paths(self) -> List[str]:
        """Retorna lista de caminhos monitorados."""
        return list(self._configs.keys())
    
    @property
    def events(self) -> List[WatchEvent]:
        """Retorna histórico de eventos."""
        return self._events.copy()
    
    def set_callbacks(
        self,
        on_file_organized: Optional[Callable[[WatchEvent], None]] = None,
        on_status_changed: Optional[Callable[[str, bool], None]] = None
    ) -> None:
        """Define callbacks para eventos."""
        self._on_file_organized = on_file_organized
        self._on_status_changed = on_status_changed
    
    def _handle_event(self, event: WatchEvent) -> None:
        """Processa um evento de organização."""
        with self._lock:
            self._events.append(event)
            # Manter apenas últimos 100 eventos
            if len(self._events) > 100:
                self._events = self._events[-100:]
        
        if self._on_file_organized:
            self._on_file_organized(event)
    
    def add_watch(self, config: WatchConfig) -> bool:
        """Adiciona uma pasta ao monitoramento."""
        path = os.path.normpath(config.path)
        
        if not os.path.isdir(path):
            return False
        
        # Remover watch anterior se existir
        if path in self._configs:
            self.remove_watch(path)
        
        self._configs[path] = config
        
        # Se já está rodando e config está enabled, iniciar observer
        if self._running and config.enabled:
            self._start_observer(path)
        
        return True
    
    def remove_watch(self, path: str) -> bool:
        """Remove uma pasta do monitoramento."""
        path = os.path.normpath(path)
        
        if path not in self._configs:
            return False
        
        self._stop_observer(path)
        del self._configs[path]
        
        return True
    
    def update_watch(self, path: str, enabled: bool) -> bool:
        """Atualiza status de uma pasta monitorada."""
        path = os.path.normpath(path)
        
        if path not in self._configs:
            return False
        
        self._configs[path].enabled = enabled
        
        if self._running:
            if enabled:
                self._start_observer(path)
            else:
                self._stop_observer(path)
        
        return True
    
    def _start_observer(self, path: str) -> None:
        """Inicia observer para um caminho."""
        if path in self._observers:
            return
        
        config = self._configs.get(path)
        if not config or not config.enabled:
            return
        
        handler = OrganizeHandler(config, self._handle_event)
        observer = Observer()
        observer.schedule(handler, path, recursive=False)
        
        try:
            observer.start()
            self._observers[path] = observer
            self._handlers[path] = handler
            _log.info("Observer iniciado em: %s", path)

            if self._on_status_changed:
                self._on_status_changed(path, True)
        except Exception:
            _log.exception("Falha ao iniciar observer em %s", path)
            if self._on_status_changed:
                self._on_status_changed(path, False)
    
    def _stop_observer(self, path: str) -> None:
        """Para observer para um caminho."""
        if path not in self._observers:
            return
        
        observer = self._observers[path]
        observer.stop()
        observer.join(timeout=2.0)
        
        del self._observers[path]
        if path in self._handlers:
            del self._handlers[path]
        
        if self._on_status_changed:
            self._on_status_changed(path, False)
    
    def start(self) -> None:
        """Inicia todos os observers configurados."""
        if self._running:
            return
        
        self._running = True
        
        for path, config in self._configs.items():
            if config.enabled:
                self._start_observer(path)
    
    def stop(self) -> None:
        """Para todos os observers."""
        if not self._running:
            return
        
        self._running = False
        
        for path in list(self._observers.keys()):
            self._stop_observer(path)
    
    def get_config(self, path: str) -> Optional[WatchConfig]:
        """Retorna configuração de um caminho."""
        return self._configs.get(os.path.normpath(path))
    
    def get_all_configs(self) -> List[WatchConfig]:
        """Retorna todas as configurações."""
        return list(self._configs.values())
    
    def clear_events(self) -> None:
        """Limpa histórico de eventos."""
        with self._lock:
            self._events.clear()
