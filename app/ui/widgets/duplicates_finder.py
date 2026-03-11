from __future__ import annotations
import os
import sys
import subprocess
from typing import List, Optional

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QProgressDialog, QApplication, QMenu,
)

from app.core.duplicates import find_duplicates
from app.core.app_settings import load_setting, save_setting
from app.core.logger import get_logger

log = get_logger(__name__)

_SETTING_KEY = 'duplicates_finder.last_dir'


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
        # Melhoria 1: pré-preencher com último diretório usado
        last_dir = load_setting(_SETTING_KEY)
        if last_dir and os.path.isdir(last_dir):
            self.ed_dir.setText(last_dir)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Linha de opções
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

        # Tabela
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Grupo', 'Tamanho', 'Caminho', 'Excluir?'])
        self.table.horizontalHeader().setStretchLastSection(True)
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
            save_setting(_SETTING_KEY, d)  # Melhoria 1: persiste último dir

    def _notify_tray(self, message: str) -> None:
        from app.core.system_tray import notify_tray
        notify_tray('Localizador de Duplicados', message)

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
            QMessageBox.warning(self, 'Aviso', 'Selecione um diretório válido.')
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
            # Melhoria 3: ordenar por espaço desperdiçado desc (tamanho × cópias - 1)
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
                self.lbl_summary.setText(
                    f'Encontrados {len(groups)} grupos de duplicados ({total_files} arquivos)'
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
            QMessageBox.critical(self, 'Erro na Varredura', msg)
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
        self.table.setRowCount(0)
        grp_idx = 1
        for g in groups:
            size = os.path.getsize(g[0]) if g else 0
            for path in g:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(grp_idx)))
                self.table.setItem(row, 1, QTableWidgetItem(f'{size:,}'.replace(',', '.')))
                item = QTableWidgetItem(path)
                item.setToolTip(path)
                self.table.setItem(row, 2, item)
                chk = QTableWidgetItem('')
                chk.setFlags(chk.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                chk.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row, 3, chk)
            grp_idx += 1

    def _on_select_keep_newest(self) -> None:
        if not self._groups:
            return
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 3)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)
        groups_map: dict = {}
        for r in range(self.table.rowCount()):
            grp_item  = self.table.item(r, 0)
            path_item = self.table.item(r, 2)
            if not grp_item or not path_item:
                continue
            try:
                gid = int(grp_item.text())
            except ValueError:
                continue
            p = path_item.text()
            try:
                mt = os.path.getmtime(p)
            except OSError:
                mt = 0.0
            groups_map.setdefault(gid, []).append((p, mt, r))
        for gid, lst in groups_map.items():
            if len(lst) <= 1:
                continue
            lst.sort(key=lambda t: t[1], reverse=True)
            for _, _, r in lst[1:]:
                chk = self.table.item(r, 3)
                if chk is not None:
                    chk.setCheckState(Qt.CheckState.Checked)

    def _on_trash_selected(self) -> None:
        to_delete: list = []
        for r in range(self.table.rowCount()):
            chk       = self.table.item(r, 3)
            path_item = self.table.item(r, 2)
            if not chk or not path_item:
                continue
            if chk.checkState() == Qt.CheckState.Checked:
                to_delete.append(path_item.text())
        if not to_delete:
            QMessageBox.information(self, 'Nada selecionado', 'Marque os arquivos a excluir.')
            return
        total_size = sum(os.path.getsize(p) for p in to_delete if os.path.exists(p))
        size_mb = total_size / (1024 * 1024)
        resp = QMessageBox.question(
            self, 'Enviar para Lixeira',
            f'Deletar {len(to_delete)} arquivo(s) para a Lixeira (~{size_mb:.2f} MB)?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
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
            QMessageBox.warning(self, 'Concluído com erros', msg)
        else:
            QMessageBox.information(self, 'Concluído', msg)

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
                w.writerow(['grupo', 'tamanho_bytes', 'caminho'])
                for grp_idx, g in enumerate(self._groups, 1):
                    size = os.path.getsize(g[0]) if g else 0
                    for p in g:
                        w.writerow([grp_idx, size, p])
            QMessageBox.information(self, 'Exportado', f'Arquivo salvo em:\n{path}')
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao exportar: {e}')

    def _on_table_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        path_item = self.table.item(index.row(), 2)
        if not path_item:
            return
        menu = QMenu(self)
        act_open = menu.addAction('Abrir pasta')
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_open:
            self._open_in_folder(path_item.text())

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
            QMessageBox.warning(self, 'Aviso', 'Não foi possível abrir a pasta no explorador.')

    # ── Limpeza ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_thread()
        super().closeEvent(event)
