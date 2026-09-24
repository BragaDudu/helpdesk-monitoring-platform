"""Endpoints HTTP das consultas analiticas (Exercicio 2).

Sao todos GET, todos sem efeito colateral: consultar um relatorio nunca
altera nada. Por isso podem ser chamados a vontade, e um navegador ou proxy
poderia ate cachea-los.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import escopo_do_cliente, get_current_user, require_admin
from backend.app.models import User

from backend.app.schemas.analytics import (
    AverageResolutionTime,
    CategoryResolutionTimeItem,
    CustomerRankingItem,
    DashboardSummary,
    OpenTicketsSummary,
    TicketsByCategoryItem,
    TicketsByClientItem,
)
from backend.app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["Analytics (Exercicio 2)"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Resumo geral para o dashboard",
)
def summary(
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> DashboardSummary:
    """Todos os numeros da tela inicial numa unica requisicao.

    Endpoint EXTRA, nao pedido no enunciado. Existe para o dashboard nao
    precisar de 7 chamadas HTTP para pintar os cartoes.
    """
    return analytics_service.dashboard_summary(db, client_scope=escopo)


@router.get(
    "/tickets-by-client",
    response_model=list[TicketsByClientItem],
    summary="1) Quantidade de chamados por cliente",
)
def tickets_by_client(
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> list[TicketsByClientItem]:
    """Item 1 do Exercicio 2.

    Inclui clientes com ZERO chamados (LEFT JOIN), porque "este cliente
    nunca abriu chamado" tambem e' informacao relevante para a empresa.
    """
    return analytics_service.tickets_by_client(db, client_scope=escopo)


@router.get(
    "/tickets-by-category",
    response_model=list[TicketsByCategoryItem],
    summary="2) Quantidade de chamados por categoria",
)
def tickets_by_category(
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> list[TicketsByCategoryItem]:
    """Item 2 do Exercicio 2. GROUP BY category, ordenado pelo maior volume."""
    return analytics_service.tickets_by_category(db, client_scope=escopo)


@router.get(
    "/customer-ranking",
    response_model=list[CustomerRankingItem],
    summary="3) Ranking dos clientes com mais chamados",
)
def customer_ranking(
    limit: int = Query(10, ge=1, le=100, description="Quantos clientes no ranking"),
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> list[CustomerRankingItem]:
    """Item 3 do Exercicio 2. Apenas clientes que possuem chamados (INNER JOIN)."""
    return analytics_service.customer_ranking(db, limit=limit, client_scope=escopo)


@router.get(
    "/average-resolution-time",
    response_model=AverageResolutionTime,
    summary="4) Tempo medio de fechamento dos chamados",
)
def average_resolution_time(
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> AverageResolutionTime:
    """Item 4 do Exercicio 2.

    Considera SOMENTE chamados finalizados que possuem data de fechamento.
    Se nao houver nenhum, devolve null e "sem dados" -- nunca zero, que
    significaria "resolve instantaneamente".
    """
    return analytics_service.average_resolution_time(db, client_scope=escopo)


@router.get(
    "/open-tickets",
    response_model=OpenTicketsSummary,
    summary="5) Quantidade de chamados ainda abertos",
)
def open_tickets(
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> OpenTicketsSummary:
    """Item 5 do Exercicio 2, com a quebra por prioridade dos pendentes."""
    return analytics_service.open_tickets(db, client_scope=escopo)


@router.get(
    "/category-resolution-time",
    response_model=list[CategoryResolutionTimeItem],
    summary="6) Tempo medio de resolucao por categoria",
)
def category_resolution_time(
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> list[CategoryResolutionTimeItem]:
    """Item 6 do Exercicio 2.

    Ordenado do MAIOR tempo medio para o menor: o primeiro item da lista e'
    a resposta direta de "qual categoria demora mais para ser resolvida".
    """
    return analytics_service.category_resolution_time(db, client_scope=escopo)
