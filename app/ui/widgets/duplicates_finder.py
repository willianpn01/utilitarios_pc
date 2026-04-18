from __future__ import annotations
import os
import sys
import subprocess
from typing import List, Optional

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QProgressDialog, QApplication, QMenu, QHeaderView, QAbstractItemView,
)
from PyQt6.QtGui import QColor, QBrush

from app.core.duplicates import find_duplicates
from app.core.app_settings import load_setting, save_setting
from app.core.logger import get_logger
from app.ui.custom_dialog import CustomDialog

log = get_logger(__name__)

_SETTING_KEY = 'duplicates_finder.last_dir'

# Cores alternadas para grupos (tons escuros sutis)
_GROUP_COLORS = [
    QColor(40, 42, 54),    # Padrão escuro
    QColor(50, 52, 64),    # Levemente mais claro
]


def _human_size(size_bytes: int) -> str:
    """Formata tamanho em bytes para leitura humana."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _elide_path(path: str, max_chars: int = 80) -> str:
    """
    Trunca um caminho de arquivo mantendo o início (drive/raiz) e o final (nome do arquivo).
    Exemplo: /home/user/.../subdir/arquivo_muito_longo_que_nao_cab...ado.txt
    """
    if len(path) <= max_chars:
        return path
    
    basename = os.path.basename(path)
    dirname = os.path.dirname(path)
    
    # Se só o nome já é grande, truncar o nome
    if len(basename) > max_chars - 10:
        name, ext = os.path.splitext(basename)
        available = max_chars - len(ext) - 3  # 3 para "..."
        basename = name[:available] + "..." + ext
        return basename
    
    # Truncar o diretório, mantendo início e nome do arquivo
    available = max_chars - len(basename) - 5  # 5 para "/.../"
    if available < 10:
        return ".../" + basename
    
    # Mostrar início do diretório + ... + nome
    return dirname[:available] + "/.../" + basename


# ── Worker ────────────────────────────────────────────────────────────────────

class _ScanWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)   # list[list[str]]
    error    = pyqtSignal(str)

    def __init__(self, root: str, recursive: bool, min_size: int,
                 include_exts: set | None) -> None:
        super().__init__()
        self._root         = root
        self._recursive    = recursive
        self._min_size     = min_size
        self._include_exts = include_exts
        self._cancelled    = False

    def cancel(self) -> None:
        log.debug("DuplicatesFinder: cancel() invocado.")
        self._cancelled = True

    def run(self) -> None:
        log.debug("DuplicatesFinder: Iniciando varredura na thread.")
        try:
            result = find_duplicates(
                self._root,
                recursive=self._recursive,
                min_size_bytes=self._min_size,
                include_exts=self._include_exts,
                progress_cb=lambda p, s: self.progress.emit(p, s),
                cancel_check=lambda: self._cancelled,
            )
            log.debug(f"DuplicatesFinder: Varredura finalizada. Result list size: {len(result)}")
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Widget principal ───────────────────────────────────────────────────────────

class DuplicatesFinderWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._groups: List[List[str]] = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[_ScanWorker] = None
        self._init_ui()
        # Pré-preencher com último diretório usado
        last_dir = load_setting(_SETTING_KEY)
        if last_dir and os.path.isdir(last_dir):
            self.ed_dir.setText(last_dir)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Linha 1: diretório
        row = QHBoxLayout()
        self.ed_dir = QLineEdit()
        self.ed_dir.setPlaceholderText('Pasta para escanear…')
        btn_browse = QPushButton('Escolher…')
        btn_browse.clicked.connect(self._choose_dir)
        self.chk_recursive = QCheckBox('Incluir subpastas')
        self.chk_recursive.setChecked(True)
        row.addWidget(QLabel('Diretório:'))
        row.addWidget(self.ed_dir, 1)
        row.addWidget(btn_browse)
        row.addWidget(self.chk_recursive)

        # Linha 2: filtros + ações
        row2 = QHBoxLayout()
        row2.addWidget(QLabel('Tamanho mínimo (KB):'))
        self.sp_min_kb = QSpinBox()
        self.sp_min_kb.setRange(1, 10_000_000)
        self.sp_min_kb.setValue(1)
        row2.addWidget(self.sp_min_kb)
        row2.addSpacing(16)
        self.ed_exts = QLineEdit()
        self.ed_exts.setPlaceholderText('Filtrar extensões (ex: .jpg,.png)')
        row2.addWidget(QLabel('Extensões:'))
        row2.addWidget(self.ed_exts, 1)
        self.btn_scan = QPushButton('Escanear')
        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_export = QPushButton('Exportar CSV')
        self.btn_export.clicked.connect(self._on_export)
        self.btn_export.setEnabled(False)
        self.btn_select_keep_newest = QPushButton('Selecionar (manter mais recente)')
        self.btn_select_keep_newest.clicked.connect(self._on_select_keep_newest)
        self.btn_select_keep_newest.setEnabled(False)
        self.btn_trash = QPushButton('Enviar para Lixeira')
        self.btn_trash.clicked.connect(self._on_trash_selected)
        self.btn_trash.setEnabled(False)
        row2.addWidget(self.btn_scan)
        row2.addWidget(self.btn_select_keep_newest)
        row2.addWidget(self.btn_trash)
        row2.addWidget(self.btn_export)

        # Tabela — configuração robusta contra overflow
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Grupo', 'Tamanho', 'Nome', 'Caminho', 'Excluir?'])
        
        # Configurar colunas para não estourar
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Grupo
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Tamanho
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)       # Nome
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)           # Caminho (expande)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Excluir?
        header.setMinimumSectionSize(50)
        
        # Largura inicial razoável para "Nome"
        self.table.setColumnWidth(2, 200)
        
        # Scroll horizontal caso necessário, mas evitar overflow visual
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setWordWrap(False)
        
        # Seleção por linha inteira
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Menu de contexto
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)

        self.lbl_summary = QLabel('Pronto')

        root.addLayout(row)
        root.addLayout(row2)
        root.addWidget(self.table, 1)
        root.addWidget(self.lbl_summary)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, 'Escolher diretório')
        if d:
            self.ed_dir.setText(d)
            save_setting(_SETTING_KEY, d)

    def _notify_tray(self, message: str) -> None:
        try:
            from app.core.system_tray import notify_tray
            notify_tray('Localizador de Duplicados', message)
        except Exception:
            pass

    def _stop_thread(self) -> None:
        if self._worker:
            log.debug("DuplicatesFinder._stop_thread: Cancelando worker...")
            try:
                self._worker.cancel()
            except Exception:
                pass
        if self._thread and self._thread.isRunning():
            log.debug("DuplicatesFinder._stop_thread: Aguardando encerramento da thread...")
            self._thread.quit()
            started_wait = self._thread.wait(3000)
            log.debug(f"DuplicatesFinder._stop_thread: thread terminou no prazo de 3s? {started_wait}")
        self._thread = None
        self._worker = None

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _on_scan(self) -> None:
        directory = self.ed_dir.text().strip()
        if not directory or not os.path.isdir(directory):
            CustomDialog.warning(self, 'Aviso', 'Selecione um diretório válido.')
            return

        self._stop_thread()

        include_exts: set | None = None
        txt = self.ed_exts.text().strip()
        if txt:
            include_exts = set()
            for p in txt.split(','):
                e = p.strip().lower()
                if not e:
                    continue
                if not e.startswith('.'):
                    e = '.' + e
                include_exts.add(e)
        min_size = max(1, self.sp_min_kb.value()) * 1024

        prog = QProgressDialog('Iniciando varredura…', 'Cancelar', 0, 100, self)
        prog.setWindowTitle('Procurando Duplicados')
        prog.setMinimumDuration(0)
        prog.setWindowModality(Qt.WindowModality.WindowModal)

        self.btn_scan.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_select_keep_newest.setEnabled(False)
        self.btn_trash.setEnabled(False)

        thread = QThread(self)
        worker = _ScanWorker(directory, self.chk_recursive.isChecked(), min_size, include_exts)
        worker.moveToThread(thread)

        def on_progress(pct: int, msg: str) -> None:
            prog.setValue(pct)
            prog.setLabelText(msg)

        def on_finished(groups: list) -> None:
            prog.close()
            # Ordenar por espaço desperdiçado desc (tamanho × cópias - 1)
            def _wasted(g: list) -> int:
                try:
                    return os.path.getsize(g[0]) * (len(g) - 1) if g else 0
                except OSError:
                    return 0
            groups = sorted(groups, key=_wasted, reverse=True)
            self._groups = groups
            self._populate_table(groups)
            self.btn_scan.setEnabled(True)
            has_groups = len(groups) > 0
            self.btn_export.setEnabled(has_groups)
            self.btn_select_keep_newest.setEnabled(has_groups)
            self.btn_trash.setEnabled(has_groups)
            if groups:
                total_files = sum(len(g) for g in groups)
                total_wasted = sum(_wasted(g) for g in groups)
                self.lbl_summary.setText(
                    f'Encontrados {len(groups)} grupos de duplicados '
                    f'({total_files} arquivos, ~{_human_size(total_wasted)} desperdiçados)'
                )
                self._notify_tray(f'Varredura concluída: {len(groups)} grupo(s) de duplicados.')
            else:
                self.lbl_summary.setText('Nenhum duplicado encontrado')
            thread.quit(); thread.wait()
            worker.deleteLater(); thread.deleteLater()
            self._thread = None; self._worker = None

        def on_error(msg: str) -> None:
            prog.close()
            self.btn_scan.setEnabled(True)
            CustomDialog.critical(self, 'Erro na Varredura', msg)
            thread.quit(); thread.wait()
            worker.deleteLater(); thread.deleteLater()
            self._thread = None; self._worker = None

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        prog.canceled.connect(lambda: worker.cancel())
        thread.started.connect(worker.run)

        self._thread = thread
        self._worker = worker
        thread.start()

    # ── Tabela ────────────────────────────────────────────────────────────────

    def _populate_table(self, groups: list) -> None:
        """
        Popula a tabela de resultados de forma eficiente.
        
        Otimizações:
        - Desativa atualizações visuais durante inserção em massa
        - Desativa ordenação durante inserção
        - Pré-aloca o número total de linhas
        - Usa cores alternadas por grupo para fácil identificação visual
        - Trunca nomes longos com tooltip do caminho completo
        """
        # Desativar atualizações visuais para evitar re-layout a cada inserção
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        
        try:
            # Pré-calcular número total de linhas
            total_rows = sum(len(g) for g in groups)
            self.table.setRowCount(total_rows)
            
            current_row = 0
            for grp_idx, g in enumerate(groups, start=1):
                try:
                    size = os.path.getsize(g[0]) if g else 0
                except OSError:
                    size = 0
                
                size_str = _human_size(size)
                color = _GROUP_COLORS[grp_idx % len(_GROUP_COLORS)]
                brush = QBrush(color)
                
                for path in g:
                    basename = os.path.basename(path)
                    dirname = os.path.dirname(path)
                    
                    # Coluna 0: Grupo
                    item_grp = QTableWidgetItem(str(grp_idx))
                    item_grp.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item_grp.setBackground(brush)
                    item_grp.setFlags(item_grp.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(current_row, 0, item_grp)
                    
                    # Coluna 1: Tamanho
                    item_size = QTableWidgetItem(size_str)
                    item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item_size.setBackground(brush)
                    item_size.setFlags(item_size.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(current_row, 1, item_size)
                    
                    # Coluna 2: Nome do arquivo (truncado se muito longo)
                    display_name = basename
                    if len(display_name) > 60:
                        name_part, ext = os.path.splitext(display_name)
                        display_name = name_part[:55] + "…" + ext
                    item_name = QTableWidgetItem(display_name)
                    item_name.setToolTip(basename)  # Nome completo no tooltip
                    item_name.setBackground(brush)
                    item_name.setFlags(item_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(current_row, 2, item_name)
                    
                    # Coluna 3: Diretório (truncado, com tooltip do path completo)
                    display_dir = _elide_path(dirname, max_chars=70)
                    item_dir = QTableWidgetItem(display_dir)
                    item_dir.setToolTip(path)  # Caminho completo no tooltip
                    item_dir.setBackground(brush)
                    item_dir.setFlags(item_dir.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    # Guardar o path completo em data role para uso posterior
                    item_dir.setData(Qt.ItemDataRole.UserRole, path)
                    self.table.setItem(current_row, 3, item_dir)
                    
                    # Coluna 4: Checkbox de exclusão
                    chk = QTableWidgetItem('')
                    chk.setFlags(chk.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    chk.setCheckState(Qt.CheckState.Unchecked)
                    chk.setBackground(brush)
                    chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(current_row, 4, chk)
                    
                    current_row += 1
        
        finally:
            # Reativar atualizações visuais — dispara um único repaint
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)

    def _get_path_from_row(self, row: int) -> str:
        """Retorna o caminho completo de um arquivo na linha da tabela."""
        dir_item = self.table.item(row, 3)
        if dir_item:
            # Caminho completo guardado em UserRole
            full_path = dir_item.data(Qt.ItemDataRole.UserRole)
            if full_path:
                return full_path
            # Fallback: combinar nome + diretório
            name_item = self.table.item(row, 2)
            if name_item:
                return os.path.join(dir_item.toolTip(), name_item.toolTip())
        return ""

    def _on_select_keep_newest(self) -> None:
        if not self._groups:
            return
        # Desmarcar todos primeiro
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 4)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)
        
        # Agrupar por ID de grupo e encontrar o mais recente
        groups_map: dict = {}
        for r in range(self.table.rowCount()):
            grp_item = self.table.item(r, 0)
            if not grp_item:
                continue
            try:
                gid = int(grp_item.text())
            except ValueError:
                continue
            p = self._get_path_from_row(r)
            try:
                mt = os.path.getmtime(p)
            except OSError:
                mt = 0.0
            groups_map.setdefault(gid, []).append((p, mt, r))
        
        for gid, lst in groups_map.items():
            if len(lst) <= 1:
                continue
            lst.sort(key=lambda t: t[1], reverse=True)
            # Marcar todos exceto o mais recente
            for _, _, r in lst[1:]:
                chk = self.table.item(r, 4)
                if chk is not None:
                    chk.setCheckState(Qt.CheckState.Checked)

    def _on_trash_selected(self) -> None:
        to_delete: list = []
        for r in range(self.table.rowCount()):
            chk = self.table.item(r, 4)
            if not chk:
                continue
            if chk.checkState() == Qt.CheckState.Checked:
                path = self._get_path_from_row(r)
                if path:
                    to_delete.append(path)
        if not to_delete:
            CustomDialog.information(self, 'Nada selecionado', 'Marque os arquivos a excluir.')
            return
        total_size = sum(os.path.getsize(p) for p in to_delete if os.path.exists(p))
        resp = CustomDialog.question(
            self, 'Enviar para Lixeira',
            f'Deletar {len(to_delete)} arquivo(s) para a Lixeira (~{_human_size(total_size)})?',
        )
        if not resp:
            return
        from send2trash import send2trash
        prog = QProgressDialog('Excluindo…', 'Cancelar', 0, len(to_delete), self)
        prog.setWindowTitle('Lixeira')
        prog.setMinimumDuration(0)
        errors = 0
        for i, p in enumerate(to_delete, start=1):
            if prog.wasCanceled():
                break
            prog.setValue(i)
            prog.setLabelText(os.path.basename(p))
            try:
                send2trash(p)
            except Exception:
                errors += 1
        prog.close()
        remaining_groups = [
            [p for p in g if p not in to_delete]
            for g in self._groups
        ]
        self._groups = [g for g in remaining_groups if len(g) > 1]
        self._populate_table(self._groups)
        has = len(self._groups) > 0
        self.btn_export.setEnabled(has)
        self.btn_select_keep_newest.setEnabled(has)
        self.btn_trash.setEnabled(has)
        left = sum(len(g) for g in self._groups)
        msg = f'Exclusão concluída. Erros: {errors}. Restam {len(self._groups)} grupos ({left} arquivos).'
        if errors:
            CustomDialog.warning(self, 'Concluído com erros', msg)
        else:
            CustomDialog.information(self, 'Concluído', msg)

    def _on_export(self) -> None:
        if not self._groups:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Exportar duplicados', 'duplicados.csv', 'CSV Files (*.csv);;All Files (*)'
        )
        if not path:
            return
        import csv
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['grupo', 'tamanho_bytes', 'tamanho_humano', 'nome', 'caminho_completo'])
                for grp_idx, g in enumerate(self._groups, 1):
                    size = os.path.getsize(g[0]) if g else 0
                    for p in g:
                        w.writerow([grp_idx, size, _human_size(size), os.path.basename(p), p])
            CustomDialog.information(self, 'Exportado', f'Arquivo salvo em:\n{path}')
        except Exception as e:
            CustomDialog.critical(self, 'Erro', f'Falha ao exportar: {e}')

    def _on_table_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        path = self._get_path_from_row(index.row())
        if not path:
            return
        menu = QMenu(self)
        act_open = menu.addAction('📂 Abrir pasta')
        act_copy_path = menu.addAction('📋 Copiar caminho')
        menu.addSeparator()
        act_toggle = menu.addAction('☑ Marcar/desmarcar para exclusão')
        
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_open:
            self._open_in_folder(path)
        elif action == act_copy_path:
            QApplication.clipboard().setText(path)
        elif action == act_toggle:
            chk = self.table.item(index.row(), 4)
            if chk:
                new_state = (Qt.CheckState.Unchecked 
                           if chk.checkState() == Qt.CheckState.Checked 
                           else Qt.CheckState.Checked)
                chk.setCheckState(new_state)

    def _open_in_folder(self, path: str) -> None:
        try:
            if sys.platform.startswith('win'):
                subprocess.run(['explorer', '/select,', path], check=False)
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', path], check=False)
            else:
                folder = os.path.dirname(path) or '.'
                subprocess.run(['xdg-open', folder], check=False)
        except Exception:
            CustomDialog.warning(self, 'Aviso', 'Não foi possível abrir a pasta no explorador.')

    # ── Limpeza ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_thread()
        super().closeEvent(event)
