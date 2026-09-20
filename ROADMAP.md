# Orus — Roadmap

Estado: pipeline rodando diariamente sem intervenção, dashboards no ar, modelo de preço estimado sobre dados próprios.
Última revisão: 2026-09-19.

## 🎯 Curto prazo (fecha demo pra cliente)

- [x] Deploy admin em Streamlit Cloud
- [x] Deploy dashboard cliente em Streamlit Cloud
- [x] Fix visits enrichment (1-per-call, só winners)
- [x] Fix mock SKU coverage (live fallback quando fora do snapshot)
- [x] Fix path do `mock_client.yaml` no dashboard (usa `state/mock_client.yaml` no R2)
- [x] Configurar SMTP e validar email real (com `NOTIFY_EMAILS` pra destinatários extras)
- [x] Tirar dados de cliente do repositório público (config vive em `state/clients/` no R2)
- [x] Carteira real do cliente + simulação pra reunião
- [x] **Incluir as 7 categorias da carteira na `WATCHLIST_CATEGORIES`** — 4 delas não estavam nem na watchlist nem entre as folhas descobertas, então nunca eram coletadas. Sem isso a análise da carteira não roda sozinha.
- [ ] **Repensar o pitch a partir do achado da seção 8 do notebook** (ver abaixo) — o deck atual vende recuperação de buy box, que não é o problema desta carteira.
- [ ] Refinamento visual do dashboard (handoff em `_design/`, parcialmente aplicado)
- [ ] Slides/PDF de pitch com os insights atuais

### ⚠️ Achado que muda o posicionamento (2026-09-19)

A carteira do cliente é **100% `USER_PRODUCT`** — anúncio próprio, sem disputa de buy box. Cruzando cada SKU com seu catálogo comparável: a chance de buy box ao preço de hoje tem mediana de **1,3%**, e chegar a 50% exigiria cortar o preço pela **metade**. Ao mesmo tempo, **86% da receita acumulada está em SKUs que cobram acima da mediana do catálogo comparável**.

Ou seja: o cliente ganha dinheiro *fugindo* do catálogo, não disputando-o. Repricer de buy box não é o produto certo pra ele — o valor está em **vigiar quando um concorrente de catálogo chega perto o suficiente pra ameaçar o anúncio próprio**. Detalhe e cautelas na seção 8.1 do notebook.

## 🚀 Médio prazo (transforma em produto vendável)

### Features de produto

- [x] **Repricer v1**: regras determinísticas (`beat_winner`/`match_winner`/`hold`/`defensive`/`full_premium`) + guard rails (`min_price`, `max_price`, `max_change_pct_per_run`). Simulador com slider no dashboard. Suggest-only, cron 03:45 UTC.
- [x] **Modelo de buy box estimado**: logit condicional com efeito fixo por produto-dia. Em `services/price_model.py`. ⚠️ **Os coeficientes em produção são de 2026-09-12 e estão desatualizados** — ver a pendência de reestimação abaixo.
- [x] **Otimizador de preço**: maximiza `P(buy box) × margem` em vez de perseguir a buy box. Modo estático (argmax de hoje) e sequencial (política de MDP sobre titularidade + preço vigente, γ=0.97). Email diário com recomendações, cron 04:00 UTC.
- [x] **Histórico de preços por SKU**: `buy_box_history/` + `dashboard/pages/5_Historico.py` — série de winner, gap e posição.
- [x] **Market insights**: OLS pooled dos fatores de buy box, com avisos automáticos de amostra insuficiente e R² baixo. Ferramenta interna pro pitch.
- [x] **Enrichment de reputação por vendedor** (`seller_power_status`, `seller_ratings_negative`) — o que reviews de produto não conseguiam explicar.
- [x] **Coleta de `USER_PRODUCT`**: anúncios próprios fora do catálogo passaram a entrar na coleta (759 entradas na varredura de 12/09). Filtrados no otimizador, onde não há buy box pra disputar.
- [ ] **Repricer v2**: modo `approval` (cliente clica pra aplicar) — requer OAuth real do cliente.
- [ ] **Repricer v3**: `auto_apply` — chama `PUT /items/{id}` sem intervenção.
- [ ] **Atualizar `price_model.COEFICIENTES`** com a reestimação de 2026-09-19 (seção 6 do notebook, 214.366 ofertas em 16.362 grupos produto-dia sobre 27 dias). O que muda:

  | termo | produção | reestimado |
  |---|---|---|
  | preço | −5,1939 | −6,1053 |
  | titular | 3,4975 | 3,3338 |
  | full | 0,7066 | 0,6553 |
  | oficial | 0,5376 | 0,5439 |
  | premium | −0,3522 | −0,7446 |

  O preço-sombra da titularidade cai de **+96% para +72,6%** — não porque o coeficiente mudou, mas porque a elasticidade-preço ficou mais forte e o denominador cresceu. Trocar os betas **muda recomendação de preço**, e a cifra antiga está citada nos docstrings de `price_model`/`price_optimizer`, no e-mail diário do `optimize_prices` e no material comercial. É uma passada coordenada, não uma edição de constante.
