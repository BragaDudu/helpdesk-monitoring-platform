# Guia completo: o que falar, como funciona, e como mexer no banco

Três partes:
- **PARTE A** — O que falar (o "pitch": o que é, pra que serve, quem compraria)
- **PARTE B** — Como o projeto funciona de verdade (quem conversa com quem)
- **PARTE C** — Como mexer no banco de dados

---
---

# PARTE A — O QUE FALAR

## A1. A abertura (decore isto — 30 segundos)

> "Eu construí uma **plataforma de gestão de TI**. Ela resolve três problemas
> que toda empresa de tecnologia tem: **organizar os chamados** dos clientes,
> **entender o que esses chamados dizem** sobre a operação, e **monitorar os
> equipamentos** instalados na casa do cliente para agir antes de dar problema.
>
> Não é uma tela bonita: é um sistema com banco de dados real, API REST e
> regras de negócio no servidor. Se eu desligar o computador agora e ligar
> amanhã, os dados continuam lá."

**Por que essa abertura funciona:** ela diz *o que é*, *que problema resolve* e
já ataca a suspeita de "é mockup?" antes de perguntarem.

---

## A2. Que problema o sistema resolve

Conte como uma **história de dor**, não como lista de features:

> "Imagine uma empresa que presta suporte de TI para 20 clientes. Hoje isso
> costuma ser controlado por **WhatsApp e planilha**. O que acontece:
>
> - **Chamado se perde.** Ninguém sabe quem pediu o quê, nem quando.
> - **Não dá para medir nada.** O dono não sabe quanto tempo a equipe leva
>   para resolver, nem qual cliente dá mais trabalho.
> - **O problema só é descoberto quando já parou.** O servidor do cliente
>   superaqueceu de madrugada, queimou, e a empresa só descobriu às 8h,
>   quando o cliente ligou gritando.
>
> Meu sistema resolve os três: **registra**, **mede** e **avisa antes**."

### A tabela do "antes e depois" (bom para desenhar no quadro)

| Sem o sistema | Com o sistema |
|---|---|
| Chamado no WhatsApp | Chamado com ID, status e histórico |
| "Acho que demora umas 2 horas" | Tempo médio calculado: **20h 8min** |
| "Qual cliente dá mais trabalho?" — chute | Ranking real, com números |
| Equipamento queima e você descobre depois | **Alerta automático acima de 80°C** |
| Dado na cabeça de uma pessoa | Dado no banco, consultável por qualquer um |

---

## A3. Quem compraria este produto

Não diga "qualquer empresa". Seja específico — isso mostra maturidade.

**O cliente ideal (quem paga):**

> "Uma **empresa de serviços de TI / MSP** — aquelas que cuidam da
> infraestrutura de outras empresas. Ela tem de 10 a 200 clientes, instala
> equipamento na casa deles (servidor, nobreak, switch, storage) e precisa
> provar que está entregando serviço."

**Outros perfis que também compram:**

| Perfil | Por que compraria |
|---|---|
| **Provedor de internet regional** | Monitora equipamento em cada ponto de presença |
| **Empresa de refrigeração / climatização** | Mesmo modelo: equipamento no cliente + temperatura |
| **Departamento de TI interno** de uma empresa média | Os "clientes" viram os setores (RH, Financeiro, Fábrica) |
| **Empresa de automação industrial** | Sensores em máquinas, alerta de temperatura |

**A sacada que impressiona** — diga isto:

> "Repare que o módulo de monitoramento **não é só sobre temperatura**. A
> estrutura é `equipamento → leitura → alerta`. Se amanhã a leitura for
> **umidade**, **pressão** ou **nível de tanque**, o modelo é o mesmo. Eu mudo
> a regra em um arquivo. Isso torna o produto vendável para vários setores."

---

## A4. Por que isso é útil para a Revosys

> ⚠️ **Adapte esta seção** ao que a Revosys realmente faz — eu não conheço a
> operação interna deles. Use a estrutura abaixo e troque os exemplos.

**A estrutura da resposta (funciona para qualquer empresa de tecnologia):**

**1) Ligue ao negócio deles:**
> "A Revosys trabalha com [sistemas/serviços de TI para clientes]. Esse sistema
> é exatamente a espinha dorsal disso: cadastro de clientes, registro do que
> foi atendido, e visibilidade do que está acontecendo."

