"""Model Ticket -- tabela "tickets".

DECISAO DE MODELAGEM IMPORTANTE
    O Exercicio 1 descreve o chamado com titulo/descricao/prioridade/status/data.
    O Exercicio 2 descreve o chamado com categoria/abertura/fechamento/status/
    prioridade.
    SAO A MESMA ENTIDADE, descrita sob dois pontos de vista (atendimento e
    analise). Por isso existe UMA tabela com a uniao dos campos, e nao duas.
    Duas tabelas gerariam dados duplicados e impediriam analisar o conjunto.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.enums import TicketPriority, TicketStatus
from backend.app.utils import utcnow

if TYPE_CHECKING:
    from backend.app.models.client import Client


class Ticket(Base):
    """Um chamado aberto por um cliente."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)

    # -----------------------------------------------------------------------
    # FOREIGN KEY -- o coracao da modelagem relacional
    #
    # Guardamos APENAS o id do cliente. Nao copiamos nome, empresa nem e-mail
    # para ca.
    #
    # POR QUE? Se copiassemos e o cliente trocasse de e-mail, seria preciso
    # atualizar as 100 linhas de chamados dele. Se o processo falhasse no
    # meio, o banco ficaria com duas versoes do mesmo dado -- sem saber qual
    # e' a verdadeira. Mantendo so o id, o dado do cliente existe em UM lugar
    # e todos os chamados enxergam automaticamente a versao atual.
    # Isso se chama NORMALIZACAO.
    #
    # ondelete="RESTRICT" -> o banco proibe apagar um cliente que ainda tenha
    # chamados. O DELETE /api/clients/{id} devolvera 409 explicando o motivo.
    # -----------------------------------------------------------------------
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(150), nullable=False)

    # Text (e nao String(n)) porque descricao nao tem tamanho previsivel.
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Categoria e' texto indexado, e nao Enum, DE PROPOSITO: a empresa pode
    # criar categorias novas ("Backup", "Impressora") sem alterar o codigo.
    # Status e prioridade, ao contrario, sao o ciclo de vida do sistema --
    # esses SIM precisam ser fechados.
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # -----------------------------------------------------------------------
    # SAEnum com native_enum=False:
    #   cria uma coluna VARCHAR **mais** uma CHECK constraint com os valores
    #   permitidos. Uma unica declaracao produz as barreiras nas duas pontas:
    #   validacao em Python e validacao dentro do banco.
    #   (native_enum=True criaria um tipo ENUM nativo, que o SQLite nao tem.)
    # -----------------------------------------------------------------------
    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, native_enum=False, create_constraint=True, length=10, name="ticket_priority_enum"),
        nullable=False,
        index=True,
    )
    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, native_enum=False, create_constraint=True, length=15, name="ticket_status_enum"),
        nullable=False,
        default=TicketStatus.ABERTO,
        index=True,
    )

    # Data de abertura: carimbada pelo SERVIDOR, nunca enviada pelo frontend.
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, index=True
    )

    # -----------------------------------------------------------------------
    # closed_at PODE SER NULL -- e isso e' proposital.
    #
    # NULL significa "ainda nao aconteceu", que e' diferente de zero ou de
    # string vazia. Um chamado aberto genuinamente NAO TEM data de fechamento.
    # Preencher com uma data inventada quebraria o calculo de tempo medio de
    # resolucao do Exercicio 2. A ausencia de dado E' informacao.
    #
    # Quem preenche este campo e' o ticket_service, no instante em que o
    # status vira FINALIZADO.
    # -----------------------------------------------------------------------
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="tickets")

    # -----------------------------------------------------------------------
    # INDICES COMPOSTOS
    # Um indice comum acelera busca por UMA coluna. Um indice composto acelera
    # busca por combinacao. Criamos os dois que correspondem as consultas mais
    # frequentes do sistema:
    #   (client_id, status) -> "chamados abertos do cliente X"
    #   (status, priority)  -> a tela de chamados com os dois filtros ligados
    # -----------------------------------------------------------------------
    __table_args__ = (
        Index("ix_tickets_client_status", "client_id", "status"),
        Index("ix_tickets_status_priority", "status", "priority"),
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} client_id={self.client_id} status={self.status}>"
