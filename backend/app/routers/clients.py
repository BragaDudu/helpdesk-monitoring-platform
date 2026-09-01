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
from backend.app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from backend.app.schemas.common import ErrorResponse
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
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> ClientOut:
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


@router.get("", response_model=list[ClientOut], summary="Listar clientes")
def list_clients(
    # Query(...) declara parametros da URL: /api/clients?search=tech&limit=50
    # O FastAPI converte o texto da URL para o tipo certo e valida os limites.
    # le=500 ("less or equal") impede que alguem peca 1.000.000 de registros
    # de uma vez e derrube o servidor. Isso e' protecao, nao capricho.
    search: str | None = Query(None, description="Busca por nome, empresa ou e-mail"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ClientOut]:
    """Lista os clientes cadastrados, com busca opcional."""
    return client_service.list_clients(db, search=search, limit=limit, offset=offset)


@router.get(
    "/{client_id}",
    response_model=ClientOut,
    summary="Consultar cliente",
    responses={404: {"model": ErrorResponse, "description": "Cliente nao encontrado"}},
)
def get_client(client_id: int, db: Session = Depends(get_db)) -> ClientOut:
    """Busca um cliente pelo id.

    Se client_id nao for um numero (ex.: /api/clients/abc), o FastAPI devolve
    422 antes de executar esta funcao. Se for numero mas nao existir, o
    service levanta NotFoundError e o handler do main.py devolve 404.
    """
    return client_service.get_client(db, client_id)


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
    client_id: int, payload: ClientUpdate, db: Session = Depends(get_db)
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
def delete_client(client_id: int, db: Session = Depends(get_db)) -> None:
    """Exclui um cliente que ainda nao possua chamados nem equipamentos."""
    client_service.delete_client(db, client_id)


@router.get(
    "/{client_id}/tickets",
    response_model=list[TicketOut],
    summary="Chamados de um cliente",
    responses={404: {"model": ErrorResponse}},
)
def list_client_tickets(
    client_id: int,
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    """Item 4 do Exercicio 1: consultar os chamados de determinado cliente.

    POR QUE A ROTA E' /clients/{id}/tickets E NAO /tickets?client_id={id}?
    Porque a URL passa a expressar a HIERARQUIA do dado: "os chamados que
    pertencem a este cliente". E' o estilo REST de recursos aninhados, e
    torna a API legivel sem documentacao.

    (As duas formas funcionam neste projeto -- /api/tickets?client_id=3
     tambem existe. A aninhada e' a semantica; a com filtro e' a generica.)
    """
    return ticket_service.list_tickets_by_client(db, client_id, status=status_filter)
