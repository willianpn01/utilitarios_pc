from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
import os

class CustomDialog(QDialog):
    """
    Substituto 100% Dark Flat para o nativo QMessageBox.
    Herda os estilos globais de bordas e background presentes no theme.qss.
    """
    def __init__(self, parent=None, title="", text="", icon_type="information", buttons="ok"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setModal(True)
        self.setMinimumWidth(350)
        
        self.result_role = None
        
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 16)
        root_layout.setSpacing(20)
        
        # Conteúdo superior (Icone + Texto)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        
        # O Ícone (vamos usar um label com texto emoji ou fallback para evitar dependência gráfica pesada,
        # ou buscar SVG em assets se estritamente necessário. Emoji é nativamente escalável e respeita cor.)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        icon_font = icon_label.font()
        icon_font.setPointSize(28)
        icon_label.setFont(icon_font)
        
        if icon_type == "information":
            icon_label.setText("ℹ️")
        elif icon_type == "warning":
            icon_label.setText("⚠️")
        elif icon_type == "critical":
            icon_label.setText("❌")
        elif icon_type == "question":
            icon_label.setText("❓")
            
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        
        content_layout.addWidget(icon_label)
        content_layout.addWidget(text_label, 1)
        root_layout.addLayout(content_layout)
        
        # Botões Inferiores
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        
        if buttons == "ok":
            btn_ok = QPushButton("OK")
            btn_ok.setObjectName("PrimaryAction")
            btn_ok.setMinimumWidth(80)
            btn_ok.clicked.connect(self.accept)
            btn_layout.addWidget(btn_ok)
            
        elif buttons == "yesno":
            btn_yes = QPushButton("Sim")
            btn_yes.setObjectName("PrimaryAction")
            btn_yes.setMinimumWidth(80)
            btn_yes.clicked.connect(self.accept)
            
            btn_no = QPushButton("Não")
            btn_no.setMinimumWidth(80)
            btn_no.clicked.connect(self.reject)
            
            btn_layout.addWidget(btn_no)
            btn_layout.addWidget(btn_yes)
            
        root_layout.addLayout(btn_layout)

    @staticmethod
    def information(parent, title: str, text: str) -> None:
        dlg = CustomDialog(parent, title, text, "information", "ok")
        dlg.exec()

    @staticmethod
    def warning(parent, title: str, text: str) -> None:
        dlg = CustomDialog(parent, title, text, "warning", "ok")
        dlg.exec()

    @staticmethod
    def critical(parent, title: str, text: str) -> None:
        dlg = CustomDialog(parent, title, text, "critical", "ok")
        dlg.exec()

    @staticmethod
    def question(parent, title: str, text: str) -> bool:
        dlg = CustomDialog(parent, title, text, "question", "yesno")
        return dlg.exec() == QDialog.DialogCode.Accepted
