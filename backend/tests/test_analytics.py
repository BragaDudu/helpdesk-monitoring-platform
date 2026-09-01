"""Testes dos Analytics (Exercicio 2) com dados de duracao CONHECIDA,
para conferir a matematica."""

from datetime import datetime, timedelta

from backend.app.database import Base
from backend.app.models import Client, Ticket
from backend.tests.conftest import TestingSessionLocal, engine_test


def _seed_conhecido():
    """Insere 2 clientes e chamados com duracoes exatas, direto no banco de
    teste (precisamos de datas historicas, que a API nao permite forjar)."""
    db = TestingSessionLocal()
    c1 = Client(name="A", company="Alfa", email="a@a.com", phone="(11) 90000-0000")
    c2 = Client(name="B", company="Beta", email="b@b.com", phone="(11) 90000-0001")
    db.add_all([c1, c2]); db.commit()

    base = datetime(2026, 1, 1, 8, 0, 0)
    # (cliente, categoria, status, horas)  -> finalizados: 2h, 4h, 6h  (media 4h)
    dados = [
        (c1, "Rede", "FINALIZADO", 2),
        (c1, "Rede", "FINALIZADO", 4),
        (c1, "Hardware", "FINALIZADO", 6),
        (c1, "Rede", "ABERTO", None),
        (c2, "Rede", "ABERTO", None),
    ]
    for i, (c, cat, st, h) in enumerate(dados):
        op = base + timedelta(days=i)
        db.add(Ticket(client_id=c.id, title="t", description="descricao",
                      category=cat, priority="MEDIA", status=st, opened_at=op,
                      closed_at=(op + timedelta(hours=h)) if h else None))
    db.commit(); db.close()


def test_tickets_por_cliente_inclui_zero(client):
    """LEFT JOIN: cliente sem chamado aparece com total 0."""
    _seed_conhecido()
    rows = client.get("/api/analytics/tickets-by-client").json()
    empresas = {r["company"]: r["total"] for r in rows}
    assert empresas["Alfa"] == 4
    assert empresas["Beta"] == 1


def test_tempo_medio_so_conta_finalizados(client):
    """Media = (2+4+6)/3 = 4h; os 2 abertos sao ignorados."""
    _seed_conhecido()
    r = client.get("/api/analytics/average-resolution-time").json()
    assert r["total_finalizados"] == 3
    assert abs(r["average_hours"] - 4.0) < 0.01


def test_chamados_abertos(client):
    """(5) 2 abertos, 0 em andamento, 3 finalizados."""
    _seed_conhecido()
    r = client.get("/api/analytics/open-tickets").json()
    assert r["abertos"] == 2
    assert r["finalizados"] == 3
    assert r["pendentes"] == 2  # abertos + em andamento


def test_categoria_mais_demorada_primeiro(client):
    """(6) Hardware (6h) demora mais que Rede (media 3h) -> vem primeiro."""
    _seed_conhecido()
    rows = client.get("/api/analytics/category-resolution-time").json()
    assert rows[0]["category"] == "Hardware"


def test_ranking(client):
    """(3) Alfa (4 chamados) na frente de Beta (1)."""
    _seed_conhecido()
    rows = client.get("/api/analytics/customer-ranking").json()
    assert rows[0]["company"] == "Alfa"
    assert rows[0]["position"] == 1


def test_summary_sem_dados(client):
    """Sem chamados finalizados, tempo medio e' 'sem dados', nao zero."""
    r = client.get("/api/analytics/summary").json()
    assert r["total_chamados"] == 0
    assert r["tempo_medio_resolucao"]["average_hours"] is None
