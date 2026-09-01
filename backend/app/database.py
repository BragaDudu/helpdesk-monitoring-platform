"""Conexao com o banco de dados.

Este arquivo cria as tres pecas que todo o resto do projeto usa:

    engine       -> QUEM sabe falar com o banco (abre conexoes, executa SQL)
    SessionLocal -> a FABRICA de sessoes (uma sessao = uma transacao)
    Base         -> a classe-mae de todos os models

E define get_db(), a dependencia que entrega uma sessao para cada requisicao.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings

# ---------------------------------------------------------------------------
# 1) ENGINE -- o "motor" de conexao
# ---------------------------------------------------------------------------
# O engine NAO abre conexao agora. Ele guarda a configuracao e mantem um pool
# de conexoes que sao abertas sob demanda e reaproveitadas.
#
# connect_args={"check_same_thread": False}
#     Especifico do SQLite. Por padrao o driver do Python proibe que uma
#     conexao criada numa thread seja usada em outra. Como o Uvicorn atende
#     requisicoes em varias threads, precisamos desligar essa checagem.
#     E' seguro aqui porque o SQLAlchemy garante que cada requisicao usa a
#     SUA propria sessao (veja get_db abaixo) -- nunca duas ao mesmo tempo.
#     Em PostgreSQL este argumento nao existe, por isso o "if".
# ---------------------------------------------------------------------------
_database_url = settings.DATABASE_URL_RESOLVED
_is_sqlite = _database_url.startswith("sqlite")

engine = create_engine(
    _database_url,
    echo=settings.SQL_ECHO,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    future=True,
)


# ---------------------------------------------------------------------------
# 2) A PEGADINHA MAIS IMPORTANTE DO SQLITE
# ---------------------------------------------------------------------------
# O SQLite IGNORA chaves estrangeiras por padrao (por compatibilidade com
# versoes antigas). Ou seja: sem a linha abaixo, voce poderia inserir um
# chamado com client_id = 999 mesmo sem existir o cliente 999, e o banco
# aceitaria numa boa.
#
# O trecho abaixo registra um "ouvinte": toda vez que o SQLAlchemy abrir uma
# conexao nova, ele executa PRAGMA foreign_keys=ON naquela conexao.
#
# ★ Se a banca perguntar "suas foreign keys funcionam mesmo?", e' este bloco
#   que voce mostra.
# ---------------------------------------------------------------------------
if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ---------------------------------------------------------------------------
# 3) SESSION -- a unidade de trabalho
# ---------------------------------------------------------------------------
# Uma Session representa uma conversa com o banco: voce acumula alteracoes e,
# no final, chama commit() (grava tudo) ou rollback() (desfaz tudo).
#
# autoflush=False   -> o SQLAlchemy so envia comandos quando NOS mandarmos.
#                      Deixa o comportamento previsivel e facil de explicar.
# autocommit=False  -> nada e' gravado sem um commit() explicito. E' o que
#                      garante o "tudo ou nada": se a leitura for gravada mas
#                      o alerta falhar, NENHUM dos dois fica no banco.
# expire_on_commit=False -> depois do commit os objetos continuam legiveis,
#                      sem precisar de um novo SELECT so para ler o id.
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


# ---------------------------------------------------------------------------
# 4) BASE -- a classe-mae dos models
# ---------------------------------------------------------------------------
# Todo model (Client, Ticket, ...) herda de Base. E' assim que o SQLAlchemy
# monta o "mapa" de tabelas em Base.metadata, usado depois por create_all().
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy 2.x."""


# ---------------------------------------------------------------------------
# 5) get_db -- uma sessao por requisicao
# ---------------------------------------------------------------------------
# QUEM CHAMA: o FastAPI, automaticamente, em cada endpoint que declarar
#             db: Session = Depends(get_db)
#
# COMO FUNCIONA:
#     - antes do endpoint rodar, o FastAPI executa ate o "yield" e entrega a
#       sessao criada para o endpoint
#     - o endpoint usa a sessao
#     - quando a resposta termina (com sucesso OU com erro), o "finally"
#       fecha a sessao e devolve a conexao ao pool
#
# POR QUE ISSO IMPORTA: sem fechar, as conexoes vazariam e a aplicacao
# travaria depois de algumas centenas de requisicoes.
#
# POR QUE UMA SESSAO POR REQUISICAO: para que duas requisicoes simultaneas
# nunca compartilhem a mesma transacao. O commit de uma nao pode gravar o
# trabalho pela metade da outra.
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessao de banco para a requisicao e garante o fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
