"""Testes do modelo de preco: probabilidade de buy box e margem."""
import math

import pytest

from services.price_model import (COEFICIENTES, TARIFAS, break_even, margem,
                                  prob_vitoria, soma_rivais, utilidade)


# --- utilidade ---

def test_preco_na_mediana_zera_o_termo_de_preco():
    assert utilidade(50.0, 50.0) == pytest.approx(0.0)


def test_preco_mais_alto_reduz_utilidade():
    assert utilidade(60.0, 50.0) < utilidade(40.0, 50.0)


def test_titularidade_e_o_maior_efeito():
    """+3,4975 contra +0,7066 do FULL - e o coeficiente dominante."""
    base = utilidade(50.0, 50.0)
    assert utilidade(50.0, 50.0, titular=True) - base > utilidade(50.0, 50.0, full=True) - base


def test_premium_penaliza():
    assert utilidade(50.0, 50.0, premium=True) < utilidade(50.0, 50.0)


def test_preco_invalido_levanta():
    with pytest.raises(ValueError):
        utilidade(0.0, 50.0)


# --- probabilidade ---

def _rivais(*precos):
    return [{"price": p, "rank": i} for i, p in enumerate(precos)]


def test_probabilidade_cai_quando_o_preco_sobe():
    r = _rivais(40.0, 45.0, 50.0)
    s = soma_rivais(r, 45.0)
    assert prob_vitoria(40.0, 45.0, s) > prob_vitoria(60.0, 45.0, s)


def test_probabilidade_fica_entre_zero_e_um():
    s = soma_rivais(_rivais(40.0, 45.0), 45.0)
    for p in (1.0, 45.0, 5000.0):
        assert 0.0 < prob_vitoria(p, 45.0, s) < 1.0


def test_titular_ganha_mais_que_desafiante_no_mesmo_preco():
    s = soma_rivais(_rivais(40.0, 45.0, 50.0), 45.0)
    assert prob_vitoria(50.0, 45.0, s, titular=True) > prob_vitoria(50.0, 45.0, s)


def test_titular_caro_pode_bater_desafiante_barato():
    """Efeito medido: titular na 5a posicao de preco ganha de desafiante na 1a."""
    s = soma_rivais(_rivais(40.0, 45.0, 50.0), 45.0)
    assert prob_vitoria(70.0, 45.0, s, titular=True) > prob_vitoria(40.0, 45.0, s, titular=False)


def test_soma_rivais_ignora_preco_invalido():
    assert soma_rivais([{"price": 0}, {"price": None}, {"price": 45.0}], 45.0) == pytest.approx(
        soma_rivais([{"price": 45.0}], 45.0))


def test_soma_rivais_vazia_e_zero():
    assert soma_rivais([], 45.0) == 0.0


def test_sem_rivais_a_vitoria_e_praticamente_certa():
    assert prob_vitoria(50.0, 50.0, 0.0) == pytest.approx(1.0)


# --- margem ---

def test_margem_desconta_comissao_e_taxa_fixa():
    # 50 * 0,89 - 6,25 - 20 = 18,25
    assert margem(50.0, 20.0) == pytest.approx(50 * 0.89 - 6.25 - 20)


def test_acima_do_limiar_troca_taxa_fixa_por_frete():
    p = 100.0
    assert margem(p, 20.0) == pytest.approx(p * 0.89 - 19.90 - 20)


def test_premium_come_mais_margem():
    assert margem(50.0, 20.0, premium=True) < margem(50.0, 20.0)


def test_margem_negativa_abaixo_do_custo():
    assert margem(15.0, 30.0) < 0


# --- break-even ---

@pytest.mark.parametrize("custo", [5.0, 10.0, 20.0, 30.0, 50.0, 90.0, 150.0])
def test_break_even_zera_a_margem(custo):
    be = break_even(custo)
    assert margem(be, custo) == pytest.approx(0.0, abs=0.02)


def test_break_even_cresce_com_o_custo():
    assert break_even(10.0) < break_even(30.0) < break_even(80.0)


def test_break_even_premium_e_maior():
    assert break_even(30.0, premium=True) > break_even(30.0)


def test_break_even_respeita_a_descontinuidade_do_limiar():
    """Nao pode cair numa faixa em que a propria premissa de tarifa se contradiz."""
    for custo in range(5, 120, 5):
        be = break_even(float(custo))
        abaixo = be < TARIFAS["limiar_frete"]
        # se esta abaixo do limiar, quem entra e a taxa fixa; se acima, o frete
        esperado = (be * 0.89 - (TARIFAS["taxa_fixa"] if abaixo else TARIFAS["custo_frete"]) - custo)
        assert esperado == pytest.approx(0.0, abs=0.02) or be == TARIFAS["limiar_frete"]
