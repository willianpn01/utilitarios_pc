from __future__ import annotations
import html
import os
import subprocess
import sys
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QSpinBox,
    QGroupBox, QGridLayout, QProgressDialog, QMenu, QApplication,
)
from PyQt6.QtGui import QColor

from app.core.space_analyzer import analyze_directory, DirEntry, format_size, get_largest_items
from app.core.app_settings import load_setting, save_setting
from app.core.logger import get_logger

log = get_logger(__name__)

INDETERMINATE_THRESHOLD = 5
_SETTING_KEY = 'space_analyzer.last_dir'

# ── Worker ────────────────────────────────────────────────────────────────────

class _ScanWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)   # DirEntry or None
    error    = pyqtSignal(str)

    def __init__(self, root: str, max_depth: int) -> None:
        super().__init__()
        self._root      = root
        self._max_depth = max_depth
        self._cancelled = False

    def cancel(self) -> None:
        log.debug("SpaceAnalyzer: cancel() invocado.")
        self._cancelled = True

    def run(self) -> None:
        log.debug("SpaceAnalyzer: Iniciando varredura na thread.")
        try:
            result = analyze_directory(
                self._root,
                self._max_depth,
                progress_cb=lambda p, s: self.progress.emit(p, s),
                cancel_check=lambda: self._cancelled,
            )
            log.debug(f"SpaceAnalyzer: Varredura finalizada. Result is None? {result is None}")
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Widget principal ───────────────────────────────────────────────────────────

class SpaceAnalyzerWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._root_entry: Optional[DirEntry] = None
        self._thread: Optional[QThread]      = None
        self._worker: Optional[_ScanWorker]  = None
        self._init_ui()
        # Melhoria 1: pré-preencher com último diretório usado
        last_dir = load_setting(_SETTING_KEY)
        if last_dir and os.path.isdir(last_dir):
            self.dir_edit.setText(last_dir)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # === SEÇÃO 1: Seleção ===
        select_group = QGroupBox('📂 Selecionar pasta para analisar')
        select_layout = QGridLayout(select_group)
        select_layout.setSpacing(8)

        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText('Escolha uma pasta para analisar o uso de espaço…')
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
        self.lbl_dirs  = QLabel('Pastas: -')
        summary_layout.addWidget(self.lbl_total)
        summary_layout.addWidget(self.lbl_files)
        summary_layout.addWidget(self.lbl_dirs)

        # === SEÇÃO 3: Árvore ===
        tree_label = QLabel('🌳 Estrutura de pastas (ordenado por tamanho):')
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Nome', 'Tamanho', 'Arquivos', 'Pastas'])
        self.tree.setColumnWidth(0, 400)
        self.tree.setColumnWidth(1, 120)
        self.tree.setSortingEnabled(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_clicked)  # Melhoria 4

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
        self.top_tree.itemDoubleClicked.connect(self._on_tree_double_clicked)  # Melhoria 4

        top_section = QHBoxLayout()
        top_section.addWidget(summary_group)

        root.addWidget(select_group)
        root.addLayout(top_section)
        root.addWidget(tree_label)
        root.addWidget(self.tree, 2)
        root.addWidget(top_label)
        root.addWidget(self.top_tree, 1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, 'Escolher pasta para análise')
        if d:
            self.dir_edit.setText(d)
            save_setting(_SETTING_KEY, d)  # Melhoria 1: persiste último dir

    def _notify_tray(self, message: str) -> None:
        from app.core.system_tray import notify_tray
        notify_tray('Analisador de Espaço', message)

    def _stop_thread(self) -> None:
        if self._worker:
            log.debug("SpaceAnalyzer._stop_thread: Cancelando worker...")
            try:
                self._worker.cancel()
            except Exception:
                pass
        if self._thread and self._thread.isRunning():
            log.debug("SpaceAnalyzer._stop_thread: Aguardando encerramento da thread...")
            self._thread.quit()
            started_wait = self._thread.wait(3000)
            log.debug(f"SpaceAnalyzer._stop_thread: thread terminou no prazo de 3s? {started_wait}")
        self._thread = None
        self._worker = None

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _on_scan(self) -> None:
        directory = self.dir_edit.text().strip()
        if not directory or not os.path.isdir(directory):
            CustomDialog.warning(self, 'Aviso', 'Selecione uma pasta válida.')
            return

        self._stop_thread()

        try:
            with os.scandir(directory) as it:
                top_level_count = sum(1 for _ in it)
        except OSError:
            top_level_count = 0

        if top_level_count <= INDETERMINATE_THRESHOLD:
            prog = QProgressDialog('Iniciando análise…', 'Cancelar', 0, 0, self)
        else:
            prog = QProgressDialog('Iniciando análise…', 'Cancelar', 0, 100, self)
            
        prog.setWindowTitle('Análise de Espaço')
        prog.setMinimumDuration(0)
        prog.setWindowModality(Qt.WindowModality.WindowModal)

        self.btn_scan.setEnabled(False)
        self.btn_export.setEnabled(False)

        thread = QThread(self)
        worker = _ScanWorker(directory, self.depth_spin.value())
        worker.moveToThread(thread)

        def on_progress(pct: int, msg: str) -> None:
            prog.setValue(pct)
            prog.setLabelText(msg)

        def on_finished(entry: Optional[DirEntry]) -> None:
            prog.close()
            self._root_entry = entry
            if entry:
                self._populate_tree(entry)
                self._populate_summary(entry)
                self._populate_top(entry)
                self.btn_export.setEnabled(True)
                if not worker._cancelled:
                    self._notify_tray(
                        f'Análise de espaço concluída: {format_size(entry.size)} em {entry.file_count} arquivo(s).'
                    )
            else:
                CustomDialog.warning(self, 'Aviso', 'Análise cancelada ou sem resultado.')
                self.btn_export.setEnabled(False)
            self.btn_scan.setEnabled(True)
            thread.quit(); thread.wait()
            worker.deleteLater(); thread.deleteLater()
            self._thread = None; self._worker = None

        def on_error(msg: str) -> None:
            prog.close()
            self.btn_scan.setEnabled(True)
            CustomDialog.critical(self, 'Erro na Análise', msg)
            thread.quit(); thread.wait()
            worker.deleteLater(); thread.deleteLater()
            self._thread = None; self._worker = None

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        
        # Conexão segura (bypass de queued slot que pendurava a thread):
        prog.canceled.connect(lambda: worker.cancel())
        thread.started.connect(worker.run)

        self._thread = thread
        self._worker = worker
        thread.start()

    # ── Populate ─────────────────────────────────────────────────────────────

    def _populate_summary(self, entry: DirEntry) -> None:
        self.lbl_total.setText(f'Tamanho total: {format_size(entry.size)}')
        self.lbl_files.setText(f'Arquivos: {entry.file_count:,}'.replace(',', '.'))
        self.lbl_dirs.setText(f'Pastas: {entry.dir_count:,}'.replace(',', '.'))

    def _populate_tree(self, entry: DirEntry) -> None:
        self.tree.clear()

        def _add_node(parent_item: Optional[QTreeWidgetItem], node: DirEntry) -> None:
            item = QTreeWidgetItem(self.tree if parent_item is None else parent_item)
            item.setText(0, node.name)
            item.setText(1, format_size(node.size))
            item.setText(2, str(node.file_count))
            item.setText(3, str(node.dir_count))
            item.setData(0, Qt.ItemDataRole.UserRole, node.path)
            if node.is_dir:
                item.setForeground(0, QColor(100, 150, 255))
            for child in sorted(node.children, key=lambda x: x.size, reverse=True):
                _add_node(item, child)

        _add_node(None, entry)
        self.tree.expandToDepth(0)

    def _populate_top(self, entry: DirEntry) -> None:
        self.top_tree.clear()
        for item_entry in get_largest_items(entry, top_n=20):
            item = QTreeWidgetItem(self.top_tree)
            item.setText(0, item_entry.name)
            item.setText(1, format_size(item_entry.size))
            item.setText(2, 'Pasta' if item_entry.is_dir else 'Arquivo')
            item.setText(3, item_entry.path)
            item.setData(0, Qt.ItemDataRole.UserRole, item_entry.path)
            if item_entry.is_dir:
                item.setForeground(0, QColor(100, 150, 255))

    # ── Context Menus ─────────────────────────────────────────────────────────

    def _on_tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        menu = QMenu(self)
        act_open = menu.addAction('Abrir pasta')
        if menu.exec(self.tree.viewport().mapToGlobal(pos)) == act_open:
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
        if menu.exec(self.top_tree.viewport().mapToGlobal(pos)) == act_open:
            self._open_in_explorer(path)

    def _on_tree_double_clicked(self, item) -> None:
        """Melhoria 4: abre o item no Explorer ao dar duplo-clique."""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        if not os.path.exists(path):
            CustomDialog.warning(self, 'Item não encontrado',
                                f'O caminho não existe mais no disco:\n{path}')
            return
        self._open_in_explorer(path)

    def _open_in_explorer(self, path: str) -> None:
        try:
            if sys.platform.startswith('win'):
                if os.path.isfile(path):
                    subprocess.run(['explorer', '/select,', path], check=False)
                else:
                    subprocess.run(['explorer', path], check=False)
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R' if os.path.isfile(path) else '', path], check=False)
            else:
                folder = path if os.path.isdir(path) else os.path.dirname(path)
                subprocess.run(['xdg-open', folder], check=False)
        except Exception:
            CustomDialog.warning(self, 'Aviso', 'Não foi possível abrir no explorador.')

    # ── Exportar ──────────────────────────────────────────────────────────────

    def _on_export(self) -> None:
        if not self._root_entry:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Exportar Relatório',
            f'relatorio_espaco_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
            'HTML Files (*.html);;All Files (*)',
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._generate_html_report(self._root_entry))
            resp = CustomDialog.question(
                self, 'Relatório exportado',
                f'Relatório salvo em:\n{path}\n\nDeseja abrir no navegador?',
            )
            if resp:
                if sys.platform.startswith('win'):
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path], check=False)
                else:
                    subprocess.run(['xdg-open', path], check=False)
        except Exception as e:
            CustomDialog.critical(self, 'Erro', f'Falha ao exportar relatório: {e}')

    def _generate_html_report(self, entry: DirEntry) -> str:
        top_items = get_largest_items(entry, top_n=10)
        labels = [html.escape(i.name[:30]) for i in top_items]
        sizes  = [i.size for i in top_items]
        colors = [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
            '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384',
        ]
        if sum(sizes) < entry.size:
            labels.append('Outros')
            sizes.append(entry.size - sum(sizes))

        top_20 = get_largest_items(entry, top_n=20)
        rows = ''.join(
            f'''<tr>
                <td>{i}</td>
                <td class="{'folder' if it.is_dir else 'file'}">{html.escape(it.name)}</td>
                <td>{format_size(it.size)}</td>
                <td>{'Pasta' if it.is_dir else 'Arquivo'}</td>
                <td style="font-size:11px;color:#999">{html.escape(it.path)}</td>
            </tr>'''
            for i, it in enumerate(top_20, 1)
        )

        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório de Análise de Espaço</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
