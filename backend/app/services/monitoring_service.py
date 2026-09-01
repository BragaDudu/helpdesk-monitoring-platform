"""★ A REGRA DE NEGOCIO MAIS IMPORTANTE DO PROJETO ★

    Quando uma leitura chega, se a temperatura passar do limite
    configurado (80 C por padrao), o sistema REGISTRA UM ALERTA NO BANCO.

POR QUE ESTA REGRA MORA NO BACKEND, E NAO NO JAVASCRIPT
-------------------------------------------------------
Sao tres motivos, e voce precisa saber os tres:

 1. O NAVEGADOR NAO E' A UNICA PORTA DE ENTRADA.
    Um sensor IoT instalado na sala de servidores vai chamar
    POST /api/equipments/7/readings direto, sem navegador nenhum. Se a
    regra estivesse no JavaScript da pagina, ela simplesmente NAO RODARIA
    para o cliente mais importante do sistema -- o proprio equipamento.

 2. O CODIGO DO CLIENTE E' CONTROLAVEL PELO USUARIO.
    Qualquer pessoa abre o DevTools do navegador e desativa o JavaScript,
    ou edita a variavel do limite. Regra que roda no cliente e' sugestao,
    nao garantia. Regra que roda no servidor e' garantia.

 3. CONSISTENCIA.
    Se amanha existirem um app mobile, um script de importacao em lote e
    a pagina web, cada um reimplementaria a regra -- e algum deles usaria
    ">= 80" em vez de "> 80". Uma regra, um lugar, um comportamento.

O frontend PODE (e vai) mostrar a informacao em vermelho. Mas ele apenas
LE a decisao que o servidor tomou, no campo critical_condition_detected.
Ele nunca compara a temperatura com 80.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.config import settings
from backend.app.enums import AlertStatus, AlertType, EquipmentStatus
from backend.app.exceptions import ConflictError, NotFoundError
from backend.app.models import Alert, Client, Equipment, EquipmentReading
from backend.app.schemas.equipment import (
    AnomalyItem,
    EquipmentCreate,
    ReadingCreate,
)
from backend.app.services.client_service import get_client
from backend.app.utils import utcnow

# ===========================================================================
# EQUIPAMENTOS
# ===========================================================================


def create_equipment(db: Session, payload: EquipmentCreate) -> Equipment:
    """Cadastra um equipamento vinculado a um cliente.

    ERROS:
        404 -> o cliente informado nao existe
        409 -> ja existe equipamento com essa identificacao (coluna UNIQUE)
    """
    get_client(db, payload.client_id)

    equipment = Equipment(
        client_id=payload.client_id,
        identifier=payload.identifier,
        name=payload.name,
        location=payload.location,
        status=payload.status,
    )
    db.add(equipment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"Ja existe um equipamento com a identificacao "
            f"'{payload.identifier}'."
        ) from exc

    db.refresh(equipment)
    return get_equipment(db, equipment.id)


def _last_reading_subqueries():
    """Monta as subconsultas que trazem a leitura mais recente e a contagem
    de alertas abertos de cada equipamento.

    ★ SUBCONSULTA CORRELACIONADA -- vale entender bem:

        SELECT MAX(id) FROM equipment_readings
        WHERE equipment_id = equipments.id
                             ^^^^^^^^^^^^^ referencia a linha "de fora"

      Para CADA equipamento da consulta principal, o banco resolve esta
      subconsulta usando o id daquele equipamento. E' como um "for" feito
      pelo proprio banco, com indice.

    POR QUE MAX(id) E NAO MAX(recorded_at)?
      Porque duas leituras podem ter EXATAMENTE o mesmo recorded_at (um
      lote enviado de uma vez). MAX(recorded_at) devolveria duas linhas
      empatadas e o JOIN duplicaria o equipamento no resultado.
      O id e' unico e sempre crescente: nunca empata.
    """
    last_reading_id = (
        select(func.max(EquipmentReading.id))
        .where(EquipmentReading.equipment_id == Equipment.id)
        .correlate(Equipment)
        .scalar_subquery()
    )
    open_alerts_count = (
        select(func.count(Alert.id))
        .where(Alert.equipment_id == Equipment.id)
        .where(Alert.status == AlertStatus.ABERTO)
        .correlate(Equipment)
        .scalar_subquery()
    )
    return last_reading_id, open_alerts_count


def _rows_to_equipment_out(rows) -> list[dict]:
    """Converte as linhas da consulta em dicionarios prontos para o schema.

    Cada linha traz: o objeto Equipment, o objeto da ultima leitura (ou
    None) e a contagem de alertas abertos.
    """
    result = []
    for equipment, reading, open_alerts in rows:
        result.append(
            {
                "id": equipment.id,
                "client_id": equipment.client_id,
                "client": equipment.client,
                "identifier": equipment.identifier,
                "name": equipment.name,
                "location": equipment.location,
                "status": equipment.status,
                "created_at": equipment.created_at,
                "last_temperature": reading.temperature if reading else None,
                "last_reading_at": reading.recorded_at if reading else None,
                "open_alerts": int(open_alerts or 0),
            }
        )
    return result


def list_equipments(
    db: Session,
    client_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Lista equipamentos JA COM a temperatura atual e os alertas abertos.

    UMA consulta traz tudo: equipamento + cliente (JOIN) + ultima leitura
    (LEFT JOIN com subconsulta) + contagem de alertas (subconsulta).

    Sem isso, a tela de equipamentos faria 1 requisicao para a lista e mais
    2 por equipamento (ultima leitura e alertas). Com 15 equipamentos
    seriam 31 requisicoes. Agora e' 1.
    """
    last_reading_id, open_alerts_count = _last_reading_subqueries()

    stmt = (
        select(Equipment, EquipmentReading, open_alerts_count.label("open_alerts"))
        .options(joinedload(Equipment.client))
        .outerjoin(EquipmentReading, EquipmentReading.id == last_reading_id)
    )

    if client_id is not None:
        stmt = stmt.where(Equipment.client_id == client_id)
    if status:
        stmt = stmt.where(Equipment.status == status)

    stmt = stmt.order_by(Equipment.identifier).limit(limit).offset(offset)
    return _rows_to_equipment_out(db.execute(stmt).all())


