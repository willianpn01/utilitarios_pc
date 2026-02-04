from __future__ import annotations
import os
import sys
import subprocess
import html
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QSpinBox,
    QGroupBox, QGridLayout, QProgressDialog, QMenu
)
from PyQt6.QtGui import QColor

from app.core.space_analyzer import analyze_directory, DirEntry, format_size, get_largest_items


class ScanWorker(QObject):
    done = pyqtSignal(object)  # DirEntry
    progress = pyqtSignal(str)
    
    def __init__(self, root: str, max_depth: int) -> None:
        super().__init__()
        self.root = root
        self.max_depth = max_depth
        self.cancel = False
    
    def run(self) -> None:
        try:
            self.progress.emit(f'Analisando {self.root}...')
            result = analyze_directory(self.root, self.max_depth)
            self.done.emit(result)
        except Exception as e:
            self.done.emit(None)


class SpaceAnalyzerWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._root_entry: Optional[DirEntry] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[ScanWorker] = None
        self._init_ui()
    
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)
        
        # === SEÇÃO 1: Seleção ===
        select_group = QGroupBox('📂 Selecionar pasta para analisar')
        select_layout = QGridLayout(select_group)
        select_layout.setSpacing(8)
        
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText('Escolha uma pasta para analisar o uso de espaço...')
        btn_browse = QPushButton('Escolher pasta')
        btn_browse.clicked.connect(self._choose_dir)
        
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 10)
        self.depth_spin.setValue(3)
        self.depth_spin.setToolTip('Profundidade da análise (maior = mais detalhado, mas mais lento)')
        
        self.btn_scan = QPushButton('🔍 Analisar')
        self.btn_scan.clicked.connect(self._on_scan)
        
        self.btn_export = QPushButton('📄 Exportar Relatório')
        self.btn_export.clicked.connect(self._on_export)
        self.btn_export.setEnabled(False)
        
        select_layout.addWidget(QLabel('Pasta:'), 0, 0)
        select_layout.addWidget(self.dir_edit, 0, 1)
        select_layout.addWidget(btn_browse, 0, 2)
        select_layout.addWidget(QLabel('Profundidade:'), 1, 0)
        select_layout.addWidget(self.depth_spin, 1, 1)
        select_layout.addWidget(self.btn_scan, 1, 2)
        select_layout.addWidget(self.btn_export, 1, 3)
        
        # === SEÇÃO 2: Resumo ===
        summary_group = QGroupBox('📊 Resumo')
        summary_layout = QVBoxLayout(summary_group)
        self.lbl_total = QLabel('Tamanho total: -')
        self.lbl_files = QLabel('Arquivos: -')
        self.lbl_dirs = QLabel('Pastas: -')
        summary_layout.addWidget(self.lbl_total)
        summary_layout.addWidget(self.lbl_files)
        summary_layout.addWidget(self.lbl_dirs)
        
        # === SEÇÃO 3: Árvore de diretórios ===
        tree_label = QLabel('🌳 Estrutura de pastas (ordenado por tamanho):')
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Nome', 'Tamanho', 'Arquivos', 'Pastas'])
        self.tree.setColumnWidth(0, 400)
        self.tree.setColumnWidth(1, 120)
        self.tree.setSortingEnabled(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        
        # === SEÇÃO 4: Top maiores ===
        top_label = QLabel('🔝 Top 20 maiores itens:')
        self.top_tree = QTreeWidget()
        self.top_tree.setHeaderLabels(['Nome', 'Tamanho', 'Tipo', 'Caminho'])
        self.top_tree.setColumnWidth(0, 250)
        self.top_tree.setColumnWidth(1, 100)
        self.top_tree.setColumnWidth(2, 80)
        self.top_tree.setSortingEnabled(False)
        self.top_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.top_tree.customContextMenuRequested.connect(self._on_top_context_menu)
        
        # Montagem
        top_section = QHBoxLayout()
        top_section.addWidget(summary_group)
        
        root.addWidget(select_group)
        root.addLayout(top_section)
        root.addWidget(tree_label)
        root.addWidget(self.tree, 2)
        root.addWidget(top_label)
        root.addWidget(self.top_tree, 1)
    
    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, 'Escolher pasta para análise')
        if d:
            self.dir_edit.setText(d)
    
    def _on_scan(self) -> None:
        directory = self.dir_edit.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(self, 'Aviso', 'Selecione uma pasta válida.')
            return
        
        max_depth = self.depth_spin.value()
        
        # Progress dialog
        prog = QProgressDialog('Analisando...', 'Cancelar', 0, 0, self)
        prog.setWindowTitle('Análise de Espaço')
        prog.setMinimumDuration(0)
        prog.setRange(0, 0)
        
        # Thread worker
        self.btn_scan.setEnabled(False)
        thread = QThread(self)
        worker = ScanWorker(directory, max_depth)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda msg: prog.setLabelText(msg))
        
        def finished(entry: Optional[DirEntry]):
            prog.close()
            self._root_entry = entry
            if entry:
                self._populate_tree(entry)
                self._populate_summary(entry)
                self._populate_top(entry)
                self.btn_export.setEnabled(True)
            else:
                QMessageBox.warning(self, 'Erro', 'Falha ao analisar o diretório.')
                self.btn_export.setEnabled(False)
            self.btn_scan.setEnabled(True)
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()
            self._thread = None
            self._worker = None
        
        worker.done.connect(finished)
        prog.canceled.connect(lambda: setattr(worker, 'cancel', True))
        self._thread = thread
        self._worker = worker
        thread.start()
    
    def _populate_summary(self, entry: DirEntry) -> None:
        self.lbl_total.setText(f'Tamanho total: {format_size(entry.size)}')
        self.lbl_files.setText(f'Arquivos: {entry.file_count:,}'.replace(',', '.'))
        self.lbl_dirs.setText(f'Pastas: {entry.dir_count:,}'.replace(',', '.'))
    
    def _populate_tree(self, entry: DirEntry) -> None:
        self.tree.clear()
        
        def _add_node(parent_item: Optional[QTreeWidgetItem], node: DirEntry) -> None:
            # Criar item
            if parent_item is None:
                item = QTreeWidgetItem(self.tree)
            else:
                item = QTreeWidgetItem(parent_item)
            
            item.setText(0, node.name)
            item.setText(1, format_size(node.size))
            item.setText(2, str(node.file_count))
            item.setText(3, str(node.dir_count))
            item.setData(0, Qt.ItemDataRole.UserRole, node.path)
            
            # Cor baseada no tipo
            if node.is_dir:
                item.setForeground(0, QColor(100, 150, 255))
            
            # Ordenar filhos por tamanho (maior primeiro)
            sorted_children = sorted(node.children, key=lambda x: x.size, reverse=True)
            
            # Adicionar filhos recursivamente
            for child in sorted_children:
                _add_node(item, child)
        
        _add_node(None, entry)
        self.tree.expandToDepth(0)
    
    def _populate_top(self, entry: DirEntry) -> None:
        self.top_tree.clear()
        largest = get_largest_items(entry, top_n=20)
        
        for item_entry in largest:
            item = QTreeWidgetItem(self.top_tree)
            item.setText(0, item_entry.name)
            item.setText(1, format_size(item_entry.size))
            item.setText(2, 'Pasta' if item_entry.is_dir else 'Arquivo')
            item.setText(3, item_entry.path)
            item.setData(0, Qt.ItemDataRole.UserRole, item_entry.path)
            
            if item_entry.is_dir:
                item.setForeground(0, QColor(100, 150, 255))
    
    def _on_tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        
        menu = QMenu(self)
        act_open = menu.addAction('Abrir pasta')
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == act_open:
            self._open_in_explorer(path)
    
    def _on_top_context_menu(self, pos) -> None:
        item = self.top_tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        
        menu = QMenu(self)
        act_open = menu.addAction('Abrir pasta')
        action = menu.exec(self.top_tree.viewport().mapToGlobal(pos))
        if action == act_open:
            self._open_in_explorer(path)
    
    def _open_in_explorer(self, path: str) -> None:
        try:
            if sys.platform.startswith('win'):
                if os.path.isfile(path):
                    subprocess.run(['explorer', '/select,', path], check=False)
                else:
                    subprocess.run(['explorer', path], check=False)
            elif sys.platform == 'darwin':
                if os.path.isfile(path):
                    subprocess.run(['open', '-R', path], check=False)
                else:
                    subprocess.run(['open', path], check=False)
            else:
                folder = path if os.path.isdir(path) else os.path.dirname(path)
                subprocess.run(['xdg-open', folder], check=False)
        except Exception:
            QMessageBox.warning(self, 'Aviso', 'Não foi possível abrir no explorador.')
    
    def _on_export(self) -> None:
        if not self._root_entry:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, 
            'Exportar Relatório', 
            f'relatorio_espaco_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
            'HTML Files (*.html);;All Files (*)'
        )
        if not path:
            return
        
        try:
            html_content = self._generate_html_report(self._root_entry)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Perguntar se quer abrir
            resp = QMessageBox.question(
                self, 
                'Relatório exportado', 
                f'Relatório salvo em:\n{path}\n\nDeseja abrir no navegador?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.Yes:
                if sys.platform.startswith('win'):
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path], check=False)
                else:
                    subprocess.run(['xdg-open', path], check=False)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao exportar relatório: {e}')
    
    def _generate_html_report(self, entry: DirEntry) -> str:
        """Gera relatório HTML com gráfico de pizza usando Chart.js"""
        # Pegar top 10 para o gráfico
        top_items = get_largest_items(entry, top_n=10)
        
        # Preparar dados para o gráfico
        labels = []
        sizes = []
        colors = [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
            '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384'
        ]
        
        for item in top_items:
            labels.append(html.escape(item.name[:30]))
            sizes.append(item.size)
        
        # Calcular "Outros"
        top_total = sum(sizes)
        if top_total < entry.size:
            labels.append('Outros')
            sizes.append(entry.size - top_total)
        
        # Top 20 para tabela
        top_20 = get_largest_items(entry, top_n=20)
        
        html_content = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório de Análise de Espaço</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        h1 {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        h2 {{
            color: #764ba2;
            margin-top: 30px;
            border-left: 4px solid #764ba2;
            padding-left: 10px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 28px;
            font-weight: bold;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 30px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .folder {{
            color: #667eea;
            font-weight: 500;
        }}
        .file {{
            color: #666;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Relatório de Análise de Espaço em Disco</h1>
        
        <p><strong>Pasta analisada:</strong> {html.escape(entry.path)}</p>
        <p><strong>Data da análise:</strong> {datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}</p>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Tamanho Total</h3>
                <div class="value">{format_size(entry.size)}</div>
            </div>
            <div class="summary-card">
                <h3>Total de Arquivos</h3>
                <div class="value">{entry.file_count:,}</div>
            </div>
            <div class="summary-card">
                <h3>Total de Pastas</h3>
                <div class="value">{entry.dir_count:,}</div>
            </div>
        </div>
        
        <h2>📈 Distribuição de Espaço (Top 10)</h2>
        <div class="chart-container">
            <canvas id="pieChart"></canvas>
        </div>
        
        <h2>🔝 Top 20 Maiores Itens</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Nome</th>
                    <th>Tamanho</th>
                    <th>Tipo</th>
                    <th>Caminho</th>
                </tr>
            </thead>
            <tbody>
'''
        
        for i, item in enumerate(top_20, 1):
            item_type = 'Pasta' if item.is_dir else 'Arquivo'
            css_class = 'folder' if item.is_dir else 'file'
            html_content += f'''
                <tr>
                    <td>{i}</td>
                    <td class="{css_class}">{html.escape(item.name)}</td>
                    <td>{format_size(item.size)}</td>
                    <td>{item_type}</td>
                    <td style="font-size: 11px; color: #999;">{html.escape(item.path)}</td>
                </tr>
'''
        
        html_content += f'''
            </tbody>
        </table>
        
        <div class="footer">
            Relatório gerado por Aplicativo de Utilitários - Analisador de Espaço
        </div>
    </div>
    
    <script>
        const ctx = document.getElementById('pieChart').getContext('2d');
        const pieChart = new Chart(ctx, {{
            type: 'pie',
            data: {{
                labels: {labels},
                datasets: [{{
                    data: {sizes},
                    backgroundColor: {colors[:len(labels)]},
                    borderWidth: 2,
                    borderColor: '#fff'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'right',
                        labels: {{
                            font: {{
                                size: 12
                            }},
                            padding: 15
                        }}
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                
                                // Formatar tamanho
                                let size = value;
                                const units = ['B', 'KB', 'MB', 'GB', 'TB'];
                                let unitIndex = 0;
                                while (size >= 1024 && unitIndex < units.length - 1) {{
                                    size /= 1024;
                                    unitIndex++;
                                }}
                                
                                return label + ': ' + size.toFixed(1) + ' ' + units[unitIndex] + ' (' + percentage + '%)';
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
'''
        return html_content
    
    def closeEvent(self, event):  # type: ignore[override]
        if self._thread is not None and self._thread.isRunning():
            if self._worker is not None:
                try:
                    setattr(self._worker, 'cancel', True)
                except Exception:
                    pass
            self._thread.quit()
            self._thread.wait(3000)
        return super().closeEvent(event)
