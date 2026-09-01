# Conceitos para a apresentação

Guia de estudo. Começa pelo **básico que derruba** (tipo "localStorage vs
localhost") e vai até os conceitos do projeto. Cada item tem: **o que é**,
**analogia** e **como responder em uma frase**.

---

# PARTE 1 — O básico que derruba

## 1. localhost × localStorage

Foi a pergunta que te pegou. São coisas **completamente diferentes** que só se
parecem no nome.

| | **localhost** | **localStorage** |
|---|---|---|
| O que é | Um **endereço de rede** | Uma **gavetinha do navegador** |
| Onde vive | Na rede (TCP/IP) | Dentro do navegador do usuário |
| Serve para | Falar com um servidor que roda na **sua própria máquina** | Guardar dados no navegador (ex.: tema escuro escolhido) |
| Analogia | É o "meu próprio endereço", como dizer "estou em casa" | É uma gaveta na mesa **daquele** usuário |
| No projeto | ✅ Uso — `http://localhost:8000` é o meu servidor | ❌ **NÃO uso** — os dados ficam no banco |

**Resposta de uma frase:**
> "`localhost` é um endereço de rede que aponta para a minha própria máquina —
> é por ele que o navegador acha o meu servidor. `localStorage` é um espaço de
> armazenamento **dentro do navegador**, que guarda dado só naquele computador.
> Eu **não** uso localStorage: se usasse, os dados existiriam só no seu
> navegador e sumiriam em outro computador. Meus dados estão no SQLite, no
> servidor."

**Por que isso importa no seu projeto:** o enunciado proibia usar localStorage
como banco. Saber a diferença mostra que você entendeu *por que* era proibido.

> Curiosidade que impressiona: `localhost` sempre aponta para o IP `127.0.0.1`,
> que é o "endereço de retorno" reservado para a própria máquina.

---

## 2. O que é uma porta (o `:8000`)

Um computador tem **um** endereço (IP), mas roda **vários** programas de rede
ao mesmo tempo. A porta diz **para qual programa** a mensagem vai.

- Analogia: o IP é o **endereço do prédio**; a porta é o **número do
  apartamento**.
- `http://localhost:8000` = "na minha máquina, apartamento 8000".

**Por que eu uso a 8010:** já existe outro sistema seu ocupando a 8000. Duas
aplicações não podem usar a mesma porta — dá erro "address already in use".

---

## 3. Frontend × Backend

| | Frontend | Backend |
|---|---|---|
| Onde roda | No **navegador** do usuário | No **servidor** |
| Linguagem aqui | HTML, CSS, JavaScript | Python (FastAPI) |
| Responsável por | Mostrar a tela, capturar cliques | Regras, validação, banco |
| Quem controla | O **usuário** (ele pode editar!) | **Você** |

**A frase que resume tudo:**
> "O frontend é o que o usuário **vê**. O backend é o que o usuário **não pode
> mexer**. Por isso as regras ficam no backend."

---

## 4. O que é um servidor

Um **programa** que fica ligado esperando pedidos e respondendo. Não é
necessariamente um computador especial — no seu projeto, o servidor é o
`uvicorn` rodando no seu notebook.

> "Servidor é o programa que fica escutando numa porta e respondendo
> requisições. Aqui é o Uvicorn rodando o FastAPI."

---

## 5. O que é HTTP (requisição e resposta)

O "idioma" que navegador e servidor usam. Sempre funciona em **par**:

```
REQUISIÇÃO  →   GET /api/clients          (o navegador PEDE)
RESPOSTA    ←   200 OK + [{...}, {...}]    (o servidor RESPONDE)
```

Toda requisição tem: **método** (GET/POST...), **caminho** (`/api/clients`),
opcionalmente um **corpo** (o JSON enviado).
Toda resposta tem: **código de status** (200, 404...) e geralmente um **corpo**.

---

## 6. Os métodos HTTP (GET, POST, PATCH, DELETE)

| Método | Significa | Muda o banco? | No projeto |
|---|---|---|---|
| **GET** | "me dá" | ❌ Não | Listar clientes |
| **POST** | "cria isto" | ✅ Sim | Cadastrar cliente |
| **PATCH** | "muda **só** este campo" | ✅ Sim | Alterar status do chamado |
| **PUT** | "substitui **tudo**" | ✅ Sim | *(não uso)* |
| **DELETE** | "apaga" | ✅ Sim | Excluir cliente |

**Por que PATCH e não PUT no status?**
> "PUT substitui o recurso inteiro — eu teria que reenviar título, descrição,
> categoria, e se esquecesse um campo ele seria apagado. PATCH altera só o que
> mandei. Como só quero mudar o status, PATCH é o verbo correto."

---

## 7. Códigos de status HTTP

| Código | Significa | Quando uso |
|---|---|---|
| **200** OK | Deu certo | GET, PATCH |
| **201** Created | Criei algo novo | POST de cliente/chamado |
| **204** No Content | Deu certo, sem resposta | DELETE |
| **404** Not Found | Não existe | Cliente 999 |
| **409** Conflict | Existe mas conflita | E-mail duplicado; finalizado→aberto |
| **422** Unprocessable | Dado mal formado | E-mail sem @, prioridade inválida |
| **500** Internal Error | Erro meu, do servidor | Bug inesperado |

**A pegadinha 409 × 422** (podem te perguntar):
> "422 é 'o dado que você mandou está errado'. 409 é 'o dado está certo, mas
> conflita com o estado atual'. Tentar mudar FINALIZADO para ABERTO é 409,
> porque 'ABERTO' é um status válido — o problema é a transição."

---

## 8. O que é uma API

API = a **porta de entrada** do backend. Um conjunto de endereços (endpoints)
que outros programas chamam.

- Analogia: o **cardápio + o balcão** do restaurante. Você não entra na cozinha;
  você pede pelo balcão, no formato que ele aceita.
- **REST** é o estilo que usei: cada coisa é um "recurso" com URL própria
  (`/api/clients`, `/api/tickets`) e você usa os métodos HTTP nela.

---

## 9. O que é JSON

O **formato de texto** em que os dados viajam. Parece um objeto JavaScript:

```json
{ "id": 1, "name": "Ana", "company": "Alfa" }
```

> "JSON é como eu escrevo os dados para mandar pela internet. O Python
> transforma o objeto dele em JSON, o JavaScript transforma JSON em objeto
> dele. É o idioma comum entre os dois."

---

## 10. O que é `fetch()`

A função do JavaScript que **faz a requisição HTTP** a partir do navegador.

```js
const clientes = await fetch('/api/clients').then(r => r.json());
```

> "`fetch` é o comando do JavaScript que vai buscar dados no servidor sem
> recarregar a página."

---

## 11. URL, caminho e query string

```
http://localhost:8000/api/tickets?status=ABERTO&priority=ALTA
└─┬──┘ └────┬───────┘└────┬─────┘ └──────────┬──────────────┘
protocolo  host:porta   caminho          query string (filtros)
```

A **query string** (depois do `?`) leva os filtros. No projeto, ela vira
cláusula `WHERE` no banco.

---

## 12. "O que acontece se eu der F5?"

**Pergunta quase certa na banca.** A resposta:

> "A página recarrega e o JavaScript refaz os `fetch`. Os dados voltam do
> banco. **Nada se perde**, porque nada estava guardado no navegador — está
> tudo no arquivo `app.db`, no servidor. Se eu tivesse guardado num array de
> JavaScript ou no localStorage, o F5 apagaria tudo."

Você pode **demonstrar**: cadastra um cliente, dá F5, ele continua lá.

---

## 13. Memória × Disco (por que o dado "some")

| | Memória (RAM) | Disco (arquivo) |
|---|---|---|
| Dura | Enquanto o programa roda | Para sempre |
| Exemplo ruim | array JavaScript, banco `:memory:` | — |
| Exemplo bom | — | `data/app.db` |

> "Um array em JavaScript vive na memória: fechou o navegador, acabou. O SQLite
> é um **arquivo em disco**: posso desligar o computador que ele continua lá."

---

## 14. Git × GitHub

| | **Git** | **GitHub** |
|---|---|---|
| O que é | Um **programa** que roda na sua máquina | Um **site** |
| Faz o quê | Controla versões do código (histórico) | Hospeda repositórios Git na nuvem |
| Analogia | O "salvar com histórico" do seu projeto | O Google Drive dos repositórios |

Termos:
- **repositório** = a pasta do projeto com histórico
- **commit** = uma "foto" do projeto num momento, com mensagem
- **push** = mandar os commits para o GitHub
- **`.gitignore`** = lista do que **não** deve ser versionado

> "No meu `.gitignore` estão o `data/app.db` e o `.env`. O banco é *estado*,
> não código — versionar um arquivo binário que muda a cada INSERT geraria
> conflito e ainda vazaria dados de clientes. O `.env` pode ter senhas."

---

## 15. Ambiente virtual (`.venv`) e `pip`

- **pip** = o instalador de bibliotecas do Python.
- **`.venv`** = uma pasta com um Python **isolado** só para este projeto.

> "Sem ambiente virtual, todas as bibliotecas iriam para o Python do sistema e
> dois projetos poderiam brigar por versões diferentes. O `.venv` isola. O
> `requirements.txt` lista as versões exatas, para o projeto rodar igual em
> qualquer máquina."

---

## 16. Terminal / CLI

Interface de texto para dar comandos. `uvicorn ...`, `pytest`, `git commit`.
CLI = *Command Line Interface*.

---

## 17. O que é o DOM

A **árvore de elementos** da página, como o JavaScript enxerga o HTML.
Quando o `clientes.js` monta as linhas da tabela, ele está **manipulando o DOM**.

---

## 18. Síncrono × Assíncrono (`async` / `await`)

Buscar dados na rede demora. Se o JavaScript esperasse parado, a página
**travaria**.

- **`async`** marca uma função que pode esperar.
- **`await`** = "espera esta resposta chegar, mas **libera** a página enquanto
  isso".

> "`await fetch(...)` significa: manda o pedido, libera o navegador para
> continuar respondendo, e quando a resposta chegar, segue daqui."

---

## 19. O que é CORS

Regra de segurança do navegador: por padrão, uma página de um endereço **não
pode** chamar outro endereço.

> "No meu projeto o FastAPI serve o próprio frontend, então tudo roda em
> `localhost:8000` — **mesma origem**, sem problema de CORS. Se eu abrisse o
> HTML com duplo clique (`file:///`), a origem seria diferente e o navegador
> bloquearia as chamadas."

---

## 20. Cache do navegador

O navegador guarda cópias de CSS/JS para não baixar de novo. Por isso às vezes
você muda o CSS e **nada acontece** — precisa recarregar forçado
(**Ctrl + Shift + R**). *(Isso aconteceu de verdade durante o desenvolvimento.)*

---

# PARTE 2 — Banco de dados

## 21. Banco de dados × arquivo comum

> "SQLite **é** um arquivo, mas não é um arquivo qualquer: ele entende SQL, tem
> chaves estrangeiras, índices e transações. A diferença para o PostgreSQL é
> que o SQLite é **embutido** (uma biblioteca dentro do meu programa) e o
> Postgres é um **servidor separado**."

## 22. O que é SQL

A linguagem para conversar com bancos relacionais:
`SELECT` (ler), `INSERT` (criar), `UPDATE` (alterar), `DELETE` (apagar).

## 23. O que é ORM (e por que uso)

ORM = *Object-Relational Mapper*. Traduz **classes Python ↔ tabelas SQL**.

```python
db.query(Client).filter(Client.id == 5)   # eu escrevo isto
SELECT * FROM clients WHERE id = ?        # o SQLAlchemy gera isto
```

> "O ORM me deixa trabalhar com objetos Python em vez de escrever SQL na mão, e
> ele gera **SQL parametrizado**, o que torna SQL Injection impossível."

## 24. Chave primária × chave estrangeira

- **PK (primária)**: identifica **unicamente** cada linha. `clients.id`.
- **FK (estrangeira)**: aponta para a PK de outra tabela. `tickets.client_id`.

> "A foreign key é uma coluna que aponta para outra tabela, **e o banco garante
> que o valor apontado existe**. Se eu tentar criar um chamado com
> `client_id = 999` e esse cliente não existir, o banco recusa."

**Pegadinha que eu tratei:** o SQLite ignora FK por padrão! Tive que ligar com
`PRAGMA foreign_keys=ON` (está em `database.py`).

## 25. Normalização (a pergunta "por que 2 tabelas?")

> "O chamado guarda só o `client_id`, nunca uma cópia do nome ou e-mail do
> cliente. Se copiasse: o dia que o cliente trocasse de e-mail, eu teria 100
> linhas para atualizar, e se falhasse no meio o banco ficaria com duas versões
> da verdade. Guardando só o id, o dado do cliente existe em **um** lugar."

## 26. Índice

Como o índice remissivo de um livro: em vez de ler as 20.000 linhas, o banco
vai direto. Custa espaço e deixa o INSERT um pouco mais lento — por isso só
crio onde realmente se busca.

## 27. Constraints (as travas do banco)

| Constraint | Garante | No projeto |
|---|---|---|
| `NOT NULL` | campo obrigatório | `title` |
| `UNIQUE` | não repete | `clients.email`, `alerts.reading_id` |
| `CHECK` | valor dentro de uma lista/faixa | status válido, temperatura −50..200 |
| `FOREIGN KEY` | o alvo existe | `tickets.client_id` |

## 28. `NULL` — e por que `closed_at` pode ser nulo

`NULL` = "não existe valor", diferente de zero ou de texto vazio.

> "Um chamado aberto genuinamente **não tem** data de fechamento. Se eu
> preenchesse com uma data inventada, o cálculo de tempo médio de resolução
> ficaria errado. A ausência de dado **é** informação."

## 29. Transação, commit e rollback

Uma transação é um bloco de operações **tudo-ou-nada**.

```python
db.add(leitura)
db.flush()     # gera o id, mas NADA está confirmado ainda
db.add(alerta)
db.commit()    # AGORA os dois viram permanentes, JUNTOS
```

> "É impossível existir no banco uma leitura de 90 graus sem o alerta
> correspondente. Se qualquer coisa falhar no meio, a transação inteira é
> desfeita (rollback)."

**`flush` × `commit`**: `flush` manda o comando ao banco dentro da transação
(gera o id); `commit` confirma de verdade.

## 30. `JOIN` × `LEFT JOIN`

- **JOIN (INNER)**: só devolve o que existe **nas duas** tabelas.
- **LEFT JOIN**: mantém **todos** da esquerda, mesmo sem par à direita.

> "No relatório de chamados por cliente eu uso LEFT JOIN, senão um cliente que
> nunca abriu chamado **desapareceria** do relatório — e 'esse cliente nunca
> abriu chamado' é justamente uma informação valiosa."

## 31. Migrations (e por que não usei Alembic)

> "`create_all()` cria tabelas que não existem, mas não **altera** tabelas
> existentes. Quando o schema evoluir em produção, entra o Alembic, que gera
> scripts de migração versionados. Não usei agora porque o schema nasce fechado
> e seria mais uma ferramenta para defender sem ganho real."

---

# PARTE 3 — Conceitos do projeto

## 32. Arquitetura em camadas

```
Router   → fala HTTP, não tem regra    (1 a 3 linhas por função)
Schema   → valida entrada / formata saída  (Pydantic)
Service  → AQUI estão as regras de negócio
Model    → vira tabela                  (SQLAlchemy)
```

> "Separei para poder testar a regra dos 80 graus **sem subir servidor web**, e
> para o script de seed reusar exatamente o mesmo código que a API usa."

## 33. Onde está a regra dos 80°C (a pergunta principal)

`backend/app/services/monitoring_service.py`, função `register_reading`, linha
`if payload.temperature > threshold:`

**Os 3 motivos de estar no backend** (decore estes):
1. **O navegador não é a única porta de entrada** — um sensor IoT chama a API
   direto, sem navegador. Se a regra estivesse no JavaScript, não rodaria.
2. **O código do cliente é controlável pelo usuário** — qualquer um abre o
   DevTools e desliga o JavaScript.
3. **Consistência** — se houvesse app mobile + script de importação, cada um
   reimplementaria a regra e algum usaria `>=` em vez de `>`.

> "O frontend mostra em vermelho, mas ele só **lê** o campo
> `critical_condition_detected`. Ele nunca compara a temperatura com 80."

## 34. Máquina de estados

```
ABERTO ⇄ EM_ANDAMENTO → FINALIZADO ✗ (não volta)
```

> "Não é um monte de `if`. É um dicionário em `enums.py` que diz, para cada
> status, quais destinos são permitidos. Se vocês quiserem permitir reabrir
> chamados agora, é **uma linha**."

## 35. Validação em 3 camadas

1. **Pydantic** → 422 antes de chegar no service
2. **Service** → regra de negócio (404, 409)
3. **Banco** → CHECK/UNIQUE/FK (última defesa)

> "Se alguém abrir o SQLite e tentar inserir um status inválido na mão, o banco
> recusa. Posso demonstrar."

## 36. Enum

Lista fechada de valores válidos.

> "Se status fosse texto livre, entraria 'aberto', 'ABERTO ', 'Aberto', e a
> consulta 'quantos chamados abertos?' passaria a mentir."

## 37. Datas: UTC e fuso horário

> "Tudo no banco é **UTC**. A API devolve com sufixo `Z` (padrão ISO-8601 para
> UTC). Só o JavaScript converte para o fuso do usuário na hora de exibir. Se
> eu guardasse horário de Brasília, o histórico ficaria errado no horário de
> verão e o cálculo de tempo médio daria resultado absurdo."

