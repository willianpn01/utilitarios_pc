from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List, Optional


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


def _get_dir_size(path: str, max_depth: int = -1, current_depth: int = 0) -> tuple[int, int, int]:
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
        entry_path = os.path.join(path, entry_name)
        try:
            if os.path.isfile(entry_path):
                total_size += os.path.getsize(entry_path)
                file_count += 1
            elif os.path.isdir(entry_path):
                dir_count += 1
                if max_depth == -1 or current_depth < max_depth:
                    sub_size, sub_files, sub_dirs = _get_dir_size(entry_path, max_depth, current_depth + 1)
                    total_size += sub_size
                    file_count += sub_files
                    dir_count += sub_dirs
        except (PermissionError, OSError):
            continue
    
    return (total_size, file_count, dir_count)


def analyze_directory(root_path: str, max_depth: int = 2) -> DirEntry:
    """
    Analisa um diretório e retorna uma árvore de DirEntry com tamanhos agregados.
    max_depth: profundidade máxima para análise detalhada (-1 = ilimitado)
    """
    if not os.path.isdir(root_path):
        raise ValueError(f"Caminho não é um diretório válido: {root_path}")
    
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
                path=path,
                name=name,
                size=0,
                is_dir=True,
                children=[],
                file_count=0,
                dir_count=0
            )
        
        # Processar entradas
        for entry_name in entries:
            entry_path = os.path.join(path, entry_name)
            try:
                if os.path.isfile(entry_path):
                    size = os.path.getsize(entry_path)
                    total_size += size
                    file_count += 1
                    # Adicionar arquivo como filho
                    children.append(DirEntry(
                        path=entry_path,
                        name=entry_name,
                        size=size,
                        is_dir=False,
                        children=[],
                        file_count=0,
                        dir_count=0
                    ))
                elif os.path.isdir(entry_path):
                    dir_count += 1
                    if max_depth == -1 or depth < max_depth:
                        # Recursão: construir subárvore
                        child = _build_tree(entry_path, depth + 1)
                        children.append(child)
                        total_size += child.size
                        file_count += child.file_count
                        dir_count += child.dir_count
                    else:
                        # Apenas calcular tamanho sem construir árvore
                        sub_size, sub_files, sub_dirs = _get_dir_size(entry_path)
                        children.append(DirEntry(
                            path=entry_path,
                            name=entry_name,
                            size=sub_size,
                            is_dir=True,
                            children=[],
                            file_count=sub_files,
                            dir_count=sub_dirs
                        ))
                        total_size += sub_size
                        file_count += sub_files
                        dir_count += sub_dirs
            except (PermissionError, OSError):
                continue
        
        return DirEntry(
            path=path,
            name=name,
            size=total_size,
            is_dir=True,
            children=children,
            file_count=file_count,
            dir_count=dir_count
        )
    
    return _build_tree(root_path, 0)


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
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"
