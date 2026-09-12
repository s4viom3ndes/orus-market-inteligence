"""Testes do rastreio de categorias sem ranking em /highlights.

O ponto do rastreio e detectar RECUPERACAO (sazonalidade entrando), entao os
testes cobrem o ciclo completo: entra, acumula, volta.
"""
from services.highlights_tracker import update

T0 = 1_700_000_000
DIA = 86_400


def test_primeira_run_registra_como_nova():
    st = update({}, sem_ranking=["A", "B"], com_ranking=["C"], now=T0)
    assert set(st["categories"]) == {"A", "B"}
    assert st["new"] == ["A", "B"]
    assert st["recovered"] == []
    assert st["categories"]["A"]["runs_consecutivas"] == 1
    assert st["categories"]["A"]["primeira_vez"] == T0


def test_falha_consecutiva_incrementa_e_mantem_primeira_vez():
    st = update({}, ["A"], [], now=T0)
    st = update(st, ["A"], [], now=T0 + DIA)
    st = update(st, ["A"], [], now=T0 + 2 * DIA)
    a = st["categories"]["A"]
    assert a["runs_consecutivas"] == 3
    assert a["primeira_vez"] == T0
    assert a["ultima_vez"] == T0 + 2 * DIA
    assert st["new"] == []


def test_recuperacao_sai_do_estado_e_e_reportada():
    """Caso MLB455298: 404 por dias, depois volta a coletar."""
    st = update({}, ["A", "B"], [], now=T0)
    st = update(st, ["A", "B"], [], now=T0 + DIA)
    st = update(st, ["B"], ["A"], now=T0 + 2 * DIA)
    assert st["recovered"] == ["A"]
    assert "A" not in st["categories"]
    assert st["categories"]["B"]["runs_consecutivas"] == 3


def test_recai_depois_de_recuperar_recomeca_contagem():
    st = update({}, ["A"], [], now=T0)
    st = update(st, [], ["A"], now=T0 + DIA)
    st = update(st, ["A"], [], now=T0 + 2 * DIA)
    assert st["new"] == ["A"]
    assert st["categories"]["A"]["runs_consecutivas"] == 1
    assert st["categories"]["A"]["primeira_vez"] == T0 + 2 * DIA


def test_categoria_ausente_da_run_e_preservada():
    """Run parcial ou watchlist alterada nao pode zerar o historico."""
    st = update({}, ["A", "B"], [], now=T0)
    st = update(st, ["A"], [], now=T0 + DIA)
    assert st["categories"]["B"]["runs_consecutivas"] == 1
    assert "B" not in st["recovered"]


def test_nao_muta_o_estado_anterior():
    prev = update({}, ["A"], [], now=T0)
    snapshot = prev["categories"]["A"]["runs_consecutivas"]
    update(prev, ["A"], [], now=T0 + DIA)
    assert prev["categories"]["A"]["runs_consecutivas"] == snapshot


def test_estado_vazio_e_run_limpa():
    st = update({}, [], ["A", "B"], now=T0)
    assert st["categories"] == {}
    assert st["recovered"] == []
    assert st["new"] == []


def test_record_nunca_levanta(monkeypatch):
    """Rastreio e observabilidade - nao pode derrubar a coleta."""
    from services import highlights_tracker as ht

    def boom():
        raise RuntimeError("R2 fora do ar")

    monkeypatch.setattr(ht, "load_state", boom)
    assert ht.record(["A"], []) == {}
