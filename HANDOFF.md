# HANDOFF — contexto completo do projeto

> **Como usar:** cole este arquivo inteiro no início de um chat novo. Ele
> contém tudo que foi feito, o estado atual, os pontos fracos identificados e
> o que falta fazer. Assim o assistente não precisa reler a conversa toda.

---

## 0. CONTEXTO DA SITUAÇÃO

- **Quem sou:** Guilherme Braga (GitHub: BragaDudu). Estou fazendo uma
  **avaliação técnica** que será julgada por **3 pessoas, incluindo meu tio**.
- **Empresa avaliadora:** Revosys.
- **Apresentação:** amanhã de manhã.
- **Meu nível:** iniciante. Preciso **entender e conseguir explicar** tudo —
  não adianta ter código bonito que eu não sei defender.
- **A banca pode:** abrir o código, pedir para eu explicar uma função, pedir
  para eu alterar uma regra ao vivo, consultar o banco, testar a API.

---

## 1. O QUE FOI CONSTRUÍDO

**HelpDesk & Monitoring Platform** — plataforma de gestão de TI que unifica os
3 exercícios da avaliação em um sistema só.

- **Pasta:** `C:\Users\Gui\Desktop\Duzinho\helpdesk-platform`
- **GitHub (público):** https://github.com/BragaDudu/helpdesk-monitoring-platform
- **Porta:** 8010 (a 8000 está ocupada por outro sistema meu, o "Revosys")

### Os 3 exercícios viraram 3 módulos

| Exercício | Módulo | Endpoints |
|---|---|---|
| 1 — Sistema de chamados | Clientes + Chamados | `/api/clients`, `/api/tickets` |
| 2 — Banco e análise | Analytics (6 consultas) | `/api/analytics/*` |
| 3 — Monitoramento | Equipamentos + Leituras + Alertas | `/api/equipments`, `/api/alerts` |

**Motivo da unificação:** os três giram em torno da mesma entidade — o
**Cliente**. Ele abre chamados, esses chamados geram dados para analisar, e ele
tem equipamentos monitorados.

### Stack
Python 3.10 (não havia 3.12 na máquina) · FastAPI · SQLAlchemy 2.x · Pydantic v2
· SQLite · Uvicorn · pytest · HTML/CSS/JS puro (sem framework)

### Arquitetura em 4 camadas
```
NAVEGADOR (HTML/CSS/JS + fetch)
   ↓ HTTP/JSON
ROUTERS   (FastAPI)     → falam HTTP, sem regra (1-3 linhas por função)
SCHEMAS   (Pydantic)    → validam entrada/saída → 422 automático
SERVICES  (Python)      → AQUI moram as regras de negócio
MODELS    (SQLAlchemy)  → viram tabelas
   ↓ SQL parametrizado
SQLite → data/app.db (arquivo em disco)
```

### Banco: 5 tabelas
```
clients ──1:N── tickets
clients ──1:N── equipments ──1:N── equipment_readings ──1:0..1── alerts
                    └──────1:N──────────────────────────────────── alerts
```

Decisões de modelagem:
- `tickets.client_id` é FK — **não** copia nome/e-mail (normalização)
- `closed_at` pode ser NULL (chamado aberto não tem data de fechamento)
- `alerts.reading_id` é **UNIQUE** — uma leitura gera no máximo 1 alerta
  (protege contra race condition; a garantia está no banco, não num `if`)
- `ON DELETE RESTRICT` — não apaga cliente com histórico (409)
- CHECK constraints nos enums (status inválido é recusado pelo próprio banco)
- **`PRAGMA foreign_keys=ON`** — o SQLite ignora FK por padrão; foi preciso ligar

### As 3 regras de negócio principais
1. **Temperatura > 80°C gera alerta** (`services/monitoring_service.py`, função
   `register_reading`, linha com `if payload.temperature > threshold:`).
   Leitura e alerta gravados na **mesma transação** (flush + commit único).
2. **Máquina de estados do chamado** (`enums.py`, dict `TICKET_STATUS_TRANSITIONS`):
   ABERTO ↔ EM_ANDAMENTO → FINALIZADO (não volta). Transição inválida → 409.
3. **Deleção protegida**: cliente com chamados/equipamentos não pode ser apagado.

### Números finais
- 32 rotas REST · 34 testes pytest (todos passando) · 5 tabelas · ~60 arquivos
- Códigos HTTP corretos: 200/201/204/404/409/422/500

---

## 2. ESTADO ATUAL DO SISTEMA

- **Banco propositalmente VAZIO** (comando `--wipe`) — eu quis inserir os dados
  manualmente para testar e apresentar partindo do zero.
- Dados que eu inseri testando: 1 cliente (Eduardo Ciqueira / Escola Ântonio
  Padilha), 1 chamado, 1 equipamento (EQP-011), 2 leituras, 2 alertas.
- O seed continua disponível: `python -m backend.seed` cria 20 clientes e 100
  chamados em 2 segundos, se eu quiser mostrar os relatórios com volume.

