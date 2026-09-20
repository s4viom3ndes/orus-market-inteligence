# Orus

Ferramenta de market intelligence + repricer para sellers do Mercado Livre.
Repositorio **publico** — nada de dado de cliente, credencial ou pesquisa comercial aqui dentro.

## O que o produto faz hoje

1. **Coleta de mercado** — bestsellers de ~214 categorias e todas as ofertas concorrentes de cada um, com enrichment de consumidor (visits/reviews/questions) e de vendedor (reputacao). Vai pra Parquet no R2.
2. **Monitor de Buy Box** — acompanha os SKUs do cliente contra o mercado, detecta mudanca de estado, manda email.
3. **Preco otimo por SKU** — maximiza `P(buy box) x margem` usando um logit estimado nos proprios dados, nao regra de bolso. Roda todo dia, manda email quando ha recomendacao acionavel.
4. **Dashboards** — um pro cliente, um pra ops.

O repricer e `suggest_only`. Nada altera preco no ML sozinho.

## Stack

- Python 3.12 (o CI fixa 3.12; local tambem roda no conda base)
- polars + pyarrow (Parquet), numpy (OLS/MDP)
- httpx (cliente HTTP), pydantic (models), PyYAML (config)
- boto3 → Cloudflare R2 (S3-compat)
- FastAPI + uvicorn — so pro OAuth callback e webhook
- Streamlit — dashboards (Streamlit Cloud)
- GitHub Actions — todo o agendamento
- Cloudflare Tunnel (`cloudflared`) pra expor o webhook local em https

## Estrutura

Tudo do backend vive sob `etl/`. Os imports sao relativos a `etl/`, entao **todo `python -m jobs.x` roda com cwd em `etl/`** — e os workflows fazem isso via `working-directory: etl`.

```
etl/
  src/
    config.py          .env, WATCHLIST_CATEGORIES/SELLERS, flag USE_REMOTE_STORAGE
    webhook.py         FastAPI: /health, /webhook/ml/{secret}, /oauth/start, /oauth/callback
  services/
    ml_client.py       HTTP com auto-refresh de token por expires_at
    token_store.py     tokens.json local + espelho em state/tokens.json no R2
    search.py          iter_highlights, iter_product_items, normalize_offer, get_product_safe
    categories.py      walker da arvore por max_depth
    category_names.py  cache {cat_id: {name, path}} em state/category_names.json
    enrichment.py      visits/reviews/questions por item + reputacao por seller
    highlights_tracker.py  registra categorias sem ranking, sem podar nenhuma
    buy_box_monitor.py     avalia SKU vs snapshot, com fallback live
    repricer.py        regras deterministicas v1 + simulador
    price_model.py     logit da buy box + margem/break-even (funcoes puras)
    price_optimizer.py argmax de lucro esperado; estatico ou MDP
    market_insights.py OLS pooled dos fatores de buy box (uso interno, pitch)
    client_config.py   config de cliente vinda do R2
    client_history.py  1 linha por SKU por dia, pra serie temporal
    data_health.py     metricas green/yellow/red por dataset
    job_status.py      context manager track() pra observabilidade
    email_notifier.py  SMTP + destinatarios extras via NOTIFY_EMAILS
  jobs/                um modulo por workflow (ver tabela abaixo)
  storage/
    parquet_writer.py  write_snapshot: local ou R2 conforme USE_REMOTE_STORAGE
    r2.py              cliente boto3
  models/              User, MLAccount/MLTokens, MyListing/OfferSnapshot/BuyBoxEvent, product
  scripts/
    custo_infra.py     custo de operar N clientes de hora em hora (numeros medidos)
    market_insights.py roda o OLS sob demanda
  config/mock_client.yaml   4 SKUs fake atrelados a catalog_product_ids reais
  tests/               172 testes; roda em cada push/PR

dashboard/   Streamlit do cliente: app.py + 5 paginas (Mercado, Buy Box, Repricer, Trends, Historico)
admin/       Streamlit de ops: app.py + 5 paginas (Runs, Snapshots, Config, Notificacoes, Data Health)
auth/        scaffold multi-tenant (SQLite + passlib + itsdangerous). NAO esta ligado em nada ainda
notebooks/   analise exploratoria; 01_buy_box_e_margem.ipynb e de onde saem os coeficientes
docs/        material de produto/negocio — gitignored, fica so local
```