def get_equipment(db: Session, equipment_id: int) -> dict:
    """Busca UM equipamento com temperatura atual e alertas abertos.

    ERRO: NotFoundError -> HTTP 404
    """
    last_reading_id, open_alerts_count = _last_reading_subqueries()

    stmt = (
        select(Equipment, EquipmentReading, open_alerts_count.label("open_alerts"))
        .options(joinedload(Equipment.client))
        .outerjoin(EquipmentReading, EquipmentReading.id == last_reading_id)
        .where(Equipment.id == equipment_id)
    )
    rows = db.execute(stmt).all()
    if not rows:
        raise NotFoundError("Equipamento", equipment_id)
    return _rows_to_equipment_out(rows)[0]


def change_equipment_status(
    db: Session, equipment_id: int, new_status: EquipmentStatus
) -> dict:
    """Altera o estado operacional do equipamento.

    Diferente do chamado, AQUI NAO HA MAQUINA DE ESTADOS: um equipamento
    pode ir de qualquer estado para qualquer outro. Um aparelho pode cair
    (ONLINE -> OFFLINE), entrar em manutencao a qualquer momento e voltar.
    Nao existe transicao proibida no mundo real, entao nao inventamos uma.

    ★ Isso e' uma decisao consciente, nao esquecimento: restringir aqui
      seria criar burocracia que nao existe no dominio.
    """
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise NotFoundError("Equipamento", equipment_id)

    equipment.status = new_status
    db.commit()
    return get_equipment(db, equipment_id)


# ===========================================================================
# ★★★ O CORACAO DO EXERCICIO 3 ★★★
# ===========================================================================


