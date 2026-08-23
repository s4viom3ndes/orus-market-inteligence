# Orus

Ferramenta de market intelligence + repricer para sellers do Mercado Livre.

## Objetivo do MVP

Demo pra apresentar como produto a cliente potencial. Duas features principais:

1. **"Grande select" de mercado** → coleta bestsellers e todas as ofertas concorrentes, salva em Parquet para inferencia futura.
2. **Monitor de Buy Box + repricer** → detecta perda/ganho de buy box em SKUs proprios, sugere ajuste de preco respeitando margem, notifica dono por email.

## Stack

- Python 3.14 (tambem funciona no conda base miniconda)
- FastAPI + uvicorn (webhook + OAuth callback)
- httpx (cliente HTTP)
- polars + pyarrow (Parquet)
- pydantic (models)
- Cloudflare Tunnel (`cloudflared`) para expor o webhook local em https publico

## Estrutura

```
src/
  config.py         # carrega .env, constantes
  webhook.py        # FastAPI: /health, /webhook/ml/{secret}, /oauth/start, /oauth/callback
services/
  ml_client.py      # MLClient com auto-refresh de token baseado em expires_at
  search.py         # iter_highlights, iter_product_items, normalize_offer
storage/
  parquet_writer.py # write_snapshot: local ou R2 conforme USE_REMOTE_STORAGE
  r2.py             # cliente boto3 apontando pro Cloudflare R2
services/
  token_store.py    # load/save tokens.json (local + R2 quando habilitado)
jobs/
  collect_market.py # CLI: python -m jobs.collect_market [--categories MLB1055 ...]
  scheduler.py      # long-running: python -m jobs.scheduler --every-minutes 60 --run-now
models/
  user.py           # User do sistema Orus
  account.py        # MLAccount + MLTokens
  listing.py        # MyListing, OfferSnapshot, BuyBoxEvent
data/               # parquets (gitignored)
tokens.json         # tokens OAuth atuais (gitignored) - MVP single-tenant
```

## Descobertas importantes da API do ML

- `/sites/MLB/search` foi **restringido** (403). Nao usar pra buscar mercado geral.
- `/products/search` retorna produtos "filho" sem PDP e sem `/items` (404). Nao serve pra buy box.
- **Caminho que funciona pra market intelligence**: `/highlights/{site}/category/{cat_id}` → lista bestsellers, dai `/products/{id}/items` retorna todas as ofertas concorrentes.
- `buy_box_winner` no `/products/{id}` retorna `null` na maioria dos casos. Ranking real vem da ordem dos itens em `/products/{id}/items` (posicao 0 = vencedor).
- Autorizacao offline (`refresh_token`) precisa ser habilitada explicitamente no painel do app no ML. Sem isso, access_token expira em 6h e quebra tudo.
- ML retorna 403 `PolicyAgent` quando o IP/app/token esta em estado ruim, mesmo em endpoints publicos. Nesse caso: novo app + esperar.

## Fluxo de token

`tokens.json` guarda `access_token`, `refresh_token`, `expires_at`. `services/ml_client.get_access_token()` verifica expiracao (com margem de 5 min) e renova via `/oauth/token` grant `refresh_token` quando necessario. **Refresh_tokens do ML sao single-use** — o refresh retorna um novo par que substitui o antigo.

## Rodando localmente

Terminal 1 (uvicorn):
```
uvicorn src.webhook:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 (tunnel publico, se for testar webhook do ML):
```
cloudflared tunnel --url http://localhost:8000
```

Coletar mercado (uma vez, usa WATCHLIST_CATEGORIES do config se omitir --categories):
```
python -m jobs.collect_market
```

Rodar coleta recorrente (loop de longa duracao):
```
python -m jobs.scheduler --every-minutes 60 --run-now
```

## Como descobrir category_id de um produto do cliente

Nao ha endpoint publico que liste categorias de outro seller (todos 403).
Fluxo manual:
1. Cliente manda URL do produto no ML.
2. Rodar: `GET /sites/MLB/domain_discovery/search?q=<nome do produto>` -> retorna `category_id` predito.
3. Adicionar em `WATCHLIST_CATEGORIES` em src/config.py.
4. Scheduler ja pega na proxima rodada.

## Storage remoto (Cloudflare R2)

Se `.env` tem `R2_ENDPOINT` + `R2_ACCESS_KEY_ID` + `R2_SECRET_ACCESS_KEY`, o sistema:
- Escreve parquets em `r2://{bucket}/{dataset}/date=YYYY-MM-DD/snapshot-*.parquet`
- Sincroniza `tokens.json` em `r2://{bucket}/state/tokens.json` (necessario pra GH Actions que nao tem storage persistente entre runs)

`services/token_store` sempre grava local tambem — o R2 e "espelho" pra runs remotos.

## GitHub Actions

`.github/workflows/collect_market.yml` roda `python -m jobs.collect_market` a cada hora (cron `0 * * * *`).

Secrets necessarios no GitHub (Settings > Secrets and variables > Actions):
- `ML_APP_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`, `ML_WEBHOOK_SECRET`
- `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`

Usa `concurrency: collect-market` com `cancel-in-progress: false` porque `refresh_token` do ML e single-use — nao pode ter 2 runs simultaneos.

## Nao fazer

- Nao usar `/sites/MLB/search` — endpoint restringido.
- Nao commitar `.env` nem `tokens.json`.
- Nao mascarar IP pra contornar `PolicyAgent` — cria risco de banimento do app.
- Nao chamar `/products/{id}/items` para produtos com `parent_id` (sao variacoes sem `/items`). So chamar em produtos que aparecem em `/highlights`.

## Proximos passos previstos

1. Buy Box monitor dos anuncios proprios (services/buy_box_monitor.py, jobs/monitor_loop.py).
2. Motor de repricer baseado em regras (services/repricer.py).
3. Notificacao por email (services/email_notifier.py) — canal SMTP a definir.
4. Migrar tokens.json → SQLite/DuckDB quando for multi-tenant.
