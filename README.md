# Orus — Market Intelligence para Mercado Livre

Inteligência de mercado, monitoramento de Buy Box e precificação para vendedores do Mercado Livre. Coleta ofertas concorrentes por categoria, guarda histórico em Parquet no Cloudflare R2, calcula o preço que maximiza lucro esperado e expõe tudo em dashboards Streamlit.

**Este repositório é público.** Nada de credencial, dado de cliente ou pesquisa comercial entra aqui — ver `.gitignore` e a seção [Config de cliente](#config-de-cliente).

## O que faz

- **Coleta diária** de bestsellers em ~214 categorias (Casa / Cozinha / Eletrodomésticos)
- Pra cada produto: **todas as ofertas concorrentes** — preço, vendedor, logística, condição
- **Enrichment**: visits/reviews/questions por produto, reputação por vendedor
- **Buy Box Monitor**: posição dos SKUs do cliente vs mercado, com detecção de mudança
- **Preço ótimo por SKU**: maximiza `P(buy box) × margem` usando um logit estimado nos próprios dados
- **Repricer por regra**: cinco estratégias determinísticas com guard rails, e um simulador interativo
- **Histórico diário** por SKU, pra série temporal no dashboard
- **Data health**: métricas de qualidade por dataset, com alerta por email
- **Trends**: trending searches do Brasil

O repricer é `suggest_only`. Nenhum código escreve preço no Mercado Livre.

## Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                   GitHub Actions (8 crons)                    │
│  collect_market  collect_trends  monitor_buy_box  repricer    │
│  optimize_prices  check_data_health  track_client_history     │
│  discover_categories                                          │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
              ┌─────────────────────────┐      ┌──────────────┐
              │   Mercado Livre API      │◄────►│ tokens.json  │
              │ /highlights /products/*  │      │  (espelho    │
              └────────────┬─────────────┘      │   no R2)     │
                           ▼                     └──────────────┘
              ┌──────────────────────────────┐
              │        Cloudflare R2          │
              │  market_offers/  trends/      │
              │  reprice_suggestions/         │
              │  price_optimizer/             │
              │  buy_box_history/             │
              │  state/  notification_log/    │
              └───────┬───────────────────────┘
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
      ┌──────────┐        ┌──────────┐
      │  Admin   │        │Dashboard │  ← Streamlit Cloud
      │  (ops)   │        │(cliente) │
      └──────────┘        └──────────┘
```

Além do cron existe um FastAPI local (`etl/src/webhook.py`) com `/oauth/start`, `/oauth/callback` e `/webhook/ml/{secret}`, publicado via Cloudflare Tunnel. Ele só é necessário pra autorizar a conta e receber notificação push do ML.

## Estrutura

Todo o backend vive sob `etl/`, e os imports são relativos a essa pasta — **`python -m jobs.x` roda com cwd em `etl/`**. Os workflows fazem isso via `working-directory: etl`.

```
etl/
├── src/
│   ├── config.py           .env, WATCHLIST_CATEGORIES/SELLERS, flag USE_REMOTE_STORAGE
│   └── webhook.py          FastAPI: OAuth callback + webhook ML
├── services/
│   ├── ml_client.py        HTTP com auto-refresh de token
│   ├── token_store.py      tokens.json local + espelho no R2
│   ├── search.py           highlights, product items, normalize_offer
│   ├── categories.py       walker da árvore por max_depth
│   ├── category_names.py   cache de nome/path por categoria
│   ├── enrichment.py       visits/reviews/questions + reputação de seller
│   ├── highlights_tracker.py   registra categorias sem ranking, sem podar
│   ├── buy_box_monitor.py  avalia SKU vs snapshot, com fallback live
│   ├── repricer.py         regras determinísticas v1 + simulador
│   ├── price_model.py      logit da buy box + margem/break-even (funções puras)
│   ├── price_optimizer.py  argmax de lucro esperado; estático ou MDP
│   ├── market_insights.py  OLS dos fatores de buy box (uso interno)
│   ├── client_config.py    config de cliente vinda do R2
│   ├── client_history.py   1 linha por SKU por dia
│   ├── data_health.py      métricas green/yellow/red por dataset
│   ├── job_status.py       track() pra observabilidade
│   └── email_notifier.py   SMTP + destinatários extras via NOTIFY_EMAILS
├── jobs/                   um módulo por workflow
├── storage/
│   ├── parquet_writer.py   write_snapshot: local ou R2
│   └── r2.py               cliente boto3
├── models/                 Pydantic: User, MLAccount, MyListing, OfferSnapshot…
├── scripts/
│   ├── custo_infra.py      custo de operar N clientes (números medidos)
│   └── market_insights.py  roda o OLS sob demanda
├── config/mock_client.yaml 4 SKUs fake ligados a catalog_product_ids reais
├── tests/                  172 testes
└── requirements.txt

dashboard/                  Streamlit do cliente
├── app.py                  Visão geral: KPIs, winners, logística
├── pages/1_Mercado.py      Deep dive por categoria
├── pages/2_Buy_Box.py      Status dos SKUs vs mercado
├── pages/3_Repricer.py     Sugestões + simulador com slider
├── pages/4_Trends.py       Trending searches
├── pages/5_Historico.py    Série temporal por SKU
└── lib/                    r2_reader (cache 600s), theme, components

admin/                      Streamlit de ops
├── app.py                  Job status + uso do R2
└── pages/                  Runs · Snapshots · Config · Notificações · Data Health

auth/                       Scaffold multi-tenant — NÃO ligado em nada ainda
notebooks/                  Análise exploratória; de onde saem os coeficientes
docs/                       Material de produto/negócio — gitignored, fica local
.github/workflows/          8 crons + tests.yml
```

## Stack

- **Python 3.12** — o CI fixa essa versão
- **polars + pyarrow** (Parquet), **numpy** (OLS e value iteration)
- **httpx** (cliente HTTP), **pydantic** (models), **PyYAML** (config)
- **boto3** → Cloudflare R2 (S3-compatível)
- **FastAPI + uvicorn** — só OAuth callback e webhook
- **Streamlit** — dashboards, deployados no Streamlit Cloud
- **GitHub Actions** — todo o agendamento
- **Cloudflare Tunnel** (`cloudflared`) — expõe o webhook local em HTTPS

## Setup dev

### Pré-requisitos

- Python 3.12+
- Conta Cloudflare com R2 habilitado, bucket criado e API token
- App criada no [Mercado Livre Developer Center](https://developers.mercadolivre.com.br), **com autorização offline habilitada**
- (Opcional) domínio na Cloudflare e `cloudflared` instalado, pra túnel fixo

### 1) Clone + install

```powershell
git clone https://github.com/s4viom3ndes/orus-market-inteligence.git
cd orus-market-inteligence

cd etl && pip install -r requirements.txt && cd ..
cd dashboard && pip install -r requirements.txt && cd ..
cd admin && pip install -r requirements.txt && cd ..
```

### 2) Configurar `.env` na raiz

```env
ML_APP_ID=seu_app_id_numerico
ML_CLIENT_SECRET=seu_client_secret
ML_REDIRECT_URI=https://hook.SEU-DOMINIO/oauth/callback
ML_WEBHOOK_SECRET=gere-uma-string-longa-aleatoria

R2_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=nome-do-bucket

# opcional, pra notificação por email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=voce@gmail.com
SMTP_PASSWORD=app-password-gerada-no-google
SMTP_FROM=voce@gmail.com
NOTIFY_EMAILS=outro@exemplo.com,mais_um@exemplo.com
```

Sem as três variáveis de R2, `USE_REMOTE_STORAGE` fica `False` e todo o pipeline cai pra disco local — dá pra desenvolver sem nuvem nenhuma.

### 3) Autorização OAuth inicial

Precisa uma vez, pra gerar `tokens.json`:

```powershell
# Terminal 1: FastAPI
cd etl && uvicorn src.webhook:app --host 0.0.0.0 --port 8000

# Terminal 2: túnel público
cloudflared tunnel --url http://localhost:8000
```

Cadastra a URL do túnel no painel do ML como Redirect URI (`https://SEU-TUNEL.trycloudflare.com/oauth/callback`) e abre:

```
https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=SEU_APP_ID&redirect_uri=https://SEU-TUNEL.trycloudflare.com/oauth/callback
```

Se aparecer "Autorizado com sucesso" sem aviso laranja sobre refresh_token, deu certo. Se aparecer o aviso, habilita **Autorização offline** no painel do app e refaz — sem isso o token expira em 6h e todo o cron quebra.

## Rodando

### Jobs (sempre com cwd em `etl/`)

```powershell
cd etl

python -m jobs.collect_market --max-per-cat 10
python -m jobs.discover_categories --max-depth 2
python -m jobs.collect_trends
python -m jobs.monitor_buy_box
python -m jobs.run_repricer
python -m jobs.optimize_prices --modo sequencial --sem-email
python -m jobs.track_client_history
python -m jobs.check_data_health

python -m jobs.scheduler --every-minutes 60 --run-now   # loop local de dev
python -m jobs.test_email                                # valida SMTP isoladamente
```

### Testes e scripts

```powershell
cd etl
python -m pytest -q          # 172 testes, tudo sintético — não chama API nem R2
python scripts/custo_infra.py
python scripts/market_insights.py
```

### Dashboards

```powershell
cd dashboard && streamlit run app.py    # cliente
cd admin && streamlit run app.py        # ops
```

### Túnel público persistente

Com domínio na Cloudflare:

```powershell
cloudflared tunnel login
cloudflared tunnel create orus-dev
cloudflared tunnel route dns orus-dev hook.SEU-DOMINIO.com
cloudflared tunnel run orus-dev          # config em ~/.cloudflared/config.yml
```

## Deploy

### GitHub Actions

Já configurado. Secrets em `Settings > Secrets and variables > Actions`:

- `ML_APP_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`, `ML_WEBHOOK_SECRET`
- `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
- Opcionais: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `NOTIFY_EMAILS`

| cron (UTC) | workflow | duração | o que faz |
|---|---|---|---|
| `0 3 * * *` | collect-market | ~33 min | ofertas + enrichment, `--max-per-cat 10` |
| `15 3 * * *` | collect-trends | ~2 min | trending searches |
| `30 3 * * *` | monitor-buy-box | ~2 min | estado dos SKUs, email na mudança |
| `30 3 * * 1` | discover-categories | — | atualiza `state/leaves.json` |
| `45 3 * * *` | repricer | ~2 min | sugestões por regra |
| `0 4 * * *` | optimize-prices | ~5 min | preço ótimo por MDP + email |
| `0 4 * * *` | check-data-health | ~2 min | saúde dos datasets, email se `red` |
| `15 4 * * *` | track-client-history | ~2 min | série diária por SKU |

Mais `tests.yml`, que roda em push e PR. Todos aceitam `workflow_dispatch` pela UI.

Cada workflow usa `concurrency: <nome>` com `cancel-in-progress: false`. O motivo é sempre o mesmo: **refresh_token do ML é single-use**, então dois runs simultâneos renovando token quebram um ao outro.

Consumo atual: ~1280 min/mês, dentro do free tier de 2000. `etl/scripts/custo_infra.py` recalcula isso pra N clientes — o detalhe que domina a conta é que o Actions fatura **por job**, arredondando pro minuto, então processar vários clientes num run só é o que faz fechar.

### Streamlit Cloud

Pra cada app (`dashboard` e `admin`):

1. https://share.streamlit.io → **Create app**
2. Repo `s4viom3ndes/orus-market-inteligence`, branch `main`
3. Main file: `dashboard/app.py` ou `admin/app.py`
4. **Advanced → Secrets** (TOML):
   ```toml
   R2_ENDPOINT = "https://..."
   R2_ACCESS_KEY_ID = "..."
   R2_SECRET_ACCESS_KEY = "..."
   R2_BUCKET = "..."
   ```

Os dois apps são somente leitura sobre o R2. **Nenhum dos dois tem login** — publicados, as URLs são públicas pra quem descobrir. Isso precisa de solução antes de operar com cliente pagante, principalmente o `admin/`, que expõe configuração interna.

## Modelo de preço

Duas metades independentes, e vale entender a diferença antes de mexer.

**`price_model.py` — probabilidade e margem, funções puras.** Logit condicional com efeito fixo por produto-dia, estimado sobre 181.972 ofertas em 17.075 grupos (`notebooks/01_buy_box_e_margem.ipynb`, coeficientes de 2026-09-12). O efeito fixo cancela na razão, então vale a forma multinomial padrão.

O coeficiente que manda é `titular = 3.4975` — **+96% de preço-sombra**. Quem já tem a buy box cobra quase o dobro de um desafiante e mantém a mesma chance. Por isso a probabilidade depende do *estado*, não só do preço.

`TARIFAS` (comissão, taxa fixa, limiar e custo de frete) são **defaults plausíveis, não auditados no contrato do cliente**. Ficam isolados num dict pra serem trocados quando o número real aparecer.

**`price_optimizer.py` — a decisão.** Maximiza `P(buy box) × margem`, não a chance de ganhar: ganhar buy box é trivial (basta cobrar pouco), o que tem máximo interior é o produto dos dois.

- modo `estatico` — argmax do lucro esperado de hoje
- modo `sequencial` (default) — política de um MDP sobre o estado (titular?, preço vigente), value iteration com γ=0.97

A consequência prática é que **titular e desafiante recebem recomendações opostas no mesmo mercado**: o desafiante desce o preço, o titular sobe. Isso é o modelo funcionando, não bug. Volume de vendas não entra — multiplica os dois lados do argmax e some, o que é conveniente porque volume por SKU é justamente o dado que não temos.

**`market_insights.py`** é coisa separada: OLS pooled com dummy de categoria, ferramenta interna pro pitch. Usa OLS e não logística de propósito, porque o coeficiente sai em pontos percentuais e vira frase pra humano sem converter odds ratio. Gera avisos automáticos quando R² é baixo ou a regra obs/parâmetro é violada — **não mandar essa saída pro cliente sem revisar**.

## Config de cliente

Vive em `state/clients/{nome}.yaml` **no R2**, não no git: o repo é público e config de cliente carrega carteira, preços e o mapeamento de catálogos concorrentes, que é resultado da nossa análise.

```python
from services import client_config
client_config.push("nome-do-cliente")   # sobe local → R2; é assim que um cliente novo entra
cfg = client_config.load("nome-do-cliente")
client_config.listar()
```

Precedência: R2 primeiro, `etl/config/client_{nome}.yaml` como fallback de desenvolvimento (gitignored). Sem `--cliente`, os jobs caem no `mock_client.yaml`, que é versionado e serve pra demo.

## Datasets no R2

```
market_offers/date=YYYY-MM-DD/snapshot-<epoch>.parquet
  1 linha = 1 oferta (produto de catálogo × vendedor)
  captured_at, category_id, catalog_product_id, product_name, product_type,
  item_id, seller_id, price, currency_id, condition, listing_type_id,
  rank, is_buy_box_winner, is_watched_seller, official_store_id,
  shipping_free, shipping_mode, shipping_logistic_type, shipping_cost,
  visits_30d, reviews_count, reviews_avg_rating, questions_count,
  seller_power_status, seller_ratings_negative, brand, model, state, city…

trends/date=.../snapshot-*.parquet              captured_at, site, scope, category_id, rank, keyword, url
reprice_suggestions/date=.../snapshot-*.parquet sugestão por regra (repricer v1)
price_optimizer/date=.../snapshot-*.parquet     preço ótimo do MDP, margem, P(buy box), ganho relativo
buy_box_history/date=.../snapshot-*.parquet     1 linha por SKU por dia (winner, gap, posição)

state/tokens.json               OAuth — fonte de verdade pro Actions
state/leaves.json               categorias-folha descobertas
state/clients/{nome}.yaml       config de cliente
state/mock_client.yaml          cópia do mock, pro dashboard ler
state/buy_box_state.json        estado anterior do monitor
state/highlights_404.json       categorias sem ranking + há quantas runs
state/category_names.json       cache de nome/path por categoria
state/job_status/<job>_latest.json          + history/
state/data_health/<dataset>_latest.json     + history/ + _summary_latest.json
notification_log/<epoch>_<email>.json       auditoria de envio de email
```

## Descobertas da API do ML

- `/sites/MLB/search` foi **restringido em 2024**. Não usar.
- `/products/search` retorna produtos "filho" sem PDP e sem `/items`. Inútil pra buy box.
- **Caminho que funciona**: `/highlights/{site}/category/{cat_id}` → bestsellers → `/products/{id}/items` → todas as ofertas concorrentes.
- `buy_box_winner` em `/products/{id}` vem `null` na maioria dos casos. O vencedor real é o item de `rank == 0` em `/products/{id}/items` — no snapshot isso bate 100% com `is_buy_box_winner`.
- `/highlights` devolve dois tipos: `PRODUCT` (catálogo, disputa buy box) e `USER_PRODUCT` (anúncio próprio, sem concorrente na página). **Os dois são coletados** — na varredura de 12/09/2026, 759 entradas eram anúncio próprio, e são justamente sellers que fogem do catálogo por diferenciação. Mas quem otimiza preço **filtra `product_type == "PRODUCT"`**, porque num anúncio próprio não há buy box.
- 43 das 214 categorias dão 404 em `/highlights` toda run. **Não podar**: o conjunto tem rotatividade medida (MLB455298 dava 404 em 24/08 e voltou em 10/09) e inclui sazonais de Natal. `highlights_tracker` só registra quem está fora e quem voltou.
- `/visits/items` aceita **1 ID por chamada** (mudança recente do ML). Por isso visits só é enriquecido no vencedor.
- `reviews_count`, `reviews_avg_rating` e `questions_count` são atributos do **produto**, iguais pra todo concorrente do mesmo anúncio — não explicam por que um vendedor específico ganha. Quem diferencia é a reputação por **seller** (`seller_power_status`, `seller_ratings_negative`), coletada desde 27/08; snapshots anteriores não têm essas colunas.
- ~0,03% das ofertas têm preço absurdo (um item de R$27 com concorrente a R$399.900.000,00). Nunca vencem, mas contaminam qualquer estatística de preço relativo. `market_insights.remove_price_outliers` corta acima de 20× a mediana do produto — qualquer lógica que leia "menor preço do concorrente" direto do snapshot precisa desse guard rail.
- Endpoints de outros vendedores (`/users/{id}/items/search`, `/items/{id}` alheio) retornam 403. Categoria do cliente só via `/sites/MLB/domain_discovery/search`.
- **`refresh_token` exige "Autorização offline" habilitada no painel do app** — sem isso o access_token expira em 6h.
- **`refresh_token` é single-use**: cada refresh retorna um par novo. Não pode haver execuções concorrentes.
- `403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES` (PolicyAgent) aparece quando IP/app/token está em estado ruim, mesmo em endpoint público.

## Adicionar categorias novas do cliente

Não há endpoint público que liste categorias de outro vendedor.

1. Rodar em qualquer python:
   ```python
   import httpx, json
   tok = json.load(open("tokens.json"))["access_token"]
   r = httpx.get(
       "https://api.mercadolibre.com/sites/MLB/domain_discovery/search",
       headers={"Authorization": f"Bearer {tok}"},
       params={"q": "nome do produto do cliente", "limit": 3},
   )
   print(r.json())
   ```
2. Copiar o `category_id` retornado
3. Adicionar em `etl/src/config.py` → `WATCHLIST_CATEGORIES`
4. Commit + push. A watchlist tem prioridade sobre as folhas descobertas, então o próximo cron já pega.

## Troubleshooting

**`ModuleNotFoundError` ao rodar um job**: você está fora de `etl/`. Todos os imports são relativos a essa pasta.

**`cloudflared` não reconhecido**: `winget install Cloudflare.cloudflared` e reabre o terminal.

**Streamlit Cloud "Invalid TOML"**: cada linha precisa de `CHAVE = "valor"`, com aspas e espaços.

**`monitor_buy_box` retorna `no_data` pra todos os SKUs**: os `catalog_product_id` do YAML não estão no snapshot atual. Confere se as categorias estão em `WATCHLIST_CATEGORIES` ou se os produtos aparecem em `/highlights` da categoria.

**`optimize_prices` retorna `sem_custo`**: falta `custo_compra` no YAML do SKU. Sem ele não dá pra separar preço que dá lucro de preço que dá prejuízo, então o otimizador se recusa a chutar.

**`optimize_prices` retorna `inviavel`**: o break-even está acima do teto do SKU. Nenhuma sequência de ajustes resolve — a decisão é de compra, não de preço.

**`403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES`**: bloqueio de IP/app pelo PolicyAgent. Trocar de rede, aguardar, ou regenerar credenciais. **Não mascarar IP** — risco de banir o app.

## Contexto do produto

MVP construído como demo pra cliente potencial (vendedor de variedades, categorias: saca-rolhas, raladores, cabides, luminárias). Objetivo: mostrar diagnóstico de mercado, monitor de buy box e motor de precificação, provando valor antes de fechar contrato.

Estado atual: pipeline rodando diariamente sem intervenção, dashboards no ar, buy box do cliente ainda mockado (depende de OAuth da conta dele). Detalhe do que falta está em `ROADMAP.md`; contexto de desenvolvimento, em `CLAUDE.md`.

## Licença

Privado — sem licença de uso público até definir modelo comercial.