**2) Mostre que resolve uma dor real deles:**
> "Qualquer empresa que atende múltiplos clientes precisa responder três
> perguntas todo mês: *quanto trabalho cada cliente deu*, *quanto tempo levamos
> para resolver*, e *o que está prestes a dar problema*. Meu dashboard responde
> as três em uma tela."

**3) Mostre que é base para crescer (o argumento mais forte):**
> "Não é um sistema pronto e fechado — é uma **base**. A arquitetura está em
> camadas, tem testes automatizados e a documentação da API é gerada sozinha.
> Se a Revosys quisesse adicionar contrato, SLA, faturamento por chamado ou
> app mobile, o caminho já está aberto: a API já existe, o mobile só consumiria
> os mesmos endpoints."

**4) Feche falando de você, não do código:**
> "E o mais importante para vocês: **eu escrevi e eu explico**. Cada arquivo
> tem comentário dizendo o que faz e por que existe. Se me pedirem para mudar
> uma regra agora, eu mudo na frente de vocês."

---

## A5. Se perguntarem "isso já não existe pronto?"

**Não minta dizendo que é único.** Responda assim:

> "Existe — GLPI, Zendesk, Freshservice. Duas diferenças:
>
> Primeira: as ferramentas de chamado **não monitoram equipamento**, e as de
> monitoramento (Zabbix) **não gerenciam chamado**. Aqui os dois estão no mesmo
> lugar, ligados pelo cliente — dá para responder 'esse cliente abriu 10
> chamados e o equipamento dele passou de 80 graus 5 vezes'.
>
> Segunda: como é próprio, a regra de negócio é minha. Se o limite for 70 graus
> para um cliente e 90 para outro, eu implemento. Em ferramenta de prateleira,
> você se adapta a ela."

---

## A6. Roteiro de demonstração narrado (10 minutos)

Com o banco **vazio**, você constrói tudo na frente deles. É mais forte do que
mostrar dados prontos.

### Ato 1 — "O sistema está vazio" (30s)
Abra o Dashboard. Tudo zero, tempo médio "sem dados".
> "Repare: **sem dados**, não zero. Zero significaria 'resolve
> instantaneamente', o que seria mentira. A ausência de dado é informação."

### Ato 2 — "Vou cadastrar um cliente" (1 min)
Cadastre. Depois **dê F5 na frente deles**.
> "Dei F5 e ele continua. Porque quando cliquei em salvar, o JavaScript mandou
> um POST para a API, a API gravou no SQLite, e agora ele está num **arquivo em
> disco** — não na memória do navegador."

### Ato 3 — "Vou provar que está no banco" (1 min)
Abra outro terminal:
```bash
python -m backend.db_shell "SELECT * FROM clients"
```
> "Esse é o banco de dados, sem passar pela aplicação. O cliente está aqui."

**Este é o momento que mata a dúvida de "é mockup?".**

### Ato 4 — "Vou tentar quebrar o sistema" (2 min)
Tente cadastrar o **mesmo e-mail** de novo → erro 409.
> "O banco tem uma restrição UNIQUE no e-mail. Não é um `if` no meu código —
> é o banco recusando. Se duas pessoas tentassem ao mesmo tempo, o `if`
> falharia; a restrição não."

Tente cadastrar com e-mail sem `@` → erro 422.

### Ato 5 — Chamado e ciclo de vida (2 min)
Abra um chamado, mude para EM_ANDAMENTO, depois FINALIZADO.
> "Quando finalizei, o **servidor** carimbou a data de fechamento. O frontend
> não manda essa data — nem existe esse campo no formulário. Se mandasse, o
> usuário poderia falsear o relatório de tempo médio."

Tente voltar para ABERTO → **409**.
> "Isso é uma máquina de estados. Está num dicionário no arquivo `enums.py`.
> Se vocês quiserem permitir reabrir agora, é uma linha."

### Ato 6 — O momento alto: os 80°C (2 min)
Cadastre um equipamento. Mande **75°C**:
> "Nada aconteceu. Correto."

Mande **85°C** → alerta vermelho aparece.
> "O alerta foi criado **pelo servidor**, não pelo JavaScript. O JavaScript só
> leu um campo da resposta chamado `critical_condition_detected`. Ele nunca
> compara a temperatura com 80."

