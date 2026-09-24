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


# ---------------------------------------------------------------------------
# PAGINACAO -- o envelope que acompanha toda listagem
# ---------------------------------------------------------------------------
# ★ POR QUE A LISTAGEM DEIXOU DE DEVOLVER UMA LISTA CRUA
#
#   Antes, GET /api/tickets devolvia [ {...}, {...} ]. Com 5.000 chamados
#   isso tem dois problemas:
#
#     1. Sem limite, seriam 5.000 objetos numa resposta so -- megabytes de
#        JSON que o navegador tem que baixar e desenhar. A tela trava.
#     2. COM limite, a lista crua nao diz quantos existem no total. O
#        frontend recebe 20 itens e nao tem como saber se sao 20 ou 5.000 --
#        e sem isso e' impossivel desenhar "pagina 3 de 250".
#
#   O envelope resolve os dois: entrega a fatia (items) e o tamanho do bolo
#   (total). E' o padrao de qualquer API que lida com volume.
#
# CUSTO HONESTO: o `total` exige um segundo SELECT COUNT(*) com os mesmos
# filtros. E' uma consulta a mais por listagem. Vale a pena porque sem ela
# nao existe paginacao de verdade -- e o COUNT usa os mesmos indices do
# WHERE, entao e' barato.
# ---------------------------------------------------------------------------
from typing import Generic, TypeVar  # noqa: E402

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Uma fatia de uma lista, com o contexto para navegar entre fatias."""

    items: list[T]
    total: int      # quantos registros existem COM ESTES FILTROS
    limit: int      # tamanho da fatia pedida
    offset: int     # quantos foram pulados
    has_more: bool  # ainda ha pagina depois desta?

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 5000,
                "limit": 20,
                "offset": 40,
                "has_more": True,
            }
        }
    }


def montar_pagina(items: list, total: int, limit: int, offset: int) -> dict:
    """Monta o envelope. Existe para os routers nao repetirem a conta.

    has_more e' CALCULADO no backend de proposito: se cada frontend tivesse
    que fazer `offset + len(items) < total` na mao, um deles erraria o sinal
    e o botao "proxima" apareceria na ultima pagina.
    """
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


# ---------------------------------------------------------------------------
# ORDENACAO
# ---------------------------------------------------------------------------
# ★ POR QUE EXISTE UMA "LISTA BRANCA" DE COLUNAS PERMITIDAS
#
#   A tentacao e' pegar o nome da coluna direto da URL e jogar no ORDER BY:
#
#       stmt.order_by(text(request.query_params["sort"]))   # NAO FACA ISSO
#
#   Isso e' SQL Injection pela porta dos fundos. Parametro do SQLAlchemy
#   protege VALORES (o "?" que voce ve no log), mas nome de coluna nao e'
#   valor -- ele entra na estrutura da consulta. Alguem mandaria
#   ?sort=(SELECT password_hash FROM users LIMIT 1) e o banco obedeceria.
#
#   Com a lista branca, o texto da URL nunca vira SQL: ele e' apenas a
#   CHAVE de um dicionario que ja contem as colunas reais. O que nao esta
#   no dicionario simplesmente nao existe.
# ---------------------------------------------------------------------------
def aplicar_ordenacao(stmt, sort: str | None, order: str | None, permitidas: dict, padrao):
    """Acrescenta ORDER BY a consulta, aceitando so colunas conhecidas.

    RECEBE:
        sort       -- nome vindo da URL (ex.: "company")
        order      -- "asc" ou "desc"
        permitidas -- {"company": Client.company, ...}
        padrao     -- lista de colunas usada quando nao pediram nada

    RETORNA: a consulta com o ORDER BY aplicado.
    """
    coluna = permitidas.get(sort or "")
    if coluna is None:
        return stmt.order_by(*padrao)

    return stmt.order_by(coluna.desc() if order == "desc" else coluna.asc())