## GitHub Actions

Oito workflows. A ordem importa: quase tudo le o snapshot que o `collect_market` escreve.

| cron (UTC) | workflow | duracao | o que faz |
|---|---|---|---|
| `0 3 * * *` | collect-market | ~33 min | ofertas + enrichment, `--max-per-cat 10` |
| `15 3 * * *` | collect-trends | ~2 min | trending searches do site |
| `30 3 * * *` | monitor-buy-box | ~2 min | estado dos SKUs, email na mudanca |
| `30 3 * * 1` | discover-categories | — | atualiza `state/leaves.json`, `--max-depth 2` |
| `45 3 * * *` | repricer | ~2 min | sugestoes por regra → `reprice_suggestions/` |
| `0 4 * * *` | optimize-prices | ~5 min | preco otimo por MDP → `price_optimizer/` + email |
| `0 4 * * *` | check-data-health | ~2 min | saude dos datasets → `state/data_health/` |
| `15 4 * * *` | track-client-history | ~2 min | serie diaria por SKU → `buy_box_history/` |

Mais o `tests.yml`, que roda em push e PR (sem cron).

Todos usam `concurrency: <nome>` com `cancel-in-progress: false`. O motivo e o mesmo em todos: **refresh_token do ML e single-use**, entao dois runs simultaneos renovando token quebram um ao outro.