- [x] **Versionar a estimação**: até 2026-09-19 os betas de produção vinham de uma estimação que não existia em nenhum arquivo do repo — só o resultado hardcoded. A seção 6 do notebook reconstrói e documenta.
- [ ] **Automatizar a reestimação**: decidir cadência e como detectar drift. Hoje ainda é reexecutar o notebook e copiar à mão.
- [ ] **Detecção de anomalias**: snapshot vs anterior. "Novo concorrente entrou na cat X 30% abaixo", "winner mudou 3× na semana".
- [ ] **Alertas configuráveis** por cliente: perda de buy box, queda de preço da categoria, entrada de concorrente estratégico.
- [ ] **Report semanal por email**: digest no domingo.

### Infra pra vender

- [~] **Multi-tenant + Auth** — scaffold em `auth/` (SQLite + SQLAlchemy + passlib + itsdangerous; models User, MLAccount, MLTokenSet, ClientSku, Session; telas de signup, login, link_ml, my_skus). Standalone, sem impacto no dashboard. **Falta**: (a) `streamlit-cookies-manager` pra sessão real, (b) migrar `tokens.json` + config de cliente pro DB, (c) `verify_session` no topo do dashboard, (d) parquets particionados por `user_id`, (e) Postgres em produção.
- [x] **Config de cliente fora do git**: `services/client_config.py` lê de `state/clients/{nome}.yaml` no R2, com fallback local pra dev. O repo é público, então carteira e preços não podem ser versionados.
- [x] **Testes automatizados**: 172 testes em `etl/tests/`, cobrindo price_model (26), monitor_buy_box (20), categories (15), price_optimizer (14), repricer (12), optimize_prices (12), search (11), client_history (10), market_insights (9), highlights_tracker (8), e o resto. Workflow `tests.yml` em cada push/PR. Tudo sintético — nenhum teste chama API ou R2.
- [x] **Custo de infraestrutura medido** (`etl/scripts/custo_infra.py`): números de 12/09, não estimativas. O que domina é o Actions faturar por job arredondando pro minuto — lote de clientes num run só é o que faz a conta fechar.
- [ ] **Autenticação nos dashboards**: hoje as duas URLs do Streamlit Cloud são públicas pra quem descobrir. Bloqueio técnico antes de cliente pagante, principalmente no `admin/`.

### Observability / operações

- [x] **Data health**: métricas por dataset (linhas, nulos, unicidade, distribuição), classificação green/yellow/red e job diário de verificação cruzada com alerta por email.
- [x] **Auditoria de notificação**: toda tentativa de envio fica em `notification_log/` no R2, visível no admin.
- [x] **Rastreio de categorias sem ranking**: `highlights_tracker` registra quem some do `/highlights` e quem volta, sem podar nada — 43 de 214 dão 404 por run, mas com rotatividade medida.
- [ ] Slack/Discord como alternativa ao email pra alerta de falha
- [ ] Monitoramento de custo: alertar antes de estourar free tier do Actions ou do R2
- [ ] Retenção de snapshots: deleta > 90 dias, agrega semanalmente, ou nunca deleta?

