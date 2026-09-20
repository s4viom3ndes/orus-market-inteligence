# Notebooks de analise

Analises exploratorias sobre os dados coletados em `market_offers` (R2). Nao fazem parte do
pipeline de producao — sao o lugar de formular e testar hipoteses antes de virarem codigo no ETL.

## Notebooks

| Arquivo | O que responde |
|---|---|
| `01_buy_box_e_margem.ipynb` | O que determina ganhar a buy box, quanto cada atributo vale em preço, quanto dura a posse, e se a carteira do cliente disputa buy box |
| `mdp_prototype.py` | Protótipo do repricer como MDP sobre titularidade: vale mais conquistar a buy box ou colher margem? Virou `services/price_optimizer.otimizar(modo="sequencial")` |

## O que daqui vira produção

Este diretório não é só exploratório — é a **origem dos coeficientes** que o ETL usa como
constante:

- A **seção 6** do `01` estima o logit condicional dinâmico (grupo = produto × dia, com o termo
  `titular`) que alimenta `price_model.COEFICIENTES`.
- `mdp_prototype.py` desenhou a política que virou o modo sequencial do otimizador.

> **Nota de 2026-09-19.** Até esta revisão, a estimação dinâmica **não estava versionada em lugar
> nenhum**: só o resultado final aparecia, hardcoded em `price_model.py` e no `mdp_prototype.py`.
> A seção 6 do notebook agora reconstrói e documenta esse passo. Como os filtros originais não são
> conhecidos, a diferença entre os betas novos e os de produção mistura mudança de mercado com
> mudança de método — o notebook diz isso explicitamente em 6.1.

Consequência prática que continua valendo: **reestimar aqui não atualiza produção sozinho.** Os
betas são copiados à mão para `etl/services/price_model.py`, e o comentário lá carrega a data da
estimativa. Trocá-los muda recomendação de preço, então é decisão, não sincronização automática.

## Como rodar

Os notebooks leem direto do R2, entao precisam das credenciais que o ETL ja usa
(`R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` no `.env` da raiz).

```
pip install -r notebooks/requirements.txt
cd notebooks && jupyter lab
```

O `sys.path` e ajustado na primeira celula para enxergar os modulos de `etl/`, entao o
**working directory precisa ser `notebooks/`**.

Para reexecutar tudo em batch:

```
cd notebooks
jupyter nbconvert --to notebook --execute --inplace 01_buy_box_e_margem.ipynb
```

## Convencoes

- **Outputs ficam commitados.** Estes notebooks sao relatorios para leitura, nao so codigo —
  quem abre no GitHub precisa ver os numeros e graficos sem rodar nada.
- **Premissas de custo ficam isoladas numa unica celula**, marcada como "A CONFIRMAR COM O
  CLIENTE". Nenhum numero de tarifa deve estar espalhado pelo texto.
- **Toda afirmacao no markdown tem que bater com um output logo acima.** Se reexecutar mudar um
  numero, o texto ao redor precisa ser atualizado junto.
