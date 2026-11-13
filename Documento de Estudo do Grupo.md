# Documento de Estudo do Grupo — Projeto Transferências

Material de estudo do grupo para a apresentação de **19/11** (5 minutos, dois
integrantes sorteados na hora). Este documento responde ao que interessa
entender: **a linguagem do projeto, como o grupo chegou na conclusão da
estratégia e como foi o processo de construção.**

---

## 1. O problema, em linguagem simples

O projeto é uma carteira digital: usuários transferem moedas entre si e todos
começam com 1000. A transferência em si é fácil — o difícil é o cenário real:

- Várias requisições chegam **ao mesmo tempo** (a mesma pessoa clicando várias
  vezes, ou muitos usuários de uma vez);
- O servidor pode **cair no meio** de uma transferência;
- A mesma transferência repetida em menos de **60 segundos** não pode valer duas
  vezes.

Disso nascem três garantias que o sistema nunca pode quebrar:

1. **Exatamente uma vez** — cada transferência efetivada acontece uma única vez,
   nunca duas;
2. **Tudo ou nada** — se o servidor cair, a transferência existiu por inteiro ou
   não existiu (nunca debitou sem creditar);
3. **Conservação** — a soma de todos os saldos é sempre `1000 × número de
   usuários`, e nenhum saldo fica negativo.

Ou seja: o problema não é "fazer transferência", é **garantir essas três coisas
sob concorrência e falhas**.

---

## 2. Linguagem: os conceitos que o grupo domina

Termos que aparecem na discussão e que todo integrante precisa saber usar:

| Termo | Significado objetivo |
|:---|:---|
| **Transação** | Operação que o banco aplica como um bloco único: ou completa toda, ou desfaz toda. É a ferramenta contra queda no meio. |
| **Atomicidade** | Propriedade da transação de não ter "estado pela metade". É o que impede saldo dividido. |
| **Condição de corrida (race condition)** | Quando dois processos lêem e escrevem ao mesmo tempo e o resultado depende da ordem do acaso. |
| **Lock de linha (trava)** | Mecanismo que tranza registros específicos até o fim da transação; quem tenta mexer neles espera. Aqui usamos o `FOR UPDATE`. |
| **Serialização** | Transformar operações simultâneas em "uma depois da outra" — é isso que a trava faz com as transferências. |
| **Deadlock** | Duas transações esperando a trava uma da outra, para sempre. Evitável com ordem fixa de travamento. |
| **Duplicidade / janela de 60s** | Identificar que é "a mesma transferência" (origem + destino + valor) recém-feita e recusar. |
| **JWT / token Bearer** | Recibo assinado que o login devolve e que as rotas protegidas apresentam; a API confere a assinatura sem consulta extra. |
| **Hash de senha** | Guardar a senha transformada (com sal), nunca em texto puro. |
| **Volume do Docker** | Espaço de disco persistido fora dos containers — parar e religar não apaga os dados. |
| **Auditoria** | Rota pública que mostra os totais — é a prova visível de que a soma dos saldos se conserva. |

---

## 3. Como o grupo chegou na conclusão da estratégia

O raciocínio foi uma cadeia de perguntas e respostas, nesta ordem:

**Pergunta 1 — Quem deve garantir "exatamente uma vez"?**
A primeira conclusão: **o banco de dados**, não a aplicação. Uma aplicação guarda
estado em memória, mas memória morre na queda e cada instância da aplicação tem
a sua. O banco relacional é a fonte única de verdade e já nasceu resolvido para
isso — profissionais usam transação há décadas. Daí a primeira decisão:
PostgreSQL e uma transação só por transferência.

**Pergunta 2 — A transação sozinha resolve tudo?**
Não. A transação protege contra queda, mas não contra **duas requisições iguais
rodando ao mesmo tempo**: as duas poderiam ler o saldo, ver "sem duplicata" e
passar juntas. Precisamos **serializar** — segurar as contas enquanto decidimos.
Daí a segunda decisão: travar as duas linhas de conta com `SELECT ... FOR
UPDATE` **antes** de qualquer checagem.

