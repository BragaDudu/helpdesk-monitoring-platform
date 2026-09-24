"""Schemas do Chamado -- o contrato JSON da entidade Ticket."""

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from backend.app.enums import (
    CATEGORY_LABELS,
    TICKET_SUBCATEGORIES,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from backend.app.schemas.client import ClientSummary
from backend.app.schemas.common import UtcDatetime, required_text


class TicketCreate(BaseModel):
    """Corpo do POST /api/tickets.

    O QUE O CLIENTE DA API ENVIA:
        client_id, title, description, category, priority

    O QUE ELE **NAO** ENVIA (e nao pode enviar):
        id         -> gerado pelo banco
        status     -> todo chamado nasce ABERTO, por definicao do negocio
        opened_at  -> carimbado pelo SERVIDOR com a hora real
        closed_at  -> so existe quando o chamado for finalizado

    ★ Este e' o ponto do enunciado "nao invente datas no frontend": nao ha
      nem como inventar, porque o campo simplesmente nao existe no contrato
      de entrada. Se o JavaScript mandar "opened_at", o Pydantic ignora.
    """

    # gt=0 significa "greater than 0". Ids comecam em 1; um id 0 ou negativo
    # e' invalido por construcao, e vale barrar antes de ir ao banco.
    client_id: int = Field(gt=0, description="ID do cliente dono do chamado")

    title: required_text(3, 150)
    description: required_text(5, 5000)

    # Enum, nao mais texto livre. "Rede " com espaco agora e' 422.
    category: TicketCategory

    # Opcional: o problema especifico dentro da categoria.
    subcategory: str | None = Field(
        default=None, max_length=60,
        description="Problema especifico; precisa pertencer a categoria escolhida",
    )

    # O tipo e' o Enum. Se chegar "URGENTE", o Pydantic devolve 422 com a
    # lista dos valores aceitos. Nao chega no service, nao chega no banco.
    priority: TicketPriority

    # -----------------------------------------------------------------------
    # ★ VALIDACAO QUE DEPENDE DE DOIS CAMPOS
    #
    # "Fonte queimada" e' valida em HARDWARE e invalida em TELEFONIA. Isso
    # nao da para checar olhando so a subcategoria -- e' preciso ver a
    # categoria junto. Por isso usamos model_validator (que roda depois de
    # todos os campos) em vez de field_validator (que ve um campo so).
    #
    # E POR QUE NAO UMA CHECK CONSTRAINT NO BANCO? Daria, mas seria uma
    # expressao gigante com 50 combinacoes, ilegivel e chata de manter. Aqui
    # a regra e' declarativa: esta no dicionario TICKET_SUBCATEGORIES.
    # -----------------------------------------------------------------------
    @model_validator(mode="after")
    def check_subcategory(self) -> "TicketCreate":
        if self.subcategory is None:
            return self
        permitidas = TICKET_SUBCATEGORIES.get(self.category, [])
        if self.subcategory not in permitidas:
            raise ValueError(
                f"'{self.subcategory}' nao e' uma subcategoria de "
                f"{CATEGORY_LABELS[self.category]}. "
                f"Opcoes: {', '.join(permitidas)}."
            )
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": 1,
                "title": "Servidor de arquivos fora do ar",
                "description": "Desde as 08h ninguem acessa a pasta compartilhada.",
                "category": "INFRAESTRUTURA",
                "subcategory": "Servidor fora do ar",
                "priority": "ALTA",
            }
        }
    )


class TicketStatusUpdate(BaseModel):
    """Corpo do PATCH /api/tickets/{id}/status.

    Um campo so. E' de proposito: o endpoint faz UMA coisa. Se aceitasse
    titulo e descricao junto, seria um "update generico" disfarcado e a
    regra de transicao de status ficaria misturada com edicao de texto.
    """

    status: TicketStatus

    model_config = ConfigDict(json_schema_extra={"example": {"status": "EM_ANDAMENTO"}})


class TicketOut(BaseModel):
    """O que a API DEVOLVE ao falar de um chamado.

    Repare em "client: ClientSummary". No BANCO existe apenas a coluna
    client_id. Aqui, na saida, entregamos o objeto do cliente ja montado.

    COMO ISSO ACONTECE: o service faz a consulta com joinedload(Ticket.client),
    o SQLAlchemy gera um JOIN, e o relacionamento .client fica preenchido.
    O Pydantic entao le ticket.client e monta o JSON aninhado.

    ISSO NAO E' DUPLICACAO DE DADO: nada foi copiado na tabela. E' juncao
    feita na hora da leitura -- exatamente para o que serve um JOIN.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client: ClientSummary

    title: str
    description: str
    category: TicketCategory
    subcategory: str | None = None
    priority: TicketPriority
    status: TicketStatus

    opened_at: UtcDatetime

    # None enquanto o chamado nao for finalizado. No JSON sai como null.
    # E' informacao: null = "ainda nao fechou".
    closed_at: UtcDatetime | None = None

    # -----------------------------------------------------------------------
    # CAMPO CALCULADO -- existe no JSON, nao existe no banco.
    #
    # O banco guarda ACESSO_E_SENHA; a tela precisa de "Acesso e Senha".
    # Em vez de o JavaScript manter a propria tabela de traducao (que sairia
    # do ar assim que uma categoria nova nascesse), o backend ja entrega o
    # rotulo pronto. Uma fonte da verdade so.
    # -----------------------------------------------------------------------
    @computed_field
    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category.value)
