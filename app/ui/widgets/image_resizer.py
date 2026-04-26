from __future__ import annotations
import os
from typing import Optional, List

from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QSpinBox, QGroupBox, QGridLayout,
    QProgressDialog, QRadioButton, QButtonGroup, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtGui import QColor

from app.core.image_resizer import (
    ResizeOptions, batch_resize, ProcessResult, get_image_files
)
from app.core.logger import get_logger
from app.ui.custom_dialog import CustomDialog

_log = get_logger("image_resizer.ui")


class ResizeWorker(QObject):
    done = pyqtSignal(list)  # List[ProcessResult]
    progress = pyqtSignal(int, str)  # current, filename
    
    def __init__(
        self,
        src_dir: str,
        dst_dir: str,
        options: ResizeOptions,
        recursive: bool,
        suffix: str
    ) -> None:
        super().__init__()
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.options = options
        self.recursive = recursive
        self.suffix = suffix
        self.cancel = False
    
    def run(self) -> None:
        try:
            _log.info("Resize iniciado: src=%s dst=%s recursive=%s",
                      self.src_dir, self.dst_dir, self.recursive)
            # Processar em lote
            results = batch_resize(
                self.src_dir,
                self.dst_dir,
                self.options,
                self.recursive,
                self.suffix
            )
            _log.info("Resize finalizado: %d resultados", len(results))
            self.done.emit(results)
        except Exception:
            _log.exception("Falha no batch_resize (src=%s dst=%s)",
                           self.src_dir, self.dst_dir)
            self.done.emit([])


class ImageResizerWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[ResizeWorker] = None
        self._init_ui()
    
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)
        
        # === SEÇÃO 1: Modo de seleção ===
        mode_select_group = QGroupBox('📂 O que deseja processar?')
        mode_select_layout = QHBoxLayout(mode_select_group)
        
        self.mode_select_group = QButtonGroup(self)
        self.rb_batch = QRadioButton('Lote de imagens (pasta)')
        self.rb_batch.setChecked(True)
        self.rb_single = QRadioButton('Imagem única')
        self.mode_select_group.addButton(self.rb_batch, 0)
        self.mode_select_group.addButton(self.rb_single, 1)
        self.mode_select_group.buttonClicked.connect(self._on_mode_select_changed)
        
        mode_select_layout.addWidget(self.rb_batch)
        mode_select_layout.addWidget(self.rb_single)
        mode_select_layout.addStretch()
        
        # === SEÇÃO 2: Seleção de arquivos/pastas ===
        folders_group = QGroupBox('📁 Arquivos')
        folders_layout = QGridLayout(folders_group)
        folders_layout.setSpacing(8)
        
        # Origem (pasta ou arquivo)
        self.lbl_src = QLabel('Pasta de origem:')
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText('Pasta com as imagens originais...')
        self.btn_src_folder = QPushButton('Escolher pasta')
        self.btn_src_folder.clicked.connect(lambda: self._choose_dir('src'))
        self.btn_src_file = QPushButton('Escolher arquivo')
        self.btn_src_file.clicked.connect(self._choose_file)
        self.btn_src_file.setVisible(False)
        
        # Destino
        self.lbl_dst = QLabel('Pasta de destino:')
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText('Pasta para salvar as imagens processadas...')
        self.btn_dst_folder = QPushButton('Escolher pasta')
        self.btn_dst_folder.clicked.connect(lambda: self._choose_dir('dst'))
        self.btn_dst_file = QPushButton('Salvar como...')
        self.btn_dst_file.clicked.connect(self._choose_save_file)
        self.btn_dst_file.setVisible(False)
        
        # Opções adicionais
        self.recursive_chk = QCheckBox('Incluir subpastas')
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText('_resized')
        self.suffix_edit.setText('_resized')
        self.suffix_edit.setMaximumWidth(120)
        
        folders_layout.addWidget(self.lbl_src, 0, 0)
        folders_layout.addWidget(self.src_edit, 0, 1, 1, 2)
        folders_layout.addWidget(self.btn_src_folder, 0, 3)
        folders_layout.addWidget(self.btn_src_file, 0, 4)
        folders_layout.addWidget(self.lbl_dst, 1, 0)
        folders_layout.addWidget(self.dst_edit, 1, 1, 1, 2)
        folders_layout.addWidget(self.btn_dst_folder, 1, 3)
        folders_layout.addWidget(self.btn_dst_file, 1, 4)
        folders_layout.addWidget(self.recursive_chk, 2, 0)
        folders_layout.addWidget(QLabel('Sufixo do nome:'), 2, 1)
        folders_layout.addWidget(self.suffix_edit, 2, 2)
        
        # === SEÇÃO 3: Modo de redimensionamento ===
        resize_group = QGroupBox('📐 Modo de redimensionamento')
        resize_layout = QVBoxLayout(resize_group)
        
        self.resize_mode_group = QButtonGroup(self)
        
        # Largura fixa
        width_row = QHBoxLayout()
        self.rb_width = QRadioButton('Largura fixa (altura proporcional)')
        self.rb_width.setChecked(True)
        self.resize_mode_group.addButton(self.rb_width, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10000)
        self.width_spin.setValue(1920)
        self.width_spin.setSuffix(' px')
        self.width_spin.setMinimumWidth(120)
        width_row.addWidget(self.rb_width)
        width_row.addWidget(self.width_spin)
        width_row.addStretch()
        
        # Altura fixa
        height_row = QHBoxLayout()
        self.rb_height = QRadioButton('Altura fixa (largura proporcional)')
        self.resize_mode_group.addButton(self.rb_height, 1)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 10000)
        self.height_spin.setValue(1080)
        self.height_spin.setSuffix(' px')
        self.height_spin.setMinimumWidth(120)
        height_row.addWidget(self.rb_height)
        height_row.addWidget(self.height_spin)
        height_row.addStretch()
        
        # Ambas dimensões
        both_row = QHBoxLayout()
        self.rb_both = QRadioButton('Largura e altura (fit proporcional)')
        self.resize_mode_group.addButton(self.rb_both, 2)
        self.both_width_spin = QSpinBox()
        self.both_width_spin.setRange(1, 10000)
        self.both_width_spin.setValue(1920)
        self.both_width_spin.setSuffix(' px')
        self.both_width_spin.setMinimumWidth(120)
        both_row.addWidget(self.rb_both)
        both_row.addWidget(QLabel('L:'))
        both_row.addWidget(self.both_width_spin)
        self.both_height_spin = QSpinBox()
        self.both_height_spin.setRange(1, 10000)
        self.both_height_spin.setValue(1080)
        self.both_height_spin.setSuffix(' px')
        self.both_height_spin.setMinimumWidth(120)
        both_row.addWidget(QLabel('A:'))
        both_row.addWidget(self.both_height_spin)
        both_row.addStretch()
        
        # Escala percentual
        scale_row = QHBoxLayout()
        self.rb_scale = QRadioButton('Escala percentual')
        self.resize_mode_group.addButton(self.rb_scale, 3)
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(1, 500)
        self.scale_spin.setValue(50)
        self.scale_spin.setSuffix(' %')
        self.scale_spin.setMinimumWidth(120)
        scale_row.addWidget(self.rb_scale)
        scale_row.addWidget(self.scale_spin)
        scale_row.addStretch()
        
        resize_layout.addLayout(width_row)
        resize_layout.addLayout(height_row)
        resize_layout.addLayout(both_row)
        resize_layout.addLayout(scale_row)
        
        # === SEÇÃO 4: Formato e qualidade ===
        format_group = QGroupBox('🎨 Formato e qualidade')
        format_layout = QGridLayout(format_group)
        format_layout.setSpacing(8)
        
        self.format_combo = QComboBox()
        self.format_combo.addItem('JPEG (menor tamanho)', 'JPEG')
        self.format_combo.addItem('PNG (sem perda)', 'PNG')
        self.format_combo.addItem('WebP (moderno)', 'WEBP')
        self.format_combo.addItem('BMP (sem compressão)', 'BMP')
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(85)
        self.quality_spin.setToolTip('Qualidade de compressão (maior = melhor qualidade, maior arquivo)')
        
        self.preserve_exif_chk = QCheckBox('Preservar metadados EXIF')
        self.preserve_exif_chk.setChecked(True)
        self.preserve_exif_chk.setToolTip('Manter informações de câmera, localização, etc.')
        
        format_layout.addWidget(QLabel('Formato de saída:'), 0, 0)
        format_layout.addWidget(self.format_combo, 0, 1)
        format_layout.addWidget(QLabel('Qualidade:'), 1, 0)
        format_layout.addWidget(self.quality_spin, 1, 1)
        format_layout.addWidget(self.preserve_exif_chk, 2, 0, 1, 2)
        
        # === BOTÃO PROCESSAR ===
        process_row = QHBoxLayout()
        process_row.addStretch()
        self.btn_process = QPushButton('🚀 Processar Imagens')
        self.btn_process.clicked.connect(self._on_process)
        self.btn_process.setMinimumHeight(40)
        process_row.addWidget(self.btn_process)
        process_row.addStretch()
        
        # === TABELA DE RESULTADOS ===
        results_label = QLabel('📊 Resultados:')
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            'Arquivo', 'Status', 'Tamanho Original', 'Novo Tamanho', 'Economia'
        ])
        self.table.setColumnWidth(0, 300)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        self.lbl_summary = QLabel('Aguardando processamento...')
        
        # Montagem
        root.addWidget(mode_select_group)
        root.addWidget(folders_group)
        root.addWidget(resize_group)
        root.addWidget(format_group)
        root.addLayout(process_row)
        root.addWidget(results_label)
        root.addWidget(self.table, 1)
        root.addWidget(self.lbl_summary)
    
    def _choose_dir(self, side: str) -> None:
        d = QFileDialog.getExistingDirectory(self, f'Escolher pasta de {side}')
        if d:
            if side == 'src':
                self.src_edit.setText(d)
            else:
                self.dst_edit.setText(d)
    
    def _choose_file(self) -> None:
        file, _ = QFileDialog.getOpenFileName(
            self,
            'Escolher imagem',
            '',
            'Imagens (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp);;Todos os arquivos (*)'
        )
        if file:
            self.src_edit.setText(file)
    
    def _choose_save_file(self) -> None:
        # Sugerir nome baseado no formato selecionado
        fmt = self.format_combo.currentData()
        ext_map = {
            'JPEG': 'jpg',
            'PNG': 'png',
            'WEBP': 'webp',
            'BMP': 'bmp'
        }
        ext = ext_map.get(fmt, 'jpg')
        
        file, _ = QFileDialog.getSaveFileName(
            self,
            'Salvar imagem como',
            f'imagem_redimensionada.{ext}',
            f'Imagens {fmt} (*.{ext});;Todos os arquivos (*)'
        )
        if file:
            self.dst_edit.setText(file)
    
    def _on_mode_select_changed(self) -> None:
        """Alterna entre modo lote e imagem única"""
        is_batch = self.rb_batch.isChecked()
        
        # Atualizar labels e visibilidade
        if is_batch:
            self.lbl_src.setText('Pasta de origem:')
            self.src_edit.setPlaceholderText('Pasta com as imagens originais...')
            self.btn_src_folder.setVisible(True)
            self.btn_src_file.setVisible(False)
            self.btn_dst_folder.setVisible(True)
            self.btn_dst_file.setVisible(False)
            self.recursive_chk.setVisible(True)
            self.lbl_dst.setText('Pasta de destino:')
            self.dst_edit.setPlaceholderText('Pasta para salvar as imagens processadas...')
        else:
            self.lbl_src.setText('Arquivo de origem:')
            self.src_edit.setPlaceholderText('Escolha a imagem para redimensionar...')
            self.btn_src_folder.setVisible(False)
            self.btn_src_file.setVisible(True)
            self.btn_dst_folder.setVisible(False)
            self.btn_dst_file.setVisible(True)
            self.recursive_chk.setVisible(False)
            self.lbl_dst.setText('Salvar como:')
            self.dst_edit.setPlaceholderText('Caminho completo do arquivo de saída...')
        
        # Limpar campos
        self.src_edit.clear()
        self.dst_edit.clear()
    
    def _on_format_changed(self) -> None:
        fmt = self.format_combo.currentData()
        # Habilitar qualidade apenas para JPEG e WEBP
        self.quality_spin.setEnabled(fmt in ['JPEG', 'WEBP'])
    
    def _on_process(self) -> None:
        src_path = self.src_edit.text().strip()
        dst_path = self.dst_edit.text().strip()
        
        is_batch = self.rb_batch.isChecked()
        
        # Validações
        if is_batch:
            # Modo lote
            if not src_path or not os.path.isdir(src_path):
                CustomDialog.warning(self, 'Aviso', 'Selecione uma pasta de origem válida.')
                return
            if not dst_path:
                CustomDialog.warning(self, 'Aviso', 'Selecione uma pasta de destino.')
                return
            
            # Verificar se há imagens
            images = get_image_files(src_path, self.recursive_chk.isChecked())
            if not images:
                CustomDialog.warning(self, 'Aviso', 'Nenhuma imagem encontrada na pasta de origem.')
                return
            
            num_images = len(images)
        else:
            # Modo imagem única
            if not src_path or not os.path.isfile(src_path):
                CustomDialog.warning(self, 'Aviso', 'Selecione um arquivo de imagem válido.')
                return
            if not dst_path:
                CustomDialog.warning(self, 'Aviso', 'Especifique o caminho de saída.')
                return
            
            num_images = 1
        
        # Construir opções
        options = ResizeOptions()
        
        # Modo
        if self.rb_width.isChecked():
            options.mode = 'width'
            options.width = self.width_spin.value()
        elif self.rb_height.isChecked():
            options.mode = 'height'
            options.height = self.height_spin.value()
        elif self.rb_both.isChecked():
            options.mode = 'both'
            options.width = self.both_width_spin.value()
            options.height = self.both_height_spin.value()
        elif self.rb_scale.isChecked():
            options.mode = 'scale'
            options.scale_percent = float(self.scale_spin.value())
        
        # Formato e qualidade
        options.output_format = self.format_combo.currentData()
        options.quality = self.quality_spin.value()
        options.preserve_exif = self.preserve_exif_chk.isChecked()
        
        # Confirmar
        resp = CustomDialog.question(
            self,
            'Confirmar',
            f'Processar {num_images} imagem(ns)?'
        )
        if not resp:
            return
        
        # Processar
        if is_batch:
            self._process_batch(src_path, dst_path, options)
        else:
            self._process_single(src_path, dst_path, options)
    
    def _process_batch(self, src_dir: str, dst_dir: str, options: ResizeOptions) -> None:
        """Processa lote de imagens"""
        images = get_image_files(src_dir, self.recursive_chk.isChecked())
        
        # Progress dialog
        prog = QProgressDialog('Processando...', 'Cancelar', 0, len(images), self)
        prog.setWindowTitle('Redimensionando Imagens')
        prog.setMinimumDuration(0)
        
        # Thread worker
        self.btn_process.setEnabled(False)
        thread = QThread(self)
        worker = ResizeWorker(
            src_dir,
            dst_dir,
            options,
            self.recursive_chk.isChecked(),
            self.suffix_edit.text()
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        
        def finished(results: List[ProcessResult]):
            prog.close()
            if results:
                self._populate_results(results)
                self._update_summary(results)
            else:
                CustomDialog.warning(self, 'Erro', 'Falha ao processar imagens.')
            self.btn_process.setEnabled(True)
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
    
    def _process_single(self, src_file: str, dst_file: str, options: ResizeOptions) -> None:
        """Processa uma única imagem"""
        from app.core.image_resizer import resize_image
        
        self.btn_process.setEnabled(False)
        
        # Processar diretamente (sem thread para uma imagem)
        result = resize_image(src_file, dst_file, options)
        
        if result.success:
            self._populate_results([result])
            self._update_summary([result])
            CustomDialog.information(
                self,
                'Sucesso',
                f'Imagem processada com sucesso!\n\nSalva em: {dst_file}'
            )
        else:
            CustomDialog.critical(
                self,
                'Erro',
                f'Falha ao processar imagem:\n{result.error_msg}'
            )
        
        self.btn_process.setEnabled(True)
    
    def _populate_results(self, results: List[ProcessResult]) -> None:
        self.table.setRowCount(0)
        
        for result in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            filename = os.path.basename(result.src_path)
            self.table.setItem(row, 0, QTableWidgetItem(filename))
            
            status_item = QTableWidgetItem('✓ Sucesso' if result.success else f'✗ Erro: {result.error_msg}')
            if result.success:
                status_item.setForeground(QColor(0, 150, 0))
            else:
                status_item.setForeground(QColor(255, 0, 0))
            self.table.setItem(row, 1, status_item)
            
            if result.success:
                orig_size = f'{result.original_size[0]}x{result.original_size[1]} ({self._format_bytes(result.original_file_size)})'
                new_size = f'{result.new_size[0]}x{result.new_size[1]} ({self._format_bytes(result.new_file_size)})'
                
                self.table.setItem(row, 2, QTableWidgetItem(orig_size))
                self.table.setItem(row, 3, QTableWidgetItem(new_size))
                
                if result.original_file_size > 0:
                    savings = ((result.original_file_size - result.new_file_size) / result.original_file_size) * 100
                    savings_text = f'{savings:.1f}%'
                    if savings > 0:
                        savings_text = f'↓ {savings_text}'
                    elif savings < 0:
                        savings_text = f'↑ {abs(savings):.1f}%'
                    self.table.setItem(row, 4, QTableWidgetItem(savings_text))
            else:
                self.table.setItem(row, 2, QTableWidgetItem('-'))
                self.table.setItem(row, 3, QTableWidgetItem('-'))
                self.table.setItem(row, 4, QTableWidgetItem('-'))
    
    def _update_summary(self, results: List[ProcessResult]) -> None:
        success = sum(1 for r in results if r.success)
        errors = len(results) - success
        
        total_original = sum(r.original_file_size for r in results if r.success)
        total_new = sum(r.new_file_size for r in results if r.success)
        
        if total_original > 0:
            savings = ((total_original - total_new) / total_original) * 100
            self.lbl_summary.setText(
                f'Processadas: {success} | Erros: {errors} | '
                f'Tamanho original: {self._format_bytes(total_original)} | '
                f'Novo tamanho: {self._format_bytes(total_new)} | '
                f'Economia: {savings:.1f}%'
            )
        else:
            self.lbl_summary.setText(f'Processadas: {success} | Erros: {errors}')
    
    def _format_bytes(self, size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'
    
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
