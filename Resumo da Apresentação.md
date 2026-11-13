# Resumo da Apresentação — Projeto Transferências

## O que é

Uma carteira digital: usuários transferem moedas entre si, todos começam com
1000. A transferência em si é simples — o difícil é garantir que ela aconteça
**exatamente uma vez**, mesmo com muita gente mexendo ao mesmo tempo e com o
servidor caindo no meio.

## As 3 regras que nunca podem ser quebradas

1. **Uma vez só** — a mesma transferência nunca vale duas vezes;
2. **Tudo ou nada** — queda no meio nunca deixa transferência pela metade;
3. **Soma certa** — a soma de todos os saldos é sempre `1000 × usuários`.

## Como resolvemos (a estratégia inteira em 3 passos)

1. **Travamos as duas contas** antes de decidir qualquer coisa — assim mais
   ninguém mexe nelas enquanto pensamos;
2. **Com a trava na mão**, checamos se é duplicata (últimos 60s) e se tem saldo;
3. **Debita, credita e registra tudo junto**, numa transação só — ou salva
   inteiro, ou não salva nada.

**Por que funciona:** a trava faz as requisições iguais passarem uma de cada vez
(passa só uma), a ordem fixa das travas evita travamento entre si, e a transação
é o que protege contra queda.

## Como provamos que funciona

- 30 transferências idênticas ao mesmo tempo → **exatamente uma** passou;
- Cortei o servidor no meio das transferências → religou e a soma dos saldos
  continuava certa;
- Parei tudo e subi de novo (`down -v` / `up --build -d`) → API no ar, banco
  consistente;
- 100 requisições simultâneas → todas responderam sem erro.

## Frase de fechamento

> Concorrência não se resolve no código da aplicação — resolve-se com banco,
> transação e uma regra simples de ordem.

## Demonstração ao vivo (2 minutos)

1. Transferir e repetir na hora → a repetição volta `TRANSFERENCIA_DUPLICADA`;
2. 3 terminais com a MESMA transferência → só uma `201`;
3. `GET /auditoria` → soma dos saldos sempre `1000 × usuários`.
