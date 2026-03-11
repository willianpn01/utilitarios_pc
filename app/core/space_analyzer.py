from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class DirEntry:
    """Representa um diretório ou arquivo com seu tamanho"""
    path: str
    name: str
    size: int  # bytes
    is_dir: bool
    children: List[DirEntry]
    file_count: int = 0
    dir_count: int = 0


def _get_dir_size(
    path: str,
    max_depth: int = -1,
    current_depth: int = 0,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> tuple[int, int, int]:
    """
    Retorna (tamanho_total_bytes, num_arquivos, num_subdirs)
    max_depth: -1 = ilimitado, 0 = apenas arquivos diretos
    """
    total_size = 0
    file_count = 0
    dir_count = 0

    try:
        entries = os.listdir(path)
    except (PermissionError, OSError):
        return (0, 0, 0)

    for entry_name in entries:
        if cancel_check and cancel_check():
            return (total_size, file_count, dir_count)
        entry_path = os.path.join(path, entry_name)
        try:
            if os.path.isfile(entry_path):
                total_size += os.path.getsize(entry_path)
                file_count += 1
            elif os.path.isdir(entry_path):
                dir_count += 1
                if max_depth == -1 or current_depth < max_depth:
                    sub_size, sub_files, sub_dirs = _get_dir_size(
                        entry_path, max_depth, current_depth + 1, cancel_check
                    )
                    total_size += sub_size
                    file_count += sub_files
                    dir_count += sub_dirs
        except (PermissionError, OSError):
            continue

    return (total_size, file_count, dir_count)


def analyze_directory(
    root_path: str,
    max_depth: int = 2,
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> DirEntry:
    """
    Analisa um diretório e retorna uma árvore de DirEntry com tamanhos agregados.
    max_depth: profundidade máxima para análise detalhada (-1 = ilimitado)
    """
    if not os.path.isdir(root_path):
        raise ValueError(f'Caminho não é um diretório válido: {root_path}')

    # Contar entradas de 1º nível para estimar progresso
    try:
        top_level = [e for e in os.listdir(root_path)]
    except OSError:
        top_level = []
    total_top = max(len(top_level), 1)
    processed_top = [0]  # lista mutável para acesso dentro do closure

    def _build_tree(path: str, depth: int) -> DirEntry:
        name = os.path.basename(path) or path
        children: List[DirEntry] = []
        total_size = 0
        file_count = 0
        dir_count = 0

        try:
            entries = os.listdir(path)
        except (PermissionError, OSError):
            return DirEntry(
                path=path, name=name, size=0, is_dir=True,
                children=[], file_count=0, dir_count=0
            )

        for entry_name in entries:
            if cancel_check and cancel_check():
                return None  # Propagar cancelamento
            entry_path = os.path.join(path, entry_name)
            try:
                if os.path.isfile(entry_path):
                    size = os.path.getsize(entry_path)
                    total_size += size
                    file_count += 1
                    children.append(DirEntry(
                        path=entry_path, name=entry_name, size=size,
                        is_dir=False, children=[], file_count=0, dir_count=0
                    ))
                elif os.path.isdir(entry_path):
                    dir_count += 1
                    if max_depth == -1 or depth < max_depth:
                        child = _build_tree(entry_path, depth + 1)
                        if child is None:
                            return None  # Propaga interrupção
                        children.append(child)
                        total_size += child.size
                        file_count += child.file_count
                        dir_count += child.dir_count
                    else:
                        sub_size, sub_files, sub_dirs = _get_dir_size(
                            entry_path, cancel_check=cancel_check
                        )
                        if cancel_check and cancel_check():
                            return None
                        children.append(DirEntry(
                            path=entry_path, name=entry_name, size=sub_size,
                            is_dir=True, children=[], file_count=sub_files, dir_count=sub_dirs
                        ))
                        total_size += sub_size
                        file_count += sub_files
                        dir_count += sub_dirs

                    # Progresso baseado nas entradas de 1º nível
                    if depth == 0:
                        processed_top[0] += 1
                        pct = min(95, int(processed_top[0] / total_top * 95))
                        if progress_cb:
                            progress_cb(pct, f'Analisando: {entry_name}')
            except (PermissionError, OSError):
                continue

        return DirEntry(
            path=path, name=name, size=total_size, is_dir=True,
            children=children, file_count=file_count, dir_count=dir_count
        )

    if progress_cb:
        progress_cb(0, f'Iniciando análise de {root_path}…')
    result = _build_tree(root_path, 0)
    if progress_cb:
        progress_cb(100, 'Análise concluída.')
    return result


def get_largest_items(entry: DirEntry, top_n: int = 20) -> List[DirEntry]:
    """Retorna os N maiores itens (arquivos e pastas) ordenados por tamanho"""
    items: List[DirEntry] = []

    def _collect(node: DirEntry) -> None:
        items.append(node)
        for child in node.children:
            _collect(child)

    _collect(entry)
    items.sort(key=lambda x: x.size, reverse=True)
    return items[:top_n]


def format_size(size_bytes: int) -> str:
    """Formata tamanho em bytes para formato legível"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024.0
    return f'{size_bytes:.1f} PB'
