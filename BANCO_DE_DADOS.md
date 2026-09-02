# Aula completa: o banco de dados deste projeto

Tudo que você precisa para explicar, abrir, consultar e editar o banco.

---

# PARTE 1 — O QUE É O BANCO

## 1.1 O banco é UM ARQUIVO

```
helpdesk-platform/data/app.db
```

É isso. Um arquivo só. Se você copiar esse arquivo para um pen drive, levou o
banco inteiro — todos os clientes, chamados, equipamentos, leituras e alertas.

**Como explicar:**
> "O SQLite é um banco **embutido**: ele não é um programa rodando separado, é
> uma biblioteca dentro da minha aplicação que lê e escreve num arquivo. O
> PostgreSQL, por outro lado, é um **servidor** — um programa separado que fica
> ligado esperando conexões."

| | SQLite (aqui) | PostgreSQL / MySQL |
|---|---|---|
| O que é | Uma biblioteca + um arquivo | Um servidor separado |
| Precisa instalar? | Não (já vem com o Python) | Sim |
| Onde ficam os dados | `data/app.db` | Numa pasta gerenciada pelo servidor |
| Vários programas ao mesmo tempo | Limitado na escrita | Feito para isso |
| É SQL de verdade? | **Sim** | Sim |

**Se disserem "SQLite não é banco de verdade":**
> "É um banco relacional completo: tem SQL, transações ACID, chaves
> estrangeiras, índices e constraints. A limitação é concorrência de escrita.
> Por isso usei SQLAlchemy e coloquei a URL do banco no `.env` — trocar para
> PostgreSQL é mudar uma linha de configuração, o código não muda."

---

## 1.2 As 5 tabelas e como elas se ligam

```
        ┌──────────────────┐
        │     clients      │   ← quem contrata o serviço
        │  id (PK)         │
        └───┬──────────┬───┘
       1:N  │          │  1:N
    ┌───────┘          └────────┐
    ▼                           ▼
┌─────────┐             ┌──────────────┐
│ tickets │             │  equipments  │   ← aparelhos instalados no cliente
│client_id│──FK         │  client_id   │──FK
└─────────┘             └──┬────────┬──┘
                       1:N │        │ 1:N
                ┌──────────┘        └──────────┐
                ▼                              ▼
     ┌────────────────────┐            ┌──────────────┐
     │ equipment_readings │            │    alerts    │
     │   equipment_id     │──FK        │ equipment_id │──FK
     └──────────┬─────────┘            │ reading_id   │──FK (UNIQUE)
                └────────── 1:0..1 ────────────┘
```

**Como ler isso em voz alta:**
> "Um cliente tem **vários** chamados e **vários** equipamentos. Cada
> equipamento tem **várias** leituras. Cada leitura pode gerar **um** alerta —
> ou nenhum, se a temperatura estiver normal."

| Tabela | Guarda | Exemplo |
|---|---|---|
| `clients` | Quem contrata | Escola Ântonio Padilha |
| `tickets` | Os chamados | "Impressora não imprime" |
| `equipments` | Aparelhos no cliente | EQP-011, Servidor Rack |
| `equipment_readings` | Cada medição enviada | 85.6°C às 14h32 |
| `alerts` | Problemas detectados | "Temperatura crítica: 85.6°C" |

---

## 1.3 Como as tabelas "conversam": a chave estrangeira

A tabela `tickets` **não** guarda o nome do cliente. Ela guarda só o número:

```
clients                          tickets
┌────┬──────────────────┐        ┌────┬───────────┬──────────────────┐
│ id │ company          │        │ id │ client_id │ title            │
├────┼──────────────────┤        ├────┼───────────┼──────────────────┤
│ 1  │ Escola Ântonio   │◄───────│ 1  │     1     │ Impressora ...   │
└────┴──────────────────┘   FK   └────┴───────────┴──────────────────┘
                                          ▲
                              "este chamado pertence ao cliente 1"
```

**Por que não copiar o nome do cliente dentro do chamado?**
> "Se eu copiasse, o dia que o cliente trocasse de nome ou e-mail eu teria que
> atualizar 100 linhas de chamados. Se falhasse no meio, o banco ficaria com
> duas versões da verdade. Guardando só o `id`, o dado do cliente existe em
> **um lugar só**. Isso se chama **normalização**."

