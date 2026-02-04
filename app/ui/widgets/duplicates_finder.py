from __future__ import annotations
import os
import sys
import subprocess
from typing import List

from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QMessageBox
)

from app.core.duplicates import find_duplicates


class ScanWorker(QObject):
    done = pyqtSignal(list)  # list of groups (list[list[str]])
    progress = pyqtSignal(str)

    def __init__(self, root: str, recursive: bool, min_size: int, include_exts: set[str] | None) -> None:
        super().__init__()
        self.root = root
        self.recursive = recursive
        self.min_size = min_size
        self.include_exts = include_exts
        self.cancel = False

    def run(self) -> None:
        try:
            self.progress.emit('Varredura de duplicados...')
            groups = find_duplicates(
                self.root,
                recursive=self.recursive,
                min_size_bytes=self.min_size,
                include_exts=self.include_exts,
            )
        except Exception as e:
            groups = []
        self.done.emit(groups)


class DuplicatesFinderWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._groups: List[List[str]] = []
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Linha de opções
        row = QHBoxLayout()
        self.ed_dir = QLineEdit(); self.ed_dir.setPlaceholderText('Pasta para escanear...')
        btn_browse = QPushButton('Escolher...'); btn_browse.clicked.connect(self._choose_dir)
        self.chk_recursive = QCheckBox('Incluir subpastas'); self.chk_recursive.setChecked(True)
        row.addWidget(QLabel('Diretório:'))
        row.addWidget(self.ed_dir, 1)
        row.addWidget(btn_browse)
        row.addWidget(self.chk_recursive)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel('Tamanho mínimo (KB):'))
        self.sp_min_kb = QSpinBox(); self.sp_min_kb.setRange(1, 10_000_000); self.sp_min_kb.setValue(1)
        row2.addWidget(self.sp_min_kb)
        row2.addSpacing(16)
        self.ed_exts = QLineEdit(); self.ed_exts.setPlaceholderText('Filtrar extensões (ex: .jpg,.png)')
        row2.addWidget(QLabel('Extensões:'))
        row2.addWidget(self.ed_exts, 1)
        self.btn_scan = QPushButton('Escanear'); self.btn_scan.clicked.connect(self._on_scan)
        self.btn_export = QPushButton('Exportar CSV'); self.btn_export.clicked.connect(self._on_export); self.btn_export.setEnabled(False)
        # Ações de seleção/exclusão
        self.btn_select_keep_newest = QPushButton('Selecionar (manter mais recente)'); self.btn_select_keep_newest.clicked.connect(self._on_select_keep_newest); self.btn_select_keep_newest.setEnabled(False)
        self.btn_trash = QPushButton('Enviar para Lixeira'); self.btn_trash.clicked.connect(self._on_trash_selected); self.btn_trash.setEnabled(False)
        row2.addWidget(self.btn_scan)
        row2.addWidget(self.btn_select_keep_newest)
        row2.addWidget(self.btn_trash)
        row2.addWidget(self.btn_export)

        # Tabela de resultados
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Grupo', 'Tamanho', 'Caminho', 'Excluir?'])
        self.table.horizontalHeader().setStretchLastSection(True)
        # Menu de contexto (clique direito)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)

        self.lbl_summary = QLabel('Pronto')

        root.addLayout(row)
        root.addLayout(row2)
        root.addWidget(self.table, 1)
        root.addWidget(self.lbl_summary)

    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, 'Escolher diretório')
        if d:
            self.ed_dir.setText(d)

    def _on_scan(self) -> None:
        directory = self.ed_dir.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(self, 'Aviso', 'Selecione um diretório válido.')
            return
        include_exts: set[str] | None = None
        txt = self.ed_exts.text().strip()
        if txt:
            include_exts = set()
            for p in txt.split(','):
                e = p.strip().lower()
                if not e:
                    continue
                if not e.startswith('.'): e = '.' + e
                include_exts.add(e)
        min_size = max(1, self.sp_min_kb.value()) * 1024

        # Progress dialog
        from PyQt6.QtWidgets import QProgressDialog
        prog = QProgressDialog('Iniciando...', 'Cancelar', 0, 0, self)
        prog.setWindowTitle('Procurando Duplicados')
        prog.setMinimumDuration(0)
        prog.setRange(0, 0)  # indeterminado

        # Thread worker
        self.btn_scan.setEnabled(False)
        self.btn_export.setEnabled(False)
        thread = QThread(self)
        worker = ScanWorker(directory, self.chk_recursive.isChecked(), min_size, include_exts)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda msg: prog.setLabelText(msg))

        def finished(groups: list[list[str]]):
            prog.close()
            self._groups = groups
            self._populate_table(groups)
            self.btn_scan.setEnabled(True)
            has_groups = len(groups) > 0
            self.btn_export.setEnabled(has_groups)
            self.btn_select_keep_newest.setEnabled(has_groups)
            self.btn_trash.setEnabled(has_groups)
            if groups:
                total_files = sum(len(g) for g in groups)
                self.lbl_summary.setText(f"Encontrados {len(groups)} grupos de duplicados ({total_files} arquivos)")
            else:
                self.lbl_summary.setText('Nenhum duplicado encontrado')
            thread.quit(); thread.wait(); worker.deleteLater(); thread.deleteLater()
            self._thread = None; self._worker = None

        worker.done.connect(finished)
        prog.canceled.connect(lambda: setattr(worker, 'cancel', True))
        self._thread = thread; self._worker = worker
        thread.start()

    def _populate_table(self, groups: list[list[str]]) -> None:
        self.table.setRowCount(0)
        grp_idx = 1
        for g in groups:
            size = os.path.getsize(g[0]) if g else 0
            for path in g:
                row = self.table.rowCount(); self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(grp_idx)))
                self.table.setItem(row, 1, QTableWidgetItem(f"{size:,}".replace(',', '.')))
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
        # Limpar seleção
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 3)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)
        # Para cada grupo, marcar todos menos o mais recente
        # Construir mapa: grupo -> [(path, mtime, row)]
        groups_map: dict[int, list[tuple[str, float, int]]] = {}
        for r in range(self.table.rowCount()):
            grp_item = self.table.item(r, 0)
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
            # manter mais recente
            lst.sort(key=lambda t: t[1], reverse=True)
            keep_row = lst[0][2]
            for _, _, r in lst[1:]:
                chk = self.table.item(r, 3)
                if chk is not None:
                    chk.setCheckState(Qt.CheckState.Checked)

    def _on_trash_selected(self) -> None:
        # Coletar caminhos marcados
        to_delete: list[str] = []
        for r in range(self.table.rowCount()):
            chk = self.table.item(r, 3)
            path_item = self.table.item(r, 2)
            if not chk or not path_item:
                continue
            if chk.checkState() == Qt.CheckState.Checked:
                to_delete.append(path_item.text())
        if not to_delete:
            QMessageBox.information(self, 'Nada selecionado', 'Marque os arquivos a excluir.')
            return
        # Confirmar
        total_size = 0
        for p in to_delete:
            try:
                total_size += os.path.getsize(p)
            except OSError:
                pass
        size_mb = total_size / (1024*1024)
        resp = QMessageBox.question(self, 'Enviar para Lixeira', f'Deletar {len(to_delete)} arquivo(s) para a Lixeira (~{size_mb:.2f} MB)?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        # Progresso e envio para Lixeira
        from send2trash import send2trash
        from PyQt6.QtWidgets import QProgressDialog
        prog = QProgressDialog('Excluindo...', 'Cancelar', 0, len(to_delete), self)
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
        # Atualizar grupos removendo arquivos deletados e filtrando grupos com >1
        remaining_groups: list[list[str]] = []
        for g in self._groups:
            rem = [p for p in g if p not in to_delete]
            if len(rem) > 1:
                remaining_groups.append(rem)
        self._groups = remaining_groups
        self._populate_table(self._groups)
        self.btn_export.setEnabled(len(self._groups) > 0)
        self.btn_select_keep_newest.setEnabled(len(self._groups) > 0)
        self.btn_trash.setEnabled(len(self._groups) > 0)
        left = sum(len(g) for g in self._groups)
        msg = f"Exclusão concluída. Erros: {errors}. Restam {len(self._groups)} grupos ({left} arquivos)."
        if errors:
            QMessageBox.warning(self, 'Concluído com erros', msg)
        else:
            QMessageBox.information(self, 'Concluído', msg)

    def _on_export(self) -> None:
        if not self._groups:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar duplicados', 'duplicados.csv', 'CSV Files (*.csv);;All Files (*)')
        if not path:
            return
        import csv
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['grupo', 'tamanho_bytes', 'caminho'])
                grp_idx = 1
                for g in self._groups:
                    size = os.path.getsize(g[0]) if g else 0
                    for p in g:
                        w.writerow([grp_idx, size, p])
                    grp_idx += 1
            QMessageBox.information(self, 'Exportado', f'Arquivo salvo em:\n{path}')
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao exportar: {e}')

    def _on_table_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        path_item = self.table.item(row, 2)
        if not path_item:
            return
        path = path_item.text()
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        act_open = menu.addAction('Abrir pasta')
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_open:
            self._open_in_folder(path)

    def _open_in_folder(self, path: str) -> None:
        # Abre a pasta contendo o arquivo, selecionando-o quando possível
        try:
            if sys.platform.startswith('win'):
                # Explorer com seleção do arquivo
                subprocess.run(['explorer', '/select,', path], check=False)
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', path], check=False)
            else:
                # Linux: abre diretório contendo
                folder = os.path.dirname(path) or '.'
                # tenta xdg-open, fallback para abrir arquivo
                if os.path.isdir(folder):
                    subprocess.run(['xdg-open', folder], check=False)
                else:
                    subprocess.run(['xdg-open', path], check=False)
        except Exception:
            QMessageBox.warning(self, 'Aviso', 'Não foi possível abrir a pasta no explorador.')

    def closeEvent(self, event):  # type: ignore[override]
        if self._thread is not None and self._thread.isRunning():
            if self._worker is not None:
                try:
                    setattr(self._worker, 'cancel', True)
                except Exception:
                    pass
            self._thread.quit(); self._thread.wait(3000)
        return super().closeEvent(event)
