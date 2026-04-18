from typing import Dict
import os
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QSizePolicy, QPushButton
)
from PyQt6.QtGui import QIcon

from app.ui.widgets.dashboard import DashboardWidget
from app.ui.widgets.project_creator import ProjectCreatorWidget
from app.ui.widgets.batch_renamer import BatchRenamerWidget
from app.ui.widgets.auto_organizer import AutoOrganizerTabbedWidget
from app.ui.widgets.duplicates_finder import DuplicatesFinderWidget
from app.ui.widgets.space_analyzer import SpaceAnalyzerWidget
from app.ui.widgets.folder_compare import FolderCompareWidget
from app.ui.widgets.image_resizer import ImageResizerWidget
from app.ui.widgets.clipboard_history import ClipboardHistoryWidget


class MainWindow(QMainWindow):
    # ── Constantes de índice das páginas ──────────────────────────────────────
    PAGE_DASHBOARD = 0
    PAGE_PROJECT_CREATOR = 1
    PAGE_BATCH_RENAMER = 2
    PAGE_ORGANIZER = 3
    PAGE_DUPLICATES = 4
    PAGE_SPACE_ANALYZER = 5
    PAGE_FOLDER_COMPARE = 6
    PAGE_IMAGE_RESIZER = 7
    PAGE_CLIPBOARD = 8

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Aplicativo de Utilitários')
        self.resize(1100, 720)

        self._modules: Dict[str, QWidget] = {}

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Container Principal de Navegação (Duas linhas)
        self.nav_container = QWidget()
        self.nav_container.setObjectName('NavContainer')
        nav_main_layout = QVBoxLayout(self.nav_container)
        nav_main_layout.setContentsMargins(0, 0, 0, 0)
        nav_main_layout.setSpacing(0)
        
        # Linha 1 e Linha 2 de abas
        self.nav_line1 = QWidget()
        layout_l1 = QHBoxLayout(self.nav_line1)
        layout_l1.setContentsMargins(0, 0, 0, 0)
        layout_l1.setSpacing(0)
        
        self.nav_line2 = QWidget()
        layout_l2 = QHBoxLayout(self.nav_line2)
        layout_l2.setContentsMargins(0, 0, 0, 0)
        layout_l2.setSpacing(0)
        
        nav_main_layout.addWidget(self.nav_line1)
        nav_main_layout.addWidget(self.nav_line2)

        self._buttons: list[QPushButton] = []

        # Conteúdo principal
        self.stack = QStackedWidget()
        self.stack.setObjectName('MainStack')

        # Páginas
        self._init_pages()

        # Criar botões alinhados às páginas
        titles = [
            'Dashboard',
            'Criador de Estrutura de Projetos',
            'Renomeador em Massa',
            'Organizador Automático',
            'Localizador de Duplicados',
            'Analisador de Espaço',
            'Comparador de Pastas',
            'Redimensionador de Imagens',
            'Histórico da Área de Transferência',
        ]
        icon_files = [
            'dashboard.svg',
            'project.svg',
            'rename.svg',
            'organize.svg',
            'duplicates.svg',
            'disk.svg',
            'compare.svg',
            'resize.svg',
            'clipboard.svg',
        ]
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'assets', 'icons')
        assets_dir = os.path.normpath(assets_dir)
        for i, title in enumerate(titles):
            btn = QPushButton(title)
            btn.setObjectName('NavTab')
            btn.setCheckable(True)
            # ícone (material icons assets map)
            icon_path = os.path.join(assets_dir, icon_files[i])
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(20, 20))
                
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, idx=i: self._on_sidebar_clicked(idx))
            self._buttons.append(btn)
            
            # Distribuição nas duas linhas: Primeiros 5 na L1, restantes na L2
            if i < 5:
                layout_l1.addWidget(btn)
            else:
                layout_l2.addWidget(btn)

        root.addWidget(self.nav_container)
        root.addWidget(self.stack, 1)

        self._on_sidebar_clicked(self.PAGE_DASHBOARD)

    def _init_pages(self) -> None:
        # Dashboard (implementado)
        dashboard = DashboardWidget()
        self.stack.addWidget(dashboard)

        # Criador de Estrutura de Projetos (implementado)
        creator = ProjectCreatorWidget()
        self.stack.addWidget(creator)

        # Renomeador em Massa (implementado)
        renamer = BatchRenamerWidget()
        self.stack.addWidget(renamer)

        # Organizador Automático (implementado) - agora com abas para monitoramento
        organizer = AutoOrganizerTabbedWidget()
        self.stack.addWidget(organizer)

        # Localizador de Duplicados (implementado)
        duplicates = DuplicatesFinderWidget()
        self.stack.addWidget(duplicates)

        # Analisador de Espaço (implementado)
        space_analyzer = SpaceAnalyzerWidget()
        self.stack.addWidget(space_analyzer)

        # Comparador de Pastas (implementado)
        folder_compare = FolderCompareWidget()
        self.stack.addWidget(folder_compare)

        # Redimensionador de Imagens (implementado)
        image_resizer = ImageResizerWidget()
        self.stack.addWidget(image_resizer)

        # Histórico da Área de Transferência (implementado)
        clipboard_history = ClipboardHistoryWidget()
        self.stack.addWidget(clipboard_history)

    def _placeholder(self, text: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(text)
        label.setObjectName('PlaceholderTitle')
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        lay.addWidget(label)
        return w

    def _on_sidebar_clicked(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self._buttons):
            b.setChecked(i == index)
