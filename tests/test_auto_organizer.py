import os
from app.core.auto_organizer import (
    parse_rules, default_mapping, build_plan, apply_plan,
    OrganizeRule, resolve_collision,
)


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


def test_resolve_collision_returns_same_when_missing(tmp_path):
    dst = tmp_path / 'Imagens' / 'foo.png'
    # Arquivo não existe: retorna o próprio caminho intacto
    assert resolve_collision(str(dst)) == str(dst)


def test_resolve_collision_appends_counter(tmp_path):
    dest_dir = tmp_path / 'Imagens'
    dest_dir.mkdir()
    (dest_dir / 'foo.png').write_bytes(b'x')
    (dest_dir / 'foo (1).png').write_bytes(b'x')

    result = resolve_collision(str(dest_dir / 'foo.png'))

    assert result == str(dest_dir / 'foo (2).png')


def test_apply_plan_resolves_runtime_collision_between_items(tmp_path):
    """
    Regressão: com recursive=True, dois arquivos com o mesmo nome em
    subpastas distintas geravam o MESMO dst no plano. No Windows, o
    segundo shutil.move falhava silenciosamente (FileExistsError); em
    Linux podia sobrescrever. apply_plan agora chama resolve_collision
    em runtime para garantir unicidade.
    """
    # Estrutura:
    #   root/
    #     sub_a/foo.jpg   (conteúdo A)
    #     sub_b/foo.jpg   (conteúdo B)
    # Regra: .jpg -> Imagens/
    root = tmp_path
    (root / 'sub_a').mkdir()
    (root / 'sub_b').mkdir()
    (root / 'sub_a' / 'foo.jpg').write_bytes(b'AAA')
    (root / 'sub_b' / 'foo.jpg').write_bytes(b'BBB')

    rule = OrganizeRule(mapping={'Imagens': ['.jpg']}, recursive=True)
    plan = build_plan(str(root), rule)

    moves = [p for p in plan if p.action == 'move']
    assert len(moves) == 2

    # Sem o fix, build_plan gera dsts idênticos (ou quase) e apply_plan
    # precisa lidar com isso. Forçamos o pior caso fazendo ambos apontarem
    # para o mesmo destino ANTES do apply (simulando: build_plan avalia
    # os dois antes de qualquer um existir em Imagens/).
    target = str(root / 'Imagens' / 'foo.jpg')
    for m in moves:
        m.dst = target

    moved, skipped, errors = apply_plan(plan)

    assert moved == 2, f"esperado 2 movidos, obtido {moved} (erros={errors})"
    assert errors == 0

    # Ambos sobreviveram no destino com nomes distintos
    imagens = root / 'Imagens'
    assert imagens.exists()
    arquivos = sorted(f.name for f in imagens.iterdir())
    assert len(arquivos) == 2
    # Um tem o nome original; o outro foi sufixado " (1)"
    assert 'foo.jpg' in arquivos
    assert any('foo (' in n for n in arquivos)


def test_apply_plan_successful_move(tmp_path):
    root = tmp_path
    (root / 'a.jpg').write_bytes(b'x')
    rule = OrganizeRule(mapping={'Imagens': ['.jpg']}, recursive=False)
    plan = build_plan(str(root), rule)

    moved, skipped, errors = apply_plan(plan)

    assert moved == 1
    assert errors == 0
    assert (root / 'Imagens' / 'a.jpg').exists()
    assert not (root / 'a.jpg').exists()
