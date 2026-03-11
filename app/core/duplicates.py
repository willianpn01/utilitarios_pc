from __future__ import annotations
import os
import hashlib
from typing import Callable, Dict, Iterable, List, Optional, Tuple


def _iter_files(root: str, recursive: bool = True) -> Iterable[str]:
    if recursive:
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                for f in filenames:
                    yield os.path.join(dirpath, f)
        except PermissionError:
            pass
    else:
        try:
            for f in os.listdir(root):
                p = os.path.join(root, f)
                if os.path.isfile(p):
                    yield p
        except PermissionError:
            pass


def _hash_file(path: str, algo: str = 'sha256', first_bytes: int | None = None, chunk: int = 1024 * 1024) -> str:
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        if first_bytes is not None:
            data = f.read(first_bytes)
            h.update(data)
            return h.hexdigest()
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def find_duplicates(
    root: str,
    recursive: bool = True,
    min_size_bytes: int = 1,
    include_exts: set[str] | None = None,
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> List[List[str]]:
    """
    Return groups of duplicate files (by content) as a list of lists with absolute paths.
    Strategy: size -> quick-hash(first 64KB) -> full-hash
    """
    root = os.path.abspath(root)

    # ── Fase 1: Inventário de arquivos (0-20%)
    if progress_cb:
        progress_cb(0, 'Inventariando arquivos…')
    files: List[Tuple[str, int]] = []
    for p in _iter_files(root, recursive=recursive):
        if cancel_check and cancel_check():
            return []
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_size < min_size_bytes:
            continue
        if include_exts:
            _, ext = os.path.splitext(p)
            if ext.lower() not in include_exts:
                continue
        files.append((p, st.st_size))

    total_files = len(files)
    if progress_cb:
        progress_cb(20, f'{total_files} arquivos encontrados. Agrupando por tamanho…')

    # ── Fase 2: Agrupar por tamanho (20-35%)
    by_size: Dict[int, List[str]] = {}
    for p, sz in files:
        by_size.setdefault(sz, []).append(p)
    candidate_groups = [v for v in by_size.values() if len(v) > 1]
    total_candidates = sum(len(g) for g in candidate_groups)

    if progress_cb:
        progress_cb(35, f'{total_candidates} candidatos. Calculando hash rápido…')

    # ── Fase 3: Quick hash – primeiros 64 KB (35-65%)
    quick_groups: List[List[str]] = []
    processed = 0
    for group in candidate_groups:
        if cancel_check and cancel_check():
            return []
        buckets: Dict[str, List[str]] = {}
        for p in group:
            if cancel_check and cancel_check():
                return []
            try:
                h = _hash_file(p, first_bytes=64 * 1024)
            except OSError:
                continue
            buckets.setdefault(h, []).append(p)
            processed += 1
            if progress_cb and total_candidates > 0:
                pct = 35 + int(processed / total_candidates * 30)
                progress_cb(pct, f'Hash rápido: {os.path.basename(p)}')
        for v in buckets.values():
            if len(v) > 1:
                quick_groups.append(v)

    total_quick = sum(len(g) for g in quick_groups)
    if progress_cb:
        progress_cb(65, f'{total_quick} candidatos restantes. Verificando hash completo…')

    # ── Fase 4: Full hash (65-95%)
    result: List[List[str]] = []
    processed = 0
    for group in quick_groups:
        if cancel_check and cancel_check():
            return []
        buckets: Dict[str, List[str]] = {}
        for p in group:
            if cancel_check and cancel_check():
                return []
            try:
                h = _hash_file(p, first_bytes=None)
            except OSError:
                continue
            buckets.setdefault(h, []).append(p)
            processed += 1
            if progress_cb and total_quick > 0:
                pct = 65 + int(processed / total_quick * 30)
                progress_cb(pct, f'Hash completo: {os.path.basename(p)}')
        for v in buckets.values():
            if len(v) > 1:
                result.append(sorted(v))

    # sort groups by size desc then name
    result.sort(key=lambda g: (-os.path.getsize(g[0]) if g else 0, g[0]))

    if progress_cb:
        progress_cb(100, f'{len(result)} grupos encontrados.')
    return result
