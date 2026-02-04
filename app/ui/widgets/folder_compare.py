from __future__ import annotations
import os
import shutil
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QCheckBox,
    QGroupBox, QGridLayout, QProgressDialog, QComboBox
)
from PyQt6.QtGui import QColor

from app.core.folder_compare import compare_directories, CompareResult, FileInfo


class CompareWorker(QObject):
    done = pyqtSignal(object)  # CompareResult
    progress = pyqtSignal(str)
    
    def __init__(self, left: str, right: str, recursive: bool, compare_content: bool) -> None:
        super().__init__()
        self.left = left
        self.right = right
        self.recursive = recursive
        self.compare_content = compare_content
        self.cancel = False
    
    def run(self) -> None:
        try:
            self.progress.emit('Comparando diretórios...')
            result = compare_directories(
                self.left,
                self.right,
                recursive=self.recursive,
                compare_content=self.compare_content
            )
            self.done.emit(result)
        except Exception as e:
            self.done.emit(None)


class FolderCompareWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result: Optional[CompareResult] = None
        self._left_dir: str = ''
        self._right_dir: str = ''
        self._thread: Optional[QThread] = None
        self._worker: Optional[CompareWorker] = None
        self._init_ui()
    
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)
        
        # === SEÇÃO 1: Seleção de pastas ===
        select_group = QGroupBox('📂 Selecionar pastas para comparar')
        select_layout = QGridLayout(select_group)
        select_layout.setSpacing(8)
        
        self.left_edit = QLineEdit()
        self.left_edit.setPlaceholderText('Pasta da esquerda (origem)...')
        btn_left = QPushButton('Escolher')
        btn_left.clicked.connect(lambda: self._choose_dir('left'))
        
        self.right_edit = QLineEdit()
        self.right_edit.setPlaceholderText('Pasta da direita (destino)...')
        btn_right = QPushButton('Escolher')
        btn_right.clicked.connect(lambda: self._choose_dir('right'))
        
        select_layout.addWidget(QLabel('Pasta A:'), 0, 0)
        select_layout.addWidget(self.left_edit, 0, 1)
        select_layout.addWidget(btn_left, 0, 2)
        select_layout.addWidget(QLabel('Pasta B:'), 1, 0)
        select_layout.addWidget(self.right_edit, 1, 1)
        select_layout.addWidget(btn_right, 1, 2)
        
        # Opções
        options_row = QHBoxLayout()
        self.recursive_chk = QCheckBox('Incluir subpastas')
        self.recursive_chk.setChecked(True)
        self.content_chk = QCheckBox('Comparar conteúdo (hash MD5)')
        self.content_chk.setToolTip('Mais preciso, mas mais lento')
        
        self.btn_compare = QPushButton('🔍 Comparar')
        self.btn_compare.clicked.connect(self._on_compare)
        
        options_row.addWidget(self.recursive_chk)
        options_row.addWidget(self.content_chk)
        options_row.addStretch()
        options_row.addWidget(self.btn_compare)
        
        select_layout.addLayout(options_row, 2, 0, 1, 3)
        
        # === SEÇÃO 2: Filtros ===
        filter_group = QGroupBox('🔎 Filtrar resultados')
        filter_layout = QHBoxLayout(filter_group)
        
        filter_layout.addWidget(QLabel('Mostrar:'))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem('Todos', 'all')
        self.filter_combo.addItem('Apenas em A', 'only_left')
        self.filter_combo.addItem('Apenas em B', 'only_right')
        self.filter_combo.addItem('Diferentes', 'different')
        self.filter_combo.addItem('Idênticos', 'identical')
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        
        # === SEÇÃO 3: Resumo ===
        self.lbl_summary = QLabel('Selecione duas pastas e clique em "Comparar"')
        
        # === SEÇÃO 4: Resultados ===
        results_label = QLabel('📋 Resultados da comparação:')
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Arquivo', 'Status', 'Tamanho A', 'Tamanho B', 'Data Modificação A', 'Data Modificação B'])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 150)
        self.tree.setSortingEnabled(True)
        
        # === SEÇÃO 5: Ações ===
        actions_group = QGroupBox('⚡ Ações de sincronização')
        actions_layout = QHBoxLayout(actions_group)
        
        self.btn_copy_to_right = QPushButton('→ Copiar A para B')
        self.btn_copy_to_right.clicked.connect(lambda: self._sync_action('copy_to_right'))
        self.btn_copy_to_right.setEnabled(False)
        
        self.btn_copy_to_left = QPushButton('← Copiar B para A')
        self.btn_copy_to_left.clicked.connect(lambda: self._sync_action('copy_to_left'))
        self.btn_copy_to_left.setEnabled(False)
        
        self.btn_delete_left = QPushButton('🗑 Excluir de A')
        self.btn_delete_left.clicked.connect(lambda: self._sync_action('delete_left'))
        self.btn_delete_left.setEnabled(False)
        
        self.btn_delete_right = QPushButton('🗑 Excluir de B')
        self.btn_delete_right.clicked.connect(lambda: self._sync_action('delete_right'))
        self.btn_delete_right.setEnabled(False)
        
        actions_layout.addWidget(self.btn_copy_to_right)
        actions_layout.addWidget(self.btn_copy_to_left)
        actions_layout.addWidget(self.btn_delete_left)
        actions_layout.addWidget(self.btn_delete_right)
        actions_layout.addStretch()
        
        # Montagem
        root.addWidget(select_group)
        root.addWidget(filter_group)
        root.addWidget(self.lbl_summary)
        root.addWidget(results_label)
        root.addWidget(self.tree, 1)
        root.addWidget(actions_group)
    
    def _choose_dir(self, side: str) -> None:
        d = QFileDialog.getExistingDirectory(self, f'Escolher pasta {side}')
        if d:
            if side == 'left':
                self.left_edit.setText(d)
            else:
                self.right_edit.setText(d)
    
    def _on_compare(self) -> None:
        left = self.left_edit.text().strip()
        right = self.right_edit.text().strip()
        
        if not left or not os.path.isdir(left):
            QMessageBox.warning(self, 'Aviso', 'Selecione uma pasta válida para A.')
            return
        if not right or not os.path.isdir(right):
            QMessageBox.warning(self, 'Aviso', 'Selecione uma pasta válida para B.')
            return
        
        self._left_dir = left
        self._right_dir = right
        
        # Progress dialog
        prog = QProgressDialog('Comparando...', 'Cancelar', 0, 0, self)
        prog.setWindowTitle('Comparação de Pastas')
        prog.setMinimumDuration(0)
        prog.setRange(0, 0)
        
        # Thread worker
        self.btn_compare.setEnabled(False)
        thread = QThread(self)
        worker = CompareWorker(
            left,
            right,
            self.recursive_chk.isChecked(),
            self.content_chk.isChecked()
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda msg: prog.setLabelText(msg))
        
        def finished(result: Optional[CompareResult]):
            prog.close()
            self._result = result
            if result:
                self._populate_tree(result)
                self._update_summary(result)
                self._enable_actions(True)
            else:
                QMessageBox.warning(self, 'Erro', 'Falha ao comparar diretórios.')
                self._enable_actions(False)
            self.btn_compare.setEnabled(True)
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
    
    def _populate_tree(self, result: CompareResult) -> None:
        self.tree.clear()
        
        # Apenas em A
        for file_info in result.only_left:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, file_info.rel_path)
            item.setText(1, 'Apenas em A')
            item.setText(2, self._format_size(file_info.size))
            item.setText(3, '-')
            item.setText(4, self._format_date(file_info.mtime))
            item.setText(5, '-')
            item.setForeground(1, QColor(255, 140, 0))  # laranja
            item.setData(0, Qt.ItemDataRole.UserRole, ('only_left', file_info, None))
        
        # Apenas em B
        for file_info in result.only_right:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, file_info.rel_path)
            item.setText(1, 'Apenas em B')
            item.setText(2, '-')
            item.setText(3, self._format_size(file_info.size))
            item.setText(4, '-')
            item.setText(5, self._format_date(file_info.mtime))
            item.setForeground(1, QColor(0, 150, 255))  # azul
            item.setData(0, Qt.ItemDataRole.UserRole, ('only_right', None, file_info))
        
        # Diferentes
        for left_info, right_info in result.different:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, left_info.rel_path)
            item.setText(1, 'Diferente')
            item.setText(2, self._format_size(left_info.size))
            item.setText(3, self._format_size(right_info.size))
            item.setText(4, self._format_date(left_info.mtime))
            item.setText(5, self._format_date(right_info.mtime))
            item.setForeground(1, QColor(255, 0, 0))  # vermelho
            item.setData(0, Qt.ItemDataRole.UserRole, ('different', left_info, right_info))
        
        # Idênticos
        for left_info, right_info in result.identical:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, left_info.rel_path)
            item.setText(1, 'Idêntico')
            item.setText(2, self._format_size(left_info.size))
            item.setText(3, self._format_size(right_info.size))
            item.setText(4, self._format_date(left_info.mtime))
            item.setText(5, self._format_date(right_info.mtime))
            item.setForeground(1, QColor(0, 150, 0))  # verde
            item.setData(0, Qt.ItemDataRole.UserRole, ('identical', left_info, right_info))
    
    def _update_summary(self, result: CompareResult) -> None:
        total = len(result.only_left) + len(result.only_right) + len(result.different) + len(result.identical)
        self.lbl_summary.setText(
            f'Total: {total} arquivos | '
            f'Apenas em A: {len(result.only_left)} | '
            f'Apenas em B: {len(result.only_right)} | '
            f'Diferentes: {len(result.different)} | '
            f'Idênticos: {len(result.identical)}'
        )
    
    def _apply_filter(self) -> None:
        if not self._result:
            return
        
        filter_type = self.filter_combo.currentData()
        
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    status = data[0]
                    if filter_type == 'all':
                        item.setHidden(False)
                    else:
                        item.setHidden(status != filter_type)
    
    def _enable_actions(self, enabled: bool) -> None:
        self.btn_copy_to_right.setEnabled(enabled)
        self.btn_copy_to_left.setEnabled(enabled)
        self.btn_delete_left.setEnabled(enabled)
        self.btn_delete_right.setEnabled(enabled)
    
    def _sync_action(self, action: str) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.information(self, 'Aviso', 'Selecione um ou mais arquivos na lista.')
            return
        
        # Confirmar ação
        action_names = {
            'copy_to_right': 'copiar de A para B',
            'copy_to_left': 'copiar de B para A',
            'delete_left': 'excluir de A',
            'delete_right': 'excluir de B'
        }
        resp = QMessageBox.question(
            self,
            'Confirmar',
            f'Deseja {action_names[action]} {len(selected)} arquivo(s)?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        
        # Executar ação
        success = 0
        errors = 0
        
        for item in selected:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data:
                continue
            
            status, left_info, right_info = data
            
            try:
                if action == 'copy_to_right' and left_info:
                    dst = os.path.join(self._right_dir, left_info.rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(left_info.path, dst)
                    success += 1
                elif action == 'copy_to_left' and right_info:
                    dst = os.path.join(self._left_dir, right_info.rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(right_info.path, dst)
                    success += 1
                elif action == 'delete_left' and left_info:
                    os.remove(left_info.path)
                    success += 1
                elif action == 'delete_right' and right_info:
                    os.remove(right_info.path)
                    success += 1
            except Exception:
                errors += 1
        
        QMessageBox.information(
            self,
            'Concluído',
            f'Operação concluída.\nSucesso: {success}\nErros: {errors}'
        )
        
        # Recomparar
        self._on_compare()
    
    def _format_size(self, size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'
    
    def _format_date(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M')
    
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
