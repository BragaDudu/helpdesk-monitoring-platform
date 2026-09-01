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
from backend.app.routers import alerts, analytics, clients, equipments, tickets

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
        problems.append(f"{field}: {error['msg']}" if field else error["msg"])

    detail = "Dados invalidos. " + " | ".join(problems)
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