Prove no banco:
```bash
python -m backend.db_shell "SELECT * FROM alerts"
```

**E então a frase-chave:**
> "A regra está no servidor porque o navegador não é a única porta de entrada.
> Um sensor de verdade chamaria essa API **sem navegador nenhum**. Se a regra
> estivesse no JavaScript, ela não rodaria justamente para o cliente mais
> importante."

### Ato 7 — Analytics (1 min)
Volte ao Dashboard, mostre os números vivos.
> "Esses gráficos não têm valor inventado. Cada barra vem de um `GROUP BY` no
> banco. Quer ver o SQL? Posso ligar o log e mostrar a consulta rodando."

### Ato 8 — O golpe final (30s)
**Pare o servidor com Ctrl+C. Suba de novo. Dê F5.**
> "Reiniciei a aplicação inteira. Está tudo aqui."

---
---

# PARTE B — COMO O PROJETO FUNCIONA DE VERDADE

## B1. O mapa (quem conversa com quem)

```
   VOCÊ clica no botão "Salvar"
            │
            ▼
┌───────────────────────────────────────────────────────┐
│ NAVEGADOR                                              │
│                                                        │
│  clientes.html   → o formulário (o que você vê)        │
│       │                                                │
│  clientes.js     → captura o clique, monta o objeto    │
│       │                                                │
│  api.js          → o ÚNICO que faz fetch()             │
└───────┼───────────────────────────────────────────────┘
        │  HTTP: POST /api/clients  +  JSON
        │  (viaja pela rede, mesmo que seja localhost)
        ▼
┌───────────────────────────────────────────────────────┐
│ SERVIDOR (uvicorn + FastAPI)                           │
│                                                        │
│  routers/clients.py   → recebe o POST                  │
│       │                  (3 linhas, sem regra nenhuma) │
│       ▼                                                │
│  schemas/client.py    → VALIDA (nome? e-mail? fone?)   │
│       │                  se falhar: para aqui → 422    │
│       ▼                                                │
│  services/client_service.py  → A REGRA DE NEGÓCIO      │
│       │                  (e-mail já existe? → 409)     │
│       ▼                                                │
│  models/client.py     → o objeto que vira LINHA        │
│       │                                                │
│  database.py          → a sessão / a transação         │
└───────┼───────────────────────────────────────────────┘
        │  SQL: INSERT INTO clients (...) VALUES (?, ?)
        ▼
┌───────────────────────────────────────────────────────┐
│ data/app.db      ← arquivo em disco. É AQUI que fica.  │
└───────────────────────────────────────────────────────┘
```

E a **volta** é o mesmo caminho ao contrário:
banco → model → service → schema (vira JSON) → HTTP → `api.js` → `clientes.js`
→ HTML na tela.

---

## B2. Rastreando UMA ação, linha por linha

Vamos seguir **"cadastrar o cliente João"** do clique até o disco.

### Passo 1 — O HTML define o formulário
`frontend/clientes.html`
```html
<form id="form-client">
  <input name="name" />
  <input name="email" />
</form>
```
*O HTML só desenha. Ele não sabe o que é banco.*

### Passo 2 — O JavaScript captura o envio
`frontend/js/clientes.js`
```js
document.getElementById("form-client").addEventListener("submit", createClient);

async function createClient(event) {
  event.preventDefault();       // impede o navegador de recarregar a página
  const payload = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    // ...
  };
  const created = await api.post("/clients", payload);   // ← chama o api.js
}
```

### Passo 3 — O `api.js` faz a requisição HTTP
`frontend/js/api.js`
```js
const response = await fetch("/api/clients", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload),      // objeto JS → texto JSON
});
```
*Aqui o dado **sai** do navegador e vira uma mensagem de rede.*

### Passo 4 — O FastAPI recebe e decide qual função chamar
`backend/app/routers/clients.py`
```python
@router.post("", response_model=ClientOut, status_code=201)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    return client_service.create_client(db, payload)
```
Três coisas acontecem **antes** dessa função rodar:
1. O FastAPI vê `payload: ClientCreate` e tenta montar esse objeto com o JSON.
2. Se algum campo for inválido → devolve **422** e **a função nem é chamada**.
3. `Depends(get_db)` abre uma sessão de banco para esta requisição.

