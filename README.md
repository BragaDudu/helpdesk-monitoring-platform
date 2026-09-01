# HelpDesk & Monitoring Platform

Plataforma de gestão de TI que unifica os três exercícios da avaliação em uma
única aplicação **full stack real**: cadastro de clientes e chamados, análises
sobre esses chamados, e monitoramento de equipamentos com geração automática
de alertas.

> **Não é mockup.** Backend em FastAPI, banco SQLite persistente, API REST de
> verdade, regras de negócio no servidor e frontend consumindo a API por
> `fetch()`. Os dados sobrevivem a F5, a reinício do servidor e a reboot da
> máquina.

---

## 1. O que é o projeto

| Exercício | Vira o módulo | Endpoints |
|---|---|---|
| 1 — Sistema de chamados | Clientes + Chamados | `/api/clients`, `/api/tickets` |
| 2 — Banco e análise | Analytics | `/api/analytics/*` |
| 3 — Monitoramento | Equipamentos + Leituras + Alertas | `/api/equipments`, `/api/alerts` |

Os três giram em torno de uma entidade central — o **Cliente** — então foram
unificados numa só plataforma em vez de três programas soltos.

## 2. Arquitetura

Arquitetura em **4 camadas**. Cada requisição atravessa:

```
NAVEGADOR (HTML/CSS/JS + fetch)
      │  HTTP / JSON
ROUTERS      (FastAPI)      -> falam HTTP, sem regra de negócio
SCHEMAS      (Pydantic)     -> validam entrada e formatam saída (422 automático)
SERVICES     (Python puro)  -> AQUI moram as regras de negócio
MODELS       (SQLAlchemy)   -> classes que viram tabelas
      │  SQL parametrizado
SQLite  ->  data/app.db  (arquivo em disco)
```

Por que separar? Para poder testar a regra dos 80°C sem subir servidor web, e
para o *seed* reusar o mesmo código que a API usa. **Erros de negócio**
(`NotFoundError`, `ConflictError`) são levantados pelos services sem saber o que
é HTTP; um único handler no `main.py` os traduz em 404/409.

## 3. Tecnologias

| Ferramenta | Para quê |
|---|---|
| **FastAPI** | rotas, validação e Swagger automático |
| **Pydantic** | valida dados na entrada, formata na saída |
| **SQLAlchemy 2.x** | ORM: classes ↔ tabelas, SQL parametrizado (imune a injection) |
| **Uvicorn** | servidor que escuta a porta |
| **SQLite** | banco relacional em arquivo (FK, índices, transações) |
| **pytest** | testes automatizados |
| **pydantic-settings** | lê o `.env` (troca SQLite→PostgreSQL sem mexer no código) |

## 4. Estrutura de pastas

```
helpdesk-platform/
├── backend/
│   ├── app/
│   │   ├── main.py          # cria o app, handlers de erro, serve o frontend
│   │   ├── config.py        # lê o .env (DATABASE_URL, limite de 80°C)
│   │   ├── database.py      # engine, session, PRAGMA das foreign keys
│   │   ├── enums.py         # status válidos + máquina de estados
│   │   ├── exceptions.py    # erros de domínio
│   │   ├── models/          # as 5 tabelas
│   │   ├── schemas/         # contrato JSON (Pydantic)
│   │   ├── services/        # regras de negócio  ← monitoring_service = 80°C
│   │   └── routers/         # endpoints HTTP
│   ├── seed.py              # popula 20 clientes, 100 chamados, etc.
│   ├── init_db.py           # cria as tabelas
│   └── tests/               # 34 testes pytest
├── frontend/                # 5 páginas HTML + css/ + js/
├── data/app.db              # o banco (NÃO versionado)
├── .env.example             # modelo de configuração
├── requirements.txt
└── README.md
```

## 5. Como instalar

Requisito: **Python 3.10+** (testado no 3.10). Na raiz do projeto:

```bash
python -m venv .venv
```

Ativar o ambiente virtual:

```bash
.\.venv\Scripts\Activate.ps1
```

(No Linux/Mac: `source .venv/bin/activate`)

Instalar as dependências:

```bash
pip install -r requirements.txt
```

Criar o arquivo de configuração a partir do modelo:

```bash
copy .env.example .env
```

## 6. Como criar o banco

```bash
python -m backend.init_db
```

