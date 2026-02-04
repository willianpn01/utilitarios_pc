from __future__ import annotations
import os
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class FileInfo:
    """Informações sobre um arquivo"""
    path: str
    rel_path: str  # caminho relativo à raiz
    size: int
    mtime: float  # timestamp de modificação
    hash: Optional[str] = None  # hash MD5 (calculado sob demanda)


@dataclass
class CompareResult:
    """Resultado da comparação entre dois diretórios"""
    only_left: List[FileInfo]  # arquivos apenas na esquerda
    only_right: List[FileInfo]  # arquivos apenas na direita
    different: List[tuple[FileInfo, FileInfo]]  # arquivos diferentes (esquerda, direita)
    identical: List[tuple[FileInfo, FileInfo]]  # arquivos idênticos


def _scan_directory(root: str, recursive: bool = True) -> Dict[str, FileInfo]:
    """
    Escaneia um diretório e retorna um dicionário {rel_path: FileInfo}
    """
    result: Dict[str, FileInfo] = {}
    root = os.path.abspath(root)
    
    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                try:
                    rel_path = os.path.relpath(full_path, root)
                    stat = os.stat(full_path)
                    result[rel_path] = FileInfo(
                        path=full_path,
                        rel_path=rel_path,
                        size=stat.st_size,
                        mtime=stat.st_mtime
                    )
                except (OSError, ValueError):
                    continue
    else:
        try:
            for filename in os.listdir(root):
                full_path = os.path.join(root, filename)
                if os.path.isfile(full_path):
                    try:
                        stat = os.stat(full_path)
                        result[filename] = FileInfo(
                            path=full_path,
                            rel_path=filename,
                            size=stat.st_size,
                            mtime=stat.st_mtime
                        )
                    except OSError:
                        continue
        except OSError:
            pass
    
    return result


def _calculate_hash(file_path: str, chunk_size: int = 8192) -> str:
    """Calcula hash MD5 de um arquivo"""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, IOError):
        return ''


def compare_directories(
    left_dir: str,
    right_dir: str,
    recursive: bool = True,
    compare_content: bool = False
) -> CompareResult:
    """
    Compara dois diretórios e retorna as diferenças.
    
    Args:
        left_dir: diretório da esquerda
        right_dir: diretório da direita
        recursive: incluir subdiretórios
        compare_content: comparar conteúdo via hash (mais lento)
    """
    left_files = _scan_directory(left_dir, recursive)
    right_files = _scan_directory(right_dir, recursive)
    
    only_left: List[FileInfo] = []
    only_right: List[FileInfo] = []
    different: List[tuple[FileInfo, FileInfo]] = []
    identical: List[tuple[FileInfo, FileInfo]] = []
    
    # Arquivos apenas na esquerda
    for rel_path, left_info in left_files.items():
        if rel_path not in right_files:
            only_left.append(left_info)
    
    # Arquivos apenas na direita
    for rel_path, right_info in right_files.items():
        if rel_path not in left_files:
            only_right.append(right_info)
    
    # Arquivos em ambos: verificar se são diferentes
    for rel_path, left_info in left_files.items():
        if rel_path in right_files:
            right_info = right_files[rel_path]
            
            # Comparar por tamanho primeiro (rápido)
            if left_info.size != right_info.size:
                different.append((left_info, right_info))
                continue
            
            # Se compare_content, calcular hash
            if compare_content:
                left_hash = _calculate_hash(left_info.path)
                right_hash = _calculate_hash(right_info.path)
                left_info.hash = left_hash
                right_info.hash = right_hash
                
                if left_hash != right_hash:
                    different.append((left_info, right_info))
                else:
                    identical.append((left_info, right_info))
            else:
                # Comparar por data de modificação
                if abs(left_info.mtime - right_info.mtime) > 1:  # tolerância de 1 segundo
                    different.append((left_info, right_info))
                else:
                    identical.append((left_info, right_info))
    
    # Ordenar resultados
    only_left.sort(key=lambda x: x.rel_path)
    only_right.sort(key=lambda x: x.rel_path)
    different.sort(key=lambda x: x[0].rel_path)
    identical.sort(key=lambda x: x[0].rel_path)
    
    return CompareResult(
        only_left=only_left,
        only_right=only_right,
        different=different,
        identical=identical
    )
