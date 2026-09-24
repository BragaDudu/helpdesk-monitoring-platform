"""Ponto de entrada da aplicacao.

RESPONSABILIDADE DESTE ARQUIVO -- e' curta de proposito:
  1. criar o objeto FastAPI
  2. garantir que as tabelas existam ao subir
  3. registrar os tradutores de erro (dominio -> HTTP)
  4. registrar os routers
  5. servir o frontend

NAO ha nenhuma regra de negocio aqui. Se este arquivo comecar a crescer,
e' sinal de que algo esta no lugar errado.

COMO RODAR:
    uvicorn backend.app.main:app --reload
                ^^^^^^^^^^^^^^^^ ^^^^
                caminho do modulo | nome da variavel FastAPI
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import FRONTEND_DIR, settings
from backend.app.database import Base, engine
from backend.app.exceptions import DomainError
from backend.app.routers import alerts, analytics, auth, clients, equipments, tickets

# Importa os models para registra-los em Base.metadata antes do create_all.
import backend.app.models  # noqa: F401

# OBSERVABILIDADE BASICA: sem logging, um erro em producao vira um 500 mudo
# e ninguem descobre a causa. Com isso, todo erro inesperado sai no terminal
# com a stack trace completa.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("helpdesk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Roda uma vez ao SUBIR e uma vez ao DESLIGAR a aplicacao.

    create_all NAO APAGA NADA. Ele apenas cria as tabelas que ainda nao
    existem. Se o banco ja tem 20 clientes, eles continuam la depois de
    reiniciar o servidor -- que e' exatamente o requisito de persistencia.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Banco pronto: %s", settings.DATABASE_URL_RESOLVED)
    logger.info(
        "Limite de alerta de temperatura: %s C",
        settings.TEMPERATURE_ALERT_THRESHOLD,
    )
    yield
    logger.info("Aplicacao encerrada.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API REST da plataforma de gestao de TI: clientes, chamados, "
        "analytics e monitoramento de equipamentos."
    ),
    lifespan=lifespan,
    docs_url="/docs",     # Swagger UI  (interativo)
    redoc_url="/redoc",   # ReDoc       (documentacao para leitura)
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# O frontend deste projeto e' servido pelo PROPRIO FastAPI (veja o final do
# arquivo), entao ele roda na MESMA ORIGEM da API e nao precisaria de CORS.
#
# Habilitamos assim mesmo, restrito a localhost, para o caso de voce abrir o
# HTML por outro servidor durante o desenvolvimento (Live Server do VS Code,
# por exemplo). Sem isso, o navegador BLOQUEARIA o fetch e o erro seria
# confuso ("Failed to fetch", sem explicacao).
#
# Nao usamos allow_origins=["*"]: liberar tudo e' um habito ruim de producao.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# TRADUTORES DE ERRO -- dominio -> HTTP, num lugar so
# ---------------------------------------------------------------------------
@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Converte QUALQUER erro de negocio no codigo HTTP correto.

    Cada excecao carrega o proprio status_code:
        NotFoundError      -> 404
        ConflictError      -> 409
        BusinessRuleError  -> 409

    E' POR CAUSA DESTE HANDLER que os services podem ignorar HTTP por
    completo. Existe UM ponto de traducao. Se amanha 409 virar 422 para
    algum caso, muda aqui -- nao em vinte endpoints.
    """
    logger.warning(
        "[%s] %s %s -> %s",
        exc.error_code,
        request.method,
        request.url.path,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "detail": exc.message},
    )


# ---------------------------------------------------------------------------
# TRADUCAO DE ERRO DE VALIDACAO PARA PORTUGUES DE GENTE
#
# O Pydantic devolve mensagens tecnicas em ingles:
#     "String should have at least 5 characters"
#     "value is not a valid email address: An email address must have an @-sign."
#
# Isso serve para DEPURAR, nao para mostrar ao usuario final. Quem esta
# cadastrando um cliente nao quer saber o que e' uma "String".
#
# ★ POR QUE TRADUZIR AQUI E NAO NO FRONTEND:
#   porque o frontend nao e' a unica porta de entrada -- a mesma API atende
#   Swagger, integracoes e (no futuro) um app. Traduzindo no backend, a
#   mensagem boa chega para todo mundo, escrita uma vez so.
# ---------------------------------------------------------------------------
ROTULOS_DOS_CAMPOS: dict[str, str] = {
    "name": "O nome",
    "company": "A empresa",
    "email": "O e-mail",
    "phone": "O telefone",
    "title": "O titulo",
    "description": "A descricao",
    "category": "A categoria",
    "subcategory": "O problema especifico",
    "priority": "A prioridade",
    "status": "O status",
    "client_id": "O cliente",
    "temperature": "A temperatura",
    "identifier": "O identificador",
    "location": "A localizacao",
}


