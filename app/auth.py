import hashlib
import hmac
import os
import secrets
import time

import jwt

CHAVE = os.getenv("JWT_SECRET", "segredo-padrao-apenas-para-desenvolvimento")
ALGORITMO = "HS256"
VALIDADE_DO_TOKEN = 24 * 60 * 60  # segundos


def criar_hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)
    digesto = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 100_000)
    return salt.hex() + ":" + digesto.hex()


def conferir_senha(senha, guardado: str) -> bool:
    if not isinstance(senha, str) or ":" not in guardado:
        return False
    salt_hex, digesto_hex = guardado.split(":", 1)
    digesto = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), bytes.fromhex(salt_hex), 100_000
    )
    return hmac.compare_digest(digesto.hex(), digesto_hex)


def criar_token(username: str) -> str:
    agora = int(time.time())
    payload = {"sub": username, "iat": agora, "exp": agora + VALIDADE_DO_TOKEN}
    return jwt.encode(payload, CHAVE, algorithm=ALGORITMO)


def ler_token(token: str):
    try:
        payload = jwt.decode(token, CHAVE, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None
