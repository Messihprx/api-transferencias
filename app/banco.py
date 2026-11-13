import os
import time
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

URL_DO_BANCO = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/transferencias",
)

engine = create_engine(
    URL_DO_BANCO,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    saldo: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)


class Transferencia(Base):
    __tablename__ = "transferencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origem: Mapped[str] = mapped_column(String(64), nullable=False)
    destino: Mapped[str] = mapped_column(String(64), nullable=False)
    valor: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


# indice para achar rapido as transferencias repetidas da janela de 60s
Index(
    "ix_transferencias_duplicidade",
    Transferencia.origem,
    Transferencia.destino,
    Transferencia.valor,
    Transferencia.criado_em,
)


def esperar_banco():
    """Espera o postgres aceitar conexoes (a subida do container)."""
    while True:
        try:
            with engine.connect() as conexao:
                conexao.execute(text("SELECT 1"))
            return
        except Exception:
            time.sleep(1)


def criar_tabelas():
    Base.metadata.create_all(engine)
