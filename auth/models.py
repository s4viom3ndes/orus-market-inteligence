from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime)

    ml_accounts = relationship("MLAccount", back_populates="user", cascade="all, delete-orphan")


class MLAccount(Base):
    __tablename__ = "ml_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ml_user_id = Column(Integer, nullable=False)
    ml_nickname = Column(String)
    ml_email = Column(String)
    site_id = Column(String, nullable=False, default="MLB")
    is_active = Column(Boolean, nullable=False, default=True)
    linked_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "ml_user_id"),)

    user = relationship("User", back_populates="ml_accounts")
    tokens = relationship("MLTokenSet", back_populates="ml_account", uselist=False, cascade="all, delete-orphan")
    skus = relationship("ClientSku", back_populates="ml_account", cascade="all, delete-orphan")


class MLTokenSet(Base):
    __tablename__ = "ml_token_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ml_account_id = Column(Integer, ForeignKey("ml_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String)
    token_type = Column(String, nullable=False, default="Bearer")
    scope = Column(String)
    obtained_at = Column(Integer, nullable=False)
    expires_at = Column(Integer, nullable=False)

    ml_account = relationship("MLAccount", back_populates="tokens")


class ClientSku(Base):
    __tablename__ = "client_skus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ml_account_id = Column(Integer, ForeignKey("ml_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String, nullable=False)
    catalog_product_id = Column(String, nullable=False)
    category_id = Column(String)
    product_hint = Column(String)
    current_price = Column(Float, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float)
    target_position = Column(Integer, nullable=False, default=0)
    strategy = Column(String, nullable=False, default="beat_winner")
    beat_delta = Column(Float, nullable=False, default=0.01)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("ml_account_id", "sku"),)

    ml_account = relationship("MLAccount", back_populates="skus")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)
