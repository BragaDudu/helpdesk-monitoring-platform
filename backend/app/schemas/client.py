"""Schemas do Cliente -- o contrato JSON da entidade Cliente.

Sao QUATRO classes porque existem quatro formatos diferentes de cliente
trafegando pela API:

    ClientCreate   -> o que ENTRA num POST   (sem id, sem created_at)
    ClientUpdate   -> o que ENTRA num PATCH  (tudo opcional)
    ClientOut      -> o que SAI              (com id e created_at)
    ClientSummary  -> versao curta, embutida dentro de outros objetos
"""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from backend.app.schemas.common import UtcDatetime, required_text

# ---------------------------------------------------------------------------
# VALIDACAO DE TELEFONE
#
# Aceitamos o telefone escrito de forma humana -- "(11) 98888-7777",
# "11988887777", "+55 11 98888-7777" -- e validamos apenas a QUANTIDADE de
# digitos, ignorando pontuacao.
#
#   10 digitos = fixo com DDD          (11) 3333-4444
#   11 digitos = celular com DDD       (11) 98888-7777
#   12-13      = com codigo do pais    +55 11 98888-7777
#
# POR QUE NAO UM REGEX RIGIDO DE FORMATO? Porque rejeitaria telefone valido
# escrito de forma diferente, e o usuario nao entenderia o motivo. Validar
# a ESSENCIA (quantos digitos) e ser tolerante com a FORMA e' mais util.
# ---------------------------------------------------------------------------
_ONLY_DIGITS = re.compile(r"\D")


def _validate_phone(value: str) -> str:
    digits = _ONLY_DIGITS.sub("", value or "")
    if not 10 <= len(digits) <= 13:
        raise ValueError(
            "Telefone deve ter entre 10 e 13 digitos "
            "(ex.: (11) 98888-7777 ou +55 11 98888-7777)."
        )
    return value.strip()


class ClientBase(BaseModel):
    """Campos comuns a criacao e leitura. Existe so para nao repetir codigo."""

    # EmailStr vem do Pydantic (via email-validator). Ele checa formato,
    # dominio e caracteres proibidos. "joao@" ou "joao.com" sao rejeitados
    # com HTTP 422 antes de chegar ao service.
    name: required_text(2, 120)
    company: required_text(2, 120)
    email: EmailStr
    phone: required_text(10, 25)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return _validate_phone(value)


class ClientCreate(ClientBase):
    """Corpo do POST /api/clients.

    Note o que NAO existe aqui: id e created_at. Se o cliente da API pudesse
    escolher o proprio id, ele poderia sobrescrever outro cliente. Quem gera
    id e' o banco; quem gera created_at e' o servidor. Nunca o requisitante.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Joao da Silva",
                "company": "Tech Solutions LTDA",
                "email": "joao.silva@techsolutions.com.br",
                "phone": "(11) 98888-7777",
            }
        }
    )


class ClientUpdate(BaseModel):
    """Corpo do PATCH /api/clients/{id}. TODOS os campos sao opcionais.

    E' isso que diferencia PATCH de PUT: em PATCH voce manda so o que quer
    mudar. Se o campo nao veio no JSON, ele fica None e o service o ignora --
    diferente de "veio como null", que significaria apagar. Distinguimos os
    dois com exclude_unset=True no service.
    """

    name: required_text(2, 120) | None = None
    company: required_text(2, 120) | None = None
    email: EmailStr | None = None
    phone: required_text(10, 25) | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value) if value is not None else None


class ClientOut(ClientBase):
    """O que a API DEVOLVE ao falar de um cliente.

    from_attributes=True e' a peca que liga Pydantic e SQLAlchemy:
    autoriza o Pydantic a ler um OBJETO Python (cliente.name) em vez de
    exigir um dicionario (cliente["name"]). Sem essa linha, seria preciso
    converter o model para dict na mao em todo endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: UtcDatetime


class ClientSummary(BaseModel):
    """Versao enxuta do cliente, embutida dentro do chamado.

    POR QUE EXISTE: a tela de chamados precisa mostrar o nome da empresa em
    cada linha. Sem isso, o JavaScript teria que fazer uma requisicao extra
    por chamado para descobrir o nome -- 100 chamados = 101 requisicoes
    (o problema classico do "N+1"). Enviando um resumo junto, e' 1 so.

    NAO e' duplicacao no banco: no banco continua so o client_id. A juncao
    acontece na hora da leitura, com um JOIN.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company: str
