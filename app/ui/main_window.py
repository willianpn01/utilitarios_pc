from typing import Dict
import os
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QSizePolicy, QToolButton
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
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Aplicativo de Utilitários')
        self.resize(1100, 720)

        self._modules: Dict[str, QWidget] = {}

        container = QWidget()
        self.setCentralWidget(container)
        root = QHBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar (botões)
        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName('Sidebar')
        self.sidebar_container.setFixedWidth(240)
        sb_layout = QVBoxLayout(self.sidebar_container)
        sb_layout.setContentsMargins(12, 12, 12, 12)
        sb_layout.setSpacing(8)
        self._buttons: list[QToolButton] = []

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
            btn = QToolButton()
            btn.setText(title)
            btn.setObjectName('SidebarButton')
            btn.setCheckable(True)
            # ícone
            icon_path = os.path.join(assets_dir, icon_files[i])
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(18, 18))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, idx=i: self._on_sidebar_clicked(idx))
            self._buttons.append(btn)
            sb_layout.addWidget(btn)
        sb_layout.addStretch(1)

        root.addWidget(self.sidebar_container)
        root.addWidget(self.stack, 1)

        # Ajustar largura mínima da sidebar para caber os textos
        fm = self.sidebar_container.fontMetrics()
        max_text = max((fm.horizontalAdvance(t) for t in titles), default=0)
        icon_w = 18
        spacing = 8
        padding_lr = 32  # conforme QSS (16px + 16px)
        reserve = 28     # margem/layout extra
        min_w = max(220, max_text + icon_w + spacing + padding_lr + reserve)
        self.sidebar_container.setMinimumWidth(min_w)

        self._on_sidebar_clicked(0)

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
