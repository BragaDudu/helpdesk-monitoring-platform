"""Endpoints HTTP de Clientes.

O ROUTER E' UMA CASCA FINA. Repare que cada funcao abaixo tem 1 a 3 linhas
de corpo: ela recebe a requisicao, chama o service e devolve o resultado.
Nenhuma regra de negocio mora aqui.

O TRABALHO PESADO E' DECLARATIVO -- feito pelos parametros do decorador:
  response_model -> filtra e formata a saida, e documenta o Swagger
  status_code    -> define o codigo HTTP de sucesso
  responses      -> documenta os erros possiveis no Swagger
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import escopo_do_cliente, get_current_user, require_admin
from backend.app.models import User

from backend.app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from backend.app.schemas.common import ErrorResponse, Page, montar_pagina
from backend.app.schemas.ticket import TicketOut
from backend.app.services import client_service, ticket_service

# prefix="/api/clients" -> toda rota deste arquivo comeca assim.
# tags=["Clientes"]     -> agrupa os endpoints numa secao do Swagger.
router = APIRouter(prefix="/api/clients", tags=["Clientes"])


@router.post(
    "",
    response_model=ClientOut,
    # ★ 201 Created, nao 200 OK. 201 significa "criei um recurso novo".
    #   Devolver 200 em toda criacao e' o erro mais comum em APIs amadoras:
    #   joga fora informacao que o padrao HTTP ja oferece de graca.
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cliente",
    responses={409: {"model": ErrorResponse, "description": "E-mail ja cadastrado"}},
)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ClientOut:
    """Cadastra um novo cliente.

    O QUE ACONTECE ANTES DESTA FUNCAO RODAR:
      1. O FastAPI le o corpo da requisicao e monta um ClientCreate.
      2. Se algum campo for invalido (e-mail sem @, nome vazio, telefone com
         5 digitos), o Pydantic recusa e o FastAPI devolve 422 sozinho --
         esta funcao NEM E' CHAMADA.
      3. Depends(get_db) abre uma sessao de banco para esta requisicao.

    Ou seja: quando o codigo abaixo executa, os dados JA sao validos.
    """
    return client_service.create_client(db, payload)


@router.get("", response_model=Page[ClientOut], summary="Listar clientes")
def list_clients(
    # Query(...) declara parametros da URL: /api/clients?search=tech&limit=50
    # O FastAPI converte o texto da URL para o tipo certo e valida os limites.
    # le=500 ("less or equal") impede que alguem peca 1.000.000 de registros
    # de uma vez e derrube o servidor. Isso e' protecao, nao capricho.
    search: str | None = Query(None, description="Busca por nome, empresa ou e-mail"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    sort: str | None = Query(None, description="Coluna: name, company, email, created_at"),
    order: str | None = Query(None, pattern="^(asc|desc)$"),
    escopo: int | None = Depends(escopo_do_cliente),
) -> Page[ClientOut]:
    """Lista os clientes cadastrados, com busca opcional e paginacao."""
    items, total = client_service.list_clients(
        db, search=search, limit=limit, offset=offset, client_scope=escopo,
        sort=sort, order=order
    )
    return montar_pagina(items, total, limit, offset)


# ---------------------------------------------------------------------------
# ★ ROTA LITERAL ANTES DA ROTA COM PARAMETRO
#   Se /{client_id} viesse primeiro, uma chamada a /api/clients/options seria
#   capturada por ela, que tentaria converter "options" em int -> 422.
# ---------------------------------------------------------------------------
@router.get("/options", summary="Clientes para preencher um select")
def list_client_options(
    search: str | None = Query(None, description="Filtra por nome ou empresa"),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> list[dict]:
    """Lista enxuta de clientes, para alimentar os campos de selecao.

    ★ POR QUE ESTE ENDPOINT EXISTE, SE JA HA GET /api/clients

      Sao dois usos com necessidades OPOSTAS:

        A TELA de clientes mostra 20 por vez, com todos os campos. Ela e'
        paginada porque ninguem le 1.000 linhas -- e trazer tudo travaria
        o navegador.

        O SELECT de "abrir chamado" precisa do conjunto COMPLETO (senao o
        cliente 850 nao aparece na lista e o chamado dele nao pode ser
        aberto), mas so de dois campos: id e empresa.

      Forcar os dois a usarem a mesma rota daria errado nos dois lados:
      ou a tela ficaria pesada, ou o select ficaria incompleto. Por isso
      este endpoint devolve MUITAS linhas, mas MAGRAS -- os 1.000 clientes
      aqui pesam menos que 20 clientes completos.
    """
    items, _ = client_service.list_clients(
        db, search=search, limit=limit, offset=0, client_scope=escopo
    )
    return [
        {"id": c.id, "name": c.name, "company": c.company}
        for c in items
    ]


@router.get(
    "/{client_id}",
    response_model=ClientOut,
    summary="Consultar cliente",
    responses={404: {"model": ErrorResponse, "description": "Cliente nao encontrado"}},
)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> ClientOut:
    """Busca um cliente pelo id.

    Se client_id nao for um numero (ex.: /api/clients/abc), o FastAPI devolve
    422 antes de executar esta funcao. Se for numero mas nao existir, o
    service levanta NotFoundError e o handler do main.py devolve 404.
    """
    return client_service.get_client(db, client_id, client_scope=escopo)


@router.patch(
    "/{client_id}",
    response_model=ClientOut,
    summary="Atualizar cliente (parcial)",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "E-mail ja usado por outro cliente"},
    },
)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ClientOut:
    """Altera apenas os campos enviados. PATCH, nao PUT."""
    return client_service.update_client(db, client_id, payload)


@router.delete(
    "/{client_id}",
    # ★ 204 No Content: deu certo e nao ha corpo para devolver.
    #   Devolver {"ok": true} com 200 seria redundante -- o proprio codigo
    #   ja diz que deu certo.
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir cliente",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Cliente possui historico"},
    },
)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> None:
    """Exclui um cliente que ainda nao possua chamados nem equipamentos."""
    client_service.delete_client(db, client_id)


@router.get(
    "/{client_id}/tickets",
    response_model=Page[TicketOut],
    summary="Chamados de um cliente",
    responses={404: {"model": ErrorResponse}},
)
def list_client_tickets(
    client_id: int,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> Page[TicketOut]:
    """Item 4 do Exercicio 1: consultar os chamados de determinado cliente.

    POR QUE A ROTA E' /clients/{id}/tickets E NAO /tickets?client_id={id}?
    Porque a URL passa a expressar a HIERARQUIA do dado: "os chamados que
    pertencem a este cliente". E' o estilo REST de recursos aninhados, e
    torna a API legivel sem documentacao.

    (As duas formas funcionam neste projeto -- /api/tickets?client_id=3
     tambem existe. A aninhada e' a semantica; a com filtro e' a generica.)
    """
    items, total = ticket_service.list_tickets_by_client(
        db, client_id, client_scope=escopo,
        status=status_filter, limit=limit, offset=offset,
    )
    return montar_pagina(items, total, limit, offset)
