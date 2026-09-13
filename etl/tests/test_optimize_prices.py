"""Testes do job de preco otimo: email e robustez do carregamento de ofertas."""
import polars as pl
import pytest

from jobs.optimize_prices import _ordenar, format_email


def _r(**over):
    base = {"sku": "SKU-1", "status": "suggest_change", "current_price": 50.0,
            "suggested_price": 44.0, "p_win_atual": 0.05, "p_win_sugerido": 0.22,
            "margem_sugerida": 8.0, "ganho_relativo": 3.1, "titular_hoje": False,
            "reason": "desafiante: baixar", "break_even": 30.0}
    base.update(over)
    return base


SELLER = {"name": "Cliente Teste", "contact_email": "a@b.com"}


# --- _ordenar: o fallback live devolve DataFrame sem colunas quando falha ---

def test_ordenar_tolera_dataframe_vazio():
    """Regressao: sort("rank") num DF sem colunas levanta ColumnNotFoundError."""
    assert _ordenar(pl.DataFrame()).is_empty()


def test_ordenar_tolera_dataframe_sem_a_coluna():
    df = pl.DataFrame({"price": [1.0, 2.0]})
    assert _ordenar(df).height == 2


def test_ordenar_ordena_quando_da():
    df = pl.DataFrame({"rank": [2, 0, 1], "price": [3.0, 1.0, 2.0]})
    assert _ordenar(df)["rank"].to_list() == [0, 1, 2]


# --- email ---

def test_email_lista_as_mudancas():
    a, html, _ = format_email([_r()], SELLER)
    assert "1 ajuste(s)" in a
    assert "SKU-1" in html
    assert "R$ 44,00" in html


def test_email_marca_direcao_do_ajuste():
    _, sobe, _ = format_email([_r(current_price=40.0, suggested_price=46.0)], SELLER)
    _, desce, _ = format_email([_r(current_price=50.0, suggested_price=44.0)], SELLER)
    assert "&#9650;" in sobe        # seta pra cima
    assert "&#9660;" in desce       # seta pra baixo


def test_email_distingue_titular_de_desafiante():
    _, t, _ = format_email([_r(titular_hoje=True)], SELLER)
    _, d, _ = format_email([_r(titular_hoje=False)], SELLER)
    assert "titular" in t
    assert "desafiante" in d


def test_email_cobra_o_custo_que_falta():
    """sem_custo e a razao mais provavel de o cliente nao ter valor no dia 1."""
    _, html, _ = format_email(
        [_r(status="sem_custo", suggested_price=None,
            reason="custo_compra ausente - sem ele nao da pra separar lucro de prejuizo")],
        SELLER)
    assert "Precisam de atencao" in html
    assert "custo_compra" in html


def test_email_reporta_sku_inviavel():
    _, html, _ = format_email([_r(status="inviavel", suggested_price=None,
                                  reason="break-even acima do teto")], SELLER)
    assert "inviavel" in html


def test_email_menciona_quem_ja_esta_otimo():
    _, html, _ = format_email([_r(sku="OK-1", status="hold", suggested_price=50.0)], SELLER)
    assert "OK-1" in html
    assert "otimo" in html


def test_email_nao_quebra_com_campos_nulos():
    """Caminho sem_custo/sem_mercado deixa quase tudo None."""
    vazio = {"sku": "X", "status": "sem_mercado", "current_price": 10.0,
             "suggested_price": None, "p_win_atual": None, "p_win_sugerido": None,
             "margem_sugerida": None, "ganho_relativo": None, "titular_hoje": None,
             "reason": "sem ofertas", "break_even": None}
    a, html, txt = format_email([vazio], SELLER)
    assert isinstance(a, str) and isinstance(html, str) and isinstance(txt, str)
    assert "None" not in html


def test_email_retorna_tres_valores():
    out = format_email([_r()], SELLER)
    assert len(out) == 3
    assert all(isinstance(x, str) for x in out)


def test_email_expoe_as_premissas_de_tarifa():
    """O leitor precisa saber que os numeros dependem de premissas nao auditadas."""
    _, html, _ = format_email([_r()], SELLER)
    assert "confirmar" in html.lower()