def register_reading(
    db: Session, equipment_id: int, payload: ReadingCreate
) -> dict:
    """Registra uma leitura e, se necessario, gera um alerta critico.

    ESTA FUNCAO CUMPRE OS 5 PASSOS PEDIDOS NO ENUNCIADO:

      1. VALIDAR OS DADOS
         Ja aconteceu antes desta funcao: o Pydantic (ReadingCreate) checou
         que a temperatura e' numerica e esta entre -50 e 200, e que
         recorded_at nao esta no futuro. Se falhasse, o FastAPI teria
         devolvido 422 e esta funcao nem seria chamada.

      2. ENCONTRAR O EQUIPAMENTO
         db.get(...). Se nao existir -> NotFoundError -> HTTP 404.
         ★ Sem esta checagem, a FOREIGN KEY do banco recusaria o INSERT,
           mas com um erro tecnico feio. Checar antes permite uma mensagem
           clara. As duas protecoes coexistem.

      3. REGISTRAR A LEITURA NO BANCO

      4. VERIFICAR A TEMPERATURA
         Comparacao com settings.TEMPERATURE_ALERT_THRESHOLD, que vem do
         .env. O numero 80 NAO esta escrito no meio do codigo.

      5. SE PASSAR DO LIMITE, CRIAR O ALERTA
         com data/hora, associado ao equipamento E a leitura que o causou.

    ★★★ O DETALHE TECNICO MAIS IMPORTANTE: UMA UNICA TRANSACAO ★★★

        db.add(reading)
        db.flush()          <- gera o id da leitura, mas NAO confirma nada
        db.add(alert)       <- usa esse id
        db.commit()         <- SO AQUI os dois viram permanentes, JUNTOS

        flush() envia o INSERT ao banco dentro da transacao aberta, o que
        faz o banco gerar o id. Mas nada esta confirmado ainda.
        commit() confirma TUDO de uma vez.

        CONSEQUENCIA: e' IMPOSSIVEL existir no banco uma leitura de 90 C
        sem o alerta correspondente. Se qualquer coisa falhar entre os dois
        passos, a transacao inteira e' desfeita e NENHUM dos dois fica.

        Se fizessemos dois commits separados, uma falha no meio deixaria a
        leitura gravada e o alerta perdido -- e o sistema mentiria dizendo
        que esta tudo bem.

    ★ E O EFEITO COLATERAL: atualizamos tambem equipments.status com o
      status reportado na leitura. Isso mantem coerentes as duas visoes:
      a leitura e' o FATO HISTORICO ("as 14h32 estava ONLINE"), o campo do
      equipamento e' o ESTADO ATUAL. Mesma diferenca entre extrato e saldo.

    RECEBE:  sessao, id do equipamento (da URL), ReadingCreate validado
    RETORNA: dict com a leitura, o booleano critical_condition_detected,
             o alerta (ou None) e o limite configurado
    ERROS:   404 se o equipamento nao existir; 422 barrado pelo Pydantic
    """
    # ---- passo 2: o equipamento existe? ----------------------------------
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise NotFoundError("Equipamento", equipment_id)

    # ---- passo 3: monta a leitura ---------------------------------------
    reading = EquipmentReading(
        equipment_id=equipment.id,
        temperature=payload.temperature,
        status=payload.status,
        # se o sensor nao informou quando mediu, o servidor carimba agora
        recorded_at=payload.recorded_at or utcnow(),
    )
    db.add(reading)

    # flush: manda o INSERT para o banco DENTRO da transacao aberta, para
    # obter o reading.id. Nada foi confirmado ainda -- um rollback aqui
    # apagaria tudo.
    db.flush()

    # ---- efeito colateral: sincroniza o estado atual do equipamento -----
    if equipment.status != payload.status:
        equipment.status = payload.status

    # ---- passos 4 e 5: A REGRA ------------------------------------------
    threshold = settings.TEMPERATURE_ALERT_THRESHOLD
    alert = None

    # ★ ESTA E' A LINHA. Estritamente MAIOR que o limite: 80.0 exato NAO
    #   gera alerta; 80.1 gera. O enunciado diz "temperatura > 80 C".
    if payload.temperature > threshold:
        alert = Alert(
            equipment_id=equipment.id,
            reading_id=reading.id,
            alert_type=AlertType.TEMPERATURA_CRITICA,
            temperature=payload.temperature,
            message=(
                f"Temperatura critica detectada no equipamento "
                f"{equipment.identifier}: {payload.temperature} C "
                f"(limite configurado: {threshold} C)."
            ),
            status=AlertStatus.ABERTO,
            created_at=utcnow(),
        )
        db.add(alert)

    # ---- commit unico: leitura + alerta + status do equipamento ---------
    try:
        db.commit()
    except IntegrityError as exc:
        # Rede de seguranca. A constraint UNIQUE em alerts.reading_id
        # impede dois alertas para a mesma leitura, mesmo que duas
        # requisicoes cheguem simultaneamente.
        db.rollback()
        raise ConflictError(
            "Nao foi possivel registrar a leitura: ja existe um alerta "
            "associado a esta leitura."
        ) from exc

    db.refresh(reading)
    if alert is not None:
        db.refresh(alert)

    return {
        "reading": reading,
        "critical_condition_detected": alert is not None,
        "alert": alert,
        "threshold": threshold,
    }