**Pergunta 3 — E a duplicidade, onde entra?**
Com a trava na mão, a consulta dos últimos 60 segundos fica confiável: se duas
iguais chegarem juntas, uma ganha a trava, commita e grava; a outra só segue
depois, consulta, **enxerga** a primeira e é recusada. Passa exatamente uma — e
como recusa não gera registro, recusas não contam.

**Pergunta 4 — A ordem das travas importa?**
Importa, e quase quebramos aqui: se a João transfere pra Maria e a Maria
transfere pra João ao mesmo tempo, uma espera a outra travar e as duas travadas
nunca avançam — **deadlock**. A solução é simples: sempre travar na **ordem do
id** da conta (menor primeiro). Com ordem fixa, todo mundo espera na mesma
sequência e o sistema anda.

**Pergunta 5 — E se o servidor cair no meio?**
Débito, crédito e registro precisam estar **na mesma transação**. Aí o banco
garante o resto: caiu antes do commit, ele desfaz tudo; caiu depois, tudo ficou.
Nunca metade. E como débito e crédito se anulam dentro do mesmo bloco, a soma dos
saldos é conservada automaticamente.

**Conclusão final (a frase do grupo):**
> Uma transação + trava das duas contas em ordem fixa + checagem de duplicidade
> dentro da trava = exatamente uma vez, sem deadlock, sem saldo negativo e sem
> transferência pela metade.

Essa conclusão não foi só teórica: **validamos nos extremos** — 30 transferências
idênticas disparadas juntas (passou exatamente uma), `docker kill` no meio de uma
rajada (soma dos saldos intacta ao religar) e o banco zerado e religado (API
pronta e consistente). Os testes bateram com a teoria.

---

## 4. Como foi o processo de construção

**Etapa 1 — Entender o contrato antes de escrever código.**
Lemos o enunciado e transformamos em lista: as 5 rotas, o formato único de erro
(`{"error": "<CODIGO>"}`), a ordem das validações da transferência e as três
garantias. Anotamos os casos de borda que quase sempre são esquecidos — como
"transferência repetida responde DUPLICADA mesmo sem saldo" e "valor em texto é
inválido".

**Etapa 2 — Escolher as ferramentas com critério.**
Python (linguagem que o grupo domina), FastAPI (direto e gera o Swagger sozinho,
ótimo para demonstrar), PostgreSQL (é o banco: é ele que dá as travas
robustas de que o problema precisa) e Docker (exigência do enunciado — tudo
roda localmente, sem serviço na nuvem). A decisão de Postgres e não de um banco
em nuvem foi justamente pela exigência do `docker compose`.

**Etapa 3 — Primeiro o fácil, para ter retorno rápido.**
Montamos as rotas de registro, login, saldo e auditoria, com todas as validações
e o formato de erro, e testamos manualmente no Swagger caso a caso. Quando o
"básico" responde certo, sobra cabeça para o núcleo.

**Etapa 4 — O núcleo: a estratégia de concorrência.**
Implementamos os três passos (travar → checar duplicidade → debitar e creditar
juntos). Uma descoberta importante no caminho: testando com um banco simples
(SQLite) localmente, a trava de linha era **ignorada** — o teste de rajada
mostrou várias transferências iguais passando. Isso confirmou que a garantia
real só existe no PostgreSQL, e todos os testes sérios passaram a rodar contra
ele, dentro do Docker.

**Etapa 5 — Testes de resistência.**
Em vez de só testar o caminho feliz, atacamos os cenários do enunciado:
rajadas simultâneas, repetição dentro da janela de 60 segundos, matar o servidor
no meio das transferências, parar tudo e subir de novo, e média de volume.
Foi o que revelou, por exemplo, que a duplicidade precisa ser checada **dentro**
da trava e antes da escrita.

**Etapa 6 — Organizar para entender.**
Reorganizamos o código em três arquivos com papéis claros (rotas, banco,
autenticação) e deixamos a estratégia comentada no ponto exato em que ela
acontece. Depois da limpeza, rodamos a suíte completa de novo — **49 cenários
automatizados** — para garantir que nada quebrou no caminho.

