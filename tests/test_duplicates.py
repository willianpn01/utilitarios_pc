"""Testes para app.core.duplicates — detecção de arquivos duplicados."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.duplicates import find_duplicates, _hash_file


class TestHashFile:
    """Testa o cálculo de hash de arquivos."""
    
    def test_hash_deterministic(self, tmp_path):
        f = tmp_path / 'test.bin'
        f.write_bytes(b'hello world')
        h1 = _hash_file(str(f))
        h2 = _hash_file(str(f))
        assert h1 == h2
    
    def test_hash_different_content(self, tmp_path):
        f1 = tmp_path / 'a.bin'
        f2 = tmp_path / 'b.bin'
        f1.write_bytes(b'content A')
        f2.write_bytes(b'content B')
        assert _hash_file(str(f1)) != _hash_file(str(f2))
    
    def test_hash_same_content(self, tmp_path):
        f1 = tmp_path / 'a.bin'
        f2 = tmp_path / 'b.bin'
        content = b'identical content'
        f1.write_bytes(content)
        f2.write_bytes(content)
        assert _hash_file(str(f1)) == _hash_file(str(f2))
    
    def test_quick_hash_first_bytes(self, tmp_path):
        f = tmp_path / 'test.bin'
        # 128KB de dados
        f.write_bytes(b'A' * 64 * 1024 + b'B' * 64 * 1024)
        quick = _hash_file(str(f), first_bytes=64 * 1024)
        full = _hash_file(str(f))
        # Quick hash deve ser diferente do full quando conteúdo varia após 64KB
        assert quick != full


class TestFindDuplicates:
    """Testa a busca de duplicados."""
    
    def test_no_duplicates(self, tmp_path):
        (tmp_path / 'a.txt').write_text('conteudo A')
        (tmp_path / 'b.txt').write_text('conteudo B')
        (tmp_path / 'c.txt').write_text('conteudo C')
        
        groups = find_duplicates(str(tmp_path))
        assert len(groups) == 0
    
    def test_basic_duplicates(self, tmp_path):
        content = 'mesmo conteudo em todos'
        (tmp_path / 'a.txt').write_text(content)
        (tmp_path / 'b.txt').write_text(content)
        (tmp_path / 'c.txt').write_text('diferente')
        
        groups = find_duplicates(str(tmp_path))
        assert len(groups) == 1
        assert len(groups[0]) == 2
    
    def test_multiple_groups(self, tmp_path):
        (tmp_path / 'a1.txt').write_text('grupo A')
        (tmp_path / 'a2.txt').write_text('grupo A')
        (tmp_path / 'b1.txt').write_text('grupo B')
        (tmp_path / 'b2.txt').write_text('grupo B')
        (tmp_path / 'unico.txt').write_text('unico')
        
        groups = find_duplicates(str(tmp_path))
        assert len(groups) == 2
    
    def test_min_size_filter(self, tmp_path):
        # Arquivo pequeno (< 100 bytes)
        (tmp_path / 'small1.txt').write_text('x')
        (tmp_path / 'small2.txt').write_text('x')
        
        # Arquivo maior
        big_content = 'X' * 200
        (tmp_path / 'big1.txt').write_text(big_content)
        (tmp_path / 'big2.txt').write_text(big_content)
        
        groups = find_duplicates(str(tmp_path), min_size_bytes=100)
        assert len(groups) == 1
        assert all('big' in os.path.basename(p) for p in groups[0])
    
    def test_extension_filter(self, tmp_path):
        content = 'mesmo'
        (tmp_path / 'a.txt').write_text(content)
        (tmp_path / 'b.txt').write_text(content)
        (tmp_path / 'c.jpg').write_text(content)
        (tmp_path / 'd.jpg').write_text(content)
        
        groups = find_duplicates(str(tmp_path), include_exts={'.txt'})
        assert len(groups) == 1
        assert all(p.endswith('.txt') for p in groups[0])
    
    def test_recursive(self, tmp_path):
        subdir = tmp_path / 'sub'
        subdir.mkdir()
        content = 'duplicado'
        (tmp_path / 'top.txt').write_text(content)
        (subdir / 'bottom.txt').write_text(content)
        
        groups_recursive = find_duplicates(str(tmp_path), recursive=True)
        groups_flat = find_duplicates(str(tmp_path), recursive=False)
        
        assert len(groups_recursive) == 1
        assert len(groups_flat) == 0
    
    def test_cancel(self, tmp_path):
        content = 'x' * 100
        for i in range(20):
            (tmp_path / f'file{i}.txt').write_text(content)
        
        groups = find_duplicates(str(tmp_path), cancel_check=lambda: True)
        assert groups == []
    
    def test_progress_callback(self, tmp_path):
        content = 'test'
        (tmp_path / 'a.txt').write_text(content)
        (tmp_path / 'b.txt').write_text(content)
        
        progress_values = []
        def cb(pct, msg):
            progress_values.append(pct)
        
        find_duplicates(str(tmp_path), progress_cb=cb)
        assert len(progress_values) > 0
        assert progress_values[-1] == 100
    
    def test_empty_directory(self, tmp_path):
        groups = find_duplicates(str(tmp_path))
        assert groups == []
