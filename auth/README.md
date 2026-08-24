# Orus Auth — Scaffold

Estrutura de autenticação e onboarding multi-tenant. **Não ativa ainda** — só estrutura.

## O que resolve (quando ativado)

Hoje o Orus é single-user (savio). Pra vender pra clientes reais:

- Cada cliente cria conta (email + senha ou Google OAuth)
- Cada cliente autoriza sua própria conta ML (fluxo OAuth próprio, cada um com refresh_token dele)
- Cada cliente cadastra seus SKUs (não mais `mock_client.yaml` hardcoded)
- Cada cliente vê SÓ os dados dele no dashboard
- Admin (savio) vê todo mundo

## Arquitetura proposta

```
┌─────────────────────────────────────────────────────────┐
│                    dashboard/ (Streamlit)                │
│                                                          │
│  ┌─────────────────┐          ┌───────────────────────┐ │
│  │  Login/Signup   │──sessão──│  Overview / Buy Box   │ │
│  │  (auth/pages/)  │           │  (dashboard/pages/)   │ │
│  └────────┬────────┘          └───────┬───────────────┘ │
│           │                            │                 │
└───────────┼────────────────────────────┼─────────────────┘
            ▼                            ▼
   ┌────────────────┐          ┌──────────────────┐
   │  auth_service  │          │  R2 (parquets    │
   │  (SQLite/PG)   │          │   agora por user)│
   └───────┬────────┘          └──────────────────┘
           │
           ▼
   ┌────────────────────────────────┐
   │ users                          │
   │   id, email, pwd_hash, name    │
   │ ml_accounts                    │
   │   id, user_id, ml_user_id,     │
   │   access_token, refresh_token  │
   │ client_skus                    │
   │   id, ml_account_id, sku,      │
   │   catalog_pid, min/max_price   │
   └────────────────────────────────┘
```

## Stack escolhido (scaffold)

- **SQLite** pra dev local (arquivo único, zero infra)
- **SQLAlchemy** ORM (facilita migração pra Postgres depois)
- **Passlib** (bcrypt) pra hash de senha
- **itsdangerous** pra sessão via cookie assinado (compatível com Streamlit)
- **streamlit** pras telas (login, signup, link_ml)

Migração futura pra produção:
- SQLite → **Supabase Postgres** (free tier: 500MB, 50k MAU)
- Ou → Neon / Railway Postgres
- ORM não muda, só a connection string

## Por que não Supabase / Firebase / Auth0 direto

- Adicionar dependência gerenciada em código que ainda não roda em produção = overhead precoce
- SQLite deixa iterar 100% offline
- Quando for ativar, `sqlalchemy` troca driver e pronto — não reescreve

## Estrutura

```
auth/
├── README.md               (este arquivo)
├── requirements.txt        deps planejadas
├── schema.sql              schema DDL (referência humana)
├── models.py               SQLAlchemy: User, MLAccount, MLTokenSet, ClientSku
├── db.py                   session/engine SQLite
├── auth_service.py         signup, login, verify_session, change_password
├── ml_link.py              OAuth ML por usuário (adaptado de etl/src/webhook.py)
├── session.py              cookie assinado com itsdangerous
├── pages/                  Streamlit pages (não wired ainda)
│   ├── login.py
│   ├── signup.py
│   ├── link_ml.py          botão "conectar minha conta ML"
│   └── my_skus.py          form pra cadastrar SKUs
└── app.py                  runner standalone opt-in
```

## Como ativar (roadmap de integração)

**Fase 1 — Standalone (validar fluxo)**
1. `pip install -r auth/requirements.txt`
2. `python -m auth.db --init` cria SQLite
3. `streamlit run auth/app.py` sobe login/signup/link_ml em URL separada
4. Testa fluxo end-to-end com 1-2 contas fake

**Fase 2 — Integrar no dashboard**
5. `dashboard/app.py` chama `auth_service.verify_session()` no topo
6. Sem sessão → redireciona pra `auth/pages/login.py`
7. Com sessão → filtra queries por `user_id` (parquets no R2 viram particionados por user)

**Fase 3 — Migrar dados existentes**
8. Criar "user zero" (savio) na tabela
9. Migrar `mock_client.yaml` → `client_skus` desse user
10. Migrar `tokens.json` → `ml_token_sets` desse user
11. Deletar arquivos legados

**Fase 4 — Produção**
12. Trocar SQLite por Postgres (Supabase/Neon)
13. Deploy separado do dashboard, mesmo domínio (`orus.observer`)
14. Emails transacionais (verificação, reset senha) via SMTP já configurado

## Não fazer

- Não integrar isso com o dashboard atual sem antes ter DB migrado
- Não commitar `auth/auth.db` (SQLite gerado) — vai pro `.gitignore`
- Não usar bcrypt rounds > 12 em dev (fica lento; produção usa 12)
- Não reinventar OAuth ML — copiar padrão de `etl/src/webhook.py` e adaptar pra user_id