**O que deu mais trabalho:** a ordem exata das validações e o entendimento de
por que a checagem de duplicidade tem que vir **depois** de ganhar a trava (feito
antes, duas iguais passariam juntas). **O que o grupo leva disso:** a concorrência
não se resolve "no código da aplicação" — resolve-se combinando banco, transação
e uma regra de ordenação simples.

---

## 5. Perguntas prováveis e respostas prontas

**Explique a estratégia em 30 segundos.**
A gente trava as duas contas numa ordem fixa de id, e com a trava na mão checa a
duplicidade dos últimos 60 segundos e o saldo; só então debitamos, creditamos e
registramos tudo numa transação só. A trava faz iguais passarem uma de cada vez,
a ordem fixa evita deadlock, e a transação garante que queda nunca divida a
transferência.

**E se duas transferências idênticas chegarem no mesmo milissegundo?**
As duas disputam a mesma trava. Uma ganha, commita e grava. A outra só segue
depois, consulta, vê a duplicata e é recusada. Resultado: uma única efetivada.

**Por que a duplicidade é checada antes do saldo?**
Porque o contrato exige: uma repetida responde `TRANSFERENCIA_DUPLICADA` mesmo
com saldo zerado. A ordem das validações do projeto está implementada assim.

**Como o saldo nunca fica negativo?**
A checagem e a escrita acontecem com a trava na mão, na mesma transação — ninguém
consegue drenar a conta entre uma coisa e outra.

**Como vocês provam que nenhuma moeda é criada ou destruída?**
Débito e crédito são do mesmo bloco, então se anulam; a rota de auditoria mostra
a soma de todos os saldos, e testamos sob rajada e após quedas — a soma
sempre igual a `1000 × usuários`.

**O que acontece se o servidor cair no meio?**
O banco termina sozinho: commitou, tá tudo salvo; não commitou, desfaz tudo.
Requisições em andamento podem cair com erro de conexão — o contrato permite,
desde que seja tudo ou nada.

**Por que não usar trava dentro da aplicação (em memória)?**
Memória morre na queda, e várias instâncias da aplicação não compartilham
memória. O banco é a fonte única e é ele que todos acessam.

**Qual a diferença entre `docker compose down` e `down -v`?**
`down` para e remove os containers mantendo os dados; `down -v` apaga também o
volume — por isso o projeto começa zerado depois dele.

**Como vocês mostram que funciona sob carga?**
Medimos: 100 requisições simultâneas responderam todas com sucesso, e as
rajadas de 30 e 40 transferências simultâneas tiveram o resultado esperado
(exatamente uma efetivada no caso das iguais).

---

## 6. Roteiro da apresentação (5 minutos)

| Tempo | O que falar |
|:---|:---|
| 0:00–0:40 | O problema: exatamente uma vez, com concorrência e quedas (as 3 garantias) |
| 0:40–1:20 | A conclusão do grupo em uma frase (transação + trava em ordem fixa + duplicidade dentro da trava) |
| 1:20–3:00 | Como chegamos lá: as 5 perguntas do raciocínio (resumidas: banco manda, trava serializa, ordem fixa evita deadlock, transação protege da queda) |
| 3:00–4:20 | Demonstração ao vivo: transferir, repetir e ser recusado; 3 terminais com a mesma transferência → só uma passa |
| 4:20–4:50 | Resiliência: matar o servidor no meio e mostrar a auditoria com a soma certa |
| 4:50–5:00 | Fechamento: "concorrência não se resolve no código — resolve-se com banco, transação e ordem" |

### Para demonstrar ao vivo (o grupo testa antes)

- Registrar dois usuários, logar, transferir e repetir na mesma hora → a
  repetição volta `TRANSFERENCIA_DUPLICADA`.
- Abrir 3 terminais e mandar a mesma transferência quase juntos → só uma `201`.
- `GET /auditoria` → a soma continua `1000 × usuários` em qualquer momento.
- `docker kill api` seguido de `docker start api` → auditoria continua certa.

---

## 7. Comandos do ambiente (para o dia)

```bash
docker compose up --build -d     # sobe app + banco
docker compose ps                # os dois no ar
docker compose restart           # reinicia mantendo dados
docker compose down -v           # para e apaga tudo (banco zerado)
```

API em `http://localhost:8080` · Swagger em `http://localhost:8080/docs`