Secrets necessarios (Settings > Secrets and variables > Actions):
`ML_APP_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`, `ML_WEBHOOK_SECRET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `SMTP_*`, `NOTIFY_EMAILS`.

`NOTIFY_EMAILS` (lista separada por virgula) existe porque o repo e publico e email de terceiro nao pode ficar versionado. `email_notifier.destinatarios()` le a env a cada chamada, nao no import — trocar o secret nao exige reiniciar nada.

## Modelo de preco

Essa e a parte que vale mais atencao, e ela tem duas metades independentes.

**`price_model.py` — probabilidade e margem, funcoes puras.**
Logit condicional com efeito fixo por produto-dia, estimado sobre 181.972 ofertas em 17.075 grupos (`notebooks/01_buy_box_e_margem.ipynb`, coeficientes de 2026-09-12). O efeito fixo cancela na razao, entao `P(vence) = exp(V) / (exp(V) + soma exp(V_rival))`.

O coeficiente dominante e `titular = 3.4975` — **+96% de preco-sombra**. Quem ja tem a buy box cobra quase o dobro de um desafiante e mantem a mesma chance. Por isso a probabilidade depende do *estado*, nao so do preco.

`TARIFAS` (comissao, taxa fixa, limiar e custo de frete) sao **defaults plausiveis, nao auditados no contrato do cliente**. Estao isolados num dict justamente pra serem trocados quando o numero real aparecer. Se alguem citar esses valores num material pro cliente, tem que vir com a ressalva.

**`price_optimizer.py` — a decisao.**
Maximiza `P(buy box) x margem`, nao a chance de ganhar. Ganhar buy box e trivial (basta cobrar pouco); o que tem maximo interior e o produto dos dois.

- modo `estatico`: argmax do lucro esperado de hoje.
- modo `sequencial` (default): politica de um MDP sobre o estado (titular?, preco vigente), value iteration com γ=0.97. Existe por causa do +96%: conquistar a buy box e investimento amortizado sobre ~7,7 dias de posse.

A consequencia pratica e que **titular e desafiante recebem recomendacoes opostas no mesmo mercado** — o desafiante desce o preco, o titular sobe. Isso e o modelo funcionando, nao bug.

Volume de vendas nao entra: multiplica os dois lados do argmax e some. Conveniente, porque volume por SKU e justamente o dado que nao temos.

Status possiveis: `hold`, `suggest_change`, `locked` (faixa da rodada nao alcanca), `inviavel` (break-even acima do teto — decisao e de compra, nao de preco), `sem_custo`, `sem_mercado`, `no_data`.

**`market_insights.py`** e coisa separada: OLS pooled com dummy de categoria, ferramenta interna pro pitch. Usa OLS e nao logistica de proposito — o coeficiente sai em pontos percentuais e vira frase pra humano sem converter odds ratio. Gera avisos automaticos quando R² e baixo ou a regra obs/parametro e violada. **Nao mandar esse texto direto pro cliente sem revisar.**

## Descobertas da API do ML

- `/sites/MLB/search` foi **restringido** (403). Nao usar pra mercado geral.
- `/products/search` devolve produtos "filho" sem PDP e sem `/items` (404). Nao serve pra buy box.
- **Caminho que funciona**: `/highlights/{site}/category/{cat_id}` → bestsellers, dai `/products/{id}/items` → todas as ofertas concorrentes.
- `buy_box_winner` no `/products/{id}` vem `null` na maioria dos casos. Ranking real e a ordem em `/products/{id}/items` (posicao 0 = vencedor). No snapshot, `rank == 0` bate 100% com `is_buy_box_winner`.
- `/highlights` devolve dois tipos: `PRODUCT` (catalogo, disputa buy box) e `USER_PRODUCT` (anuncio proprio do seller, sem concorrente na pagina). **Os dois sao coletados** — ignorar `USER_PRODUCT` custava caro: na varredura de 12/09/2026, 759 entradas eram anuncio proprio, e sao justamente sellers que fogem do catalogo por diferenciacao. Mas quem otimiza preco **filtra por `product_type == "PRODUCT"`**, porque num anuncio proprio nao ha buy box e a probabilidade do modelo nao significa nada.
- 43 das 214 categorias dao 404 em `/highlights` toda run. **Nao podar**: o conjunto tem rotatividade medida (MLB455298 dava 404 em 24/08 e voltou em 10/09) e inclui sazonais de Natal. `highlights_tracker` so registra quem esta fora e quem voltou.
- `/visits/items` aceita **1 ID por chamada** (mudanca recente do ML). Por isso o enrichment de visits so roda no vencedor.
- `reviews_count`, `reviews_avg_rating` e `questions_count` sao atributos do **produto**, iguais pra todo concorrente do mesmo anuncio. Nao explicam por que um seller especifico ganha. Quem diferencia e a reputacao por **seller** (`seller_power_status`, `seller_ratings_negative`), adicionada em 27/08 — snapshots anteriores nao tem essas colunas, entao todo uso delas e condicional.
- ~0,03% das ofertas tem preco absurdo (um item de R$27 com concorrente a R$399.900.000,00). Nunca sao vencedoras, mas contaminam qualquer estatistica de preco relativo. `market_insights.remove_price_outliers` corta acima de 20x a mediana do produto. **Qualquer estrategia que leia "menor preco do concorrente" direto do snapshot precisa desse guard rail.**
- Endpoints de outros sellers (`/users/{id}/items/search`, `/items/{id}` alheio) dao 403. Categoria do cliente so via `/sites/MLB/domain_discovery/search`.
- Autorizacao offline (`refresh_token`) precisa ser habilitada **explicitamente** no painel do app. Sem isso o access_token expira em 6h e quebra tudo.
- 403 `PA_UNAUTHORIZED_RESULT_FROM_POLICIES` (PolicyAgent) aparece quando IP/app/token esta em estado ruim, mesmo em endpoint publico. Solucao: app novo + esperar.

## Fluxo de token

`tokens.json` guarda `access_token`, `refresh_token`, `expires_at`. `ml_client.get_access_token()` checa expiracao com margem de 5 min e renova via `/oauth/token` grant `refresh_token`.

**Refresh_token e single-use** — o refresh devolve um par novo que substitui o antigo. Daí o `concurrency` em todos os workflows, e daí o espelho em `state/tokens.json` no R2: o Actions nao tem storage persistente entre runs, entao o R2 e a fonte de verdade na pratica. `token_store` sempre grava local tambem.

## Config de cliente

Vive em `state/clients/{nome}.yaml` **no R2**, nao no git — o repo e publico e config de cliente carrega carteira, precos e o mapeamento de catalogos concorrentes, que e resultado da nossa analise.

```python
from services import client_config
client_config.push("nome-do-cliente")   # sobe o local pro R2 (e assim que um cliente novo entra)
cfg = client_config.load("nome-do-cliente")
client_config.listar()
```

Precedencia: R2 primeiro, `etl/config/client_{nome}.yaml` como fallback de desenvolvimento (esse caminho esta no `.gitignore`).

Sem `--cliente`, os jobs caem no `mock_client.yaml`, que fica versionado e serve pra demo.

## Rodando localmente

Sempre com cwd em `etl/`:

```
cd etl

