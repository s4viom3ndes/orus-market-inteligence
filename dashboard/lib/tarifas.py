"""Estrutura de tarifas do Mercado Livre usada nas contas de margem.

Copia dos valores de `etl/services/price_model.TARIFAS`. Existe porque o painel
nao importa de `etl/` - se a estrutura mudar la, muda aqui junto.

**Nenhum destes numeros foi auditado no contrato do vendedor.** Sao valores de
mercado, plausiveis e declarados na tela para quem le poder conferir contra a
propria fatura. Com a conta autorizada, a API do ML devolve a tarifa real por
anuncio e estes defaults saem de cena.
"""

COMISSAO_CLASSICO = 0.11   # anuncio classico (gold_special)
COMISSAO_PREMIUM = 0.16    # anuncio premium (gold_pro)
TAXA_FIXA = 6.25           # por unidade, abaixo do limiar de frete
LIMIAR_FRETE = 79.00       # acima disso o frete gratis passa a ser subsidiado
CUSTO_FRETE = 19.90        # custo medio do frete subsidiado


def margem(preco: float, custo: float, premium: bool = False) -> float:
    """Quanto sobra por unidade vendida, depois de tarifa, frete e custo."""
    com = COMISSAO_PREMIUM if premium else COMISSAO_CLASSICO
    fixa = TAXA_FIXA if preco < LIMIAR_FRETE else 0.0
    frete = CUSTO_FRETE if preco >= LIMIAR_FRETE else 0.0
    return preco * (1 - com) - fixa - frete - custo


def break_even(custo: float, premium: bool = False) -> float:
    """Menor preco que ainda cobre tudo.

    A funcao e descontinua no limiar: abaixo dele paga taxa fixa, acima paga
    frete. Resolve-se os dois regimes e fica o que e internamente consistente.
    """
    com = COMISSAO_PREMIUM if premium else COMISSAO_CLASSICO
    abaixo = (custo + TAXA_FIXA) / (1 - com)
    if abaixo < LIMIAR_FRETE:
        return abaixo
    return max((custo + CUSTO_FRETE) / (1 - com), LIMIAR_FRETE)
