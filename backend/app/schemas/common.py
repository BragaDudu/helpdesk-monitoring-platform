"""Pecas reutilizadas por todos os schemas.

SCHEMA x MODEL -- a diferenca que mais cai em prova:

    MODEL  (SQLAlchemy) = como o dado e' GUARDADO   -> tabela, coluna, FK
    SCHEMA (Pydantic)   = como o dado TRAFEGA        -> JSON que entra e sai

Por que separar, se os campos sao quase iguais?
  1. SEGURANCA: o model pode ter campos que nunca devem sair na API. Se a
     resposta fosse o proprio model, qualquer coluna nova vazaria sem querer.
  2. ENTRADA != SAIDA: ao criar um cliente o JSON NAO tem "id" nem
     "created_at" (quem gera e' o banco). Na resposta, tem. Sao formatos
     diferentes, entao sao classes diferentes.
  3. CONTRATO: o schema e' o que o FastAPI usa para gerar o Swagger. Ele
     documenta a API sozinho.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, PlainSerializer, StringConstraints


# ---------------------------------------------------------------------------
# DATA/HORA NA SAIDA DA API
# ---------------------------------------------------------------------------
# No banco guardamos UTC sem fuso (ver backend/app/utils.py). Aqui, ao
# serializar para JSON, acrescentamos o sufixo "Z", que no padrao ISO-8601
# significa exatamente "este horario e' UTC".
#
#     no banco:  2026-09-01 14:32:10
#     na API:    "2026-09-01T14:32:10Z"
#
# POR QUE ISSO IMPORTA: no JavaScript, new Date("2026-09-01T14:32:10Z")
# entende que e' UTC e converte sozinho para o fuso do usuario ao exibir.
# SEM o "Z", o navegador assumiria que ja e' horario local e mostraria 3
# horas erradas no Brasil.
#
# PlainSerializer = "quando for transformar este campo em JSON, use esta
# funcao". Descartamos os microssegundos porque nao tem utilidade na tela.
# ---------------------------------------------------------------------------
UtcDatetime = Annotated[
    datetime,
    PlainSerializer(
        lambda value: value.replace(microsecond=0).isoformat() + "Z",
        return_type=str,
    ),
]


# ---------------------------------------------------------------------------
# TEXTOS OBRIGATORIOS
# ---------------------------------------------------------------------------
# strip_whitespace=True remove espacos das pontas ANTES de medir o tamanho.
# Sem isso, um nome com tres espacos ("   ") passaria por "3 caracteres".
# Com isso, vira "" e o min_length rejeita. E' a validacao que impede o
# classico campo obrigatorio preenchido com espaco.
# ---------------------------------------------------------------------------
def required_text(min_length: int, max_length: int):
    """Gera um tipo de texto obrigatorio, ja sem espacos nas pontas."""
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=min_length, max_length=max_length
        ),
    ]


class ErrorResponse(BaseModel):
    """Formato UNICO de erro da API inteira.

    Toda falha -- 404, 409, 422, 500 -- devolve este mesmo formato. Assim o
    JavaScript tem um so caminho de tratamento:

        if (!response.ok) { mostrarToast(json.detail) }

    Se cada endpoint inventasse o seu formato, o frontend viraria um
    emaranhado de "if" tentando adivinhar onde esta a mensagem.
    """

    error: str          # codigo estavel para o codigo ler: "not_found"
    detail: str         # mensagem em portugues para o humano ler

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "not_found",
                "detail": "Cliente com id 999 nao foi encontrado.",
            }
        }
    }
