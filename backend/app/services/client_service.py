"""Regras de negocio do Cliente.

ESTE ARQUIVO NAO SABE QUE HTTP EXISTE.
Nao ha "404" nem "HTTPException" aqui -- so NotFoundError e ConflictError,
que sao conceitos do NEGOCIO. Quem traduz isso para codigo HTTP e' o
main.py, num unico lugar.

POR QUE ISSO IMPORTA: estas mesmas funcoes serao chamadas pelo script de
seed (Etapa 6) e pelos testes (Etapa 8), que nao passam por HTTP nenhum.
Se a regra estivesse dentro do endpoint, seria preciso reescreve-la.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.exceptions import ConflictError, ForbiddenError, NotFoundError
from backend.app.models import Client, Equipment, Ticket
from backend.app.schemas.client import ClientCreate, ClientUpdate
from backend.app.schemas.common import aplicar_ordenacao


def create_client(db: Session, payload: ClientCreate) -> Client:
    """Cadastra um cliente.

    RECEBE: a sessao do banco + os dados JA VALIDADOS pelo Pydantic
            (aqui dentro, nome nao vem vazio e e-mail tem formato correto --
             isso ja foi garantido uma camada acima).
    RETORNA: o objeto Client com o id que o banco gerou.
    ERRO:    ConflictError se o e-mail ja existir -> vira HTTP 409.

    ★ POR QUE TRATAR O E-MAIL DUPLICADO COM try/except E NAO COM UM "if"?

      A versao ingenua seria:
          if db.query(Client).filter_by(email=...).first():
              raise ConflictError(...)
          db.add(...)

      Isso tem uma RACE CONDITION: duas requisicoes simultaneas com o mesmo
      e-mail podem executar o "if" ao mesmo tempo, ambas verem "nao existe",
      e ambas inserirem. A janela entre a checagem e a insercao e' real.

      A versao correta e' a daqui: TENTA inserir e deixa a constraint UNIQUE
      do banco decidir. A constraint e' atomica -- nao existe janela. Este
      padrao se chama EAFP ("melhor pedir perdao do que permissao") e e' a
      forma correta de garantir unicidade em banco de dados.
    """
    client = Client(
        name=payload.name,
        company=payload.company,
        email=payload.email,
        phone=payload.phone,
    )
    db.add(client)  # marca para insercao (ainda nao foi ao banco)
    try:
        db.commit()  # AQUI o INSERT e' realmente executado e confirmado
    except IntegrityError as exc:
        # rollback e' obrigatorio: sem ele a sessao fica "suja" e qualquer
        # comando seguinte falha com PendingRollbackError.
        db.rollback()
        raise ConflictError(
            f"Ja existe um cliente cadastrado com o e-mail '{payload.email}'."
        ) from exc

    db.refresh(client)  # recarrega o objeto com id e created_at gerados
    return client


def list_clients(
    db: Session,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    client_scope: int | None = None,
    sort: str | None = None,
    order: str | None = None,
) -> tuple[list[Client], int]:
    """Lista clientes, opcionalmente filtrando por texto.

    O FILTRO E' FEITO NO BANCO (WHERE ... LIKE), nao em Python.
    Se trouxessemos 20.000 clientes para a memoria e filtrassemos com um
    "for", gastariamos rede, memoria e tempo a toa. Filtrar no banco e'
    para isso que o banco existe.

    SEGURANCA: repare que o termo de busca NUNCA e' concatenado numa string
    de SQL. O SQLAlchemy o envia como PARAMETRO. Se alguem buscar por
        ' OR 1=1 --
    isso e' tratado como TEXTO a procurar, nao como comando. SQL Injection
    e' impossivel por construcao.
    """
    # Mesma condicao para a lista e para a contagem -- ver o comentario
    # equivalente no ticket_service: se divergirem, o rodape mente.
    condicoes = []

    # ★ O FILTRO DO MULTI-EMPRESA VEM PRIMEIRO, ANTES DE QUALQUER OUTRO.
    #   client_scope=None  -> sem restricao (usuario da empresa de TI)
    #   client_scope=3     -> a listagem inteira vira "so o cliente 3"
    #
    #   Colocado como PRIMEIRA condicao de proposito: assim ele nunca fica
    #   dentro de um "if" de outro filtro e nunca deixa de ser aplicado.
    if client_scope is not None:
        condicoes.append(Client.id == client_scope)

    if search and search.strip():
        term = f"%{search.strip()}%"
        condicoes.append(
            Client.name.ilike(term)
            | Client.company.ilike(term)
            | Client.email.ilike(term)
        )

    total = db.scalar(
        select(func.count()).select_from(Client).where(*condicoes)
    ) or 0

    stmt = select(Client).where(*condicoes)
    stmt = aplicar_ordenacao(
        stmt, sort, order,
        # As colunas que a tela pode ordenar. Nome vindo da URL a esquerda,
        # coluna real a direita -- e nada fora daqui chega ao SQL.
        {"id": Client.id, "name": Client.name, "company": Client.company,
         "email": Client.email, "created_at": Client.created_at},
        padrao=[Client.company, Client.name],
    )
    stmt = stmt.limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all()), total


def get_client(
    db: Session, client_id: int, client_scope: int | None = None
) -> Client:
    """Busca UM cliente pelo id, ou levanta NotFoundError.

    QUEM CHAMA: o router de clientes, o router de chamados (para validar que
    o cliente do chamado existe) e o router de equipamentos.

    Centralizar a busca aqui evita que cada lugar reimplemente o "se nao
    achou, erro 404" -- e garante que a mensagem seja sempre a mesma.
    """
    client = db.get(Client, client_id)  # SELECT ... WHERE id = ? (usa a PK)
    if client is None:
        raise NotFoundError("Cliente", client_id)

    # ★ CHECAGEM DE DONO: o cliente existe, mas e' DESTE usuario?
    #
    #   Sem isto, um ADMIN_EMPRESA da empresa 3 acessaria /api/clients/7
    #   trocando o numero na URL e leria os dados da empresa 7. Essa falha
    #   tem nome -- IDOR, "referencia direta insegura a objeto" -- e e' uma
    #   das mais comuns em API. Filtrar so a LISTAGEM nao basta: quem sabe
    #   o id acessa direto.
    if client_scope is not None and client.id != client_scope:
        raise ForbiddenError("Voce nao tem acesso aos dados deste cliente.")
    return client


def update_client(db: Session, client_id: int, payload: ClientUpdate) -> Client:
    """Atualiza parcialmente um cliente (PATCH).

    exclude_unset=True e' o coracao do PATCH: devolve apenas os campos que
    REALMENTE VIERAM no JSON. Se o corpo foi {"phone": "..."}, so o telefone
    e' alterado; nome, empresa e e-mail nem sao tocados.

    Sem essa opcao, os campos ausentes viriam como None e apagariam os dados
    existentes -- transformando um PATCH num PUT destrutivo.
    """
    client = get_client(db, client_id)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(client, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"Ja existe outro cliente com o e-mail '{changes.get('email')}'."
        ) from exc

    db.refresh(client)
    return client


def delete_client(db: Session, client_id: int) -> None:
    """Remove um cliente -- somente se ele nao tiver historico.

    ★ DECISAO DE NEGOCIO IMPORTANTE:
      Poderiamos ter usado ON DELETE CASCADE, e apagar o cliente levaria
      junto os 100 chamados dele. NAO fizemos isso de proposito: apagar
      historico de atendimento em silencio destroi informacao da empresa.

      Aqui verificamos antes e devolvemos HTTP 409 explicando o motivo.
      A FK com ON DELETE RESTRICT e' a rede de seguranca: mesmo que esta
      checagem falhasse, o banco recusaria o DELETE.

      Duas camadas: uma para dar uma MENSAGEM BOA ao usuario, outra para
      GARANTIR que nao acontece.
    """
    client = get_client(db, client_id)

    tickets = db.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.client_id == client_id)
    )
    equipments = db.scalar(
        select(func.count()).select_from(Equipment).where(Equipment.client_id == client_id)
    )

    if tickets or equipments:
        raise ConflictError(
            f"Nao e' possivel excluir o cliente '{client.name}': ele possui "
            f"{tickets} chamado(s) e {equipments} equipamento(s) vinculados. "
            "Historico de atendimento nao pode ser apagado."
        )

    db.delete(client)
    db.commit()
