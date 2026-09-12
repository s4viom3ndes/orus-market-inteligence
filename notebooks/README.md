# Notebooks de analise

Analises exploratorias sobre os dados coletados em `market_offers` (R2). Nao fazem parte do
pipeline de producao — sao o lugar de formular e testar hipoteses antes de virarem codigo no ETL.

## Notebooks

| Arquivo | O que responde |
|---|---|
| `01_buy_box_e_margem.ipynb` | O que determina ganhar a buy box, quanto cada atributo vale em preco, e qual preco maximiza lucro esperado dado o custo de fornecedor |

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
