"""
Regressão do bug do dia 26/04: 8 widgets usavam `CustomDialog.warning/...`
sem ter importado `CustomDialog`. Crash só aparecia quando o usuário
clicava no botão certo, no Windows.

Este arquivo faz análise ESTÁTICA via AST:
  - Sem Qt (instanciar widget em Qt headless levava a QTimers/threads
    que não finalizam e travam o pytest).
  - Sem subprocess (ruff F821/pyflakes não pegam uso via Attribute em
    método de classe).

Regra simples e direta: para cada widget em `app/ui/widgets/*.py`, se
alguma instrução usa `CustomDialog.<qualquer_coisa>`, então o módulo
DEVE ter importado `CustomDialog` (top-level ou via import direto).

A mesma técnica se aplica a outros nomes "frágeis" que ficam como
atributo em calls e passam silenciosamente em testes comuns.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Set

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WIDGETS_DIR = REPO_ROOT / "app" / "ui" / "widgets"

# Nomes cujo uso em call/atributo exige import top-level explícito.
# Adicione aqui qualquer símbolo que no passado tenha causado NameError
# em produção por falta de import.
REQUIRED_IMPORTS: dict[str, str] = {
    "CustomDialog": "from app.ui.custom_dialog import CustomDialog",
}


def _get_top_level_imported_names(tree: ast.Module) -> Set[str]:
    """Coleta todos os nomes disponíveis no namespace top-level do módulo."""
    names: Set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # `import a.b.c` expõe `a` no namespace
                names.add((alias.asname or alias.name).split(".")[0])
    return names


def _find_usages_of(name: str, tree: ast.Module) -> list[int]:
    """
    Retorna as linhas onde `name` é usado como base de uma chamada ou atributo
    (ex.: `CustomDialog.warning(...)` ou `CustomDialog.QUESTION`).
    """
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == name:
                hits.append(node.value.lineno)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id == name:
                hits.append(node.lineno)
    return hits


def _widget_files() -> list[Path]:
    return sorted(p for p in WIDGETS_DIR.glob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize("widget_path", _widget_files(), ids=lambda p: p.name)
def test_widget_imports_required_names(widget_path: Path) -> None:
    """
    Para cada widget, se o arquivo usa qualquer `REQUIRED_IMPORTS` como base de
    chamada/atributo, o módulo DEVE ter importado o símbolo no top-level.

    Esse é exatamente o bug que crashou o app no Windows (CustomDialog).
    """
    source = widget_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(widget_path))
    imported = _get_top_level_imported_names(tree)

    problems: list[str] = []
    for name, import_hint in REQUIRED_IMPORTS.items():
        usages = _find_usages_of(name, tree)
        if usages and name not in imported:
            first_lines = ", ".join(str(ln) for ln in sorted(set(usages))[:5])
            problems.append(
                f"  - Usa `{name}` em linha(s) {first_lines} mas não importa.\n"
                f"    Adicione: {import_hint}"
            )

    if problems:
        msg = (
            f"\n{widget_path.relative_to(REPO_ROOT)} tem nomes usados sem import:\n"
            + "\n".join(problems)
        )
        pytest.fail(msg)


def test_widget_directory_has_files() -> None:
    """Sanidade: garante que o teste parametrizado NÃO está vazio."""
    files = _widget_files()
    assert len(files) >= 5, f"Esperado >= 5 widgets em {WIDGETS_DIR}, achei {len(files)}"


# ─── Teste negativo: prova que a análise FUNCIONA ───────────────────────────

def test_analysis_catches_missing_import(tmp_path) -> None:
    """
    Teste de sanidade da própria análise: constrói um arquivo "widget" que
    usa CustomDialog sem importar, e valida que a análise detecta.

    Sem este teste meta, uma regressão na análise passaria despercebida.
    """
    bad = tmp_path / "bad_widget.py"
    bad.write_text(
        "from PyQt6.QtWidgets import QWidget\n"
        "class X(QWidget):\n"
        "    def f(self):\n"
        "        CustomDialog.warning(self, 'a', 'b')\n",
        encoding="utf-8",
    )
    tree = ast.parse(bad.read_text(encoding="utf-8"))
    imported = _get_top_level_imported_names(tree)
    usages = _find_usages_of("CustomDialog", tree)

    assert "CustomDialog" not in imported
    assert usages, "deveria detectar uso de CustomDialog"


def test_analysis_accepts_proper_import(tmp_path) -> None:
    """Mesmo arquivo, agora COM o import — análise não acusa."""
    good = tmp_path / "good_widget.py"
    good.write_text(
        "from PyQt6.QtWidgets import QWidget\n"
        "from app.ui.custom_dialog import CustomDialog\n"
        "class X(QWidget):\n"
        "    def f(self):\n"
        "        CustomDialog.warning(self, 'a', 'b')\n",
        encoding="utf-8",
    )
    tree = ast.parse(good.read_text(encoding="utf-8"))
    imported = _get_top_level_imported_names(tree)
    assert "CustomDialog" in imported


# Qt-based smoke tests foram removidos: DashboardWidget cria QTimer(5s) no
# __init__ que nunca para, e ClipboardHistoryWidget/FolderWatcherWidget têm
# estado global (DB, observer) que trava o teardown do pytest. O benefício
# de instanciá-los não compensa a fragilidade. A análise AST acima pega o
# bug real (NameError por import faltando) sem tocar em Qt.
