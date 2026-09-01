"""Endpoints HTTP de Alertas.

★ REPARE NO QUE **NAO** EXISTE AQUI: nao ha POST /api/alerts.

  Alerta nao e' algo que se cadastra -- e' CONSEQUENCIA de uma leitura
  anormal. Ele nasce dentro de register_reading(), no monitoring_service.

  Se existisse um POST de alerta, qualquer pessoa poderia criar alertas
  falsos sem nenhuma leitura por tras, e o historico deixaria de ser
  confiavel. A ausencia deste endpoint E' uma decisao de seguranca.

  Tambem nao existe DELETE: alerta nao se apaga, se RESOLVE. O historico
  de incidentes de uma empresa nao deve poder ser limpo.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.enums import AlertStatus
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.equipment import AlertOut, AlertStatusUpdate
from backend.app.services import monitoring_service

router = APIRouter(prefix="/api/alerts", tags=["Monitoramento (Exercicio 3)"])


@router.get("", response_model=list[AlertOut], summary="Listar alertas")
def list_alerts(
    status_filter: AlertStatus | None = Query(None, alias="status"),
    equipment_id: int | None = Query(None, ge=1),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    """Lista alertas do mais recente para o mais antigo.

    Cada alerta ja vem com a identificacao do equipamento e a empresa do
    cliente, obtidas por JOIN -- a tela nao precisa de requisicoes extras.
    """
    return monitoring_service.list_alerts(
        db,
        equipment_id=equipment_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{alert_id}/status",
    response_model=AlertOut,
    summary="Alterar status do alerta",
    responses={404: {"model": ErrorResponse}},
)
def change_alert_status(
    alert_id: int, payload: AlertStatusUpdate, db: Session = Depends(get_db)
) -> AlertOut:
    """Marca um alerta como RECONHECIDO ou RESOLVIDO.

    ABERTO      -> ninguem olhou ainda
    RECONHECIDO -> um tecnico assumiu, mas o problema continua
    RESOLVIDO   -> normalizado

    Um alerta RESOLVIDO sai da contagem de pendencias, mas continua no
    historico para sempre.
    """
    return monitoring_service.change_alert_status(db, alert_id, payload.status)
