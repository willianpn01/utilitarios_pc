from __future__ import annotations
import os
from typing import Dict, List, Union

# Estruturas de templates: dict onde chave é nome e valor é subestrutura.
# Diretórios são dicts; arquivos são None ou string (conteúdo inicial opcional).
Structure = Dict[str, Union['Structure', None, str]]

TEMPLATES: Dict[str, Structure] = {
    'Projeto Python Básico': {
        'src': {
            '__init__.py': '',
            'main.py': """if __name__ == '__main__':\n    print('Hello, world!')\n""",
        },
        'tests': {
            '__init__.py': '',
            'test_sample.py': """def test_truth():\n    assert True\n""",
        },
        '.gitignore': "__pycache__/\n*.pyc\n.venv/\n",
        'README.md': '# Novo Projeto\n',
        'requirements.txt': ''
    },
    'Projeto Web (Flask)': {
        'app': {
            '__init__.py': """from flask import Flask\n\napp = Flask(__name__)\n\nfrom . import routes  # noqa\n""",
            'routes.py': """from . import app\n\n@app.route('/')\ndef index():\n    return 'Hello Flask'\n""",
            'templates': {
                'index.html': """<!doctype html><title>Hello</title><h1>Hello</h1>""",
            },
        },
        'run.py': """from app import app\n\nif __name__ == '__main__':\n    app.run(debug=True)\n""",
        'requirements.txt': 'flask\n',
    },
    'Projeto Dados (Notebook)': {
        'notebooks': {
            'exploracao.ipynb': None,
        },
        'data': {},
        'README.md': '# Projeto de Dados\n',
    },
}


def render_tree(structure: Structure, prefix: str = '') -> str:
    lines: List[str] = []
    items = list(structure.items())
    for i, (name, value) in enumerate(items):
        connector = '└── ' if i == len(items) - 1 else '├── '
        if isinstance(value, dict):
            lines.append(f"{prefix}{connector}{name}/")
            extension = '    ' if i == len(items) - 1 else '│   '
            lines.append(render_tree(value, prefix + extension))
        else:
            lines.append(f"{prefix}{connector}{name}")
    return '\n'.join([l for l in lines if l])


def _ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def create_structure(base_path: str, structure: Structure) -> List[str]:
    created: List[str] = []

    def _create(base: str, node: Structure) -> None:
        for name, value in node.items():
            path = os.path.join(base, name)
            if isinstance(value, dict):
                _ensure_dir(path)
                created.append(path)
                _create(path, value)
            else:
                parent = os.path.dirname(path)
                _ensure_dir(parent)
                if value is None:
                    # arquivo vazio; se terminar com .ipynb criar vazio
                    open(path, 'wb').close()
                else:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(value)
                created.append(path)

    _create(base_path, structure)
    return created