**E o banco garante que o cliente existe:**
> "Se eu tentar inserir um chamado com `client_id = 999` e esse cliente não
> existir, o banco **recusa**. Isso é a foreign key trabalhando."

---

## 1.4 O que o banco garante sozinho (as "constraints")

Estas travas estão **dentro do banco**, não no meu código Python:

| Trava | O que impede | Onde no projeto |
|---|---|---|
| `PRIMARY KEY` | dois registros com o mesmo id | todas as tabelas |
| `FOREIGN KEY` | apontar para algo que não existe | `tickets.client_id` |
| `UNIQUE` | valor repetido | `clients.email`, `alerts.reading_id` |
| `CHECK` | valor fora da lista permitida | `status`, temperatura −50 a 200 |
| `NOT NULL` | campo obrigatório vazio | `title`, `email` |
| `ON DELETE RESTRICT` | apagar cliente que tem histórico | todas as FKs |

**Demonstre isso!** Veja a Parte 4.

> ⚠️ **Detalhe que impressiona:** o SQLite **ignora foreign keys por padrão**.
> Foi preciso ligar com `PRAGMA foreign_keys=ON` em cada conexão. Está no
> arquivo `backend/app/database.py`. Muita gente não sabe disso.

---
---

# PARTE 2 — COMO ABRIR O BANCO

Você tem **3 formas**. Escolha uma para amanhã (recomendo a 1).

## Forma 1 — Console SQL do projeto (mais rápido)

Duplo clique em **`BANCO.bat`**, ou no terminal:

```bash
python -m backend.db_shell
```

Aparece `sql>` e você digita SQL. Atalhos:

| Comando | O que faz |
|---|---|
| `.tabelas` | lista as tabelas |
| `.contar` | conta os registros de todas as tabelas |
| `.schema tickets` | mostra como a tabela foi criada |
| `.sair` | sai |

**Modo comando único** (bom para colar na apresentação):
```bash
python -m backend.db_shell "SELECT * FROM clients"
```

> Este script usa **só a biblioteca padrão do Python**, então funciona mesmo
> sem ativar o `.venv`. Foi de propósito: uma ferramenta de diagnóstico não
> pode depender de tudo estar instalado.

---

## Forma 2 — VS Code (visual, você já tem instalado)

**Instale a extensão uma vez:**

1. Abra o VS Code na pasta do projeto
2. `Ctrl + Shift + X` (Extensões)
3. Busque por **SQLite Viewer** (autor: *Florian Klampfer*) — ou **SQLite** (*alexcvzz*)
4. Clique em **Install**

**Para usar:** clique no arquivo `data/app.db` na barra lateral. Ele abre uma
aba mostrando as tabelas — clicou na tabela, vê os dados.

> É a forma mais bonita para mostrar na tela. Você clica em `clients`, `tickets`,
> `alerts` e vai narrando.

**Alternativa pelo terminal do VS Code:** funciona igual ao cmd.

---

## Forma 3 — DB Browser for SQLite (programa dedicado)

Se quiser uma ferramenta completa (editar clicando, sem SQL):

```bash
winget install --id DBBrowserForSQLite.DBBrowserForSQLite -e
```

Abra o programa → **Open Database** → escolha `data/app.db`.
Abas: *Database Structure*, *Browse Data*, *Execute SQL*.

> ⚠️ Se editar por aqui, clique em **Write Changes** — senão nada é salvo.

---
---

# PARTE 3 — SQL: OS COMANDOS QUE VOCÊ PRECISA

São **4 verbos**. Só isso.

| Verbo | O que faz | Frase |
|---|---|---|
| `SELECT` | **lê** | "me mostre" |
| `INSERT` | **cria** | "adicione" |
| `UPDATE` | **altera** | "mude" |
| `DELETE` | **apaga** | "remova" |

## 3.1 SELECT — ler (99% do que você vai usar)

Tudo de uma tabela:
```sql
SELECT * FROM clients;
```
*(o `*` significa "todas as colunas")*

Só algumas colunas:
```sql
SELECT id, name, company FROM clients;
```

Com filtro (`WHERE`):
```sql
SELECT * FROM tickets WHERE status = 'ABERTO';
```