body{{font-family:'Segoe UI',sans-serif;margin:0;padding:20px;background:linear-gradient(135deg,#667eea,#764ba2);color:#333}}
.container{{max-width:1200px;margin:0 auto;background:#fff;border-radius:12px;padding:30px;box-shadow:0 10px 40px rgba(0,0,0,.2)}}
h1{{color:#667eea;border-bottom:3px solid #667eea;padding-bottom:10px}}
h2{{color:#764ba2;border-left:4px solid #764ba2;padding-left:10px}}
.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin:20px 0}}
.card{{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px;border-radius:8px}}
.card h3{{margin:0 0 10px;font-size:14px;opacity:.9}}
.card .value{{font-size:28px;font-weight:bold}}
.chart-container{{position:relative;height:400px;margin:30px 0}}
table{{width:100%;border-collapse:collapse;margin:20px 0}}
th,td{{padding:12px;text-align:left;border-bottom:1px solid #ddd}}
th{{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}}
tr:hover{{background:#f5f5f5}}
.folder{{color:#667eea;font-weight:500}}
.file{{color:#666}}
</style>
</head>
<body>
<div class="container">
<h1>📊 Relatório de Análise de Espaço em Disco</h1>
<p><strong>Pasta:</strong> {html.escape(entry.path)}</p>
<p><strong>Data:</strong> {datetime.now().strftime("%d/%m/%Y às %H:%M:%S")}</p>
<div class="summary">
  <div class="card"><h3>Tamanho Total</h3><div class="value">{format_size(entry.size)}</div></div>
  <div class="card"><h3>Arquivos</h3><div class="value">{entry.file_count:,}</div></div>
  <div class="card"><h3>Pastas</h3><div class="value">{entry.dir_count:,}</div></div>
</div>
<h2>📈 Distribuição de Espaço (Top 10)</h2>
<div class="chart-container"><canvas id="pieChart"></canvas></div>
<h2>🔝 Top 20 Maiores Itens</h2>
<table><thead><tr><th>#</th><th>Nome</th><th>Tamanho</th><th>Tipo</th><th>Caminho</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<script>
new Chart(document.getElementById('pieChart'),{{
  type:'pie',
  data:{{labels:{labels},datasets:[{{data:{sizes},backgroundColor:{colors[:len(labels)]},borderWidth:2,borderColor:'#fff'}}]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'right'}},
    tooltip:{{callbacks:{{label:function(c){{
      const v=c.parsed,t=c.dataset.data.reduce((a,b)=>a+b,0);
      let s=v;const u=['B','KB','MB','GB','TB'];let i=0;
      while(s>=1024&&i<u.length-1){{s/=1024;i++;}}
      return c.label+': '+s.toFixed(1)+' '+u[i]+' ('+((v/t)*100).toFixed(1)+'%)';
    }}}}}}}}}}
}});
</script>
</body></html>'''

    # ── Limpeza ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_thread()
        super().closeEvent(event)