### Passo 5 — O schema valida
`backend/app/schemas/client.py`
```python
class ClientCreate(ClientBase):
    name: required_text(2, 120)   # mínimo 2 caracteres (sem espaços nas pontas)
    email: EmailStr               # precisa ter formato de e-mail
```
*Esta é a **primeira** das três barreiras de validação.*

### Passo 6 — O service aplica a regra
`backend/app/services/client_service.py`
```python
def create_client(db, payload):
    client = Client(name=payload.name, email=payload.email, ...)
    db.add(client)          # "quero inserir isto" (ainda não foi ao banco)
    try:
        db.commit()         # AGORA vai. O INSERT acontece aqui.
    except IntegrityError:
        db.rollback()
        raise ConflictError("Já existe cliente com esse e-mail.")  # → 409
    db.refresh(client)      # recarrega com o id que o banco gerou
    return client
```
*Esta é a **segunda** barreira.*

### Passo 7 — O model diz como é a tabela
`backend/app/models/client.py`
```python
class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)  # ← 3ª barreira
```

### Passo 8 — O SQLAlchemy gera o SQL
```sql
INSERT INTO clients (name, company, email, phone, created_at)
VALUES (?, ?, ?, ?, ?)
```
*Os `?` são **parâmetros**. É por isso que SQL Injection é impossível.*

### Passo 9 — O SQLite grava no arquivo
`data/app.db` cresce. **O dado agora existe em disco.**

### Passo 10 — A volta
```
Client (objeto Python)
   → ClientOut (schema Pydantic) transforma em dicionário
   → FastAPI transforma em JSON e responde 201
   → fetch() resolve
   → clientes.js chama loadClients() de novo
   → a tabela é redesenhada COM o cliente novo, vindo do banco
```

---

## B3. Quem é cada arquivo (cola rápida)

| Arquivo | Papel | Analogia |
|---|---|---|
| `frontend/*.html` | Desenha a tela | A vitrine |
| `frontend/js/api.js` | Único que fala com o servidor | O telefone da loja |
| `frontend/js/*.js` | Lógica de cada tela | O vendedor |
| `backend/app/main.py` | Liga tudo, trata erros | A recepção |
| `routers/` | Recebe HTTP | O atendente do balcão |
| `schemas/` | Valida entrada/saída | O conferente |
| `services/` | **As regras** | O gerente que decide |
| `models/` | Define as tabelas | A planta do arquivo |
| `database.py` | Conexão e transação | A chave do arquivo |
| `data/app.db` | **Os dados** | O arquivo físico |

**A frase para a banca:**
> "O router tem 3 linhas. Ele não decide nada — só recebe e repassa. Quem
> decide é o service. Separei assim para poder testar a regra dos 80 graus
> **sem subir servidor web nenhum**."

---

## B4. As 3 barreiras de validação (pergunta certa na banca)

Um dado ruim precisa furar **três** paredes:

```
1. PYDANTIC   "email sem @"        → 422, nem chega no service
2. SERVICE    "e-mail já existe"   → 409, regra de negócio
3. BANCO      UNIQUE / CHECK / FK  → recusa até quem escreve SQL na mão
```

> "Se alguém abrir o arquivo do banco e tentar inserir um status inválido
> direto, o banco recusa. Posso demonstrar agora."

---
---

# PARTE C — COMO MEXER NO BANCO DE DADOS

## C1. Onde o banco está

```
helpdesk-platform/data/app.db
```

É **um arquivo só**. Copiou o arquivo, levou o banco inteiro junto.
Está no `.gitignore` — não vai para o GitHub (é dado, não código).

---

## C2. O console SQL (criei um para você)

O Windows não vem com o programa `sqlite3.exe`, então fiz um substituto.

**Modo interativo:**
```bash
python -m backend.db_shell
```

**Modo comando único:**
```bash
python -m backend.db_shell "SELECT * FROM clients"
```

### Atalhos dentro do console
| Comando | O que faz |
|---|---|
| `.tabelas` | lista as tabelas |
| `.contar` | conta registros de todas as tabelas |
| `.schema clients` | mostra como a tabela foi criada (FK, CHECK, UNIQUE) |
| `.sair` | sai |

---

## C3. Os comandos SQL que você precisa saber

### LER (o mais usado)
```sql
SELECT * FROM clients;
```
```sql
SELECT id, name, company FROM clients;
```
```sql
SELECT * FROM tickets WHERE status = 'ABERTO';
```
```sql
SELECT * FROM tickets ORDER BY opened_at DESC LIMIT 10;
```

