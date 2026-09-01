"""Endpoints HTTP de Equipamentos, Leituras e deteccao de anomalias."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.enums import AlertStatus, EquipmentStatus
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.equipment import (
    AlertOut,
    AnomalyItem,
    EquipmentCreate,
    EquipmentOut,
    EquipmentStatusUpdate,
    ReadingCreate,
    ReadingCreatedResponse,
    ReadingOut,
)
from backend.app.services import monitoring_service

router = APIRouter(prefix="/api/equipments", tags=["Monitoramento (Exercicio 3)"])


@router.post(
    "",
    response_model=EquipmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar equipamento",
    responses={
        404: {"model": ErrorResponse, "description": "Cliente nao encontrado"},
        409: {"model": ErrorResponse, "description": "Identificacao ja cadastrada"},
    },
)
def create_equipment(
    payload: EquipmentCreate, db: Session = Depends(get_db)
) -> EquipmentOut:
    """Cadastra um equipamento instalado em um cliente."""
    return monitoring_service.create_equipment(db, payload)


@router.get("", response_model=list[EquipmentOut], summary="Listar equipamentos")
def list_equipments(
    client_id: int | None = Query(None, ge=1),
    status_filter: EquipmentStatus | None = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[EquipmentOut]:
    """Lista equipamentos com a TEMPERATURA ATUAL e os alertas abertos.

    A temperatura atual vem da leitura mais recente, trazida por uma
    subconsulta correlacionada na MESMA consulta -- nao ha requisicao extra
    por equipamento.
    """
    return monitoring_service.list_equipments(
        db,
        client_id=client_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# ★ ATENCAO A ORDEM DAS ROTAS
#
# Esta rota (/anomalies) PRECISA ser declarada ANTES de /{equipment_id}.
#
# O FastAPI testa as rotas na ordem de registro. Se /{equipment_id} viesse
# primeiro, uma chamada a /api/equipments/anomalies seria capturada por ela,
# que tentaria converter "anomalies" em int e devolveria 422.
#
# Rotas com caminho FIXO sempre antes de rotas com PARAMETRO. Este e' um dos
# erros mais comuns em APIs -- e um otimo ponto para mostrar na apresentacao.
# ---------------------------------------------------------------------------
@router.get(
    "/anomalies",
    response_model=list[AnomalyItem],
    summary="Detectar situacoes anormais",
)
def detect_anomalies(db: Session = Depends(get_db)) -> list[AnomalyItem]:
    """Item 5 do Exercicio 3: detectar situacoes anormais.

    Diferente do alerta (que e' um EVENTO gravado no banco), a anomalia e'
    um DIAGNOSTICO DO MOMENTO, calculado na hora:

      TEMPERATURA_CRITICA  ultima leitura acima do limite
      TEMPERATURA_ELEVADA  na zona de atencao, antes de virar problema
      SEM_COMUNICACAO      sem leituras ha mais de N horas
      SEM_LEITURA          cadastrado, mas nunca enviou nada
      EQUIPAMENTO_OFFLINE  status OFFLINE

    Ordenado por severidade: o que precisa de atencao aparece primeiro.
    """
    return monitoring_service.detect_anomalies(db)


@router.get(
    "/{equipment_id}",
    response_model=EquipmentOut,
    summary="Consultar equipamento",
    responses={404: {"model": ErrorResponse}},
)
def get_equipment(equipment_id: int, db: Session = Depends(get_db)) -> EquipmentOut:
    """Detalhe de um equipamento, com temperatura atual e alertas abertos."""
    return monitoring_service.get_equipment(db, equipment_id)


@router.patch(
    "/{equipment_id}/status",
    response_model=EquipmentOut,
    summary="Alterar status do equipamento",
    responses={404: {"model": ErrorResponse}},
)
def change_equipment_status(
    equipment_id: int,
    payload: EquipmentStatusUpdate,
    db: Session = Depends(get_db),
) -> EquipmentOut:
    """Altera o estado operacional (ONLINE / OFFLINE / MANUTENCAO).

    Ao contrario do chamado, aqui NAO ha maquina de estados: no mundo real
    um equipamento pode ir de qualquer estado para qualquer outro.
    """
    return monitoring_service.change_equipment_status(db, equipment_id, payload.status)


# ===========================================================================
# ★★★ O ENDPOINT MAIS IMPORTANTE DO PROJETO ★★★
# ===========================================================================
@router.post(
    "/{equipment_id}/readings",
    response_model=ReadingCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar leitura (gera alerta se > limite)",
    responses={
        404: {"model": ErrorResponse, "description": "Equipamento nao encontrado"},
        422: {"model": ErrorResponse, "description": "Temperatura ou data invalida"},
    },
)
def create_reading(
    equipment_id: int, payload: ReadingCreate, db: Session = Depends(get_db)
) -> ReadingCreatedResponse:
    """Recebe uma leitura de equipamento e aplica a regra de temperatura.

    O QUE O SERVIDOR FAZ, NESTA ORDEM:
      1. valida os dados          (Pydantic, antes desta funcao)
      2. encontra o equipamento   (404 se nao existir)
      3. registra a leitura no banco
      4. verifica a temperatura contra o limite do .env
      5. se passar, cria um alerta com data/hora, ligado ao equipamento
         E a leitura que o causou
      6. informa na resposta que uma condicao critica foi detectada

    Leitura e alerta sao gravados na MESMA TRANSACAO: e' impossivel existir
    uma leitura de 90 C sem o alerta correspondente.

    ★ A REGRA ESTA AQUI, NO SERVIDOR. O frontend apenas LE o campo
      critical_condition_detected -- ele nunca compara a temperatura com 80.
      Um sensor IoT chamando este endpoint direto, sem navegador, recebe
      exatamente o mesmo tratamento.
    """
    return monitoring_service.register_reading(db, equipment_id, payload)


@router.get(
    "/{equipment_id}/readings",
    response_model=list[ReadingOut],
    summary="Historico de leituras do equipamento",
    responses={404: {"model": ErrorResponse}},
)
def list_readings(
    equipment_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ReadingOut]:
    """Item 4 do Exercicio 3: historico, da leitura mais recente para a mais antiga."""
    return monitoring_service.list_readings(db, equipment_id, limit=limit, offset=offset)


@router.get(
    "/{equipment_id}/alerts",
    response_model=list[AlertOut],
    summary="Alertas do equipamento",
    responses={404: {"model": ErrorResponse}},
)
def list_equipment_alerts(
    equipment_id: int,
    status_filter: AlertStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    """Todos os alertas gerados por um equipamento."""
    return monitoring_service.list_equipment_alerts(
        db, equipment_id, status=status_filter.value if status_filter else None
    )
