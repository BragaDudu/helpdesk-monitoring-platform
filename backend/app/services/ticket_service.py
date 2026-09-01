"""Regras de negocio do Chamado."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.enums import TICKET_STATUS_TRANSITIONS, TicketStatus
from backend.app.exceptions import BusinessRuleError, NotFoundError
from backend.app.models import Ticket
from backend.app.schemas.ticket import TicketCreate
from backend.app.services.client_service import get_client
from backend.app.utils import utcnow


def create_ticket(db: Session, payload: TicketCreate) -> Ticket:
    """Abre um chamado.

    PASSO A PASSO (e' este fluxo que voce vai narrar na apresentacao):

      1. get_client(...) -> o cliente informado existe mesmo?
         Se nao existir, levanta NotFoundError e vira HTTP 404.
         ★ Sem esta checagem, o proprio banco recusaria pela FOREIGN KEY --
           mas o erro seria um IntegrityError feio. Checar antes nos permite
           devolver uma mensagem clara. As DUAS protecoes existem: esta da
           uma boa mensagem, a FK garante que nunca passa.

      2. Monta o objeto Ticket. Repare no que NAO e' lido do payload:
           status    -> nao vem do cliente da API; nasce ABERTO (default do model)
           opened_at -> nao vem do cliente da API; o servidor carimba (default=utcnow)
           closed_at -> continua NULL, porque o chamado nao foi fechado

      3. commit() -> o INSERT e' confirmado no arquivo app.db. A partir daqui
         o dado sobrevive a F5, a reinicio do servidor e a reboot da maquina.

      4. Recarrega o chamado JA COM o cliente, para a resposta sair completa.

    RECEBE: sessao + TicketCreate validado
    RETORNA: o Ticket criado, com o cliente carregado
    """
    get_client(db, payload.client_id)  # passo 1 (levanta 404 se nao existir)

    ticket = Ticket(
        client_id=payload.client_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        # status e opened_at ficam por conta dos defaults do model
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return get_ticket(db, ticket.id)


def list_tickets(
    db: Session,
    client_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Ticket]:
    """Lista chamados com filtros opcionais, do mais recente para o mais antigo.

    ★ joinedload(Ticket.client) RESOLVE O PROBLEMA "N+1".

      SEM ele: o SQLAlchemy faria 1 consulta para trazer os 100 chamados e,
      ao serializar, mais 1 consulta por chamado para descobrir o cliente.
      Total: 101 idas ao banco.

      COM ele: o SQLAlchemy gera UM SELECT com JOIN e traz tudo de uma vez.
      Total: 1 ida ao banco.

      Este e' o problema de performance numero 1 de qualquer aplicacao que
      usa ORM, e saber o nome dele ("N+1 query problem") impressiona banca.

    Os filtros sao construidos condicionalmente: so entram no WHERE se o
    parametro veio preenchido. Isso permite combinar
    "status=ABERTO & priority=ALTA" sem escrever uma consulta para cada
    combinacao possivel.
    """
    stmt = select(Ticket).options(joinedload(Ticket.client))

    if client_id is not None:
        stmt = stmt.where(Ticket.client_id == client_id)
    if status:
        stmt = stmt.where(Ticket.status == status)
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    if category:
        stmt = stmt.where(Ticket.category == category)

    stmt = stmt.order_by(Ticket.opened_at.desc(), Ticket.id.desc())
    stmt = stmt.limit(limit).offset(offset)

    return list(db.execute(stmt).scalars().all())


def get_ticket(db: Session, ticket_id: int) -> Ticket:
    """Busca UM chamado pelo id, ja com o cliente carregado."""
    stmt = (
        select(Ticket).options(joinedload(Ticket.client)).where(Ticket.id == ticket_id)
    )
    ticket = db.execute(stmt).scalar_one_or_none()
    if ticket is None:
        raise NotFoundError("Chamado", ticket_id)
    return ticket


def list_tickets_by_client(db: Session, client_id: int, **filters) -> list[Ticket]:
    """Chamados de UM cliente -- item 4 do Exercicio 1.

    Chama get_client primeiro DE PROPOSITO. Assim:
        cliente 999 nao existe        -> HTTP 404 ("cliente nao encontrado")
        cliente 5 existe, sem chamados -> HTTP 200 com lista vazia []

    Sao situacoes diferentes e merecem respostas diferentes. Se devolvesse
    [] nos dois casos, o usuario nao saberia se digitou o id errado ou se o
    cliente realmente nao tem chamados.
    """
    get_client(db, client_id)
    return list_tickets(db, client_id=client_id, **filters)


def change_ticket_status(
    db: Session, ticket_id: int, new_status: TicketStatus
) -> Ticket:
    """Altera o status de um chamado -- item 5 do Exercicio 1.

    ★ ESTA E' A SEGUNDA REGRA MAIS IMPORTANTE DO PROJETO (a primeira e' a
      dos 80 graus, na Etapa 5). Ela e' uma MAQUINA DE ESTADOS.

    O QUE E' UMA MAQUINA DE ESTADOS?
        E' um conjunto de estados e de transicoes PERMITIDAS entre eles.
        Nem todo estado pode virar qualquer outro:

            ABERTO  <-------->  EM_ANDAMENTO  ------->  FINALIZADO
               |                                            |
               +--------------------------------------------+
                                                             X  (nao volta)

        O mapa esta em backend/app/enums.py (TICKET_STATUS_TRANSITIONS),
        separado do codigo. Quem quiser mudar a regra -- por exemplo,
        permitir reabrir chamados -- mexe naquele dicionario e NAO neste
        arquivo. Se a banca pedir "permita reabrir", e' uma linha.

    PASSO A PASSO:
      1. Busca o chamado (404 se nao existir).
      2. Se o status pedido for IGUAL ao atual, nao faz nada e devolve 200.
         POR QUE NAO E' ERRO? Porque PATCH deve ser IDEMPOTENTE: repetir a
         mesma requisicao tem que dar o mesmo resultado. Se o usuario clicar
         duas vezes no botao, ou a rede reenviar o pacote, a segunda chamada
         nao pode quebrar.
      3. Consulta o mapa de transicoes. Se a mudanca nao for permitida,
         levanta BusinessRuleError -> HTTP 409 Conflict.

         POR QUE 409 E NAO 422?
           422 = "os dados que voce mandou estao malformados".
           409 = "os dados estao corretos, mas conflitam com o estado atual".
         "FINALIZADO" e' um status perfeitamente valido -- o problema nao e'
         o VALOR, e' a TRANSICAO. Logo, 409.

      4. Se estiver entrando em FINALIZADO, carimba closed_at com a hora
         real do servidor.

         ★ QUEM DEFINE closed_at E' O SERVIDOR, NUNCA O FRONTEND.
           O schema TicketStatusUpdate tem UM unico campo: status. Nao existe
           como o JavaScript enviar uma data de fechamento. Se pudesse, um
           usuario poderia marcar que fechou o chamado ontem e falsear o
           relatorio de tempo medio de resolucao do Exercicio 2.

      5. commit() -> a alteracao vai para o arquivo app.db e sobrevive a
         reinicio do servidor.

    RECEBE:  sessao, id do chamado, novo status (ja validado como Enum)
    RETORNA: o Ticket atualizado, com o cliente carregado
    ERROS:   NotFoundError (404) | BusinessRuleError (409)
    """
    ticket = get_ticket(db, ticket_id)
    current_status = ticket.status

    # passo 2 -- idempotencia
    if current_status == new_status:
        return ticket

    # passo 3 -- a transicao e' permitida?
    allowed = TICKET_STATUS_TRANSITIONS[current_status]
    if new_status not in allowed:
        allowed_text = ", ".join(sorted(s.value for s in allowed)) or "nenhum"
        raise BusinessRuleError(
            f"Transicao de status invalida: o chamado #{ticket_id} esta "
            f"'{current_status.value}' e nao pode ir para '{new_status.value}'. "
            f"Transicoes permitidas a partir de '{current_status.value}': {allowed_text}."
        )

    # passo 4 -- aplica a mudanca e carimba a data quando finaliza
    ticket.status = new_status
    if new_status == TicketStatus.FINALIZADO:
        ticket.closed_at = utcnow()

    # passo 5 -- persiste
    db.commit()
    db.refresh(ticket)
    return ticket
