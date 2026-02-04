from __future__ import annotations
import os
import hashlib
from typing import Dict, Iterable, List, Tuple, DefaultDict


def _iter_files(root: str, recursive: bool = True) -> Iterable[str]:
    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root):
            for f in filenames:
                yield os.path.join(dirpath, f)
    else:
        for f in os.listdir(root):
            p = os.path.join(root, f)
            if os.path.isfile(p):
                yield p


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
) -> List[List[str]]:
    """
    Return groups of duplicate files (by content) as a list of lists with absolute paths.
    Strategy: size -> quick-hash(first 64KB) -> full-hash
    """
    root = os.path.abspath(root)
    files: List[Tuple[str, int]] = []
    for p in _iter_files(root, recursive=recursive):
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

    # group by size
    by_size: Dict[int, List[str]] = {}
    for p, sz in files:
        by_size.setdefault(sz, []).append(p)

    # reduce: only size groups with >1
    candidate_groups = [v for v in by_size.values() if len(v) > 1]

    # quick hash (first 64KB)
    quick_groups: List[List[str]] = []
    for group in candidate_groups:
        buckets: Dict[str, List[str]] = {}
        for p in group:
            try:
                h = _hash_file(p, first_bytes=64 * 1024)
            except OSError:
                continue
            buckets.setdefault(h, []).append(p)
        for v in buckets.values():
            if len(v) > 1:
                quick_groups.append(v)

    # full hash
    result: List[List[str]] = []
    for group in quick_groups:
        buckets: Dict[str, List[str]] = {}
        for p in group:
            try:
                h = _hash_file(p, first_bytes=None)
            except OSError:
                continue
            buckets.setdefault(h, []).append(p)
        for v in buckets.values():
            if len(v) > 1:
                result.append(sorted(v))

    # sort groups by size desc then name
    result.sort(key=lambda g: (-os.path.getsize(g[0]) if g else 0, g[0]))
    return result
