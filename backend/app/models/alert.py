"""Model Alert -- tabela "alerts" (Exercicio 3).

Um alerta e' criado PELO BACKEND quando uma leitura viola uma regra --
hoje, temperatura acima do limite configurado (80 graus por padrao).

Nunca e' criado pelo frontend. Nao existe POST /api/alerts.
Alerta e' CONSEQUENCIA de uma leitura, nao algo que se cadastra.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.enums import AlertStatus, AlertType
from backend.app.utils import utcnow

if TYPE_CHECKING:
    from backend.app.models.equipment import Equipment
    from backend.app.models.reading import EquipmentReading


class Alert(Base):
    """Alerta gerado automaticamente a partir de uma leitura anormal."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)

    # FK redundante em relacao a reading_id (daria para chegar ao equipamento
    # via leitura). E' intencional: listar "todos os alertas do equipamento X"
    # e' a consulta mais comum da tela de alertas, e assim ela nao precisa de
    # JOIN. Troca consciente de um pouco de espaco por velocidade de leitura.
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------------------------
    # ★ A CONSTRAINT MAIS IMPORTANTE DO PROJETO ★
    #
    # unique=True em reading_id garante, NO BANCO, que uma leitura gera no
    # maximo UM alerta.
    #
    # Isto responde diretamente a pergunta classica de banca:
    #   "E se duas requisicoes tentarem criar o alerta ao mesmo tempo?"
    #
    # Resposta: a segunda viola a constraint UNIQUE, o banco recusa o INSERT
    # e a transacao e' revertida. A garantia esta no BANCO, nao num "if" do
    # Python. Um "if verificar_se_ja_existe()" sofreria race condition: as
    # duas requisicoes poderiam verificar ao mesmo tempo, ambas veriam
    # "nao existe" e ambas inseririam. A constraint UNIQUE e' atomica e nao
    # tem esse problema.
    # -----------------------------------------------------------------------
    reading_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_readings.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    alert_type: Mapped[AlertType] = mapped_column(
        SAEnum(AlertType, native_enum=False, create_constraint=True, length=30, name="alert_type_enum"),
        nullable=False,
        default=AlertType.TEMPERATURA_CRITICA,
        index=True,
    )

    # Copia da temperatura que disparou o alerta. E' a UNICA desnormalizacao
    # deliberada do projeto: um "retrato" do valor no instante do disparo,
    # para a listagem de alertas nao depender de JOIN com readings.
    temperature: Mapped[float] = mapped_column(Float, nullable=False)

    # Mensagem legivel, montada pelo service. Fica gravada para que o
    # historico continue explicavel mesmo que o limite de 80 graus mude
    # depois -- o alerta antigo continua dizendo qual era o limite na epoca.
    message: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, native_enum=False, create_constraint=True, length=15, name="alert_status_enum"),
        nullable=False,
        default=AlertStatus.ABERTO,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, index=True
    )

    equipment: Mapped["Equipment"] = relationship(back_populates="alerts")
    reading: Mapped["EquipmentReading"] = relationship(back_populates="alert")

    def __repr__(self) -> str:
        return (
            f"<Alert id={self.id} equipment_id={self.equipment_id} "
            f"temp={self.temperature} status={self.status}>"
        )