## 38. SQL Injection

Ataque em que o usuário digita SQL num campo de texto.

> "É impossível aqui porque o SQLAlchemy manda todo valor como **parâmetro**
> (`?`), nunca concatenado na string. Se alguém buscar por `' OR 1=1 --`, isso
> é tratado como **texto a procurar**, não como comando."

## 39. XSS

Ataque em que o usuário injeta `<script>` num campo e ele **executa** na página.

> "Toda vez que insiro dado do banco no HTML, passo pela função `escapeHtml`,
> que troca `< > &` por entidades. O texto aparece como texto, nunca como
> código."

## 40. Problema N+1

> "Listar 100 chamados poderia gerar **101** consultas: uma para os chamados e
> uma por chamado para buscar o cliente. Com `joinedload`, o SQLAlchemy faz um
> JOIN e traz tudo em **1** consulta."

## 41. Idempotência

Repetir a mesma operação dá o mesmo resultado.

> "Se o usuário clicar duas vezes em 'Finalizar', a segunda chamada devolve 200
> sem efeito, e a data do primeiro fechamento é preservada. PATCH tem que ser
> idempotente."

## 42. Race condition (a pergunta dos 2 alertas simultâneos)

> "A coluna `alerts.reading_id` é **UNIQUE**. Se duas requisições tentarem criar
> o alerta ao mesmo tempo, a segunda viola a constraint e o banco recusa. A
> garantia está **no banco**, não num `if` do Python — um `if` teria uma janela
> entre 'verificar' e 'inserir' em que as duas passariam."