Ordenando (`ORDER BY`) e limitando:
```sql
SELECT * FROM tickets ORDER BY opened_at DESC LIMIT 10;
```
*(`DESC` = do maior para o menor; aqui, mais recente primeiro)*

Contando:
```sql
SELECT COUNT(*) FROM tickets;
```

Agrupando (`GROUP BY`) — **é isso que alimenta os gráficos do dashboard**:
```sql
SELECT status, COUNT(*) FROM tickets GROUP BY status;
```
> "Isto é exatamente o que meu endpoint de analytics faz. O agrupamento
> acontece **no banco**, não em JavaScript."

## 3.2 JOIN — juntar duas tabelas

```sql
SELECT t.id, t.title, c.company
FROM tickets t
JOIN clients c ON c.id = t.client_id;
```

**Como ler:** *"pegue os chamados e, para cada um, busque o cliente cujo `id`
seja igual ao `client_id` do chamado."*

O `t` e o `c` são apelidos, para não escrever o nome da tabela toda hora.

**Um exemplo real do seu projeto** (alertas com o equipamento):
```sql
SELECT a.id, e.identifier, a.temperature, a.status
FROM alerts a
JOIN equipments e ON e.id = a.equipment_id;
```

> "Repare: a tabela de alertas guarda só o `equipment_id`. O identificador do
> equipamento vem do JOIN, na hora da leitura. Não existe dado duplicado."

## 3.3 INSERT, UPDATE, DELETE

```sql
INSERT INTO clients (name, company, email, phone, created_at)
VALUES ('Maria Silva', 'Padaria Central', 'maria@padaria.com',
        '(11) 98888-7777', '2026-09-02 10:00:00');
```

```sql
UPDATE tickets SET status = 'FINALIZADO' WHERE id = 1;
```

```sql
DELETE FROM tickets WHERE id = 1;
```

> ⚠️ **`UPDATE` e `DELETE` sem `WHERE` afetam a TABELA INTEIRA.**
> Costume que salva: escreva o `WHERE` **antes** de escrever o resto.

---
---

# PARTE 4 — A SUA PERGUNTA: POSSO INSERIR DIRETO NO BANCO?

## A resposta curta

**Sim, você consegue. Mas você não deve — e eu provei o porquê.**

## O experimento que eu rodei (repita na apresentação!)

**Caminho 1 — INSERT direto no banco, 95°C:**
```sql
INSERT INTO equipment_readings (equipment_id, temperature, status, recorded_at)
VALUES (1, 95.0, 'ONLINE', '2026-09-02 10:00:00');
```
Resultado:
```
leituras:  1 → 2    (entrou)
alertas:   1 → 1    ← NENHUM ALERTA FOI CRIADO
```

**Caminho 2 — mesma temperatura, pela API:**
```
POST /api/equipments/1/readings   {"temperature": 95.0}
```
Resultado:
```
critical_condition_detected: True
alerta criado: SIM, id=2
leituras:  2 → 3
alertas:   1 → 2    ← O ALERTA NASCEU
```

## Por que isso acontece

```
Pela API:                          Direto no banco:

  API                                 (pula tudo isso)
   ↓
  valida os dados          ✅            ❌ não valida
   ↓
  confere o equipamento    ✅            ❌ não confere
   ↓
  grava a leitura          ✅            ✅ grava
   ↓
  COMPARA COM 80°C         ✅            ❌ NÃO COMPARA
   ↓
  cria o alerta            ✅            ❌ NÃO CRIA
```

**A frase para a banca (guarde esta):**
> "A **regra de negócio** mora na aplicação; o **banco** guarda os dados e
> garante a integridade estrutural. Inserindo direto no banco, eu pulo a regra:
> a leitura de 95 graus entra, mas o alerta não nasce — e o sistema fica
> mentindo que está tudo bem.
>
> É por isso que existe uma API. Ela não é burocracia: ela é o **único caminho
> que aplica as regras**."

## Mas o banco ainda te protege de algumas coisas

Nem tudo passa. Teste isto no console:

```sql
INSERT INTO tickets (client_id, title, description, category, priority, status, opened_at)
VALUES (999, 'teste', 'teste', 'Rede', 'ALTA', 'ABERTO', '2026-09-02 10:00:00');
```
→ **`FOREIGN KEY constraint failed`** (o cliente 999 não existe)

