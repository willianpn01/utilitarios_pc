from __future__ import annotations
import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class OrganizeRule:
    # category name -> list of extensions (lowercase, with dot)
    mapping: Dict[str, List[str]]
    # whether to include subdirectories in scan
    recursive: bool = True


@dataclass
class PlanItem:
    src: str
    dst: str
    action: str  # 'move' | 'skip' | 'error'
    reason: str = ''


def parse_rules(text: str) -> OrganizeRule:
    """
    Parse simple text rules in the format:
        Imagens: .jpg, .jpeg, .png
        Documentos: .pdf, .docx, .xlsx
    Empty lines and lines without ':' are ignored.
    Returns lowercased extensions with dot.
    """
    mapping: Dict[str, List[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or ':' not in line:
            continue
        name, exts = line.split(':', 1)
        name = name.strip()
        exts_list: List[str] = []
        for e in exts.split(','):
            ext = e.strip().lower()
            if not ext:
                continue
            if not ext.startswith('.'):
                ext = '.' + ext
            # avoid duplicates while preserving order
            if ext not in exts_list:
                exts_list.append(ext)
        if exts_list:
            if name in mapping:
                # merge and deduplicate preserving order
                existing = mapping[name]
                for ext in exts_list:
                    if ext not in existing:
                        existing.append(ext)
            else:
                mapping[name] = exts_list
    if not mapping:
        mapping = default_mapping()
    return OrganizeRule(mapping=mapping)


def default_mapping() -> Dict[str, List[str]]:
    return {
        'Imagens': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'],
        'Documentos': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md'],
        'Áudio': ['.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a'],
        'Vídeo': ['.mp4', '.mkv', '.mov', '.avi', '.wmv'],
        'Arquivos compactados': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'Executáveis': ['.exe', '.msi', '.bat', '.cmd', '.ps1'],
    }


def scan_files(root: str, recursive: bool = True) -> List[str]:
    files: List[str] = []
    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root):
            for f in filenames:
                files.append(os.path.join(dirpath, f))
    else:
        for f in os.listdir(root):
            p = os.path.join(root, f)
            if os.path.isfile(p):
                files.append(p)
    return files


def build_plan(directory: str, rule: OrganizeRule) -> List[PlanItem]:
    dir_abs = os.path.abspath(directory)
    files = scan_files(dir_abs, recursive=rule.recursive)

    # reverse mapping ext -> category
    ext_to_cat: Dict[str, str] = {}
    for cat, exts in rule.mapping.items():
        for e in exts:
            ext_to_cat[e.lower()] = cat

    plan: List[PlanItem] = []
    for src in files:
        # skip files already inside a category target folder directly under root
        rel = os.path.relpath(src, dir_abs)
        parts = rel.split(os.sep)
        if len(parts) >= 2 and parts[0] in rule.mapping.keys():
            plan.append(PlanItem(src=src, dst=src, action='skip', reason='já organizado'))
            continue

        _, ext = os.path.splitext(src)
        cat = ext_to_cat.get(ext.lower())
        if not cat:
            plan.append(PlanItem(src=src, dst=src, action='skip', reason='sem categoria'))
            continue
        dst_dir = os.path.join(dir_abs, cat)
        dst = os.path.join(dst_dir, os.path.basename(src))

        # If destination exists, try to find a unique name
        if os.path.exists(dst):
            base, ext2 = os.path.splitext(os.path.basename(src))
            i = 1
            while True:
                candidate = os.path.join(dst_dir, f"{base} ({i}){ext2}")
                if not os.path.exists(candidate):
                    dst = candidate
                    break
                i += 1
        plan.append(PlanItem(src=src, dst=dst, action='move'))
    return plan


def apply_plan(plan: List[PlanItem]) -> Tuple[int, int, int]:
    moved = 0
    skipped = 0
    errors = 0
    for item in plan:
        if item.action != 'move':
            skipped += 1
            continue
        try:
            os.makedirs(os.path.dirname(item.dst), exist_ok=True)
            shutil.move(item.src, item.dst)
            moved += 1
        except Exception as e:
            item.action = 'error'
            item.reason = str(e)
            errors += 1
    return moved, skipped, errors
