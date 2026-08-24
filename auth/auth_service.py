"""Signup / login / session verify.

Uso:
    from auth.db import get_session
    from auth import auth_service

    with get_session() as db:
        user = auth_service.signup(db, "a@b.com", "senha123", name="Ana")
        session_id = auth_service.login(db, "a@b.com", "senha123")
        # ... salvar session_id no cookie via session.sign()
        user = auth_service.verify_session(db, session_id)
"""
from datetime import datetime
from passlib.hash import bcrypt
from sqlalchemy.orm import Session as OrmSession
from auth.models import User, Session as UserSession
from auth.session import new_session_id, new_expires_at


class AuthError(Exception):
    pass


def signup(db: OrmSession, email: str, password: str, name: str | None = None) -> User:
    email = email.strip().lower()
    if db.query(User).filter_by(email=email).first():
        raise AuthError("email ja cadastrado")
    if len(password) < 8:
        raise AuthError("senha precisa ter >= 8 chars")
    user = User(email=email, password_hash=bcrypt.hash(password), name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: OrmSession, email: str, password: str) -> str:
    """Retorna session_id opaco. Frontend deve chamar session.sign() antes de setar cookie."""
    email = email.strip().lower()
    user = db.query(User).filter_by(email=email, is_active=True).first()
    if not user or not bcrypt.verify(password, user.password_hash):
        raise AuthError("credenciais invalidas")

    user.last_login_at = datetime.utcnow()

    sess = UserSession(id=new_session_id(), user_id=user.id, expires_at=new_expires_at())
    db.add(sess)
    db.commit()
    return sess.id


def verify_session(db: OrmSession, session_id: str) -> User | None:
    if not session_id:
        return None
    sess = db.query(UserSession).filter_by(id=session_id).first()
    if not sess or sess.revoked_at or sess.expires_at < datetime.utcnow():
        return None
    return sess.user if sess.user and sess.user.is_active else db.query(User).get(sess.user_id)


def logout(db: OrmSession, session_id: str) -> None:
    sess = db.query(UserSession).filter_by(id=session_id).first()
    if sess and not sess.revoked_at:
        sess.revoked_at = datetime.utcnow()
        db.commit()


def change_password(db: OrmSession, user: User, old: str, new: str) -> None:
    if not bcrypt.verify(old, user.password_hash):
        raise AuthError("senha atual incorreta")
    if len(new) < 8:
        raise AuthError("nova senha precisa ter >= 8 chars")
    user.password_hash = bcrypt.hash(new)
    db.commit()
