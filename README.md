# API de Transferências

API de uma carteira digital em que usuários transferem moedas entre si. O foco do
projeto é garantir que **cada transferência aconteça exatamente uma vez**, mesmo
com muitas requisições simultâneas, cliques repetidos e quedas do servidor.

Construída com **Python + FastAPI** e **PostgreSQL**, rodando integralmente via
**Docker Compose**.

---

## Como rodar

Pré-requisitos: Docker instalado e conexão com a internet (primeira execução
baixa as imagens).

```bash
docker compose down -v
docker compose up --build -d
```

A API fica disponível em **http://localhost:8080** e o Swagger (interface
interativa para testar) em **http://localhost:8080/docs**.

Os dados ficam em um volume do Docker: parar e religar os containers mantém as
contas e as transferências. O comando `down -v` apaga tudo (banco zerado).

---

## Endpoints

| Rota | Método | Body | Sucesso |
|:---|:---:|:---|:---|
| `/auth/registrar` | POST | `{"username": "joao", "password": "senha123"}` | `201 Created` |
| `/auth/login` | POST | `{"username": "joao", "password": "senha123"}` | `200 OK` com `{"token": "eyJ..."}` |
| `/conta` | GET | — | `200 OK` com `{"username": "joao", "saldo": 1000}` |
| `/transferencias` | POST | `{"destino": "maria", "valor": 150}` | `201 Created` com `{"id": 7, "origem": "joao", "destino": "maria", "valor": 150, "saldo": 850}` |
| `/auditoria` | GET | — | `200 OK` com `{"usuarios": 50, "somaSaldos": 50000, "transferencias": 1234}` |

- `/conta` e `/transferencias` exigem o header `Authorization: Bearer <token>`.
- `/auditoria` é pública e mostra os totais do sistema.
- Toda rejeição tem o formato `{"error": "<CODIGO>"}`.

## Códigos de erro

| Código HTTP | `error` | Quando acontece |
|:---:|:---|:---|
| 422 | `VALOR_INVALIDO` | valor ausente, não inteiro (texto `"150"`, decimal, `true`) ou ≤ 0 |
| 422 | `MESMA_CONTA` | destino igual à origem |
| 404 | `DESTINO_INEXISTENTE` | destino não cadastrado |
| 409 | `TRANSFERENCIA_DUPLICADA` | mesma origem, destino e valor efetivados há menos de 60s |
| 409 | `SALDO_INSUFICIENTE` | saldo da origem menor que o valor |
| 409 | `USUARIO_EXISTENTE` | username já registrado |
| 401 | `CREDENCIAIS_INVALIDAS` | login com usuário ou senha errados |
| 401 | `NAO_AUTENTICADO` | token ausente ou inválido |

As validações de `/transferencias` seguem essa ordem: valor → mesma conta →
destino → duplicidade → saldo.

---

## Estratégia de concorrência

Toda a garantia de "exatamente uma vez" cabe em três passos, dentro de **uma
única transação do banco** (`app/main.py`, rota `POST /transferencias`):

1. **Travar as duas contas** com `SELECT ... FOR UPDATE`, sempre na ordem do `id`
   (ordem fixa evita deadlock). Com a trava na mão, nenhuma outra transferência
   mexe nas contas enquanto decidimos.
2. **Checar a duplicidade** dos últimos 60 segundos com a trava já aplicada.
   Requisições iguais que chegam ao mesmo tempo ficam uma fila na trava: a
   primeira commita e as demais enxergam a transferência e são recusadas —
   passa exatamente uma.
3. **Debitar, creditar e registrar** na mesma transação. Ou tudo fica salvo,
   ou nada fica: uma queda no meio nunca deixa saldo dividido pela metade, e a
   soma dos saldos se conserva (nenhuma moeda é criada ou destruída).

---

## Estrutura do projeto

```
app/
├── main.py     # app FastAPI, tratamento de erros e todas as rotas
├── banco.py    # conexão com o PostgreSQL e definição das tabelas
└── auth.py     # senha (hash) e token JWT
Dockerfile
docker-compose.yml
requirements.txt
```

| Peça | Tecnologia |
|:---|:---|
| Web framework | FastAPI (Python) |
| Banco de dados | PostgreSQL 16 |
| Autenticação | JWT (Bearer) |
| Senhas | PBKDF2-SHA256 com salt |
| Infra | Docker Compose (serviços `api` e `db`) |

## Cenários verificados

- Rajada de 30 transferências idênticas simultâneas → exatamente `201`, as
  demais `409 TRANSFERENCIA_DUPLICADA`.
- Rajada de 40 transferências distintas simultâneas → todas `201` e a soma dos
  saldos preservada.
- `docker kill` no meio de uma rajada → transferências efetivadas por inteiro ou
  não efetivadas; soma dos saldos intacta ao religar.
- `docker compose down -v` seguido de `docker compose up --build -d` → API pronta
  em poucos segundos com o banco zerado.
- Requisições sem token, token inválido e todas as rejeições do contrato →
  formato `{"error": "<CODIGO>"}`.
