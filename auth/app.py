"""Runner standalone do auth. Nao esta wired no dashboard cliente ainda.

Uso (opt-in):
    cd auth && streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Orus - Auth", layout="centered")
st.title("Orus - Autenticação (dev)")

st.warning(
    "⚠️ **Scaffold em desenvolvimento.** Auth ainda nao integrado no dashboard cliente. "
    "Use a sidebar pra navegar entre paginas de teste."
)

st.markdown("""
### Pra usar:
1. Rode `python -m auth.db --init` uma vez pra criar o SQLite.
2. Configure `.env` na raiz com `ML_APP_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI_USER` (opcional, usa ML_REDIRECT_URI se ausente).
3. Va em **Signup** pra criar sua primeira conta.
4. **Login** pra pegar `session_id`.
5. **Link ML** pra vincular sua conta ML e receber `code` do callback.
6. **Meus SKUs** pra cadastrar o portfolio monitorado.

### Notas de scaffold:
- SQLite em `auth/auth.db` (gitignored).
- Session cookie ainda nao implementado — em prod usa `streamlit-cookies-manager`.
- No dev, `user_id` e passado via input manual.
- Nada disso afeta o dashboard cliente atual. Zero risco de quebra.
""")
