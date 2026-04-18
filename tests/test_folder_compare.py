"""Testes para app.core.folder_compare."""
import os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.core.folder_compare import compare_directories, _scan_directory, _calculate_hash


class TestScanDirectory:
    def test_scan_empty(self, tmp_path):
        assert len(_scan_directory(str(tmp_path))) == 0

    def test_scan_flat(self, tmp_path):
        (tmp_path / 'a.txt').write_text('a')
        (tmp_path / 'b.txt').write_text('b')
        result = _scan_directory(str(tmp_path), recursive=False)
        assert len(result) == 2

    def test_scan_recursive(self, tmp_path):
        sub = tmp_path / 'sub'; sub.mkdir()
        (tmp_path / 'top.txt').write_text('t')
        (sub / 'bot.txt').write_text('b')
        assert len(_scan_directory(str(tmp_path), recursive=True)) == 2
        assert len(_scan_directory(str(tmp_path), recursive=False)) == 1


class TestCompareDirectories:
    def test_identical(self, tmp_path):
        l, r = tmp_path / 'l', tmp_path / 'r'; l.mkdir(); r.mkdir()
        (l / 'f.txt').write_text('same'); (r / 'f.txt').write_text('same')
        res = compare_directories(str(l), str(r))
        assert len(res.identical) == 1 and not res.only_left and not res.only_right

    def test_only_left(self, tmp_path):
        l, r = tmp_path / 'l', tmp_path / 'r'; l.mkdir(); r.mkdir()
        (l / 'exc.txt').write_text('x')
        res = compare_directories(str(l), str(r))
        assert len(res.only_left) == 1

    def test_only_right(self, tmp_path):
        l, r = tmp_path / 'l', tmp_path / 'r'; l.mkdir(); r.mkdir()
        (r / 'exc.txt').write_text('x')
        res = compare_directories(str(l), str(r))
        assert len(res.only_right) == 1

    def test_different_by_size(self, tmp_path):
        l, r = tmp_path / 'l', tmp_path / 'r'; l.mkdir(); r.mkdir()
        (l / 'f.txt').write_text('short'); (r / 'f.txt').write_text('much longer')
        res = compare_directories(str(l), str(r))
        assert len(res.different) == 1

    def test_different_by_content(self, tmp_path):
        l, r = tmp_path / 'l', tmp_path / 'r'; l.mkdir(); r.mkdir()
        (l / 'f.txt').write_text('AAAA'); (r / 'f.txt').write_text('BBBB')
        res = compare_directories(str(l), str(r), compare_content=True)
        assert len(res.different) == 1

    def test_empty(self, tmp_path):
        l, r = tmp_path / 'l', tmp_path / 'r'; l.mkdir(); r.mkdir()
        res = compare_directories(str(l), str(r))
        assert not any([res.only_left, res.only_right, res.different, res.identical])
