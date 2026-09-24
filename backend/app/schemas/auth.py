"""Schemas de autenticacao -- o contrato JSON do login."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.app.enums import UserRole
from backend.app.schemas.common import UtcDatetime


class LoginRequest(BaseModel):
    """Corpo do POST /api/auth/login."""

    email: EmailStr

    # ★ min_length=8 E NAO 5:
    #   senha nao e' campo de texto comum. Cada caractere a mais multiplica
    #   o custo de quebrar por forca bruta. 8 e' o minimo aceitavel hoje;
    #   abaixo disso, mesmo com PBKDF2, um ataque com dicionario resolve.
    #
    # ★ E POR QUE NAO EXIGIMOS MAIUSCULA, NUMERO E SIMBOLO?
    #   Porque essas regras produzem "Senha123!" -- previsivel e curta. As
    #   recomendacoes atuais (NIST) preferem SENHAS LONGAS a senhas
    #   complicadas. Aqui o minimo e' comprimento; o resto e' escolha do
    #   usuario.
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "admin@helpdesk.com.br", "password": "admin12345"}
        }
    )


class UserOut(BaseModel):
    """Os dados do usuario que a API devolve.

    ★ REPARE NO QUE **NAO** ESTA AQUI: password_hash.
      O model User tem essa coluna; este schema nao. E' exatamente para isso
      que schema e model sao classes separadas -- se a resposta fosse o
      proprio model, o hash das senhas iria junto em toda resposta de login.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    client_id: int | None = None
    # Preenchido pelo service: o nome da empresa, para a tela escrever
    # "Alfa Tecnologia" no cabecalho em vez de "empresa 3".
    client_company: str | None = None
    created_at: UtcDatetime


class LoginResponse(BaseModel):
    """O que o login devolve quando da' certo.

    token_type="bearer" segue o padrao OAuth2: diz ao cliente COMO usar o
    token, ou seja, no cabecalho `Authorization: Bearer <token>`. Parece
    redundante, mas e' o que permite bibliotecas genericas (e o proprio
    Swagger) saberem montar a requisicao sozinhas.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos ate expirar -- a tela pode avisar antes
    user: UserOut
