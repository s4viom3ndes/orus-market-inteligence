"""SQLite dev DB. Migrar pra Postgres em prod trocando SQLALCHEMY_URL."""
import argparse
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from auth.models import Base

DB_PATH = Path(__file__).parent / "auth.db"
SQLALCHEMY_URL = os.getenv("AUTH_DB_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(SQLALCHEMY_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db():
    Base.metadata.create_all(engine)
    print(f"schema criado em: {SQLALCHEMY_URL}")


def drop_db():
    Base.metadata.drop_all(engine)
    print("todas as tabelas dropadas")


def get_session():
    return SessionLocal()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true", help="Cria o schema (idempotente)")
    p.add_argument("--drop", action="store_true", help="DROPA todas as tabelas (DESTRUTIVO)")
    args = p.parse_args()
    if args.drop:
        drop_db()
    if args.init:
        init_db()
    if not (args.init or args.drop):
        p.print_help()
