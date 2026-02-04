from __future__ import annotations
import os
import platform
import shutil
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QGroupBox, QFrame, QPushButton, QScrollArea
)
from PyQt6.QtGui import QFont


class DashboardWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._init_ui()
        
        # Atualizar informações periodicamente
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_system_info)
        self.timer.start(5000)  # Atualizar a cada 5 segundos
    
    def _init_ui(self) -> None:
        # Scroll area para conteúdo
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(20)
        
        # === CABEÇALHO ===
        header = QLabel('🛠️ Bem-vindo ao Aplicativo de Utilitários')
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle = QLabel('Ferramentas essenciais para produtividade e gerenciamento de arquivos')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet('color: #9ca3af; font-size: 14px;')
        
        root.addWidget(header)
        root.addWidget(subtitle)
        root.addSpacing(10)
        
        # === INFORMAÇÕES DO SISTEMA ===
        system_group = QGroupBox('💻 Informações do Sistema')
        system_layout = QGridLayout(system_group)
        system_layout.setSpacing(10)
        
        self.lbl_os = QLabel()
        self.lbl_python = QLabel()
        self.lbl_user = QLabel()
        self.lbl_disk_c = QLabel()
        self.lbl_time = QLabel()
        
        system_layout.addWidget(QLabel('Sistema Operacional:'), 0, 0)
        system_layout.addWidget(self.lbl_os, 0, 1)
        system_layout.addWidget(QLabel('Versão Python:'), 1, 0)
        system_layout.addWidget(self.lbl_python, 1, 1)
        system_layout.addWidget(QLabel('Usuário:'), 2, 0)
        system_layout.addWidget(self.lbl_user, 2, 1)
        system_layout.addWidget(QLabel('Espaço em Disco (C:):'), 3, 0)
        system_layout.addWidget(self.lbl_disk_c, 3, 1)
        system_layout.addWidget(QLabel('Data/Hora:'), 4, 0)
        system_layout.addWidget(self.lbl_time, 4, 1)
        
        self._update_system_info()
        
        # === FERRAMENTAS DISPONÍVEIS ===
        tools_group = QGroupBox('🔧 Ferramentas Disponíveis')
        tools_layout = QGridLayout(tools_group)
        tools_layout.setSpacing(15)
        
        tools = [
            ('📁', 'Criador de Estrutura\nde Projetos', 'Crie estruturas de pastas predefinidas'),
            ('📝', 'Renomeador\nem Massa', 'Renomeie múltiplos arquivos de uma vez'),
            ('🗂️', 'Organizador\nAutomático', 'Organize arquivos por tipo/extensão'),
            ('🔍', 'Localizador de\nDuplicados', 'Encontre e remova arquivos duplicados'),
            ('💾', 'Analisador de\nEspaço', 'Analise o uso de espaço em disco'),
            ('🔄', 'Comparador de\nPastas', 'Compare e sincronize diretórios'),
            ('🖼️', 'Redimensionador\nde Imagens', 'Redimensione e converta imagens'),
            ('📋', 'Histórico da Área\nde Transferência', 'Monitore e salve seu histórico'),
        ]
        
        row, col = 0, 0
        for icon, title, desc in tools:
            card = self._create_tool_card(icon, title, desc)
            tools_layout.addWidget(card, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
        
        # === DICAS RÁPIDAS ===
        tips_group = QGroupBox('💡 Dicas Rápidas')
        tips_layout = QVBoxLayout(tips_group)
        
        tips = [
            '• Use o <b>Renomeador em Massa</b> para renomear episódios de séries sequencialmente',
            '• O <b>Organizador Automático</b> pode limpar sua pasta de Downloads rapidamente',
            '• O <b>Localizador de Duplicados</b> usa hash SHA-256 para garantir precisão',
            '• Exporte relatórios HTML do <b>Analisador de Espaço</b> com gráficos interativos',
            '• O <b>Comparador de Pastas</b> pode sincronizar backups bidirecionalmente',
            '• Use o <b>Redimensionador de Imagens</b> para converter para WebP e economizar espaço',
            '• Fixe itens importantes no <b>Histórico da Área de Transferência</b>',
            '• Todos os dados são armazenados localmente - sem telemetria',
        ]
        
        for tip in tips:
            lbl = QLabel(tip)
            lbl.setWordWrap(True)
            lbl.setStyleSheet('padding: 5px;')
            tips_layout.addWidget(lbl)
        
        # === ATALHOS ===
        shortcuts_group = QGroupBox('⌨️ Atalhos Úteis')
        shortcuts_layout = QVBoxLayout(shortcuts_group)
        
        shortcuts = [
            'Use a <b>barra lateral</b> para navegar entre as ferramentas',
            'Clique com o <b>botão direito</b> em itens para ver opções adicionais',
            'A maioria das operações pode ser <b>cancelada</b> durante o processamento',
            'Arquivos excluídos vão para a <b>Lixeira</b> (reversível)',
        ]
        
        for shortcut in shortcuts:
            lbl = QLabel(f'• {shortcut}')
            lbl.setWordWrap(True)
            lbl.setStyleSheet('padding: 3px;')
            shortcuts_layout.addWidget(lbl)
        
        # === RODAPÉ ===
        footer = QLabel('Desenvolvido com ❤️ usando Python e PyQt6')
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet('color: #6b7280; font-size: 12px; margin-top: 20px;')
        
        # Montagem
        root.addWidget(system_group)
        root.addWidget(tools_group)
        root.addWidget(tips_group)
        root.addWidget(shortcuts_group)
        root.addWidget(footer)
        root.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_tool_card(self, icon: str, title: str, description: str) -> QFrame:
        """Cria um card para uma ferramenta"""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet('''
            QFrame {
                padding: 15px;
            }
        ''')
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Ícone
        icon_lbl = QLabel(icon)
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_lbl.setFont(icon_font)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Título
        title_lbl = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setWordWrap(True)
        
        # Descrição
        desc_lbl = QLabel(description)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet('color: #9ca3af; font-size: 10px;')
        
        layout.addWidget(icon_lbl)
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)
        
        card.setMinimumHeight(150)
        
        return card
    
    def _update_system_info(self) -> None:
        """Atualiza as informações do sistema"""
        # Sistema operacional
        os_info = f'{platform.system()} {platform.release()}'
        self.lbl_os.setText(os_info)
        
        # Python
        python_version = platform.python_version()
        self.lbl_python.setText(python_version)
        
        # Usuário
        username = os.getlogin()
        self.lbl_user.setText(username)
        
        # Espaço em disco
        try:
            if platform.system() == 'Windows':
                disk = shutil.disk_usage('C:')
            else:
                disk = shutil.disk_usage('/')
            
            total_gb = disk.total / (1024**3)
            used_gb = disk.used / (1024**3)
            free_gb = disk.free / (1024**3)
            percent = (disk.used / disk.total) * 100
            
            disk_info = f'{used_gb:.1f} GB usado de {total_gb:.1f} GB ({percent:.1f}% usado, {free_gb:.1f} GB livre)'
            self.lbl_disk_c.setText(disk_info)
        except Exception:
            self.lbl_disk_c.setText('Não disponível')
        
        # Data/Hora
        now = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        self.lbl_time.setText(now)
    
    def closeEvent(self, event):  # type: ignore[override]
        """Para o timer ao fechar"""
        if self.timer:
            self.timer.stop()
        return super().closeEvent(event)