### Comandos
| O que | Comando |
|---|---|
| Subir o sistema | duplo clique em `INICIAR.bat` |
| Abrir console SQL | duplo clique em `BANCO.bat` |
| Rodar testes | duplo clique em `TESTES.bat` |
| Esvaziar o banco | `python -m backend.seed --wipe` |
| Popular (20 clientes/100 chamados) | `python -m backend.seed` |
| Ver contagem | `python -m backend.seed --status` |
| Consulta rápida | `python -m backend.db_shell "SELECT * FROM clients"` |

Acessos: sistema em http://localhost:8010 · Swagger em http://localhost:8010/docs

---

## 3. DOCUMENTOS JÁ CRIADOS (estão na pasta e no GitHub)

| Arquivo | Conteúdo |
|---|---|
| `README.md` | Documentação técnica completa (15 seções) |
| `APRESENTACAO.md` | Colinha: comandos, roteiro de 5 min, frases-chave |
| `CONCEITOS.md` | **44 conceitos** do básico ao avançado + simulado de 18 perguntas |
| `GUIA_COMPLETO.md` | Pitch de venda + fluxo de dados arquivo por arquivo + banco |
| `BANCO_DE_DADOS.md` | Aula completa de banco: SQL, JOIN, como abrir, 6 demos |
| `HANDOFF.md` | Este arquivo |

**Não preciso que esses documentos sejam reescritos** — já existem e estão bons.

---

## 4. BUGS REAIS ENCONTRADOS E CORRIGIDOS DURANTE O DESENVOLVIMENTO

São boas histórias para a apresentação (mostram método, não sorte):

1. **CHECK constraints não foram gerados.** No SQLAlchemy 2.x, `create_constraint`
   do tipo Enum vem `False` por padrão. Só descobri porque **li o SQL real**
   gerado, em vez de confiar no código.
2. **Modais apareciam abertos.** O CSS `.modal { display: flex }` tinha
   prioridade sobre o atributo `hidden` do HTML. Corrigido com
   `[hidden] { display: none !important; }`.
3. **Equipamento OFFLINE virava ONLINE no seed.** O `register_reading`
   sincroniza o status do equipamento com o da leitura (feature correta), e
   isso sobrescrevia o OFFLINE plantado.
4. **`db_shell` quebrava sem o `.venv` ativado** (`ModuleNotFoundError:
   pydantic_settings`). Reescrito para usar só a biblioteca padrão.
5. **Acentos quebrados no console** (`Escola �ntonio`). Corrigido forçando UTF-8.
6. **Porta 8000 ocupada** por outro sistema meu. Uso a 8010.

---

## 5. MINHAS DÚVIDAS DE HOJE (e as respostas)

### 5.1 localhost × localStorage (meu tio perguntou e eu não soube)
- **localhost** = endereço de rede que aponta para a **minha própria máquina**
  (sempre o IP 127.0.0.1). É por ele que o navegador acha meu servidor.
- **localStorage** = uma **gaveta dentro do navegador**, guarda dado só naquele
  computador.
- São coisas totalmente diferentes que só se parecem no nome. Eu **não** uso
  localStorage — o enunciado proibia usá-lo como banco, porque o dado sumiria
  em outro computador.

### 5.2 O que é um array
Uma **lista dentro de um programa**, guardada na **memória**. Ex.:
`const clientes = ["Ana", "Bruno"]`. O enunciado proibia usar array como banco
porque memória se esvazia quando o programa fecha. Família de conceitos:

| Onde guardar | Dura quanto | Usei? |
|---|---|---|
| Array de JavaScript | Só com a aba aberta | ❌ (correto) |
| localStorage | Só naquele navegador | ❌ (correto) |
| Banco em arquivo | Para sempre | ✅ (correto) |

### 5.3 Posso inserir dados direto no banco?
**Consigo, mas não devo — e isso foi PROVADO com experimento:**

| | Leituras | Alertas |
|---|---|---|
| Estado inicial | 1 | 1 |
| `INSERT` direto no banco, 95°C | 2 ✅ | **1 ❌ nenhum alerta** |
| Mesma 95°C pela API | 3 ✅ | **2 ✅ alerta criado** |

**Motivo:** a regra de negócio mora na **aplicação**; o banco só guarda dados e
garante integridade estrutural. Inserindo direto, pulo a regra — a leitura de
95°C entra mas o alerta não nasce, e o sistema fica mentindo que está tudo bem.

Mas o banco **ainda** barra o que é estruturalmente inválido (testado):
- `INSERT` com `client_id=999` → `FOREIGN KEY constraint failed`
- `UPDATE status='BANANA'` → `CHECK constraint failed`

### 5.4 Como abrir/editar o banco
Três formas: (1) `BANCO.bat` / `python -m backend.db_shell`; (2) VS Code com a
extensão **SQLite Viewer** — clicar no arquivo `data/app.db`; (3) DB Browser for
SQLite (`winget install DBBrowserForSQLite.DBBrowserForSQLite`).

