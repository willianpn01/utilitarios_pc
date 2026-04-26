from __future__ import annotations
import os
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QTabWidget, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QApplication
)
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
from PyQt6.QtCore import Qt, QSettings, QThread, QObject, pyqtSignal

from app.core.auto_organizer import (
    parse_rules, default_mapping, build_plan, apply_plan, PlanItem,
    resolve_collision,
)
from app.core.logger import get_logger
import shutil
import csv
from datetime import datetime

_log = get_logger("organizer.ui")


def get_undo_history_dir() -> str:
    """Retorna o diretório central para arquivos de histórico de undo."""
    home = os.path.expanduser("~")
    undo_dir = os.path.join(home, ".utilitarios", "undo_history")
    os.makedirs(undo_dir, exist_ok=True)
    return undo_dir


class AutoOrganizerWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._plan: List[PlanItem] = []
        self._last_undo_path: str | None = None
        self._applying: bool = False
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._init_ui()
        self._load_last_undo_path()  # Carregar último undo da sessão anterior

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Pasta alvo
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(); self.dir_edit.setPlaceholderText('Pasta a organizar...')
        btn_dir = QPushButton('Escolher...'); btn_dir.clicked.connect(self._choose_dir)
        self.recursive = QCheckBox('Incluir subpastas'); self.recursive.setChecked(True)
        dir_row.addWidget(QLabel('Destino:'))
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_dir)
        dir_row.addWidget(self.recursive)

        # Regras (cabeçalho)
        rules_header = QHBoxLayout()
        lbl_rules = QLabel('Regras:')
        self.lbl_rules_icon = QLabel('')  # ícone de alerta (⚠)
        self.lbl_rules_icon.setVisible(False)
        self.lbl_rules_icon.setFixedWidth(18)
        self.lbl_rules_icon.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        rules_header.addWidget(lbl_rules)
        rules_header.addWidget(self.lbl_rules_icon)
        rules_header.addStretch(1)

        # Regras (controles)
        rules_controls = QHBoxLayout()
        btn_defaults = QPushButton('Restaurar Padrões')
        btn_clear = QPushButton('Limpar')
        btn_import = QPushButton('Importar...')
        btn_export = QPushButton('Exportar...')
        rules_controls.addWidget(btn_defaults)
        rules_controls.addWidget(btn_clear)
        rules_controls.addSpacing(12)
        rules_controls.addWidget(btn_import)
        rules_controls.addWidget(btn_export)
        rules_controls.addStretch(1)

        self.rules_text = QTextEdit()
        self.rules_text.setPlaceholderText(
            'Defina regras (Categoria: .ext, .ext2, ...). Exemplo:\n'
            'Imagens: .jpg, .png\nDocumentos: .pdf, .docx\nÁudio: .mp3, .wav'
        )
        # Resumo dinâmico (definido ANTES de preencher padrões para permitir atualização)
        self.rules_summary = QLabel('—')
        # Preencher com defaults
        self._fill_defaults()
        # Atualização dinâmica do resumo conforme edição manual
        self.rules_text.textChanged.connect(self._update_rules_summary)

        # Linha para adicionar categoria/ extensões rapidamente
        add_row = QHBoxLayout()
        self.input_cat = QLineEdit(); self.input_cat.setPlaceholderText('Categoria (ex.: Imagens)')
        self.input_exts = QLineEdit(); self.input_exts.setPlaceholderText('Extensões (ex.: .jpg, .png)')
        btn_add_rule = QPushButton('Adicionar')
        add_row.addWidget(QLabel('Nova regra:'))
        add_row.addWidget(self.input_cat)
        add_row.addWidget(self.input_exts, 1)
        add_row.addWidget(btn_add_rule)
        # Ações rápidas das regras
        btn_defaults.clicked.connect(self._on_rules_defaults)
        btn_clear.clicked.connect(self._on_rules_clear)
        btn_add_rule.clicked.connect(self._on_rules_add)
        btn_import.clicked.connect(self._on_rules_import)
        btn_export.clicked.connect(self._on_rules_export)

        # Persistência: salvar quando alterar campos
        self.dir_edit.textChanged.connect(lambda _: self._save_settings())
        self.rules_text.textChanged.connect(self._save_settings)
        self.recursive.stateChanged.connect(lambda _: self._save_settings())

        # Resumo dinâmico já criado acima

        # Ações
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.btn_preview = QPushButton('Gerar Prévia'); self.btn_preview.clicked.connect(self._on_preview)
        self.btn_apply = QPushButton('Aplicar'); self.btn_apply.clicked.connect(self._on_apply)
        self.btn_undo = QPushButton('Desfazer último'); self.btn_undo.clicked.connect(self._on_undo_last)
        self.btn_history = QPushButton('📜 Histórico'); self.btn_history.clicked.connect(self._on_view_history)
        actions.addWidget(self.btn_preview)
        actions.addWidget(self.btn_apply)
        actions.addWidget(self.btn_undo)
        actions.addWidget(self.btn_history)

        # Tabela
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Arquivo', 'Categoria/Destino', 'Caminho de destino', 'Ação', 'Motivo'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(False)

        # Rodapé
        self.summary = QLabel('Pronto')

        root.addLayout(dir_row)
        root.addLayout(rules_header)
        root.addLayout(rules_controls)
        root.addWidget(self.rules_text, 1)
        root.addLayout(add_row)
        root.addWidget(self.rules_summary)
        root.addLayout(actions)
        root.addWidget(self.table, 1)
        root.addWidget(self.summary)
        # Carregar preferências e atualizar estado inicial de resumo/alerta/aplicar
        self._load_settings()
        self._update_rules_summary()

    # Handlers
    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, 'Escolher diretório alvo')
        if d:
            self.dir_edit.setText(d)

    def _fill_defaults(self) -> None:
        defaults_lines = []
        for cat, exts in default_mapping().items():
            defaults_lines.append(f"{cat}: {', '.join(exts)}")
        self.rules_text.setText('\n'.join(defaults_lines))

    def _on_rules_defaults(self) -> None:
        self._fill_defaults()
        self._update_rules_summary()
        self._save_settings()

    def _on_rules_clear(self) -> None:
        self.rules_text.clear()
        self._update_rules_summary()
        self._save_settings()

    def _on_rules_add(self) -> None:
        cat = self.input_cat.text().strip()
        exts = self.input_exts.text().strip()
        if not cat or not exts:
            CustomDialog.warning(self, 'Aviso', 'Informe a categoria e as extensões.')
            return
        # Normalize to ".ext, .ext2" format
        parts = [p.strip() for p in exts.split(',') if p.strip()]
        norm: List[str] = []
        for p in parts:
            p = p.lower()
            if not p.startswith('.'):
                p = '.' + p
            norm.append(p)
        line = f"{cat}: {', '.join(norm)}"
        txt = self.rules_text.toPlainText().strip()
        if txt:
            txt = txt + '\n' + line
        else:
            txt = line
        self.rules_text.setPlainText(txt)
        self.input_cat.clear(); self.input_exts.clear()
        self._update_rules_summary()
        self._save_settings()

    def _update_rules_summary(self) -> None:
        rule = parse_rules(self.rules_text.toPlainText())
        cats = len(rule.mapping)
        total_exts = sum(len(v) for v in rule.mapping.values())
        conflicts = self._find_conflicts(rule.mapping)
        text = f'Regras: {cats} categorias, {total_exts} extensões'
        if conflicts:
            text += f' • conflitos: {len(conflicts)} ext(s) duplicada(s)'
            # destacar visualmente (laranja para poucos, vermelho para muitos)
            severity = '#f59e0b' if len(conflicts) <= 3 else '#ef4444'
            self.rules_summary.setStyleSheet(f'color: {severity}; font-weight: 600;')
            tip_lines = [f"{ext}: {', '.join(sorted(cats))}" for ext, cats in conflicts.items()]
            self.rules_summary.setToolTip('Conflitos:\n' + '\n'.join(tip_lines))
            # ícone de alerta ao lado de "Regras:"
            self.lbl_rules_icon.setText('⚠')
            self.lbl_rules_icon.setStyleSheet(f'color: {severity}; font-size: 14px;')
            self.lbl_rules_icon.setToolTip('Conflitos nas regras. Passe o mouse no resumo para detalhes.')
            self.lbl_rules_icon.setVisible(True)
        else:
            # resetar estilo quando não houver conflitos
            self.rules_summary.setStyleSheet('')
            self.rules_summary.setToolTip('')
            self.lbl_rules_icon.setVisible(False)
        # Desabilitar "Aplicar" quando houver conflitos (se já existir)
        if hasattr(self, 'btn_apply'):
            self.btn_apply.setEnabled(len(conflicts) == 0)
        self.rules_summary.setText(text)
        # destacar linhas conflitantes no editor
        self._highlight_conflicts(conflicts)

    def _highlight_conflicts(self, conflicts: dict) -> None:
        selections: list = []
        if conflicts:
            conflict_exts = set(conflicts.keys())
            doc = self.rules_text.document()
            block = doc.firstBlock()
            while block.isValid():
                line = block.text()
                if any(ext in line for ext in conflict_exts):
                    sel = QTextEdit.ExtraSelection()
                    fmt = QTextCharFormat()
                    fmt.setBackground(QColor('#402022'))  # fundo vermelho escuro suave
                    fmt.setForeground(QColor('#ffd6d6'))  # texto claro sutil
                    sel.format = fmt
                    cursor = QTextCursor(doc)
                    cursor.setPosition(block.position())
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    sel.cursor = cursor
                    selections.append(sel)
                block = block.next()
        self.rules_text.setExtraSelections(selections)

    def _find_conflicts(self, mapping) -> dict:
        # ext -> set(categories)
        exts = {}
        for cat, lst in mapping.items():
            for e in lst:
                exts.setdefault(e, set()).add(cat)
        # only those with more than one category
        return {e: cats for e, cats in exts.items() if len(cats) > 1}

    def _on_rules_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Importar regras', '', 'Text Files (*.txt);;All Files (*)')
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.rules_text.setPlainText(f.read())
            self._update_rules_summary()
            self._save_settings()
        except Exception as e:
            CustomDialog.critical(self, 'Erro', f'Falha ao importar: {e}')

    def _on_rules_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar regras', 'regras.txt', 'Text Files (*.txt);;All Files (*)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.rules_text.toPlainText())
        except Exception as e:
            CustomDialog.critical(self, 'Erro', f'Falha ao exportar: {e}')

    def _load_settings(self) -> None:
        s = QSettings()
        last_dir = s.value('organizer/last_dir', '')
        rules = s.value('organizer/rules_text', '')
        recursive = s.value('organizer/recursive', True, type=bool)
        if isinstance(last_dir, str) and last_dir:
            self.dir_edit.setText(last_dir)
        if isinstance(rules, str) and rules:
            self.rules_text.setPlainText(rules)
        if isinstance(recursive, bool):
            self.recursive.setChecked(recursive)
    
    def _load_last_undo_path(self) -> None:
        """Carrega o último arquivo de undo da sessão anterior."""
        s = QSettings()
        path = s.value('organizer/last_undo_path', '')
        if isinstance(path, str) and path and os.path.exists(path):
            self._last_undo_path = path
            self.btn_undo.setEnabled(True)
        else:
            # Verificar se há arquivos de undo disponíveis no diretório de histórico
            undo_dir = get_undo_history_dir()
            files = self._get_undo_files()
            if files:
                self._last_undo_path = files[0][1]  # Mais recente
                self.btn_undo.setEnabled(True)
            else:
                self.btn_undo.setEnabled(False)
    
    def _save_last_undo_path(self, path: str) -> None:
        """Salva o caminho do último arquivo de undo."""
        s = QSettings()
        s.setValue('organizer/last_undo_path', path)
        self._last_undo_path = path
    
    def _get_undo_files(self) -> list[tuple[str, str]]:
        """Retorna lista de arquivos de undo ordenados por data (mais recente primeiro)."""
        undo_dir = get_undo_history_dir()
        files = []
        for f in os.listdir(undo_dir):
            if f.startswith('organizador_undo_') and f.endswith('.csv'):
                full_path = os.path.join(undo_dir, f)
                mtime = os.path.getmtime(full_path)
                files.append((f, full_path, mtime))
        files.sort(key=lambda x: x[2], reverse=True)  # Mais recente primeiro
        return [(f[0], f[1]) for f in files]

    def _save_settings(self) -> None:
        s = QSettings()
        s.setValue('organizer/last_dir', self.dir_edit.text())
        s.setValue('organizer/rules_text', self.rules_text.toPlainText())
        s.setValue('organizer/recursive', self.recursive.isChecked())

    def _on_preview(self) -> None:
        directory = self.dir_edit.text().strip()
        if not directory or not os.path.isdir(directory):
            CustomDialog.warning(self, 'Aviso', 'Selecione uma pasta válida.')
            return
        rule = parse_rules(self.rules_text.toPlainText())
        # validar conflitos
        conflicts = self._find_conflicts(rule.mapping)
        if conflicts:
            msg = 'Existem extensões atribuídas a múltiplas categorias:\n' + '\n'.join(
                f"{ext}: {', '.join(sorted(cats))}" for ext, cats in conflicts.items()
            )
            CustomDialog.warning(self, 'Conflitos de regras', msg)
            return
        rule.recursive = self.recursive.isChecked()
        
        # Executar build_plan em thread separada para não travar a UI
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import QThread, QObject, pyqtSignal
        
        self.btn_preview.setEnabled(False)
        self.btn_apply.setEnabled(False)
        
        prog = QProgressDialog('Analisando arquivos...', 'Cancelar', 0, 0, self)
        prog.setWindowTitle('Gerando Prévia')
        prog.setMinimumDuration(0)
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()
        
        # Force a UI to update
        QApplication.processEvents()
        
        class PreviewWorker(QObject):
            finished = pyqtSignal(list)  # plan
            error = pyqtSignal(str)
            
            def __init__(self, directory, rule):
                super().__init__()
                self.directory = directory
                self.rule = rule
            
            def run(self):
                try:
                    _log.info("Prévia: gerando plano para %s (recursive=%s)",
                              self.directory, self.rule.recursive)
                    plan = build_plan(self.directory, self.rule)
                    _log.info("Prévia concluída: %d itens no plano", len(plan))
                    self.finished.emit(plan)
                except Exception as e:
                    _log.exception("Falha ao gerar prévia para %s", self.directory)
                    self.error.emit(str(e))
        
        thread = QThread(self)
        worker = PreviewWorker(directory, rule)
        worker.moveToThread(thread)
        
        def on_finished(plan):
            self._plan = plan
            self._update_table_from_plan()
            prog.close()
            self.btn_preview.setEnabled(True)
            self.btn_apply.setEnabled(True)
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()
            self.summary.setText(f"Prévia: {len([p for p in plan if p.action == 'move'])} arquivos para mover")
        
        def on_error(msg):
            prog.close()
            self.btn_preview.setEnabled(True)
            self.btn_apply.setEnabled(True)
            CustomDialog.critical(self, 'Erro', f'Falha ao gerar prévia: {msg}')
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()
        
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        prog.canceled.connect(lambda: thread.quit())
        
        thread.started.connect(worker.run)
        thread.start()

    def _update_table_from_plan(self) -> None:
        # Preencher tabela inteira a partir de self._plan
        self.table.setRowCount(0)
        for it in self._plan:
            row = self.table.rowCount(); self.table.insertRow(row)
            name_item = QTableWidgetItem(os.path.basename(it.src))
            cat = os.path.basename(os.path.dirname(it.dst)) if it.action == 'move' else '-'
            cat_item = QTableWidgetItem(cat)
            dst_item = QTableWidgetItem(it.dst if it.action == 'move' else '-')
            act_item = QTableWidgetItem(it.action)
            reason_item = QTableWidgetItem(it.reason or '-')
            if it.reason:
                reason_item.setToolTip(it.reason)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, cat_item)
            self.table.setItem(row, 2, dst_item)
            self.table.setItem(row, 3, act_item)
            self.table.setItem(row, 4, reason_item)
            
    def _on_apply(self) -> None:
        if self._applying:
            return
        if not self._plan:
            CustomDialog.information(self, 'Info', 'Gere uma prévia antes de aplicar.')
            return
        # Segurança: confirmar
        resp = CustomDialog.question(self, 'Confirmar', 'Aplicar o plano de organização agora?')
        if not resp:
            return
        from PyQt6.QtWidgets import QProgressDialog
        total = sum(1 for i in self._plan if i.action == 'move')
        prog = QProgressDialog('Organizando arquivos...', 'Cancelar', 0, max(total, 1), self)
        prog.setWindowTitle('Aplicando')
        prog.setMinimumDuration(0)
        prog.setValue(0)

        # Thread e worker
        self._applying = True
        self.btn_apply.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_undo.setEnabled(False)

        # Salvar undo no diretório central de histórico
        undo_dir = get_undo_history_dir()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_folder = os.path.basename(self.dir_edit.text().strip()) or 'root'
        undo_path = os.path.join(undo_dir, f'organizador_undo_{ts}_{target_folder}.csv')

        class ApplyWorker(QObject):
            progress = pyqtSignal(int, str)  # step, name
            done = pyqtSignal(int, int, int, str)  # moved, skipped, errors, undo_path
            def __init__(self, plan, undo_file):
                super().__init__()
                self.plan = plan
                self.undo_file = undo_file
                self.cancel = False
            def run(self):
                moved = skipped = errors = 0
                step = 0
                total_moves = sum(1 for i in self.plan if i.action == 'move')
                _log.info("Aplicação iniciada: %d itens para mover (undo=%s)",
                          total_moves, self.undo_file)
                try:
                    with open(self.undo_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['src', 'dst'])
                        for item in self.plan:
                            if item.action != 'move':
                                skipped += 1
                                continue
                            if self.cancel:
                                _log.warning("Aplicação cancelada pelo usuário após %d movidos", moved)
                                break
                            try:
                                os.makedirs(os.path.dirname(item.dst), exist_ok=True)
                                if self.cancel:
                                    break
                                # Resolve colisão em runtime (dois itens do plano
                                # podem apontar para o mesmo dst, ou o arquivo
                                # pode ter sido criado por terceiro após o preview).
                                item.dst = resolve_collision(item.dst)
                                writer.writerow([item.src, item.dst])
                                shutil.move(item.src, item.dst)
                                moved += 1
                            except Exception as e:
                                _log.exception("Falha ao mover %s -> %s",
                                               item.src, item.dst)
                                item.action = 'error'
                                item.reason = str(e)
                                errors += 1
                            step += 1
                            self.progress.emit(step, os.path.basename(item.src))
                except Exception:
                    _log.exception("Erro inesperado no ApplyWorker (undo=%s)", self.undo_file)
                    raise
                finally:
                    _log.info("Aplicação finalizada: movidos=%d pulados=%d erros=%d",
                              moved, skipped, errors)
                    self.done.emit(moved, skipped, errors, self.undo_file)

        thread = QThread(self)
        worker = ApplyWorker(self._plan, undo_path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda step, name: (prog.setValue(step), prog.setLabelText(f"Movendo {name}")))
        def finish_handler(moved, skipped, errors, undo_file):
            prog.close()
            self._applying = False
            self.btn_preview.setEnabled(True)
            self.btn_apply.setEnabled(True)
            if moved > 0:
                self._save_last_undo_path(undo_file)
                self.btn_undo.setEnabled(True)
            self.summary.setText(f"Aplicado: movidos {moved}, pulados {skipped}, erros {errors}")
            extra = f"\nHistórico salvo (use 📜 Histórico para ver)" if moved > 0 else ''
            if errors:
                CustomDialog.warning(self, 'Concluído com erros', f"Movidos: {moved}\nPulados: {skipped}\nErros: {errors}{extra}")
            else:
                CustomDialog.information(self, 'Concluído', f"Movidos: {moved}\nPulados: {skipped}{extra}")
            # Após aplicar, atualizar tabela (alguns itens podem ter virado 'error')
            self._update_table_from_plan()
            thread.quit(); thread.wait(); worker.deleteLater(); thread.deleteLater()
            self._thread = None
            self._worker = None
        worker.done.connect(finish_handler)
        prog.canceled.connect(lambda: setattr(worker, 'cancel', True))
        # Guardar refs para tratar fechamento
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_undo_last(self) -> None:
        # Selecionar CSV de undo
        undo_file = self._last_undo_path
        if not undo_file or not os.path.exists(undo_file):
            path, _ = QFileDialog.getOpenFileName(self, 'Selecionar arquivo de desfazer', '', 'CSV Files (*.csv);;All Files (*)')
            if not path:
                return
            undo_file = path
        # Confirmar
        resp = CustomDialog.question(self, 'Confirmar desfazer', f'Deseja desfazer as movimentações usando:\n{undo_file}?')
        if not resp:
            return
        # Ler CSV e desfazer
        from PyQt6.QtWidgets import QProgressDialog
        moves: list[tuple[str, str]] = []
        try:
            with open(undo_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        src, dst = row[0], row[1]
                        moves.append((src, dst))
        except Exception as e:
            CustomDialog.critical(self, 'Erro', f'Falha ao ler CSV: {e}')
            return
        if not moves:
            CustomDialog.information(self, 'Nada a desfazer', 'O arquivo de desfazer está vazio.')
            return
        # desfazer na ordem inversa para segurança
        moves.reverse()
        prog = QProgressDialog('Desfazendo movimentações...', 'Cancelar', 0, len(moves), self)
        prog.setWindowTitle('Desfazer')
        prog.setMinimumDuration(0)
        moved_back = skipped = errors = 0
        for i, (src, dst) in enumerate(moves, start=1):
            if prog.wasCanceled():
                break
            prog.setValue(i)
            prog.setLabelText(f"Voltando {os.path.basename(dst)}")
            try:
                # mover de dst -> src; garantir diretório e nome único
                if not os.path.exists(dst):
                    skipped += 1
                    continue
                os.makedirs(os.path.dirname(src), exist_ok=True)
                target = src
                if os.path.exists(target):
                    base, ext = os.path.splitext(os.path.basename(src))
                    dirp = os.path.dirname(src)
                    j = 1
                    while True:
                        candidate = os.path.join(dirp, f"{base} (undo {j}){ext}")
                        if not os.path.exists(candidate):
                            target = candidate
                            break
                        j += 1
                shutil.move(dst, target)
                moved_back += 1
            except Exception:
                errors += 1
        prog.close()
        self.summary.setText(f"Desfazer: retornados {moved_back}, ignorados {skipped}, erros {errors}")
        if errors:
            CustomDialog.warning(self, 'Desfazer concluído com erros', f"Retornados: {moved_back}\nIgnorados: {skipped}\nErros: {errors}")
        else:
            CustomDialog.information(self, 'Desfazer concluído', f"Retornados: {moved_back}\nIgnorados: {skipped}")
    
    def _on_view_history(self) -> None:
        """Mostra diálogo com histórico de operações de organização."""
        files = self._get_undo_files()
        
        if not files:
            CustomDialog.information(
                self, 'Histórico Vazio',
                f"Nenhum histórico de organização encontrado.\n\n"
                f"Diretório de histórico:\n{get_undo_history_dir()}"
            )
            return
        
        # Criar diálogo de seleção
        dialog = QDialog(self)
        dialog.setWindowTitle('📜 Histórico de Organizações')
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel('Selecione uma operação para desfazer ou visualizar:'))
        
        list_widget = QListWidget()
        for filename, filepath in files:
            # Extrair informações do nome do arquivo
            # formato: organizador_undo_YYYYMMDD_HHMMSS_folder.csv
            parts = filename.replace('organizador_undo_', '').replace('.csv', '')
            try:
                if '_' in parts:
                    date_part = parts[:15]  # YYYYMMDD_HHMMSS
                    folder_part = parts[16:] if len(parts) > 16 else 'N/A'
                    dt = datetime.strptime(date_part, '%Y%m%d_%H%M%S')
                    display = f"{dt.strftime('%d/%m/%Y %H:%M:%S')} - {folder_part}"
                else:
                    display = filename
            except:
                display = filename
            
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, filepath)
            
            # Adicionar contagem de itens
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    count = sum(1 for _ in f) - 1  # -1 para header
                item.setText(f"{display} ({count} arquivos)")
            except:
                pass
            
            list_widget.addItem(item)
        
        layout.addWidget(list_widget, 1)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        btn_undo = QPushButton('Desfazer Selecionado')
        btn_open_folder = QPushButton('Abrir Pasta')
        btn_delete = QPushButton('Excluir')
        btn_close = QPushButton('Fechar')
        
        btn_layout.addWidget(btn_undo)
        btn_layout.addWidget(btn_open_folder)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        def on_undo():
            item = list_widget.currentItem()
            if not item:
                CustomDialog.warning(dialog, 'Aviso', 'Selecione um item.')
                return
            filepath = item.data(Qt.ItemDataRole.UserRole)
            dialog.accept()
            self._last_undo_path = filepath
            self._on_undo_last()
        
        def on_open_folder():
            import subprocess
            import sys as _sys
            undo_dir = get_undo_history_dir()
            if _sys.platform.startswith('win'):
                subprocess.Popen(['explorer', undo_dir])
            elif _sys.platform == 'darwin':
                subprocess.Popen(['open', undo_dir])
            else:
                subprocess.Popen(['xdg-open', undo_dir])
        
        def on_delete():
            item = list_widget.currentItem()
            if not item:
                CustomDialog.warning(dialog, 'Aviso', 'Selecione um item.')
                return
            filepath = item.data(Qt.ItemDataRole.UserRole)
            resp = CustomDialog.question(
                dialog, 'Confirmar',
                f'Excluir este registro de histórico?\n{os.path.basename(filepath)}'
            )
            if resp:
                try:
                    os.remove(filepath)
                    list_widget.takeItem(list_widget.row(item))
                except Exception as e:
                    CustomDialog.critical(dialog, 'Erro', f'Falha ao excluir: {e}')
        
        btn_undo.clicked.connect(on_undo)
        btn_open_folder.clicked.connect(on_open_folder)
        btn_delete.clicked.connect(on_delete)
        btn_close.clicked.connect(dialog.reject)
        
        list_widget.itemDoubleClicked.connect(lambda: on_undo())
        
        dialog.exec()

    # Garantir cancelamento ao fechar widget se thread estiver ativa
    def closeEvent(self, event):  # type: ignore[override]
        if self._thread is not None and self._thread.isRunning():
            # Solicitar cancelamento e aguardar
            if self._worker is not None and hasattr(self._worker, 'cancel'):
                try:
                    setattr(self._worker, 'cancel', True)
                except Exception:
                    pass
            self._thread.quit()
            self._thread.wait(3000)
        return super().closeEvent(event)


class AutoOrganizerTabbedWidget(QWidget):
    """Widget container com abas para organização manual e monitoramento automático."""
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Criar abas
        self.tabs = QTabWidget()
        
        # Aba 1: Organizador Manual
        self.manual_widget = AutoOrganizerWidget()
        self.tabs.addTab(self.manual_widget, "📁 Organizar Agora")
        
        # Aba 2: Monitoramento (importar aqui para evitar circular)
        from app.ui.widgets.folder_watcher_widget import FolderWatcherWidget
        self.watcher_widget = FolderWatcherWidget()
        self.tabs.addTab(self.watcher_widget, "👁 Monitoramento")
        
        layout.addWidget(self.tabs)
    
    def closeEvent(self, event):
        """Propaga close para widgets filhos."""
        self.manual_widget.closeEvent(event)
        self.watcher_widget.closeEvent(event)
        super().closeEvent(event)

