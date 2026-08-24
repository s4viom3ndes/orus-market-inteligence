# Orus — Roadmap

Estado: MVP fechado, dashboards no ar, dados fluindo diariamente.
Data: 2026-08-23.

## 🎯 Curto prazo (fecha demo pra cliente)

- [x] Deploy admin em Streamlit Cloud
- [ ] Deploy dashboard cliente em Streamlit Cloud
- [ ] Refinamento visual do dashboard (via Claude Design)
- [x] Fix visits enrichment (1-per-call, só winners)
- [x] Fix mock SKU coverage (live fallback quando fora do snapshot)
- [ ] Fix path do `mock_client.yaml` no dashboard (usar R2)
- [ ] Configurar SMTP (Gmail App Password) e validar email real
- [ ] Slides/PDF de pitch com os insights atuais (75% winners em Full, gap de preço por SKU do cliente, etc)

## 🚀 Médio prazo (transforma em produto vendável)

### Features de produto
- [x] **Motor de repricer v1**: regras determinísticas (beat_winner/match/hold/defensive/full_premium) + guard rails (min_price, max_price, delta_max_por_run). Simulador interativo com slider no dashboard. Suggest_only. Cron 03:45 UTC.
- [ ] **Motor de repricer v2**: modo `approval` (cliente clica pra aplicar) — requer OAuth real do cliente.
- [ ] **Motor de repricer v3**: `auto_apply` — chama PUT /items/{id} sem intervenção.
- [ ] **Histórico de preços por SKU**: dashboard mostra série temporal (últimos 30/90 dias) — variação do winner, entrada/saída de vendedores.
- [ ] **Detecção de anomalias**: comparação snapshot vs anterior. Ex: "novo concorrente entrou na cat X com preço 30% abaixo", "winner mudou 3 vezes na semana".
- [ ] **Alertas configuráveis**: por cliente, escolher regras (perda de buy box, queda de preço da categoria, novo concorrente estratégico).
- [ ] **Report semanal por email**: digest da semana enviado no domingo.

### Infra pra vender
- [~] **Multi-tenant + Auth (scaffold pronto em `auth/`)**: SQLite + SQLAlchemy + passlib + itsdangerous. Models: User, MLAccount, MLTokenSet, ClientSku, Session. Fluxos: signup, login, link_ml (OAuth), my_skus. Standalone `auth/app.py`, sem impacto no dashboard atual. **Falta ativar**: (a) `streamlit-cookies-manager` pra sessão real, (b) migrar `tokens.json` + `mock_client.yaml` pro DB, (c) `verify_session` no topo do dashboard cliente, (d) parquets no R2 particionados por `user_id`, (e) Postgres (Supabase/Neon) em prod.
- [ ] **Testes automatizados**: mínimo 1 teste por serviço crítico. `pytest` em `etl/tests/`. Rodar em GH Actions em cada PR.

### Observability / operações
- [ ] Slack/Discord webhook alternativo ao email pra alertas de failure
- [ ] Monitoramento de custos: alerta antes de estourar free tier GH Actions ou R2
- [ ] Retenção de snapshots: definir se deleta > 90 dias, agrega semanalmente, ou nunca deleta

## 🌐 Longo prazo (go-to-market)

- [ ] Landing page em `orus.observer` (raiz do domínio)
- [ ] Pricing model (freemium? por SKU? por chamada?)
- [ ] Billing via Stripe
- [ ] Cadastro self-serve pra novos clientes
- [ ] Case study público com métricas reais do primeiro cliente
- [ ] Blog com insights de mercado por categoria (SEO)
- [ ] Testes de carga: e se 100 clientes rodarem juntos? Rate limit ML?
- [ ] Backup / DR: e se R2 sumir?

## 🐛 Pendências técnicas

- [ ] Categorias `max_depth=2` pegam 209 folhas. Avaliar depth=3 (pode explodir).
- [ ] `collect_trends` por categoria retorna 404 pras roots — descobrir quais IDs específicos o ML expõe.
- [ ] Cleanup do path do `tokens.json` (hoje escreve local + R2, R2 é source of truth).
- [ ] Definir schema versionado dos parquets — pra evolução sem quebrar leitores antigos.
- [ ] Timezone consistency: tudo em BRT ou tudo UTC? Hoje tá misturado.

## Contexto de decisões

- **Cron 1x/dia** (não a cada hora): cabe no free tier GH Actions (~1280 min/mês de 2000).
- **Streamlit Cloud** (não Fly.io/Railway): grátis, deploy do GitHub, zero infra.
- **R2** (não S3): AWS suspensa por bug de billing, R2 é grátis pra escala atual.
- **Highlights + product_items** (não `/sites/search`): último foi restringido em 2024.
- **Buy box mockado**: API do ML não deixa acessar listings de outro seller (403). Solução real requer cliente autorizar sua conta OAuth.
