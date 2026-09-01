"""Model EquipmentReading -- tabela "equipment_readings" (Exercicio 3).

Cada linha e' UMA medicao enviada por um equipamento. E' um registro
HISTORICO e IMUTAVEL: uma vez gravado, nao se altera nem se apaga.
Por isso nao existe endpoint de PUT/DELETE para leituras.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.enums import EquipmentStatus
from backend.app.utils import utcnow

if TYPE_CHECKING:
    from backend.app.models.alert import Alert
    from backend.app.models.equipment import Equipment


class EquipmentReading(Base):
    """Uma leitura de temperatura enviada por um equipamento."""

    __tablename__ = "equipment_readings"

    id: Mapped[int] = mapped_column(primary_key=True)

    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Float porque temperatura tem casa decimal (85.4). Usar Integer
    # arredondaria e poderia esconder o cruzamento do limite de 80 graus.
    temperature: Mapped[float] = mapped_column(Float, nullable=False)

    # Status reportado PELO EQUIPAMENTO no momento da leitura.
    status: Mapped[EquipmentStatus] = mapped_column(
        SAEnum(EquipmentStatus, native_enum=False, create_constraint=True, length=15, name="reading_status_enum"),
        nullable=False,
        default=EquipmentStatus.ONLINE,
    )

    # -----------------------------------------------------------------------
    # recorded_at aceita valor vindo de fora, diferente das outras datas.
    #
    # POR QUE? Um sensor pode ficar sem internet e enviar depois um lote de
    # leituras antigas. Se o servidor sempre carimbasse "agora", o historico
    # ficaria errado. Entao: se o cliente informar a data, respeitamos; se
    # nao informar, usamos utcnow(). Quem aplica essa regra e' o service.
    # -----------------------------------------------------------------------
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, index=True
    )

    equipment: Mapped["Equipment"] = relationship(back_populates="readings")

    # Lado "0..1" do relacionamento com Alert: uma leitura pode nao ter alerta
    # (temperatura normal) ou ter exatamente um. uselist=False faz o
    # SQLAlchemy devolver um objeto, e nao uma lista.
    alert: Mapped[Optional["Alert"]] = relationship(
        back_populates="reading", uselist=False, passive_deletes=True
    )

    __table_args__ = (
        # CHECK direto no banco: faixa fisicamente plausivel para um sensor.
        # E' a ultima linha de defesa, caso alguem escreva direto no SQLite.
        CheckConstraint(
            "temperature >= -50 AND temperature <= 200",
            name="ck_reading_temperature_range",
        ),
        # Indice composto para as duas consultas quentes do modulo:
        #   "historico do equipamento X, mais recente primeiro"
        #   "temperatura atual do equipamento X" (= a leitura mais recente)
        Index("ix_readings_equipment_recorded", "equipment_id", "recorded_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<EquipmentReading id={self.id} equipment_id={self.equipment_id} "
            f"temp={self.temperature}>"
        )