# ===========================================================================
# HISTORICO E ALERTAS
# ===========================================================================


def list_readings(
    db: Session, equipment_id: int, limit: int = 100, offset: int = 0
) -> list[EquipmentReading]:
    """Historico de leituras de um equipamento, da mais recente para a mais
    antiga (item 4 do Exercicio 3).

    Chama get_equipment antes para distinguir:
        equipamento 999 nao existe        -> 404
        equipamento 5 existe, sem leitura -> 200 com lista vazia
    """
    get_equipment(db, equipment_id)

    stmt = (
        select(EquipmentReading)
        .where(EquipmentReading.equipment_id == equipment_id)
        .order_by(EquipmentReading.recorded_at.desc(), EquipmentReading.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


def list_alerts(
    db: Session,
    equipment_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Lista alertas com os dados do equipamento e do cliente ja embutidos.

    Faz JOIN com equipments e clients para a tela de alertas mostrar
    "EQP-0007 - Alfa TI" sem requisicoes extras.
    """
    stmt = (
        select(Alert, Equipment, Client)
        .join(Equipment, Alert.equipment_id == Equipment.id)
        .join(Client, Equipment.client_id == Client.id)
    )

    if equipment_id is not None:
        stmt = stmt.where(Alert.equipment_id == equipment_id)
    if status:
        stmt = stmt.where(Alert.status == status)

    stmt = stmt.order_by(Alert.created_at.desc(), Alert.id.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = []
    for alert, equipment, client in db.execute(stmt).all():
        result.append(
            {
                "id": alert.id,
                "equipment_id": alert.equipment_id,
                "reading_id": alert.reading_id,
                "alert_type": alert.alert_type,
                "temperature": alert.temperature,
                "message": alert.message,
                "status": alert.status,
                "created_at": alert.created_at,
                "equipment_identifier": equipment.identifier,
                "equipment_name": equipment.name,
                "client_company": client.company,
            }
        )
    return result


def list_equipment_alerts(db: Session, equipment_id: int, **filters) -> list[dict]:
    """Alertas de UM equipamento. 404 se o equipamento nao existir."""
    get_equipment(db, equipment_id)
    return list_alerts(db, equipment_id=equipment_id, **filters)


def change_alert_status(
    db: Session, alert_id: int, new_status: AlertStatus
) -> dict:
    """Marca um alerta como RECONHECIDO ou RESOLVIDO.

    POR QUE UM ALERTA TEM CICLO DE VIDA: sem isso, a tela de alertas viraria
    uma lista infinita de problemas antigos e ninguem saberia o que ainda
    precisa de atencao. Um alerta RESOLVIDO some da contagem de pendencias
    mas continua no historico -- nunca apagamos alerta.
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise NotFoundError("Alerta", alert_id)

    alert.status = new_status
    db.commit()

    found = list_alerts(db, equipment_id=alert.equipment_id)
    return next(item for item in found if item["id"] == alert_id)


# ===========================================================================
# DETECCAO DE SITUACOES ANORMAIS (item 5 do Exercicio 3)
# ===========================================================================


def detect_anomalies(db: Session) -> list[AnomalyItem]:
    """Varre os equipamentos e aponta tudo que esta fora do normal.

    ★ POR QUE ISSO E' DIFERENTE DO ALERTA DE 80 GRAUS?

      O ALERTA e' um EVENTO: aconteceu uma leitura critica, ficou gravado
      no banco para sempre. E' historico.

      A ANOMALIA e' um DIAGNOSTICO DO AGORA: qual e' a situacao atual do
      parque de equipamentos? Nao se grava, se calcula na hora.

      Um equipamento pode ter tido 5 alertas ontem e estar perfeito hoje.
      E pode nunca ter gerado alerta e ainda assim estar anormal -- porque
      parou de enviar leituras.

    QUATRO TIPOS DETECTADOS:

      TEMPERATURA_CRITICA  -> ultima leitura acima do limite (severidade ALTA)
      TEMPERATURA_ELEVADA  -> na zona de atencao, entre (limite-margem) e o
                              limite. Ainda nao gera alerta, mas permite
                              agir ANTES do problema. Monitoramento serve
                              para prevenir, nao so para constatar.
      SEM_COMUNICACAO      -> nenhuma leitura ha mais de N horas. Um sensor
                              mudo tambem e' anomalia: pode ser queda de
                              energia, cabo solto ou aparelho queimado.
      EQUIPAMENTO_OFFLINE  -> status OFFLINE registrado.

    ★ POR QUE A CLASSIFICACAO ACONTECE EM PYTHON E NAO EM SQL?
      Porque isto NAO e' agregacao -- e' logica de decisao com quatro regras
      encadeadas. Os DADOS vem do banco numa unica consulta (a mesma de
      list_equipments); o que se faz em Python e' julgar cada linha.
      Escrever isso como um CASE WHEN gigante seria ilegivel e mais dificil
      de testar. Cada ferramenta no que ela e' boa.
    """
    threshold = settings.TEMPERATURE_ALERT_THRESHOLD
    warning_floor = threshold - settings.TEMPERATURE_WARNING_MARGIN
    stale_hours = settings.STALE_READING_HOURS
    now = utcnow()

    anomalies: list[AnomalyItem] = []

    for eq in list_equipments(db):
        common = {
            "equipment_id": eq["id"],
            "identifier": eq["identifier"],
            "name": eq["name"],
            "client_company": eq["client"].company,
            "last_temperature": eq["last_temperature"],
            "last_reading_at": eq["last_reading_at"],
        }

        temperature = eq["last_temperature"]
        last_at = eq["last_reading_at"]

        if temperature is not None and temperature > threshold:
            anomalies.append(
                AnomalyItem(
                    **common,
                    anomaly_type="TEMPERATURA_CRITICA",
                    severity="ALTA",
                    detail=(
                        f"Ultima leitura em {temperature} C, acima do limite "
                        f"de {threshold} C."
                    ),
                )
            )
        elif temperature is not None and temperature >= warning_floor:
            anomalies.append(
                AnomalyItem(
                    **common,
                    anomaly_type="TEMPERATURA_ELEVADA",
                    severity="MEDIA",
                    detail=(
                        f"Ultima leitura em {temperature} C, na zona de "
                        f"atencao ({warning_floor} a {threshold} C)."
                    ),
                )
            )

        if last_at is None:
            anomalies.append(
                AnomalyItem(
                    **common,
                    anomaly_type="SEM_LEITURA",
                    severity="MEDIA",
                    detail="Equipamento cadastrado, mas nunca enviou leitura.",
                )
            )
        else:
            hours_since = (now - last_at).total_seconds() / 3600
            if hours_since > stale_hours:
                anomalies.append(
                    AnomalyItem(
                        **common,
                        anomaly_type="SEM_COMUNICACAO",
                        severity="ALTA",
                        detail=(
                            f"Sem leituras ha {int(hours_since)}h "
                            f"(limite: {stale_hours}h)."
                        ),
                    )
                )

        if eq["status"] == EquipmentStatus.OFFLINE:
            anomalies.append(
                AnomalyItem(
                    **common,
                    anomaly_type="EQUIPAMENTO_OFFLINE",
                    severity="ALTA",
                    detail="Equipamento com status OFFLINE.",
                )
            )

    severity_order = {"ALTA": 0, "MEDIA": 1, "BAIXA": 2}
    anomalies.sort(key=lambda a: (severity_order.get(a.severity, 9), a.identifier))
    return anomalies
