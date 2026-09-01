"""Configuracao compartilhada dos testes (pytest encontra este arquivo sozinho).

★ A IDEIA CENTRAL: os testes usam um BANCO PROPRIO, isolado, que NUNCA toca
  no data/app.db real. Cada teste comeca com o banco limpo, entao um teste
  nao contamina o outro e nenhum dado de teste vira lixo em producao.

COMO O ISOLAMENTO E' FEITO:
  1. criamos um engine SQLite separado (aqui: em memoria, rapido e efemero)
  2. sobrescrevemos a dependencia get_db do app para usar esse engine
  3. o TestClient chama a API HTTP de verdade, mas apontando para o banco teste
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
import backend.app.models  # noqa: F401  (registra as tabelas em Base.metadata)

# Banco em memoria. StaticPool + check_same_thread=False garantem que TODAS
# as conexoes usem a MESMA base em memoria (senao cada thread teria a sua,
# vazia). E' o padrao recomendado para testar SQLite em memoria.
engine_test = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine_test, autoflush=False, autocommit=False)

# O SQLite exige ligar as FKs em cada conexao (mesma pegadinha do database.py).
from sqlalchemy import event


@event.listens_for(engine_test, "connect")
def _fk_on(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


@pytest.fixture()
def client():
    """Entrega um TestClient ligado ao banco de teste, recriado a cada teste.

    - cria todas as tabelas (banco vazio)
    - troca get_db pelo banco de teste (dependency_overrides)
    - roda o teste
    - derruba as tabelas e desfaz a troca (limpeza)
    """
    Base.metadata.create_all(bind=engine_test)

    def _get_db_override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def sample_client(client):
    """Cria um cliente e devolve o JSON dele. Atalho usado por varios testes."""
    resp = client.post(
        "/api/clients",
        json={
            "name": "Cliente Teste",
            "company": "Empresa Teste LTDA",
            "email": "teste@empresa.com",
            "phone": "(11) 98888-7777",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def sample_equipment(client, sample_client):
    """Cria um equipamento e devolve o JSON dele."""
    resp = client.post(
        "/api/equipments",
        json={
            "client_id": sample_client["id"],
            "identifier": "EQP-TEST-01",
            "name": "Equipamento Teste",
        },
    )
    assert resp.status_code == 201
    return resp.json()
