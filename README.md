# Orus — Market Intelligence para Mercado Livre

Ferramenta de inteligência de mercado + monitoramento de Buy Box para vendedores do Mercado Livre. Coleta ofertas concorrentes por categoria, armazena histórico em Parquet no Cloudflare R2, e expõe dashboards em Streamlit.

## O que faz

- **Coleta diária** de bestsellers em ~200 categorias (Casa / Cozinha / Eletrodomésticos)
- Pra cada produto: **todas as ofertas concorrentes** (preço, vendedor, logística, condição)
- **Enrichment de consumidor**: visits, reviews, questions por item vencedor
- **Buy Box Monitor**: rastreia SKUs do cliente vs mercado, gera recomendação de preço
- **Notificação por email** quando estado do buy box muda
- **Trends**: coleta trending searches do Brasil

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Actions (cron)                    │
│                                                              │
│  collect_market   collect_trends   monitor_buy_box   ...    │
│       │                │                  │                  │
└───────┼────────────────┼──────────────────┼──────────────────┘
        │                │                  │
        └────────┬───────┴──────────────────┘
                 ▼
   ┌─────────────────────────────────┐        ┌──────────────┐
   │      Mercado Livre API           │◄──────►│  tokens.json │
   │   /highlights, /products/*, ...  │        │   (R2)       │
   └─────────────┬───────────────────┘        └──────────────┘
                 │
                 ▼
   ┌─────────────────────────────────┐
   │      Cloudflare R2               │
   │  market_offers/  trends/         │
   │  state/  job_status/             │
   └─────────┬────────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
┌──────────┐    ┌──────────┐
│ Admin    │    │Dashboard │  ← Streamlit Cloud
│(savio)   │    │(cliente) │
└──────────┘    └──────────┘
```

## Estrutura

```
/
├── etl/                    Backend ETL (rodado por GitHub Actions)
│   ├── src/
│   │   ├── config.py       Vars de env + WATCHLIST_CATEGORIES/SELLERS
│   │   └── webhook.py      FastAPI: OAuth callback + webhook ML
│   ├── services/
│   │   ├── ml_client.py    Cliente HTTP com auto-refresh de token
│   │   ├── token_store.py  Sync tokens.json ↔ R2
│   │   ├── search.py       Highlights + product items
│   │   ├── categories.py   Walker recursivo da árvore de categorias
│   │   ├── enrichment.py   Visits / reviews / questions por item
│   │   ├── buy_box_monitor.py  Avalia SKUs mock vs mercado
│   │   ├── email_notifier.py   SMTP notifier (opcional)
│   │   └── job_status.py   track() context manager pra observability
│   ├── storage/
│   │   ├── parquet_writer.py   Escreve parquet local + upload R2
│   │   └── r2.py           Cliente boto3 pra R2
│   ├── jobs/
│   │   ├── collect_market.py
│   │   ├── collect_trends.py
│   │   ├── monitor_buy_box.py
│   │   ├── discover_categories.py
│   │   └── scheduler.py    Loop local (dev)
│   ├── models/             Pydantic: User, MLAccount, MLTokens, MyListing
│   ├── config/
│   │   └── mock_client.yaml  4 SKUs fake atrelados a produtos reais
│   └── requirements.txt
│
├── dashboard/              Streamlit — cliente final
│   ├── app.py              Overview: KPIs, winners, shipping
│   ├── pages/
│   │   ├── 1_Mercado.py    Deep dive por categoria
│   │   ├── 2_Buy_Box.py    Status dos SKUs mock vs mercado
│   │   └── 3_Trends.py     Trending searches
│   ├── lib/r2_reader.py    Leitor R2 cached
│   └── requirements.txt
│
├── admin/                  Streamlit — savio (ops)
│   ├── app.py              Job status + R2 usage
│   ├── pages/
│   │   ├── 1_Historico_de_Runs.py
│   │   ├── 2_Snapshots.py  Inspecionar qualquer parquet do R2
│   │   └── 3_Config.py     View read-only da config
│   ├── lib/r2.py
│   └── requirements.txt
│
├── .github/workflows/      4 crons agendados
│   ├── collect_market.yml       03:00 UTC diário
│   ├── collect_trends.yml       03:15 UTC diário
│   ├── monitor_buy_box.yml      03:30 UTC diário
│   └── discover_categories.yml  segunda 03:30 UTC
│
├── .env                    (gitignored) Secrets locais
├── .env.example            Template
├── tokens.json             (gitignored) OAuth do ML (sync com R2)
├── CLAUDE.md               Contexto pra sessões futuras com Claude Code
└── README.md
```

## Stack

- **Python 3.12** (etl, dashboards)
- **FastAPI + uvicorn** — webhook local + OAuth callback
- **httpx** — cliente HTTP
- **polars + pyarrow** — dataframes e Parquet
- **boto3** — cliente S3-compatível pra Cloudflare R2
- **Streamlit** — dashboards
- **pydantic** — models
- **Cloudflare Tunnel** (`cloudflared`) — expõe webhook local com URL fixa (`hook.orus.observer`)
- **GitHub Actions** — cron dos jobs
- **Cloudflare R2** — storage de parquets e state
- **Mercado Livre API** — fonte dos dados

## Setup dev

### Pré-requisitos

- Python 3.12+
- Conta Cloudflare com R2 habilitado + bucket criado + API token
- App criada no [Mercado Livre Developer Center](https://developers.mercadolivre.com.br)
- (Opcional) Domínio na Cloudflare pra túnel fixo
- (Opcional) `cloudflared` instalado pra túnel local

### 1) Clone + install

```powershell
git clone https://github.com/s4viom3ndes/orus-market-inteligence.git
cd orus-market-inteligence

# ETL
cd etl && pip install -r requirements.txt && cd ..

# Dashboard
cd dashboard && pip install -r requirements.txt && cd ..

# Admin
cd admin && pip install -r requirements.txt && cd ..
```

### 2) Configurar `.env` na raiz

Copia `.env.example` pra `.env` e preenche:

```env
ML_APP_ID=seu_app_id_numerico
ML_CLIENT_SECRET=seu_client_secret
ML_REDIRECT_URI=https://hook.SEU-DOMINIO/oauth/callback
ML_WEBHOOK_SECRET=gere-uma-string-longa-aleatoria

R2_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=nome-do-bucket

# Opcional pra notificação email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=voce@gmail.com
SMTP_PASSWORD=app-password-gerada-no-google
SMTP_FROM=voce@gmail.com
```

### 3) Autorização OAuth inicial

Precisa 1 vez pra gerar `tokens.json`:

```powershell
# Terminal 1: FastAPI
cd etl && uvicorn src.webhook:app --host 0.0.0.0 --port 8000

# Terminal 2: túnel público (usa cloudflared quick tunnel)
cloudflared tunnel --url http://localhost:8000
```

Copia a URL do tunnel, cadastra no painel do ML como Redirect URI:
`https://SEU-TUNEL.trycloudflare.com/oauth/callback`

Abre no navegador:
```
https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=SEU_APP_ID&redirect_uri=https://SEU-TUNEL.trycloudflare.com/oauth/callback
```

Autoriza. Se aparecer "Autorizado com sucesso" sem aviso laranja de refresh_token, deu certo. Se aparecer aviso, habilita "Autorização offline" no painel do app e refaz.

## Rodando

### Coleta manual

```powershell
cd etl

# Coleta uma vez (usa WATCHLIST_CATEGORIES + folhas descobertas)
python -m jobs.collect_market --max-per-cat 10

# Descobrir categorias-folha (roda 1x/semana no cron)
python -m jobs.discover_categories --max-depth 2

# Coletar trends
python -m jobs.collect_trends

# Rodar monitor de buy box + email (se SMTP configurado)
python -m jobs.monitor_buy_box
```

### Dashboards local

```powershell
# Admin (savio)
cd admin && streamlit run app.py
# Abre em http://localhost:8501

# Dashboard cliente
cd dashboard && streamlit run app.py
```

### Túnel público persistente (usando named tunnel)

Se tem domínio na Cloudflare:

```powershell
cloudflared tunnel login
cloudflared tunnel create orus-dev
cloudflared tunnel route dns orus-dev hook.SEU-DOMINIO.com
# Config em ~/.cloudflared/config.yml
cloudflared tunnel run orus-dev
```

## Deploy

### GitHub Actions

Já configurado. Adiciona os secrets em https://github.com/SEU_USER/orus-market-inteligence/settings/secrets/actions:

- `ML_APP_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`, `ML_WEBHOOK_SECRET`
- `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
- (Opcional) `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

Os workflows disparam automaticamente em cron ou via **workflow_dispatch** na UI do GitHub.

**Custo estimado**: ~1280 min/mês, dentro do free tier de 2000 min.

### Streamlit Cloud (dashboards)

Pra cada app (admin + dashboard):

1. https://share.streamlit.io → **Create app**
2. Repository: `s4viom3ndes/orus-market-inteligence`, branch `main`
3. Main file path: `admin/app.py` (ou `dashboard/app.py`)
4. **Advanced → Secrets** (TOML):
   ```toml
   R2_ENDPOINT = "https://..."
   R2_ACCESS_KEY_ID = "..."
   R2_SECRET_ACCESS_KEY = "..."
   R2_BUCKET = "..."
   ```
5. Deploy

## Datasets no R2

```
market_offers/date=YYYY-MM-DD/snapshot-<epoch>.parquet
  Linha = 1 oferta (produto do catálogo × vendedor)
  Colunas principais:
    captured_at, category_id, catalog_product_id, product_name,
    item_id, seller_id, price, currency_id, condition, listing_type_id,
    rank, is_buy_box_winner, is_watched_seller,
    shipping_free, shipping_mode, shipping_logistic_type, shipping_cost,
    visits_30d, reviews_count, reviews_avg_rating, questions_count,
    brand, model, state, city, ...

trends/date=YYYY-MM-DD/snapshot-<epoch>.parquet
  captured_at, site, scope (site|category), category_id, rank, keyword, url

state/leaves.json          Árvore de categorias-folha descobertas
state/tokens.json          OAuth do ML (sincronizado pelo token_store)
state/buy_box_state.json   Estado anterior do monitor (pra detectar mudança)
state/job_status/<job>_latest.json     Última execução de cada job
state/job_status/history/<job>_<ts>.json  Histórico completo
```

## Descobertas importantes da API do ML

- `/sites/MLB/search` foi **restringido em 2024**. Não usar.
- `/products/search` retorna produtos "filho" sem PDP e sem `/items`. Inútil pra buy box.
- **Caminho oficial pra market intelligence**: `/highlights/{site}/category/{cat_id}` → produtos bestsellers → `/products/{id}/items` → todas as ofertas concorrentes.
- `buy_box_winner` no `/products/{id}` frequentemente vem null. Vencedor real = item de menor `rank` em `/products/{id}/items`.
- **`refresh_token` requer "Autorização offline" habilitada no painel do app** — sem isso, access_token expira em 6h.
- **Refresh_token é single-use**: cada refresh retorna novo par. Não pode ter execuções concorrentes.
- `/visits/items` aceita apenas **1 ID por chamada** (mudança recente do ML).
- Endpoints de outros vendedores (`/users/{id}/items/search`, `/items/{id}` de outro seller) retornam 403. Só dá pra descobrir categorias do cliente via `/sites/MLB/domain_discovery/search`.
- Sinais de consumidor disponíveis: `/reviews/item/{id}`, `/questions/search?item_id=`, `/visits/items?ids=`, `/trends/{site}`.

## Adicionar categorias novas do cliente

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
2. Copiar `category_id` retornado
3. Adicionar em `etl/src/config.py` → `WATCHLIST_CATEGORIES`
4. Commit + push (o próximo cron já pega)

## Troubleshooting

**`cloudflared` não reconhecido**: instala com `winget install Cloudflare.cloudflared` e reabre o terminal.

**Streamlit Cloud "Invalid TOML"**: cada linha precisa ter `CHAVE = "valor"` com aspas e espaços.

**`monitor_buy_box` retorna `no_data` pra todos SKUs**: os `catalog_product_id` em `mock_client.yaml` não estão no snapshot atual. Verificar se estão em `WATCHLIST_CATEGORIES` (que garante coleta) ou se aparecem em `/highlights` da categoria.

**`403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES` do ML**: bloqueio de IP/app pelo PolicyAgent. Trocar de rede, aguardar, ou regenerar credenciais no painel de dev.

## Contexto do produto

MVP construído em ~2 dias como demo pra cliente potencial (vendedor VARIEDADESSB, categorias: saca rolhas, raladores, cabides, luminárias). Objetivo: mostrar diagnóstico de mercado + motor de repricer + monitor de buy box, provando valor antes de fechar contrato.

## Licença

Privado — sem licença de uso público até definir modelo comercial.