python -m jobs.collect_market --max-per-cat 10
python -m jobs.discover_categories --max-depth 2
python -m jobs.collect_trends
python -m jobs.monitor_buy_box
python -m jobs.run_repricer
python -m jobs.optimize_prices --modo sequencial --sem-email
python -m jobs.track_client_history
python -m jobs.check_data_health
python -m jobs.scheduler --every-minutes 60 --run-now   # loop de dev

python -m pytest -q          # precisa de `pip install -r requirements.txt` antes
python scripts/custo_infra.py
python scripts/market_insights.py
```

Webhook / OAuth (so quando for reautorizar ou testar notificacao do ML):

```
# terminal 1
cd etl && uvicorn src.webhook:app --host 0.0.0.0 --port 8000 --reload
# terminal 2
cloudflared tunnel --url http://localhost:8000
```

Dashboards:

```
cd dashboard && streamlit run app.py
cd admin && streamlit run app.py
```

## Datasets no R2

```
market_offers/date=YYYY-MM-DD/snapshot-<epoch>.parquet    1 linha = oferta (produto x seller)
trends/date=.../snapshot-*.parquet                        keyword, rank, scope
reprice_suggestions/date=.../snapshot-*.parquet           sugestao por regra
price_optimizer/date=.../snapshot-*.parquet               preco otimo do MDP
buy_box_history/date=.../snapshot-*.parquet               1 linha por SKU por dia

state/tokens.json               OAuth (fonte de verdade pro Actions)
state/leaves.json               categorias-folha descobertas
state/clients/{nome}.yaml       config de cliente
state/mock_client.yaml          copia do mock pro dashboard ler
state/buy_box_state.json        estado anterior do monitor
state/highlights_404.json       categorias sem ranking + ha quantas runs
state/category_names.json       cache de nome/path por categoria
state/job_status/<job>_latest.json  + history/
state/data_health/<dataset>_latest.json + history/ + _summary_latest.json
notification_log/<epoch>_<email>.json   auditoria de envio de email
```

## Como descobrir category_id de um produto do cliente

Nao ha endpoint publico que liste categorias de outro seller. Fluxo manual:

1. Cliente manda a URL do produto.
2. `GET /sites/MLB/domain_discovery/search?q=<nome do produto>&limit=3` → devolve `category_id` predito.
3. Adicionar em `WATCHLIST_CATEGORIES` em `etl/src/config.py`.
4. A watchlist tem prioridade sobre as folhas descobertas, entao a proxima rodada ja pega.

## Nao fazer

- Nao usar `/sites/MLB/search` — restringido.
- Nao commitar `.env`, `tokens.json`, `etl/config/client_*.yaml` nem nada de `docs/`. **O repo e publico.**
- Nao mascarar IP pra contornar `PolicyAgent` — risco de banir o app.
- Nao chamar `/products/{id}/items` em produto com `parent_id` (sao variacoes, nao tem `/items`).
- Nao podar categoria que da 404 em `/highlights` — ver `highlights_tracker`.
- Nao rodar dois jobs que tocam token ao mesmo tempo (refresh_token single-use).
- Nao citar numero de `TARIFAS` como se fosse auditado.
- Nao mandar saida do `market_insights` pro cliente sem revisao humana.

## Estado e proximos passos

MVP fechado, dashboards no ar, dados fluindo diariamente sem intervencao. Detalhe do que falta esta no `ROADMAP.md`; o resumo:

- **Repricer v2/v3** — modo `approval` e depois `auto_apply`. Os dois dependem de OAuth real do cliente, que ainda nao existe.
- **Multi-tenant** — `auth/` tem o scaffold (models, signup, login, link_ml, my_skus) mas nao esta ligado no dashboard. Falta sessao real via cookie, migrar config pro DB, particionar parquet por `user_id` e trocar SQLite por Postgres.
- **Cadencia** — hoje e 1x/dia. Buy box muda varias vezes por dia, entao perda so aparece 24h depois. O split hot/cold path esta desenhado e orcado (1920 min/mes, cabe no free tier), mas **adiado de proposito**: validar o cliente com cadencia diaria antes de gastar o tempo.
- **Timezone** — hoje mistura UTC e BRT. Vale padronizar antes que alguem leia um grafico errado.
