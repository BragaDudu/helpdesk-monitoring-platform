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
from backend.app.enums import UserRole
from backend.app.main import app
from backend.app.models import User
from backend.app.security import hash_senha
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
        # ★ TODA A SUITE ENTRA COMO SUPER_ADMIN POR PADRAO.
        #
        #   Depois que a API passou a exigir login, os testes de regra de
        #   negocio (chamado, alerta, transicao de status) receberiam 401 e
        #   testariam a coisa errada. Autenticando aqui uma vez, cada teste
        #   volta a testar o que ele se propoe.
        #
        #   O isolamento entre empresas tem testes PROPRIOS (test_auth.py),
        #   onde o usuario logado e' outro de proposito.
        db = TestingSessionLocal()
        try:
            db.add(User(
                name="Admin de Teste",
                email="admin@teste.com",
                password_hash=hash_senha(SENHA_PADRAO),
                role=UserRole.SUPER_ADMIN,
                client_id=None,
            ))
            db.commit()
        finally:
            db.close()

        token = c.post("/api/auth/login", json={
            "email": "admin@teste.com", "password": SENHA_PADRAO,
        }).json()["access_token"]
        # headers do TestClient valem para TODAS as requisicoes seguintes.
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_test)


SENHA_PADRAO = "senha-de-teste-123"


def criar_usuario_empresa(client, client_id: int, email: str) -> dict:
    """Cria um ADMIN_EMPRESA e devolve o cabecalho de autorizacao dele.

    Usado pelos testes de isolamento: e' com este cabecalho que se prova que
    a empresa A nao enxerga a empresa B.
    """
    db = TestingSessionLocal()
    try:
        db.add(User(
            name=f"Responsavel {client_id}",
            email=email,
            password_hash=hash_senha(SENHA_PADRAO),
            role=UserRole.ADMIN_EMPRESA,
            client_id=client_id,
        ))
        db.commit()
    finally:
        db.close()

    # Login SEM o cabecalho de admin, senao entraria com o usuario errado.
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": SENHA_PADRAO},
        headers={"Authorization": ""},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


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
