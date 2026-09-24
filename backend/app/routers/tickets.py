"""Endpoints HTTP de Chamados."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import escopo_do_cliente, get_current_user, require_admin
from backend.app.models import User

from backend.app.enums import (
    CATEGORY_LABELS,
    TICKET_SUBCATEGORIES,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from backend.app.schemas.common import ErrorResponse, Page, montar_pagina
from backend.app.schemas.ticket import TicketCreate, TicketOut, TicketStatusUpdate
from backend.app.services import ticket_service

router = APIRouter(prefix="/api/tickets", tags=["Chamados"])


@router.post(
    "",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir chamado",
    responses={404: {"model": ErrorResponse, "description": "Cliente nao encontrado"}},
)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> TicketOut:
    """Abre um chamado para um cliente existente.

    O chamado sempre nasce com status ABERTO e com opened_at = agora (UTC),
    carimbados pelo SERVIDOR. Nenhum dos dois pode ser enviado pelo cliente
    da API -- nem constam no schema de entrada.
    """
    return ticket_service.create_ticket(db, payload, client_scope=escopo)


@router.get("", response_model=Page[TicketOut], summary="Listar chamados")
def list_tickets(
    # Tipar o filtro com o Enum faz o Swagger virar um COMBOBOX com as tres
    # opcoes, e faz um valor errado (?status=BANANA) devolver 422 antes de
    # chegar ao banco. Documentacao e validacao pelo mesmo preco.
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = Query(None),
    category: TicketCategory | None = Query(None),
    client_id: int | None = Query(None, ge=1),
    search: str | None = Query(None, description="Busca no titulo, descricao ou problema"),
    # ★ le=100 (era 1000): a tela pagina de 20 em 20. Um teto alto convida
    #   alguem a pedir 1.000 registros e derrubar o navegador -- limite de
    #   API existe para proteger o SERVIDOR, nao para atrapalhar o cliente.
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    sort: str | None = Query(None, description="Coluna: id, title, company, category, priority, status, opened_at"),
    order: str | None = Query(None, pattern="^(asc|desc)$"),
    escopo: int | None = Depends(escopo_do_cliente),
) -> Page[TicketOut]:
    """Lista chamados com filtros combinaveis, do mais recente para o mais antigo.

    Todos os filtros sao opcionais e podem ser combinados:
        /api/tickets?status=ABERTO&priority=ALTA
    A filtragem acontece no BANCO (clausula WHERE), nunca em JavaScript.
    """
    items, total = ticket_service.list_tickets(
        db,
        client_id=client_id,
        status=status_filter.value if status_filter else None,
        priority=priority.value if priority else None,
        category=category.value if category else None,
        search=search,
        limit=limit,
        offset=offset,
        client_scope=escopo,
        sort=sort,
        order=order,
    )
    return montar_pagina(items, total, limit, offset)


# ---------------------------------------------------------------------------
# ★ ATENCAO A ORDEM: esta rota vem ANTES de /{ticket_id}.
#
# O FastAPI testa as rotas na ordem em que foram declaradas. Se
# /{ticket_id} viesse primeiro, uma chamada a /api/tickets/categories seria
# capturada por ela, que tentaria converter "categories" em int e devolveria
# 422. Rota literal sempre antes de rota com parametro.
# ---------------------------------------------------------------------------
@router.get(
    "/categories",
    summary="Categorias e subcategorias disponiveis",
)
def list_categories(_user: User = Depends(get_current_user)) -> list[dict]:
    """Entrega o catalogo de categorias para a tela montar os selects.

    POR QUE ISSO E' UM ENDPOINT, E NAO UMA LISTA NO JAVASCRIPT:
    se a lista estivesse escrita no frontend, ela sairia do ar no dia em que
    uma categoria nova nascesse no backend -- e o formulario passaria a
    enviar valores que a API recusa com 422. Existindo UMA fonte da verdade
    (o enum do Python), as duas pontas nunca divergem.
    """
    return [
        {
            "value": categoria.value,
            "label": CATEGORY_LABELS[categoria],
            "subcategories": TICKET_SUBCATEGORIES[categoria],
        }
        for categoria in TicketCategory
    ]


@router.get(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="Consultar chamado",
    responses={404: {"model": ErrorResponse}},
)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> TicketOut:
    """Busca um chamado pelo id, com os dados do cliente ja embutidos."""
    return ticket_service.get_ticket(db, ticket_id, client_scope=escopo)


@router.patch(
    "/{ticket_id}/status",
    response_model=TicketOut,
    summary="Alterar status do chamado",
    responses={
        404: {"model": ErrorResponse, "description": "Chamado nao encontrado"},
        409: {"model": ErrorResponse, "description": "Transicao de status invalida"},
        422: {"model": ErrorResponse, "description": "Status inexistente"},
    },
)
def change_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> TicketOut:
    """Altera o status de um chamado, respeitando a maquina de estados.

    ★ POR QUE PATCH E NAO PUT?
        PUT significa "substitua o recurso INTEIRO por este". Para usar PUT
        eu teria que reenviar titulo, descricao, categoria, prioridade e
        cliente -- e se esquecesse um campo, ele seria apagado.
        PATCH significa "altere APENAS o que estou mandando". Como so quero
        mudar o status, PATCH e' literalmente o verbo correto.

    ★ POR QUE UMA ROTA PROPRIA (/status) E NAO UM PATCH GENERICO?
        Porque mudar status NAO e' editar um campo qualquer: dispara uma
        regra (a maquina de estados) e um efeito colateral (carimbar
        closed_at). Uma rota dedicada deixa isso explicito na URL e impede
        que a regra seja contornada por um update generico.

    RESPOSTAS POSSIVEIS:
        200 -> alterado (ou ja estava nesse status: PATCH e' idempotente)
        404 -> o chamado nao existe
        409 -> transicao proibida (ex.: FINALIZADO -> ABERTO)
        422 -> o status enviado nem existe (ex.: "CANCELADO")
    """
    return ticket_service.change_ticket_status(
        db, ticket_id, payload.status, client_scope=escopo
    )
