import os
from app.core.auto_organizer import parse_rules, default_mapping, build_plan, OrganizeRule


def _conflicts(mapping: dict[str, list[str]]) -> dict[str, set[str]]:
    exts: dict[str, set[str]] = {}
    for cat, lst in mapping.items():
        for e in lst:
            exts.setdefault(e, set()).add(cat)
    return {e: cats for e, cats in exts.items() if len(cats) > 1}


def test_parse_rules_merges_and_dedups():
    text = (
        "Imagens: jpg, .png, .JPG\n"
        "Documentos: .pdf, .docx\n"
        "Imagens: .png, .gif"
    )
    rule = parse_rules(text)
    assert 'Imagens' in rule.mapping
    assert rule.mapping['Imagens'] == ['.jpg', '.png', '.gif']
    assert rule.mapping['Documentos'] == ['.pdf', '.docx']


def test_parse_rules_defaults_when_empty():
    rule = parse_rules("")
    assert rule.mapping == default_mapping()


def test_conflict_detection_logic():
    mapping = {
        'Fotos': ['.jpg', '.png'],
        'Thumbs': ['.png']
    }
    conf = _conflicts(mapping)
    assert '.png' in conf
    assert conf['.png'] == {'Fotos', 'Thumbs'}


def test_build_plan_basic(tmp_path):
    root = tmp_path
    f1 = root / 'a.jpg'
    f2 = root / 'b.txt'
    f1.write_bytes(b'1')
    f2.write_bytes(b'2')

    # Destination already exists to force unique rename
    (root / 'Imagens').mkdir()
    existing = root / 'Imagens' / 'a.jpg'
    existing.write_bytes(b'existing')

    rule = OrganizeRule(mapping={'Imagens': ['.jpg']}, recursive=False)
    plan = build_plan(str(root), rule)

    # Expect one move for a.jpg (renamed) and one skip for txt
    moves = [p for p in plan if p.action == 'move']
    skips = [p for p in plan if p.action == 'skip']

    assert len(moves) == 1
    dst = moves[0].dst
    assert os.path.dirname(dst).endswith(os.path.join('Imagens'))
    assert os.path.basename(dst) != 'a.jpg'  # must have been uniquified

    assert len(skips) == 1
    assert 'sem categoria' in skips[0].reason
