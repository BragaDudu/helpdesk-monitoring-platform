"""Regras de autenticacao.

Como todo service do projeto, este arquivo nao sabe que HTTP existe: ele
levanta UnauthorizedError, e o main.py traduz para 401.
"""

import time

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.config import settings
from backend.app.exceptions import UnauthorizedError
from backend.app.models import User
from backend.app.security import conferir_senha, criar_token, hash_senha


def autenticar(db: Session, email: str, senha: str) -> tuple[User, str]:
    """Confere e-mail e senha. Devolve (usuario, token).

    ★★★ O DETALHE MAIS IMPORTANTE DESTA FUNCAO ★★★

      Repare que existe UMA unica mensagem de erro para tres situacoes
      diferentes: e-mail inexistente, senha errada e usuario desativado.

      POR QUE: se a resposta fosse "e-mail nao cadastrado" num caso e
      "senha incorreta" no outro, qualquer pessoa descobriria quais e-mails
      existem no sistema apenas testando o formulario -- sem precisar
      acertar senha nenhuma. Isso e' um vazamento de dado real
      ("enumeracao de usuarios"), e e' a falha mais comum em tela de login.

    ★ E O SEGUNDO DETALHE: a comparacao de senha roda MESMO quando o e-mail
      nao existe (veja _senha_falsa abaixo). Sem isso, a resposta para
      "e-mail inexistente" voltaria em 1 milissegundo e a de "senha errada"
      em 100 milissegundos -- e daria para enumerar usuarios pelo RELOGIO,
      mesmo com a mensagem igual. Gastar o mesmo tempo nos dois casos fecha
      essa porta.
    """
    stmt = (
        select(User)
        .options(joinedload(User.client))
        .where(User.email == email.strip().lower())
    )
    usuario = db.execute(stmt).scalar_one_or_none()

    if usuario is None:
        _gastar_tempo_equivalente(senha)
        raise UnauthorizedError("E-mail ou senha incorretos.")

    if not conferir_senha(senha, usuario.password_hash):
        raise UnauthorizedError("E-mail ou senha incorretos.")

    if not usuario.is_active:
        raise UnauthorizedError("E-mail ou senha incorretos.")

    token = criar_token(
        user_id=usuario.id,
        role=usuario.role.value,
        client_id=usuario.client_id,
    )
    return usuario, token


# Hash descartavel, calculado uma vez quando o modulo carrega.
_HASH_DESCARTAVEL = hash_senha("uma-senha-que-nunca-sera-usada")


def _gastar_tempo_equivalente(senha: str) -> None:
    """Queima o mesmo tempo de CPU de uma conferencia real.

    Serve so para que "e-mail nao existe" demore igual a "senha errada".
    O resultado e' descartado de proposito.
    """
    conferir_senha(senha, _HASH_DESCARTAVEL)


def montar_usuario_out(usuario: User) -> dict:
    """Monta o dicionario do usuario para a resposta da API.

    Acrescenta client_company, que nao e' coluna de users: vem do
    relacionamento com clients. A tela usa isso para escrever o nome da
    empresa no cabecalho.
    """
    return {
        "id": usuario.id,
        "name": usuario.name,
        "email": usuario.email,
        "role": usuario.role,
        "client_id": usuario.client_id,
        "client_company": usuario.client.company if usuario.client else None,
        "created_at": usuario.created_at,
    }


def segundos_ate_expirar() -> int:
    """Quanto tempo o token recem-criado vale, em segundos."""
    return settings.TOKEN_EXPIRE_MINUTES * 60
