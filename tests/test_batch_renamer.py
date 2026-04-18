"""Testes para app.core.batch_renamer — renomeação em massa."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.batch_renamer import (
    RenameRule, RenameItem,
    preview_renames, apply_renames, _apply_rules_to_name,
)


class TestApplyRulesToName:
    """Testa a aplicação de regras a nomes individuais."""
    
    def test_prefix(self):
        rule = RenameRule(prefix='novo', use_sequence=False)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert result == 'novo_foto.jpg'
    
    def test_suffix(self):
        rule = RenameRule(suffix='backup', use_sequence=False)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert result == 'foto_backup.jpg'
    
    def test_prefix_and_suffix(self):
        rule = RenameRule(prefix='pre', suffix='suf', use_sequence=False)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert result == 'pre_foto_suf.jpg'
    
    def test_sequence(self):
        rule = RenameRule(use_sequence=True, sequence_start=1, sequence_pad=3)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert '001' in result
    
    def test_sequence_increment(self):
        rule = RenameRule(use_sequence=True, sequence_start=1, sequence_pad=2)
        r0 = _apply_rules_to_name('a.txt', 0, rule)
        r1 = _apply_rules_to_name('b.txt', 1, rule)
        r2 = _apply_rules_to_name('c.txt', 2, rule)
        assert '01' in r0
        assert '02' in r1
        assert '03' in r2
    
    def test_search_replace(self):
        rule = RenameRule(search='velho', replace='novo', use_sequence=False)
        result = _apply_rules_to_name('arquivo_velho.txt', 0, rule)
        assert 'novo' in result
        assert 'velho' not in result
    
    def test_regex_search_replace(self):
        rule = RenameRule(search=r'r/\d+', replace='NUM', use_sequence=False)
        result = _apply_rules_to_name('foto123.jpg', 0, rule)
        assert 'NUM' in result
        assert '123' not in result
    
    def test_case_lower(self):
        rule = RenameRule(case='lower', use_sequence=False)
        result = _apply_rules_to_name('FotoGrande.jpg', 0, rule)
        assert result == 'fotogrande.jpg'
    
    def test_case_upper(self):
        rule = RenameRule(case='upper', use_sequence=False)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert result == 'FOTO.jpg'  # extension preserved as is, case applies to composed name
    
    def test_case_title(self):
        rule = RenameRule(case='title', use_sequence=False)
        result = _apply_rules_to_name('foto grande.jpg', 0, rule)
        assert result == 'Foto Grande.jpg'
    
    def test_remove_spaces(self):
        rule = RenameRule(remove_spaces=True, use_sequence=False)
        result = _apply_rules_to_name('meu arquivo bonito.txt', 0, rule)
        assert ' ' not in result
        assert '_' in result
    
    def test_change_extension(self):
        rule = RenameRule(change_extension='png', use_sequence=False)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert result.endswith('.png')
    
    def test_ignore_original_with_base(self):
        rule = RenameRule(ignore_original=True, base_name='episodio', use_sequence=True, sequence_start=1, sequence_pad=2)
        result = _apply_rules_to_name('qualquercoisa.mp4', 0, rule)
        assert result.startswith('episodio')
        assert result.endswith('.mp4')
    
    def test_custom_separator(self):
        rule = RenameRule(prefix='pre', suffix='suf', separator='-', use_sequence=False)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert result == 'pre-foto-suf.jpg'
    
    def test_empty_separator(self):
        rule = RenameRule(prefix='A', suffix='B', separator='', use_sequence=False)
        result = _apply_rules_to_name('foto.jpg', 0, rule)
        assert result == 'AfotoB.jpg'


class TestPreviewRenames:
    """Testa a geração de preview de renomeações."""
    
    def test_preview_basic(self, tmp_path):
        # Criar arquivos de teste
        (tmp_path / 'a.txt').write_text('a')
        (tmp_path / 'b.txt').write_text('b')
        
        rule = RenameRule(prefix='new', use_sequence=False)
        items = preview_renames(str(tmp_path), False, None, rule)
        
        assert len(items) == 2
        assert all(it.status == 'ok' for it in items)
    
    def test_preview_skip_no_change(self, tmp_path):
        (tmp_path / 'arquivo.txt').write_text('data')
        
        # Regra que não muda nada
        rule = RenameRule(use_sequence=False)
        items = preview_renames(str(tmp_path), False, None, rule)
        
        assert len(items) == 1
        assert items[0].status == 'skip'
    
    def test_preview_conflict_existing_file(self, tmp_path):
        (tmp_path / 'original.txt').write_text('data')
        (tmp_path / 'new_original.txt').write_text('existing')
        
        rule = RenameRule(prefix='new', use_sequence=False)
        items = preview_renames(str(tmp_path), False, ['.txt'], rule)
        
        # Um dos arquivos deve ter conflito
        conflicts = [it for it in items if it.status == 'conflict']
        assert len(conflicts) >= 1
    
    def test_preview_filter_extensions(self, tmp_path):
        (tmp_path / 'a.txt').write_text('a')
        (tmp_path / 'b.jpg').write_text('b')
        
        rule = RenameRule(prefix='x', use_sequence=False)
        items = preview_renames(str(tmp_path), False, ['.txt'], rule)
        
        assert len(items) == 1
    
    def test_preview_cancel(self, tmp_path):
        for i in range(10):
            (tmp_path / f'file{i}.txt').write_text(str(i))
        
        rule = RenameRule(prefix='x', use_sequence=False)
        items = preview_renames(str(tmp_path), False, None, rule, cancel_check=lambda: True)
        
        # Com cancelamento imediato, deve retornar vazio ou parcial
        assert len(items) < 10


class TestApplyRenames:
    """Testa a aplicação efetiva de renomeações."""
    
    def test_apply_basic(self, tmp_path):
        (tmp_path / 'a.txt').write_text('content_a')
        (tmp_path / 'b.txt').write_text('content_b')
        
        rule = RenameRule(prefix='new', use_sequence=False)
        items = preview_renames(str(tmp_path), False, None, rule)
        
        renamed, skipped, errors = apply_renames(items)
        assert renamed == 2
        assert errors == 0
        assert (tmp_path / 'new_a.txt').exists()
        assert (tmp_path / 'new_b.txt').exists()
    
    def test_apply_refuses_conflicts(self, tmp_path):
        items = [
            RenameItem(src='/tmp/a.txt', dst='/tmp/x.txt', status='ok'),
            RenameItem(src='/tmp/b.txt', dst='/tmp/x.txt', status='conflict', message='Conflito'),
        ]
        renamed, skipped, errors = apply_renames(items)
        assert renamed == 0
        assert errors >= 1
    
    def test_apply_preserves_content(self, tmp_path):
        content = 'conteúdo importante'
        (tmp_path / 'original.txt').write_text(content)
        
        rule = RenameRule(prefix='renamed', use_sequence=False)
        items = preview_renames(str(tmp_path), False, None, rule)
        apply_renames(items)
        
        new_file = tmp_path / 'renamed_original.txt'
        assert new_file.exists()
        assert new_file.read_text() == content
