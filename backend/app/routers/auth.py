"""Endpoints de autenticacao."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_user
from backend.app.models import User
from backend.app.schemas.auth import LoginRequest, LoginResponse, UserOut
from backend.app.schemas.common import ErrorResponse
from backend.app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Autenticacao"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Entrar no sistema",
    responses={401: {"model": ErrorResponse, "description": "E-mail ou senha incorretos"}},
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Troca e-mail e senha por um token de acesso.

    ★ POR QUE POST E NAO GET

      GET coloca os dados na URL, e URL vai para o historico do navegador,
      para o log do servidor e para o cabecalho Referer. A senha vazaria em
      tres lugares. POST manda no CORPO da requisicao, que nao e' registrado
      em nenhum desses.

    ★ O QUE ACONTECE DEPOIS: o cliente guarda o token e o envia em toda
      requisicao seguinte, no cabecalho Authorization. A senha nunca mais
      trafega.
    """
    usuario, token = auth_service.autenticar(db, payload.email, payload.password)
    return LoginResponse(
        access_token=token,
        expires_in=auth_service.segundos_ate_expirar(),
        user=UserOut(**auth_service.montar_usuario_out(usuario)),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Quem sou eu",
    responses={401: {"model": ErrorResponse}},
)
def me(usuario: User = Depends(get_current_user)) -> UserOut:
    """Devolve os dados do usuario do token atual.

    PARA QUE SERVE NA PRATICA: ao abrir qualquer pagina, o frontend chama
    este endpoint. Se responder 200, o token ainda vale e a tela sabe o
    nome e o papel de quem entrou. Se responder 401, o token expirou e a
    tela manda para o login.

    ★ E' o servidor quem decide o papel, nao a tela. O frontend ate guarda
      o papel para esconder botao, mas isso e' conveniencia visual -- quem
      barra de verdade e' a dependencia require_admin em cada rota.
    """
    return UserOut(**auth_service.montar_usuario_out(usuario))


@router.post("/logout", status_code=204, summary="Sair")
def logout() -> None:
    """Encerra a sessao.

    ★ NAO HA NADA PARA FAZER NO SERVIDOR -- e isso merece explicacao,
      porque parece um endpoint vazio por preguica.

      Este token e' "sem estado" (stateless): o servidor nao guarda lista
      de sessoes ativas, ele apenas confere a assinatura. Logo, nao existe
      registro para apagar. Quem esquece o token e' o CLIENTE.

      CONSEQUENCIA HONESTA: um token roubado continua valendo ate expirar,
      mesmo depois do logout. Para invalidar na hora seria preciso manter
      uma lista de tokens revogados no servidor -- o que devolve o estado
      que o token existia para evitar.

      O endpoint existe assim mesmo por dois motivos: manter o contrato da
      API completo, e ter o lugar pronto caso um dia a revogacao entre.
    """
    return None
