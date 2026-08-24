import streamlit as st
from auth.db import get_session
from auth import auth_service, ml_link

st.set_page_config(page_title="Orus - Conectar ML", layout="centered")
st.title("Conectar conta Mercado Livre")

st.caption("STUB: em prod, verify_session le cookie. Aqui, pega user_id manual pra teste.")
user_id_str = st.text_input("user_id (dev only — em prod vem do cookie)", value="1")

try:
    user_id = int(user_id_str)
except ValueError:
    st.stop()

try:
    url = ml_link.authorize_url(user_id)
    st.markdown(f"### [Clique aqui pra autorizar sua conta ML]({url})")
    st.caption("Voce sera redirecionado pro ML. Ao aceitar, volta pro callback com um `code`.")

    st.divider()
    st.subheader("Callback (dev)")
    code = st.text_input("Cole o `code` que veio na URL apos autorizar")
    if st.button("Trocar code por token", type="primary") and code:
        try:
            with get_session() as db:
                account = ml_link.exchange_code(db, user_id, code.strip())
            st.success(f"Vinculado. ml_account_id={account.id} ml_user_id={account.ml_user_id} nick={account.ml_nickname}")
        except ml_link.MLLinkError as e:
            st.error(str(e))

except ml_link.MLLinkError as e:
    st.error(f"config ML incompleta: {e}. Configure ML_APP_ID/ML_CLIENT_SECRET/ML_REDIRECT_URI_USER no .env")
