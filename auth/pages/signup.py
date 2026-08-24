import streamlit as st
from auth.db import get_session
from auth import auth_service

st.set_page_config(page_title="Orus - Cadastro", layout="centered")
st.title("Orus - Criar conta")

name = st.text_input("Nome")
email = st.text_input("Email")
password = st.text_input("Senha (min 8)", type="password")
password2 = st.text_input("Confirme a senha", type="password")

if st.button("Criar conta", type="primary"):
    if not (name and email and password):
        st.error("Preencha todos os campos")
    elif password != password2:
        st.error("Senhas nao batem")
    else:
        try:
            with get_session() as db:
                user = auth_service.signup(db, email, password, name=name)
            st.success(f"Conta criada. user_id = {user.id}. Va em Login pra entrar.")
        except auth_service.AuthError as e:
            st.error(str(e))
