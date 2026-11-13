from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import conferir_senha, criar_hash_senha, criar_token, ler_token
from app.banco import (
    SessionLocal,
    Transferencia,
    Usuario,
    criar_tabelas,
    esperar_banco,
)

JANELA_DE_DUPLICIDADE = timedelta(seconds=60)


class ApiError(Exception):
    """Rejeicao de negocio: vira {"error": "CODIGO"} na resposta."""

    def __init__(self, status: int, codigo: str):
        self.status = status
        self.codigo = codigo
        super().__init__(codigo)


@asynccontextmanager
async def lifespan(aplicacao: FastAPI):
    esperar_banco()
    criar_tabelas()
    yield


app = FastAPI(title="API de Transferências", lifespan=lifespan)


@app.exception_handler(ApiError)
async def tratar_api_error(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content={"error": exc.codigo})


@app.exception_handler(RequestValidationError)
async def tratar_corpo_errado(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "REQUISICAO_INVALIDA"})


@app.exception_handler(Exception)
async def tratar_erro_inesperado(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "ERRO_INTERNO"})


bearer = HTTPBearer(auto_error=False)


def usuario_logado(
    credenciais: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> str:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise ApiError(401, "NAO_AUTENTICADO")
    username = ler_token(credenciais.credentials)
    if username is None:
        raise ApiError(401, "NAO_AUTENTICADO")
    return username


class Credenciais(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None


class TransferenciaIn(BaseModel):
    destino: Any = None
    valor: Any = None


@app.post("/auth/registrar", status_code=201)
def registrar(dados: Credenciais):
    if not dados.username or not dados.password:
        raise ApiError(422, "USUARIO_INVALIDO")

    db = SessionLocal()
    try:
        existente = db.scalar(select(Usuario).where(Usuario.username == dados.username))
        if existente is not None:
            raise ApiError(409, "USUARIO_EXISTENTE")

        usuario = Usuario(
            username=dados.username,
            password_hash=criar_hash_senha(dados.password),
            saldo=1000,
        )
        db.add(usuario)
        db.commit()
        return {"id": usuario.id, "username": usuario.username}
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "USUARIO_EXISTENTE")
    finally:
        db.close()


@app.post("/auth/login")
def login(dados: Credenciais):
    db = SessionLocal()
    try:
        usuario = None
        if dados.username and dados.password:
            usuario = db.scalar(select(Usuario).where(Usuario.username == dados.username))
        if usuario is None or not conferir_senha(dados.password, usuario.password_hash):
            raise ApiError(401, "CREDENCIAIS_INVALIDAS")
        return {"token": criar_token(usuario.username)}
    finally:
        db.close()


@app.get("/conta")
def minha_conta(username: str = Depends(usuario_logado)):
    db = SessionLocal()
    try:
        usuario = db.scalar(select(Usuario).where(Usuario.username == username))
        if usuario is None:
            raise ApiError(401, "NAO_AUTENTICADO")
        return {"username": usuario.username, "saldo": usuario.saldo}
    finally:
        db.close()


@app.post("/transferencias", status_code=201)
def transferir(dados: TransferenciaIn, username: str = Depends(usuario_logado)):
    # validacoes na ordem exata do contrato
    if type(dados.valor) is not int or dados.valor <= 0:
        raise ApiError(422, "VALOR_INVALIDO")
    if dados.destino == username:
        raise ApiError(422, "MESMA_CONTA")
    if not isinstance(dados.destino, str):
        raise ApiError(404, "DESTINO_INEXISTENTE")

    valor = dados.valor
    destino_nome = dados.destino

    db = SessionLocal()
    try:
        origem = db.scalar(select(Usuario).where(Usuario.username == username))
        if origem is None:
            raise ApiError(401, "NAO_AUTENTICADO")

        destino = db.scalar(select(Usuario).where(Usuario.username == destino_nome))
        if destino is None:
            raise ApiError(404, "DESTINO_INEXISTENTE")

        # 1) trava as duas contas para nenhuma outra transferencia mexer nelas
        travadas = db.scalars(
            select(Usuario)
            .where(Usuario.id.in_([origem.id, destino.id]))
            .order_by(Usuario.id)
            .with_for_update()
        ).all()
        pelo_id = {conta.id: conta for conta in travadas}
        origem = pelo_id[origem.id]
        destino = pelo_id[destino.id]

        # 2) com a trava na mao, ve se esta mesma transferencia (origem,
        # destino, valor) ja aconteceu nos ultimos 60 segundos
        limite = datetime.now(timezone.utc) - JANELA_DE_DUPLICIDADE
        repetida = db.scalar(
            select(Transferencia.id)
            .where(
                Transferencia.origem == username,
                Transferencia.destino == destino_nome,
                Transferencia.valor == valor,
                Transferencia.criado_em > limite,
            )
            .limit(1)
        )
        if repetida is not None:
            raise ApiError(409, "TRANSFERENCIA_DUPLICADA")

        if origem.saldo < valor:
            raise ApiError(409, "SALDO_INSUFICIENTE")

        # 3) debito + credito + registro numa unica transacao do banco:
        # tudo fica salvo, ou nada fica (queda no meio nao divide nada)
        origem.saldo -= valor
        destino.saldo += valor
        transferencia = Transferencia(origem=username, destino=destino_nome, valor=valor)
        db.add(transferencia)
        db.commit()

        return {
            "id": transferencia.id,
            "origem": username,
            "destino": destino_nome,
            "valor": valor,
            "saldo": origem.saldo,
        }
    finally:
        db.close()


@app.get("/auditoria")
def auditoria():
    db = SessionLocal()
    try:
        usuarios, soma_saldos = db.execute(
            select(func.count(), func.coalesce(func.sum(Usuario.saldo), 0))
        ).one()
        transferencias = (
            db.scalar(select(func.count()).select_from(Transferencia)) or 0
        )
        return {
            "usuarios": int(usuarios),
            "somaSaldos": int(soma_saldos),
            "transferencias": int(transferencias),
        }
    finally:
        db.close()
