"""Model Equipment -- tabela "equipments" (Exercicio 3).

Um equipamento instalado na sede de um cliente. Ele envia leituras de
temperatura periodicamente para a nossa API.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.enums import EquipmentStatus
from backend.app.utils import utcnow

if TYPE_CHECKING:
    from backend.app.models.alert import Alert
    from backend.app.models.client import Client
    from backend.app.models.reading import EquipmentReading


class Equipment(Base):
    """Equipamento monitorado."""

    __tablename__ = "equipments"

    # -----------------------------------------------------------------------
    # DOIS IDENTIFICADORES, DOIS PROPOSITOS -- e' proposital, nao duplicacao:
    #
    #   id         -> chave TECNICA, gerada pelo banco. E' o que as foreign
    #                 keys de readings e alerts apontam. Nunca muda.
    #   identifier -> a ETIQUETA FISICA colada no aparelho ("EQP-0007"), que
    #                 o tecnico le em campo.
    #
    # Se usassemos a etiqueta como PK e um dia ela precisasse ser trocada,
    # seria necessario atualizar todas as leituras e alertas ligados a ela.
    # Chave primaria deve ser um numero sem significado de negocio.
    # -----------------------------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    identifier: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # ESTADO ATUAL do equipamento. Nao confundir com o status gravado em cada
    # leitura: aquele e' um fato historico imutavel ("as 14h32 ele estava
    # ONLINE"); este e' o estado corrente. E' a mesma diferenca entre o
    # extrato bancario e o saldo da conta.
    status: Mapped[EquipmentStatus] = mapped_column(
        SAEnum(EquipmentStatus, native_enum=False, create_constraint=True, length=15, name="equipment_status_enum"),
        nullable=False,
        default=EquipmentStatus.ONLINE,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    client: Mapped["Client"] = relationship(back_populates="equipments")

    # order_by: sempre que lermos equipamento.readings, o SQLAlchemy ja
    # devolve da leitura mais RECENTE para a mais antiga -- que e' como o
    # historico e' exibido na tela.
    readings: Mapped[list["EquipmentReading"]] = relationship(
        back_populates="equipment",
        passive_deletes=True,
        order_by="EquipmentReading.recorded_at.desc()",
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="equipment",
        passive_deletes=True,
        order_by="Alert.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Equipment id={self.id} identifier={self.identifier!r} status={self.status}>"