```sql
INSERT INTO tickets (client_id, title, description, category, priority, status, opened_at)
VALUES (1, 'teste', 'teste', 'Rede', 'ALTA', 'BANANA', '2026-09-02 10:00:00');
```
→ **`CHECK constraint failed: ticket_status_enum`**

> "Ou seja: o banco garante que o dado é **estruturalmente** válido. Mas ele
> não sabe que 'temperatura acima de 80 gera alerta' — isso é regra de negócio,
> e regra de negócio é da aplicação."

## Então quando é OK mexer direto no banco?

| Situação | Pode? |
|---|---|
| Consultar / investigar (`SELECT`) | ✅ Sempre |
| Provar que o dado persistiu | ✅ Ótimo para a apresentação |
| Corrigir um dado errado pontual | ⚠️ Com cuidado, sabendo o que faz |
| Cadastrar clientes/chamados em massa | ❌ Use a API |
| Inserir leituras de equipamento | ❌ **Nunca** — pula a regra do alerta |

---
---

# PARTE 5 — DEMONSTRAÇÕES PARA A APRESENTAÇÃO

## Demo 1 — "Não é mockup, o dado está no banco"
Cadastre um cliente pela tela, depois:
```bash
python -m backend.db_shell "SELECT id, name, company, email FROM clients"
```
> "Isto é o banco, sem passar pela aplicação. Ele está aqui."

## Demo 2 — "A foreign key funciona de verdade"
```bash
python -m backend.db_shell "INSERT INTO tickets (client_id, title, description, category, priority, status, opened_at) VALUES (999, 'x', 'y', 'Rede', 'ALTA', 'ABERTO', '2026-09-02 10:00:00')"
```
→ `FOREIGN KEY constraint failed`
> "Não é o meu código recusando. É o **banco**."

## Demo 3 — "Status inválido não entra nem na marra"
```bash
python -m backend.db_shell "UPDATE tickets SET status = 'BANANA' WHERE id = 1"
```
→ `CHECK constraint failed`

## Demo 4 — "Ver a estrutura da tabela"
```bash
python -m backend.db_shell ".schema alerts"
```
Aparecem as colunas, as FOREIGN KEYs e os CHECK. Ótimo para explicar modelagem.

## Demo 5 — "A regra está na aplicação, não no banco"
O experimento da Parte 4. **É a demonstração mais forte que você tem.**

## Demo 6 — "Ver o SQL que o ORM gera"
No arquivo `.env`, mude para `SQL_ECHO=true`, reinicie o servidor e navegue.
Cada `SELECT` e `INSERT` aparece no terminal.
> "Isso prova que existe SQL de verdade por trás do ORM."

---

# PARTE 6 — PERGUNTAS PROVÁVEIS

**"Onde ficam os dados?"**
No arquivo `data/app.db`. Um arquivo só, em disco.

**"Como o chamado sabe de quem ele é?"**
Pela coluna `client_id`, que é uma foreign key para `clients.id`. Quando eu
listo os chamados, faço um JOIN para trazer o nome da empresa junto.

**"Você consegue inserir direto no banco?"**
Consigo, mas não devo. Se eu inserir uma leitura de 95°C por SQL, a leitura
entra mas o alerta **não** é criado — porque a regra está na aplicação. Posso
demonstrar agora.

**"E se alguém alterar o banco por fora?"**
O banco ainda barra o que é estruturalmente inválido: foreign key, CHECK de
status, UNIQUE de e-mail. Mas ele não aplica regra de negócio — por isso o
acesso correto é pela API.

**"Por que você não guardou o nome do cliente no chamado?"**
Normalização. Se guardasse, uma mudança de nome exigiria atualizar todas as
linhas, com risco de inconsistência.

**"O que é uma transação?"**
Um bloco tudo-ou-nada. Quando chega uma leitura acima de 80°C, eu gravo a
leitura e o alerta na **mesma transação**: ou os dois existem, ou nenhum. É
impossível ter leitura de 95°C sem alerta *quando passa pela API*.

**"Como você faria backup?"**
Copiar o arquivo `data/app.db`. Em produção com PostgreSQL, seria `pg_dump`.

**"Como você migraria para PostgreSQL?"**
Mudar `DATABASE_URL` no `.env`, instalar o driver e criar o schema. O código
não muda, porque o SQLAlchemy abstrai o dialeto SQL.
