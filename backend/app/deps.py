"""As dependencias de autenticacao -- o portao de entrada da API.

★ O QUE E' UMA "DEPENDENCIA" NO FASTAPI

  E' uma funcao que roda ANTES do endpoint e entrega um valor pronto para
  ele. Voce ja usa uma: get_db(), que abre a sessao do banco.

  Aqui criamos outras tres, e elas formam uma escada -- cada degrau exige
  mais que o anterior:

      get_current_user  -> "quem esta pedindo?"        401 se nao souber
      require_admin     -> "e' da empresa de TI?"      403 se nao for
      escopo_do_cliente -> "o que ele pode enxergar?"  None ou um client_id

★ POR QUE ISSO E' UMA DEPENDENCIA E NAO UM "if" DENTRO DE CADA ENDPOINT

  Porque um "if" repetido em 30 rotas e' um "if" que alguem vai esquecer em
  uma delas -- e essa uma vira o buraco por onde tudo vaza. Declarando
  `usuario = Depends(get_current_user)` na assinatura, a protecao fica
  VISIVEL na propria definicao da rota: da' para auditar lendo, sem entrar
  no corpo da funcao.

★ 401 x 403 -- a diferenca que quase todo mundo erra:

      401 Unauthorized  = "eu nao sei quem voce e'"      -> faca login
      403 Forbidden     = "eu sei quem voce e', e nao pode" -> nao adianta
                          logar de novo, seu papel nao permite
"""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.exceptions import ForbiddenError, UnauthorizedError
from backend.app.models import User
from backend.app.security import ler_token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Descobre QUEM esta fazendo a requisicao, a partir do token.

    COMO O TOKEN CHEGA: num cabecalho HTTP chamado Authorization, no
    formato definido pelo padrao Bearer:

        Authorization: Bearer eyJzdWIiOjEsInJvbGUiOi4uLg.KJ8xY2...

    ★ POR QUE NO CABECALHO E NAO NA URL:
      URL fica gravada no historico do navegador, no log do servidor e no
      cabecalho Referer enviado a outros sites. Token em URL vaza em tres
      lugares de uma vez. Cabecalho nao e' registrado por padrao.

    ERROS: 401 em qualquer falha -- ausente, mal formado, expirado,
    adulterado, usuario apagado ou desativado. Todos com a MESMA mensagem,
    de proposito: dizer "esse token expirou" x "esse usuario nao existe"
    entrega informacao util para quem esta sondando o sistema.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Faca login para acessar este recurso.")

    conteudo = ler_token(authorization[7:].strip())  # remove "Bearer "
    if conteudo is None:
        raise UnauthorizedError("Sessao invalida ou expirada. Faca login novamente.")

    usuario = db.get(User, conteudo.get("sub"))

    # ★ RELEMOS O USUARIO DO BANCO, e nao confiamos so no token.
    #   O token diz "voce e' o usuario 7, papel SUPER_ADMIN". Mas ele foi
    #   emitido ha' horas. Se nesse meio tempo o usuario 7 foi desativado ou
    #   rebaixado, o token antigo ainda afirmaria o papel antigo.
    #   Conferindo no banco, uma demissao tem efeito na proxima requisicao,
    #   nao daqui a 8 horas.
    if usuario is None or not usuario.is_active:
        raise UnauthorizedError("Sessao invalida ou expirada. Faca login novamente.")

    return usuario


def require_admin(usuario: User = Depends(get_current_user)) -> User:
    """Exige que o usuario seja da empresa de TI (SUPER_ADMIN).

    USADO EM: cadastrar/editar/excluir cliente, cadastrar equipamento.
    Sao operacoes da OPERADORA da plataforma. O responsavel de uma empresa
    atendida nao cadastra clientes -- ele e' um deles.
    """
    if not usuario.ve_tudo:
        raise ForbiddenError(
            "Apenas administradores da plataforma podem executar esta acao."
        )
    return usuario


def escopo_do_cliente(usuario: User = Depends(get_current_user)) -> int | None:
    """★ O CORACAO DO MULTI-EMPRESA. Devolve O QUE o usuario pode enxergar.

        None  -> sem restricao: e' a empresa de TI, ve todos os clientes
        3     -> so os dados do cliente 3

    Todo service de listagem recebe este valor e o transforma numa condicao
    no WHERE. Como a decisao nasce AQUI e nao dentro de cada rota, existe um
    unico ponto para revisar quando alguem perguntar "tem como o cliente A
    ver dado do cliente B?".

    ★ POR QUE None E NAO 0 OU -1 PARA "VE TUDO":
      porque None e' o unico valor que nao pode ser confundido com um id de
      verdade. Um dia o banco tem o cliente de id 0? Nao tem -- mas
      "ausencia de filtro" e "filtro pelo id 0" sao ideias diferentes, e
      merecem valores diferentes. O tipo `int | None` deixa isso explicito.
    """
    return None if usuario.ve_tudo else usuario.client_id
