"""Endpoints HTTP de Chamados."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.enums import TicketPriority, TicketStatus
from backend.app.schemas.common import ErrorResponse
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
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketOut:
    """Abre um chamado para um cliente existente.

    O chamado sempre nasce com status ABERTO e com opened_at = agora (UTC),
    carimbados pelo SERVIDOR. Nenhum dos dois pode ser enviado pelo cliente
    da API -- nem constam no schema de entrada.
    """
    return ticket_service.create_ticket(db, payload)


@router.get("", response_model=list[TicketOut], summary="Listar chamados")
def list_tickets(
    # Tipar o filtro com o Enum faz o Swagger virar um COMBOBOX com as tres
    # opcoes, e faz um valor errado (?status=BANANA) devolver 422 antes de
    # chegar ao banco. Documentacao e validacao pelo mesmo preco.
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = Query(None),
    category: str | None = Query(None),
    client_id: int | None = Query(None, ge=1),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    """Lista chamados com filtros combinaveis, do mais recente para o mais antigo.

    Todos os filtros sao opcionais e podem ser combinados:
        /api/tickets?status=ABERTO&priority=ALTA
    A filtragem acontece no BANCO (clausula WHERE), nunca em JavaScript.
    """
    return ticket_service.list_tickets(
        db,
        client_id=client_id,
        status=status_filter.value if status_filter else None,
        priority=priority.value if priority else None,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketOut,
    summary="Consultar chamado",
    responses={404: {"model": ErrorResponse}},
)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketOut:
    """Busca um chamado pelo id, com os dados do cliente ja embutidos."""
    return ticket_service.get_ticket(db, ticket_id)


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
    ticket_id: int, payload: TicketStatusUpdate, db: Session = Depends(get_db)
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
    return ticket_service.change_ticket_status(db, ticket_id, payload.status)
