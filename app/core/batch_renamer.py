from __future__ import annotations
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple, Optional


@dataclass
class RenameRule:
    prefix: str = ''
    suffix: str = ''
    search: str = ''
    replace: str = ''
    sequence_start: int = 1
    sequence_pad: int = 2
    case: str = 'none'  # 'none' | 'lower' | 'upper' | 'title'
    remove_spaces: bool = False
    change_extension: str = ''  # exemplo: 'txt' (sem ponto)
    ignore_original: bool = False  # ignora completamente o nome atual do arquivo
    base_name: str = ''  # se definido, usa como base ao ignorar o nome original
    use_sequence: bool = True  # controla se adiciona numeração sequencial
    separator: str = '_'  # separador entre partes (use '' para concatenar diretamente)


@dataclass
class RenameItem:
    src: str
    dst: str
    status: str  # 'ok' | 'skip' | 'conflict' | 'error'
    message: str = ''


def _walk_files(base_dir: str, recursive: bool, extensions: Optional[Iterable[str]]) -> List[str]:
    result: List[str] = []
    exts = set(e.lower().lstrip('.') for e in (extensions or []) if e)
    if recursive:
        for root, _dirs, files in os.walk(base_dir):
            for f in files:
                if exts and f.split('.')[-1].lower() not in exts:
                    continue
                result.append(os.path.join(root, f))
    else:
        for f in os.listdir(base_dir):
            p = os.path.join(base_dir, f)
            if os.path.isfile(p):
                if exts and f.split('.')[-1].lower() not in exts:
                    continue
                result.append(p)
    result.sort()
    return result


def _apply_rules_to_name(name: str, index: int, rule: RenameRule) -> str:
    orig_base, ext = os.path.splitext(name)

    # determine working base
    if rule.ignore_original:
        base = rule.base_name or ''
    else:
        base = orig_base
        # search/replace (regex se search começa com r/)
        if rule.search:
            if rule.search.startswith('r/'):
                pattern = rule.search[2:]
                try:
                    base = re.sub(pattern, rule.replace, base)
                except re.error:
                    pass
            else:
                base = base.replace(rule.search, rule.replace)

    # sequence
    seq_str = ''
    if rule.use_sequence and rule.sequence_start is not None:
        seq = rule.sequence_start + index
        seq_str = str(seq).zfill(max(0, rule.sequence_pad or 0))

    # compose pieces
    pieces = []
    if rule.prefix:
        pieces.append(rule.prefix)
    if base:
        pieces.append(base)
    if rule.suffix:
        pieces.append(rule.suffix)
    if seq_str:
        pieces.append(seq_str)
    composed = rule.separator.join(p for p in pieces if p)

    # spaces
    if rule.remove_spaces:
        composed = re.sub(r"\s+", "_", composed)

    # case
    if rule.case == 'lower':
        composed = composed.lower()
    elif rule.case == 'upper':
        composed = composed.upper()
    elif rule.case == 'title':
        composed = composed.title()

    # extension change
    if rule.change_extension:
        ext = '.' + rule.change_extension.lstrip('.')

    return composed + ext


def preview_renames(base_dir: str, recursive: bool, extensions: Optional[Iterable[str]], rule: RenameRule) -> List[RenameItem]:
    files = _walk_files(base_dir, recursive, extensions)
    items: List[RenameItem] = []
    seen_dsts = set()
    for i, src in enumerate(files):
        dir_name = os.path.dirname(src)
        new_name = _apply_rules_to_name(os.path.basename(src), i, rule)
        dst = os.path.join(dir_name, new_name)
        status = 'ok'
        msg = ''
        if dst == src:
            status = 'skip'
            msg = 'Sem alterações'
        elif os.path.exists(dst):
            status = 'conflict'
            msg = 'Destino já existe'
        elif dst in seen_dsts:
            status = 'conflict'
            msg = 'Conflito na sessão'
        seen_dsts.add(dst)
        items.append(RenameItem(src=src, dst=dst, status=status, message=msg))
    return items


def apply_renames(items: List[RenameItem]) -> Tuple[int, int, int]:
    """Executa renomeações. Retorna (renomeados, ignorados, erros).
    Garante rollback básico em caso de falha.
    """
    renamed: List[Tuple[str, str]] = []
    skipped = 0
    errors = 0

    # abort if there are conflicts
    if any(it.status == 'conflict' for it in items):
        return (0, sum(1 for it in items if it.status != 'ok'), len([1 for it in items if it.status == 'conflict']))

    for it in items:
        if it.status != 'ok' or it.src == it.dst:
            skipped += 1
            continue
        try:
            os.replace(it.src, it.dst)
            renamed.append((it.dst, it.src))  # armazenar para rollback
        except Exception:  # noqa: BLE001
            errors += 1
            # rollback
            for done_dst, done_src in reversed(renamed):
                try:
                    if os.path.exists(done_dst):
                        os.replace(done_dst, done_src)
                except Exception:
                    pass
            return (len(renamed), skipped, errors)
    return (len(renamed), skipped, errors)