## 43. Variável de ambiente / `.env`

Configuração que fica **fora** do código.

> "O limite de 80 graus e a URL do banco estão no `.env`. Isso permite trocar
> SQLite por PostgreSQL mudando uma linha, e evita que senha vá para o Git."

## 44. Como migraria para PostgreSQL

> "Trocar `DATABASE_URL` no `.env`, instalar o driver, rodar a criação do
> schema. O código da aplicação não muda porque o SQLAlchemy abstrai o dialeto.
> A única parte que precisou de tratamento foi a subtração de datas — SQLite usa
> `julianday`, Postgres usa `EXTRACT(EPOCH)` — e isolei isso numa função só."

---

# PARTE 4 — Simulado rápido

Cubra a resposta e tente responder:

1. Diferença entre localhost e localStorage? → *#1*
2. O que acontece se eu der F5? → *#12*
3. Diferença entre GET e POST? → *#6*
4. Por que PATCH e não PUT? → *#6*
5. O que é uma foreign key? → *#24*
6. Por que Client e Ticket são tabelas diferentes? → *#25*
7. Onde está a regra dos 80°C? Por que aí? → *#33*
8. E se o equipamento não existir? → 404, o service checa antes; a FK garante
9. E se dois alertas forem criados ao mesmo tempo? → *#42*
10. Por que SQLite? Não é banco de verdade? → *#21*
11. Como migraria para PostgreSQL? → *#44*
12. Por que não guardar os chamados no frontend? → *#3, #13*
13. Como sua API sabe qual cliente tem tal chamado? → `client_id` (FK) + JOIN
14. Como você testou? → 34 testes pytest, banco isolado em memória
15. Por que 409 e não 422? → *#7*
16. Por que não usou React? → volume pequeno, e eu consigo explicar cada linha
17. O que é uma porta? → *#2*
18. Git e GitHub são a mesma coisa? → *#14*

---

## Se travar numa pergunta

Não invente. Diga:
> "Não sei responder isso de cabeça, mas sei **onde** está no código — posso
> abrir e explicar."

E abra o arquivo. Saber navegar o próprio projeto vale mais do que decorar.