Cria as 5 tabelas em `data/app.db`. É idempotente — rodar de novo não apaga
nada. (O servidor também cria as tabelas ao subir, então este passo é
opcional.)

## 7. Como executar o seed

```bash
python -m backend.seed
```

Cria **20 clientes, 100 chamados, 18 equipamentos, ~394 leituras e ~29 alertas**.
Os alertas nascem da regra dos 80°C (o seed chama o mesmo service da API).

- Rodar de novo **não duplica** (avisa que já há dados).
- Para recomeçar do zero: `python -m backend.seed --reset`
- Só ver o que existe: `python -m backend.seed --status`

## 8. Como executar (rodar a aplicação)

```bash
uvicorn backend.app.main:app --reload
```

> ⚠️ Se a porta 8000 já estiver em uso, rode com outra porta:
> `uvicorn backend.app.main:app --reload --port 8010`

## 9. Como executar os testes

```bash
pytest
```

34 testes, banco em memória isolado (não toca no `app.db`).

## 10. Como acessar o frontend

Abra no navegador: **http://localhost:8000**

O FastAPI serve o próprio frontend (mesma origem → sem problema de CORS).
Páginas: Dashboard, Clientes, Chamados, Equipamentos, Alertas.

## 11. Documentação da API (Swagger)

Com o servidor no ar:

- **Swagger UI** (interativo): http://localhost:8000/docs
- **ReDoc** (leitura): http://localhost:8000/redoc

Gerados automaticamente pelo FastAPI a partir dos schemas.

## 12. Modelagem do banco

5 tabelas, relacionamentos 1:N (exceto leitura→alerta, que é 1:0..1):

```
clients ──1:N── tickets
clients ──1:N── equipments ──1:N── equipment_readings ──1:1── alerts
                    └────────1:N──────────────────────────── alerts
```

Decisões principais:

- **Normalização**: o chamado guarda só `client_id`, nunca uma cópia do nome/
  e-mail. Se o cliente muda de e-mail, altera-se uma linha e todos os chamados
  refletem o novo dado.
- **`closed_at` pode ser NULL**: um chamado aberto não tem data de fechamento.
  A ausência é informação; preencher com data falsa quebraria o tempo médio.
- **`alerts.reading_id` é UNIQUE**: uma leitura gera no máximo um alerta. Se
  duas requisições chegarem juntas, o banco recusa a segunda. Garantia no banco,
  não em `if` do Python.
- **`ON DELETE RESTRICT`**: não se apaga cliente com histórico (devolve 409).
- **CHECK constraints** nos enums: o banco recusa status inválido mesmo escrito
  direto no SQLite.
- **Foreign keys ativas**: o SQLite ignora FKs por padrão; ligamos com
  `PRAGMA foreign_keys=ON` a cada conexão (ver `database.py`).

**Datas**: tudo em UTC no banco; a API devolve ISO-8601 com sufixo `Z`; só o
JavaScript converte para o fuso local ao exibir.

## 13. Principais regras de negócio

1. **Temperatura > 80°C gera alerta** (`services/monitoring_service.py`). Roda no
   backend porque o navegador não é a única porta de entrada (um sensor IoT
   chama a API direto). Leitura e alerta gravados na **mesma transação**.
2. **Máquina de estados do chamado** (`enums.py`): ABERTO ↔ EM_ANDAMENTO →
   FINALIZADO, sem volta. Transição inválida → 409. Ao finalizar, o servidor
   carimba `closed_at`.
3. **Deleção protegida**: cliente com chamados/equipamentos não pode ser
   apagado.

## 14. Códigos HTTP usados

`200` ok · `201` criado · `204` sem conteúdo (delete) · `400/404` não encontrado ·
`409` conflito (e-mail duplicado, transição inválida) · `422` dado inválido ·
`500` erro interno (com stack trace só no log, nunca na resposta).

## 15. Possíveis melhorias futuras

- **Alembic** para migrações (hoje `create_all` basta porque o schema é fixo).
- **PostgreSQL**: trocar `DATABASE_URL` no `.env` e instalar o driver; o código
  não muda (a aritmética de datas já trata os dois dialetos).
- **Autenticação** (JWT) — omitida de propósito por não ser pedida.
- **Paginação com envelope** (`{items, total, page}`) em vez de lista pura.
- **Alerta → chamado**: uma temperatura crítica poderia abrir um chamado
  automaticamente, ligando os dois módulos.
