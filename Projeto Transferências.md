# **Projeto: Transferências**

## **Problema**

Em sistemas que movimentam valores, uma transferência precisa acontecer exatamente uma vez, mesmo com muitas requisições simultâneas, cliques repetidos e quedas do servidor. Sua API vai gerenciar uma carteira digital em que usuários transferem moedas entre si. As regras são fixas:

* Cada usuário começa com 1000 moedas; valores são sempre números inteiros.  
* Nenhuma moeda é criada ou destruída: a soma dos saldos é sempre 1000 × número de usuários.  
* Nenhum saldo fica negativo.  
* A mesma transferência (mesma origem, destino e valor) não pode ser efetivada duas vezes em menos de 60 segundos.  
* Uma queda da API nunca deixa uma transferência pela metade.  
* Toda requisição recebe resposta clara e rápida, sem erro 500, timeout ou travamento, exceto as que estiverem em andamento no momento de uma queda; essas devem ter sido efetivadas por inteiro ou não ter acontecido.


## 

## **Regras de Negócio**

* **Transferência:** debita a origem e credita o destino. Depois de uma queda, a transferência existiu por inteiro ou não existiu.  
* **Duplicidade:** se uma transferência com mesma origem, destino e valor foi efetivada há menos de 60 segundos, a nova é recusada e nada é movimentado. Se várias iguais chegarem ao mesmo tempo, exatamente uma é efetivada. Recusas não contam. Se a transferência for duplicada, a resposta é TRANSFERENCIA\_DUPLICADA mesmo que o saldo atual não seja suficiente.  
* **Propriedade:** nenhuma rota permite ler ou movimentar a conta de outro usuário.  
* **Rejeições de POST /transferencias:**  
* valor ausente, que não seja um número inteiro (texto como "150" é inválido) ou menor ou igual a zero → 422 VALOR\_INVALIDO  
* destino igual à origem → 422 MESMA\_CONTA  
* destino não cadastrado → 404 DESTINO\_INEXISTENTE  
* Transferência igual efetivada há menos de 60 segundos → 409 TRANSFERENCIA\_DUPLICADA  
* Saldo insuficiente → 409 SALDO\_INSUFICIENTE  
    
    
    
  


## **Desafio**

Sua arquitetura deve ser **correta** (nunca viola as regras), **resiliente** (quedas a qualquer momento não deixam inconsistência), **eficiente** (responde rápido sob grande volume simultâneo) e **limpa** (rejeições sempre no formato padronizado).

## **Endpoints**

A API deve rodar em localhost:8080 e seguir este contrato à risca. Toda rejeição tem o formato { "error": "\<CODIGO\>" }; grafia diferente (ex.: {"erro": "saldo insuficiente"}) resulta em falha.

| Rota | Body | Sucesso |
| :---- | :---- | :---- |
| POST /auth/registrar | { "username": "joao", "password": "senha123" } | 201 Created |
| POST /auth/login | { "username": "joao", "password": "senha123" } | 200 OK { "token": "eyJhbGc..." } |
| GET /conta | sem body | 200 OK { "username": "joao", "saldo": 1000 } |
| POST /transferencias | { "destino": "maria", "valor": 150 } | 201 Created { "id": 7, "origem": "joao", "destino": "maria", "valor": 150, "saldo": 850 } |
| GET /auditoria | sem body | 200 OK { "usuarios": 50, "somaSaldos": 50000, "transferencias": 1234 } |

* /conta e /transferencias exigem Authorization: Bearer \<token\>; sem token válido → 401 NAO\_AUTENTICADO. /auditoria é pública.  
* Usuário já existente → 409 USUARIO\_EXISTENTE; login inválido → 401 CREDENCIAIS\_INVALIDAS.  
* Em /transferencias, saldo é o saldo da origem após a transferência; em /auditoria, transferencias é o total de transferências efetivadas.

Aplicação e banco devem rodar integralmente via Docker Compose. O serviço da aplicação deve se chamar api, expor a porta 8080, manter os dados quando for interrompido e reiniciado, e estar pronto após os comandos:

docker compose down \-v  
docker compose up \--build \-d

## **Entregáveis**

**Repositório.** GitHub com código-fonte, Dockerfile, docker-compose.yml

**Grupo e apresentação.** 5 integrantes. Apresentação de 5 minutos sobre a estratégia de concorrência do grupo, feita por dois integrantes sorteados na hora.

|  | Data | O que acontece |
| :---- | :---- | :---- |
| **Entrega** | 17/11, 23:59 | Link do repositório GitHub no Classroom |
| **Apresentação** | 19/11 | Apresentação e testes na API |