def traduzir_erro(campo: str, erro: dict) -> str:
    """Transforma um erro do Pydantic numa frase que o usuario entende.

    RECEBE: o nome do campo e o dicionario de erro do Pydantic, que tem
            'type' (o codigo do erro) e 'ctx' (os limites que falharam).
    RETORNA: uma frase pronta, comecando com o rotulo do campo.
    """
    rotulo = ROTULOS_DOS_CAMPOS.get(campo, f"O campo '{campo}'")
    tipo = erro.get("type", "")
    ctx = erro.get("ctx", {}) or {}

    if tipo == "missing":
        return f"{rotulo} e' obrigatorio."

    if tipo == "string_too_short":
        minimo = ctx.get("min_length", "?")
        return (
            f"{rotulo} precisa ter pelo menos {minimo} caracteres."
            if minimo != 1
            else f"{rotulo} nao pode ficar em branco."
        )

    if tipo == "string_too_long":
        return f"{rotulo} pode ter no maximo {ctx.get('max_length', '?')} caracteres."

    if tipo in ("int_parsing", "float_parsing", "decimal_parsing"):
        return f"{rotulo} precisa ser um numero."

    if tipo in ("greater_than", "greater_than_equal"):
        return f"{rotulo} precisa ser maior que {ctx.get('gt', ctx.get('ge', '?'))}."

    if tipo in ("less_than", "less_than_equal"):
        return f"{rotulo} precisa ser menor que {ctx.get('lt', ctx.get('le', '?'))}."

    if tipo == "enum":
        # ctx['expected'] ja vem como "'A', 'B' or 'C'"
        return f"{rotulo} precisa ser uma das opcoes: {ctx.get('expected', '')}."

    if tipo == "value_error":
        mensagem = str(erro.get("msg", "")).replace("Value error, ", "").strip()
        # Erros de e-mail vem do email-validator, sempre em ingles.
        if "email" in mensagem.lower() or campo == "email":
            return f"{rotulo} nao parece valido. Exemplo: nome@empresa.com.br"
        # Os validadores proprios (telefone, subcategoria) ja escrevem em
        # portugues -- aproveitamos a mensagem como veio.
        return mensagem if mensagem.endswith(".") else f"{mensagem}."

    # Rede de seguranca: erro que ainda nao mapeamos nao pode virar
    # mensagem vazia. Mostramos o texto do Pydantic com o campo na frente.
    return f"{rotulo}: {erro.get('msg', 'valor invalido')}."


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Erros de VALIDACAO do Pydantic -> HTTP 422 Unprocessable Entity.

    O FastAPI ja devolveria 422 sozinho, mas num formato tecnico
    ("loc", "msg", "type") dificil de mostrar para o usuario final.
    Aqui reescrevemos no MESMO formato dos outros erros, com o nome do campo
    traduzido para algo legivel:

        "email: value is not a valid email address"

    Assim o frontend tem um unico jeito de ler erro, seja 404, 409 ou 422.
    """
    problems = []
    for error in exc.errors():
        # loc = ("body", "email") -> queremos so "email"
        field = ".".join(
            str(part)
            for part in error["loc"]
            if part not in ("body", "query", "path")
        )
        problems.append(traduzir_erro(field, error))

    detail = " ".join(problems)
    logger.warning(
        "[validation] %s %s -> %s", request.method, request.url.path, detail
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "validation_error", "detail": detail},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Rede de seguranca para erros NAO previstos -> HTTP 500.

    SEGURANCA: registramos a stack trace COMPLETA no log do servidor
    (para nos), mas devolvemos ao usuario apenas uma mensagem generica.
    Vazar stack trace numa resposta HTTP entrega nomes de arquivos,
    estrutura de pastas e as vezes trechos de SQL -- material de sobra
    para quem esta tentando atacar a aplicacao.
    """
    logger.exception("Erro inesperado em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "detail": "Erro interno no servidor. Consulte os logs da aplicacao.",
        },
    )


# ---------------------------------------------------------------------------
# ROTAS
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["Sistema"], summary="Verificar se a API esta no ar")
def health() -> dict:
    """Endpoint de saude.

    Serve para dois usos praticos:
      - o frontend checar se o backend subiu antes de reclamar de erro
      - voce provar na apresentacao que a API esta viva, em 1 segundo
    """
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


# ★ auth vem PRIMEIRO na lista por clareza: e' a porta de entrada.
#   A ordem entre routers de prefixos diferentes nao muda o roteamento,
#   mas muda a ordem das secoes no Swagger -- e login deve abrir a doc.
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(tickets.router)
app.include_router(analytics.router)
app.include_router(equipments.router)
app.include_router(alerts.router)


# ---------------------------------------------------------------------------
# FRONTEND SERVIDO PELA PROPRIA API
# ---------------------------------------------------------------------------
# DECISAO DE ARQUITETURA:
#   Servindo o HTML pelo mesmo servidor da API, tudo roda em
#   http://localhost:8000. Frontend e backend ficam na MESMA ORIGEM, entao:
#     - o JavaScript usa caminho relativo:  fetch('/api/clients')
#     - nao existe problema de CORS
#     - e' UM comando para subir o sistema inteiro, o que facilita a
#       apresentacao ao vivo
#
#   Se voce abrisse o index.html com duplo clique (file:///C:/...), a origem
#   seria diferente e o navegador bloquearia todas as chamadas.
#
# ATENCAO A ORDEM: este mount fica no FINAL do arquivo. O FastAPI testa as
# rotas na ordem em que foram registradas, e este mount captura tudo o que
# sobrar ("/"). Se viesse antes, engoliria /api/clients e /docs.
#
# html=True faz "/" servir o index.html automaticamente.
# ---------------------------------------------------------------------------
if (FRONTEND_DIR / "index.html").exists():
    app.mount(
        "/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend"
    )
    logger.info("Frontend servido a partir de %s", FRONTEND_DIR)
else:
    logger.warning(
        "Pasta frontend/ ainda vazia. A API funciona normalmente; "
        "use http://localhost:8000/docs ate a Etapa 7."
    )
