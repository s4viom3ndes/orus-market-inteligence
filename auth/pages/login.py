import streamlit as st
from auth.db import get_session
from auth import auth_service
from auth.session import sign

st.set_page_config(page_title="Orus - Login", layout="centered")
st.title("Orus - Login")

email = st.text_input("Email")
password = st.text_input("Senha", type="password")

if st.button("Entrar", type="primary"):
    if not email or not password:
        st.error("Preencha email e senha")
    else:
        try:
            with get_session() as db:
                session_id = auth_service.login(db, email, password)
            st.success("Logado com sucesso.")
            st.info(f"session_id (dev): `{session_id}`\n\nassinado: `{sign(session_id)}`")
            st.write("Em prod, esse cookie assinado seria setado no browser via streamlit-cookies-manager.")
        except auth_service.AuthError as e:
            st.error(str(e))

st.divider()
st.caption("Ainda nao tem conta? Va em Signup na sidebar.")
