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
from backend.app.deps import escopo_do_cliente, get_current_user, require_admin
from backend.app.models import User

from backend.app.enums import AlertStatus
from backend.app.schemas.common import ErrorResponse, Page, montar_pagina
from backend.app.schemas.equipment import AlertOut, AlertStatusUpdate
from backend.app.services import monitoring_service

router = APIRouter(prefix="/api/alerts", tags=["Monitoramento (Exercicio 3)"])


@router.get("", response_model=Page[AlertOut], summary="Listar alertas")
def list_alerts(
    status_filter: AlertStatus | None = Query(None, alias="status"),
    equipment_id: int | None = Query(None, ge=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    sort: str | None = Query(None, description="Coluna: id, identifier, company, temperature, status, created_at"),
    order: str | None = Query(None, pattern="^(asc|desc)$"),
    escopo: int | None = Depends(escopo_do_cliente),
) -> Page[AlertOut]:
    """Lista alertas do mais recente para o mais antigo.

    Cada alerta ja vem com a identificacao do equipamento e a empresa do
    cliente, obtidas por JOIN -- a tela nao precisa de requisicoes extras.
    """
    items, total = monitoring_service.list_alerts(
        db,
        equipment_id=equipment_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
        client_scope=escopo,
        sort=sort,
        order=order,
    )
    return montar_pagina(items, total, limit, offset)


@router.patch(
    "/{alert_id}/status",
    response_model=AlertOut,
    summary="Alterar status do alerta",
    responses={404: {"model": ErrorResponse}},
)
def change_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    escopo: int | None = Depends(escopo_do_cliente),
) -> AlertOut:
    """Marca um alerta como RECONHECIDO ou RESOLVIDO.

    ABERTO      -> ninguem olhou ainda
    RECONHECIDO -> um tecnico assumiu, mas o problema continua
    RESOLVIDO   -> normalizado

    Um alerta RESOLVIDO sai da contagem de pendencias, mas continua no
    historico para sempre.
    """
    return monitoring_service.change_alert_status(
        db, alert_id, payload.status, client_scope=escopo
    )