## 🌐 Longo prazo (go-to-market)

- [ ] Landing page em `orus.observer`
- [ ] Modelo de pricing (setup + mensalidade decidido; componente de performance em aberto — ver `docs/negocio/`)
- [ ] Billing via Stripe
- [ ] Cadastro self-serve
- [ ] Case study com métricas reais do primeiro cliente
- [ ] Blog com insights por categoria (SEO)
- [ ] Teste de carga: 100 clientes rodando juntos esbarram no rate limit do ML?
- [ ] Backup / DR: e se o R2 sumir?

## 🐛 Pendências técnicas

- [ ] Categorias em `max_depth=2` pegam 209 folhas. Avaliar depth=3 (pode explodir).
- [ ] `collect_trends` por categoria retorna 404 pras roots — descobrir quais IDs o ML expõe.
- [ ] Cleanup do path do `tokens.json` (grava local + R2; o R2 é a fonte de verdade na prática).
- [ ] Schema versionado dos parquets, pra evoluir sem quebrar leitor antigo. Já mordeu uma vez: as colunas `seller_*` só existem em snapshot posterior a 27/08, e todo uso delas precisa ser condicional.
- [ ] Timezone: partição usa America/Sao_Paulo, cron é UTC, `captured_at` é epoch. Não dá bug hoje, mas confunde quem lê "o snapshot de hoje".
- [ ] Sem retry/backoff nas chamadas ao ML — falha transitória vira dado ausente naquele run.
- [ ] Modelos Pydantic em `etl/models/` não são usados por nenhum job (o pipeline roda sobre dict e DataFrame). Decidir: contrato futuro documentado ou remover.
- [ ] Handler do webhook só loga a notificação, não reage.
- [ ] `TARIFAS` em `price_model.py` são defaults plausíveis, não auditados no contrato do cliente. Confirmar antes de qualquer material comercial citar esses números.

## Frequência de coleta — decisão adiada

Buy box no ML muda várias vezes por dia. Cadência atual (1×/dia) é insuficiente pra cliente pagante — perda de buy box só aparece 24h depois.

**Solução desenhada**: split hot path (monitor horário, ~30s/run via `_fetch_offers_live`) + cold path (`collect_market` completo 1×/dia, ~33 min).

**Custo**: 720 min/mês (hot) + 1200 (cold) = 1920, cabe no free tier de 2000. `scripts/custo_infra.py` recalcula pra N clientes.

**Status**: **adiado de propósito** — validar o cliente com cadência diária antes de gastar o tempo. Implementar quando ele confirmar valor e antes de fechar contrato pago.

## Contexto de decisões

- **Cron 1×/dia** (não horário): cabe no free tier do GitHub Actions.
- **Streamlit Cloud** (não Fly.io/Railway): grátis, deploy do GitHub, zero infra.
- **R2** (não S3): conta AWS suspensa por bug de billing, e o R2 é grátis nesta escala.
- **Highlights + product_items** (não `/sites/search`): o último foi restringido em 2024.
- **Buy box mockado**: a API do ML não deixa acessar listings de outro seller (403). A solução real exige o cliente autorizar OAuth da conta dele.
- **OLS no `market_insights`, e não logística**: o alvo é binário, então logística seria mais correta — mas o coeficiente OLS sai direto em pontos percentuais e vira frase pra humano sem converter odds ratio. O público desse módulo é sempre humano.
- **Um modelo pooled com dummy de categoria**, não um modelo por categoria: cada categoria do cliente tem ~10-20 vitórias de buy box por dia, pouco pra estimar 5+ coeficientes isoladamente.
- **Volume de vendas fora do otimizador**: ele multiplica os dois lados do argmax e some. Conveniente, porque volume por SKU é justamente o dado que não temos.