### CONTAR
```sql
SELECT COUNT(*) FROM tickets;
```
```sql
SELECT status, COUNT(*) FROM tickets GROUP BY status;
```

### JUNTAR DUAS TABELAS (o JOIN)
```sql
SELECT t.id, t.title, c.company
FROM tickets t
JOIN clients c ON c.id = t.client_id;
```
> Leia assim: *"pegue os chamados e, para cada um, busque o cliente cujo `id`
> é igual ao `client_id` do chamado."* **Isso é o JOIN.**

### INSERIR / ALTERAR / APAGAR
```sql
INSERT INTO clients (name, company, email, phone, created_at)
VALUES ('Teste', 'Empresa X', 'teste@x.com', '11999998888', '2026-09-01 10:00:00');
```
```sql
UPDATE tickets SET status = 'FINALIZADO' WHERE id = 1;
```
```sql
DELETE FROM tickets WHERE id = 1;
```

> ⚠️ **Cuidado:** `UPDATE` e `DELETE` **sem `WHERE`** afetam a tabela inteira.
> Sempre escreva o `WHERE` primeiro.

---

## C4. Demonstrações que impressionam a banca

### Demo 1 — "O dado está mesmo no banco"
Cadastre um cliente pela tela, depois:
```bash
python -m backend.db_shell "SELECT id, name, email FROM clients"
```

### Demo 2 — "As foreign keys funcionam de verdade"
No console interativo, tente criar um chamado para um cliente que não existe:
```sql
INSERT INTO tickets (client_id, title, description, category, priority, status, opened_at)
VALUES (999, 'teste', 'teste', 'Rede', 'ALTA', 'ABERTO', '2026-09-01 10:00:00');
```
**O banco recusa:** `FOREIGN KEY constraint failed`
> "Isso não é o meu código recusando. É o **banco**."

### Demo 3 — "Status inválido não entra nem na marra"
```sql
INSERT INTO tickets (client_id, title, description, category, priority, status, opened_at)
VALUES (1, 'teste', 'teste', 'Rede', 'ALTA', 'BANANA', '2026-09-01 10:00:00');
```
**Recusa:** `CHECK constraint failed: ticket_status_enum`

### Demo 4 — "Mostrar a estrutura da tabela"
```bash
python -m backend.db_shell ".schema tickets"
```
Aparecem as colunas, a FOREIGN KEY e os CHECK. Ótimo para explicar a modelagem.

### Demo 5 — "Ver o SQL que o ORM gera"
No arquivo `.env`, mude:
```
SQL_ECHO=true
```
Reinicie o servidor e navegue. **Cada SQL aparece no terminal.**
> "Isso prova que existe SQL de verdade por trás do ORM."

---

## C5. Programa gráfico (opcional, se quiser ver com o mouse)

Se preferir clicar em vez de digitar SQL, instale o **DB Browser for SQLite**:

```bash
winget install --id DBBrowserForSQLite.DBBrowserForSQLite -e
```

Depois abra o programa e escolha o arquivo `data/app.db`.
Você vê as tabelas, navega pelos dados e roda SQL numa aba própria.

---

## C6. Comandos de administração do banco

| O que quero | Comando |
|---|---|
| Criar as tabelas | `python -m backend.init_db` |
| Ver quantos registros existem | `python -m backend.seed --status` |
| **Esvaziar tudo** (começar do zero) | `python -m backend.seed --wipe` |
| Popular com 20 clientes / 100 chamados | `python -m backend.seed` |
| Apagar e popular de novo | `python -m backend.seed --reset` |

> **Para a apresentação:** o banco está **vazio** agora, do jeito que você
> pediu. Se em algum momento você quiser mostrar os relatórios com volume
> (ranking, tempo médio por categoria), rode `python -m backend.seed` — em 2
> segundos você tem 100 chamados. E `--wipe` esvazia de novo.

---

## C7. "E se eu quebrar o banco?"

Não tem problema. É um arquivo só:

```bash
python -m backend.seed --wipe
```

Se estragar de vez, apague `data/app.db` e rode:
```bash
python -m backend.init_db
```
O banco nasce de novo, vazio e correto. **Nenhum código é perdido** — o código
está no Git e no GitHub.