### 5.5 Erro que tive: ModuleNotFoundError
Rodei com `C:\Python310\python.exe` (Python do sistema) em vez do
`.venv\Scripts\python.exe` (Python do projeto). As bibliotecas só existem no
`.venv`. **Conceito de ambiente virtual:** cada projeto tem suas bibliotecas
isoladas, senão dois projetos brigariam por versões diferentes. Solução: usar
os `.bat`, ou ativar com `.venv\Scripts\activate`.

---

## 6. SABATINA — ONDE PAREI E MEUS PONTOS FRACOS

Estávamos simulando a banca. **Foram 8 perguntas; parei na pergunta 9.**

### Histórico das respostas

| # | Pergunta | Como eu fui |
|---|---|---|
| 1 | O que é o projeto? Por que unificou os 3 exercícios? | ⚠️ Vago. Só falei de chamados (esqueci analytics e monitoramento) e justifiquei com "mais fácil e melhor", sem argumento técnico |
| 2 | Onde fica gravado o cliente? | ❌ **ERRO GRAVE**: disse "não instalei banco porque vai direto no VS Code". VS Code é só um editor, não guarda dado |
| 3 | Se desligar o computador, o que acontece? | ⚠️ Conceito certo, frase fraca ("adicionei uma forma") — é simplesmente arquivo em disco |
| 4 | Por que não tem campo de data no chamado? | ⚠️ Intuição certa, faltou o motivo de segurança (falsificar o relatório de tempo médio) |
| 5 | Por que FINALIZADO não volta pra ABERTO? | ❌ Confundi com "não confiar no frontend". Motivo real: `closed_at` seria carimbado e ficaria contraditório, quebrando o cálculo de tempo médio |
| 6 | O que é uma API? | ❌ **Confundi API com SQL** — disse que API "é a linguagem que o banco entende". API = endereços HTTP do meu servidor; SQL = linguagem do banco |
| 7 | Onde está a regra dos 80°C? | ❌ Não sabia. Aprendi a navegar: `Ctrl+P` → `monitoring_service` → `Ctrl+F` → `temperature >` |
| 8 | 80.0 exato gera alerta? | ✅ **Acertei** (não gera — comparação é `>`, não `>=`) |
| 9 | Por que `alerts.reading_id` é UNIQUE? | ⏸️ **NÃO RESPONDIDA — começar daqui** |

### Meus pontos fracos identificados (preciso treinar)
1. **Confundo termos parecidos**: API × SQL, VS Code × banco de dados
2. **Não sei navegar o código** — preciso praticar achar arquivos com `Ctrl+P`
3. **Respondo vago** — falo "é melhor assim" sem dar o motivo técnico
4. **Esqueço de mencionar os 3 módulos** quando descrevo o projeto

---

## 7. O QUE FALTA FAZER (para o chat de amanhã)

1. **Continuar a sabatina da pergunta 9** (`reading_id` UNIQUE / race condition),
   seguindo até a 15. Formato: uma pergunta por vez, feedback honesto do que
   faltou, depois a "versão afiada" da resposta.
2. **Treinar os 4 pontos fracos** da seção 6, principalmente API × SQL e
   navegação no código.
3. **Ensaiar o roteiro de demonstração** (está no `GUIA_COMPLETO.md`, Parte A6):
   8 atos, partindo do banco vazio, terminando com reiniciar o servidor.

---

## 8. AS FRASES QUE PRECISO DECORAR

**Abertura:**
> "É uma plataforma de gestão de TI com três módulos: cadastro de clientes e
> chamados, análises sobre esses chamados, e monitoramento de equipamentos com
> alerta automático. Unifiquei os três porque giram em torno da mesma entidade
> — o Cliente. O cliente que abre chamado é o mesmo que tem o equipamento."

**A regra dos 80°C (3 motivos de estar no backend):**
> "Primeiro: o navegador não é a única porta de entrada — um sensor IoT chama
> essa API sem navegador nenhum. Segundo: JavaScript é controlável pelo usuário,
> que pode abrir o DevTools e desligar. Terceiro: consistência — se houvesse um
> app mobile, cada um reimplementaria a regra e alguém erraria."

**Regra de negócio × banco:**
> "A regra de negócio mora na aplicação; o banco guarda os dados e garante a
> integridade estrutural. Se eu inserir 95 graus direto no banco, a leitura
> entra mas o alerta não nasce. É por isso que existe uma API: ela é o único
> caminho que aplica as regras."

**Normalização:**
> "O chamado guarda só o `client_id`, nunca uma cópia do nome. Se copiasse, uma
> mudança de e-mail exigiria atualizar 100 linhas, e uma falha no meio deixaria
> duas versões da verdade."

**F5 / persistência:**
> "Continua tudo lá, porque o banco é um arquivo em disco, não memória.
> Desligar o computador não apaga um arquivo."

**Se travar:**
> "Não sei responder de cabeça, mas sei onde está no código — posso abrir e
> explicar." (E abrir o arquivo. Navegar o próprio projeto vale mais que decorar.)
