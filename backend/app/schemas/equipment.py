"""Schemas de Equipamento, Leitura e Alerta (Exercicio 3)."""

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.enums import AlertStatus, AlertType, EquipmentStatus
from backend.app.schemas.client import ClientSummary
from backend.app.schemas.common import UtcDatetime, required_text
from backend.app.utils import utcnow

# ===========================================================================
# EQUIPAMENTO
# ===========================================================================


class EquipmentCreate(BaseModel):
    """Corpo do POST /api/equipments."""

    client_id: int = Field(gt=0, description="Cliente onde o equipamento esta instalado")

    # A etiqueta fisica colada no aparelho. E' UNIQUE no banco: dois
    # equipamentos nao podem ter a mesma identificacao, senao seria
    # impossivel saber de qual deles veio uma leitura.
    identifier: required_text(2, 50)

    name: required_text(2, 120)
    location: required_text(2, 120) | None = None

    # Nasce ONLINE por padrao, mas pode ser cadastrado ja em MANUTENCAO.
    status: EquipmentStatus = EquipmentStatus.ONLINE

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "client_id": 1,
                "identifier": "EQP-0001",
                "name": "Servidor Rack A1",
                "location": "Sala de servidores - 1o andar",
                "status": "ONLINE",
            }
        }
    )


class EquipmentStatusUpdate(BaseModel):
    """Corpo do PATCH /api/equipments/{id}/status."""

    status: EquipmentStatus

    model_config = ConfigDict(json_schema_extra={"example": {"status": "MANUTENCAO"}})


class EquipmentOut(BaseModel):
    """O que a API devolve ao falar de um equipamento.

    Os tres ultimos campos NAO SAO COLUNAS DA TABELA -- sao calculados na
    consulta:

        last_temperature / last_reading_at -> vem da leitura mais recente,
            trazida por uma subconsulta correlacionada
        open_alerts -> contagem de alertas com status ABERTO

    POR QUE INCLUIR ISSO NA LISTAGEM: a tela de equipamentos precisa mostrar
    "temperatura atual" ao lado de cada aparelho. Sem esses campos, o
    JavaScript teria que fazer uma requisicao por equipamento para descobrir
    a ultima leitura -- o problema N+1 de novo, agora no frontend.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client: ClientSummary
    identifier: str
    name: str
    location: str | None
    status: EquipmentStatus
    created_at: UtcDatetime

    last_temperature: float | None = None
    last_reading_at: UtcDatetime | None = None
    open_alerts: int = 0


# ===========================================================================
# LEITURA
# ===========================================================================


class ReadingCreate(BaseModel):
    """Corpo do POST /api/equipments/{id}/readings.

    Repare que NAO existe campo "equipment_id" aqui: ele ja esta na URL.
    Ter o mesmo dado em dois lugares abriria a porta para eles divergirem
    (URL dizendo equipamento 5, corpo dizendo equipamento 9 -- qual vale?).
    A URL manda.
    """

    # ge/le espelham EXATAMENTE a CHECK constraint da tabela. Sao duas
    # barreiras para a mesma regra: o Pydantic devolve 422 com mensagem
    # legivel; o banco recusa se alguem escrever por fora da API.
    temperature: float = Field(
        ge=-50, le=200, description="Temperatura em graus Celsius"
    )

    status: EquipmentStatus = EquipmentStatus.ONLINE

    # ---------------------------------------------------------------------
    # recorded_at e' OPCIONAL -- e essa e' uma decisao de negocio, nao
    # descuido.
    #
    # Um sensor pode ficar sem internet e, ao reconectar, enviar um LOTE de
    # leituras antigas. Se o servidor sempre carimbasse "agora", todas elas
    # apareceriam empilhadas no mesmo minuto e o historico seria uma ficcao.
    #
    # Entao: se o equipamento informar quando mediu, respeitamos. Se nao
    # informar, usamos a hora atual.
    #
    # ATENCAO: isso NAO contradiz a regra "o frontend nao inventa datas".
    # Aqui quem envia e' o EQUIPAMENTO relatando um fato que ele presenciou.
    # E mesmo assim validamos: nao aceitamos data no futuro.
    # ---------------------------------------------------------------------
    recorded_at: datetime | None = None

    @field_validator("recorded_at")
    @classmethod
    def normalize_recorded_at(cls, value: datetime | None) -> datetime | None:
        """Converte para UTC sem fuso e rejeita datas no futuro.

        DUAS COISAS ACONTECEM AQUI:

        1. NORMALIZACAO DE FUSO
           Se chegar "2026-09-01T14:00:00-03:00" (horario de Brasilia),
           convertemos para UTC e removemos o fuso -> 17:00:00.
           Assim TUDO no banco esta na mesma referencia, e comparar duas
           leituras nunca compara laranja com banana.

        2. VALIDACAO DE FUTURO
           Uma leitura e' o registro de algo que JA ACONTECEU. Aceitar data
           futura permitiria a um sensor com relogio errado (ou a alguem
           mal-intencionado) poluir o historico com eventos que nao
           ocorreram. Damos 5 minutos de tolerancia para relogios levemente
           dessincronizados -- o que e' comum e inofensivo.
        """
        if value is None:
            return None

        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)

        if value > utcnow() + timedelta(minutes=5):
            raise ValueError(
                "recorded_at nao pode estar no futuro. "
                "Uma leitura registra um evento que ja aconteceu."
            )
        return value

    model_config = ConfigDict(
        json_schema_extra={"example": {"temperature": 85.4, "status": "ONLINE"}}
    )


class ReadingOut(BaseModel):
    """Uma leitura, como sai da API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    temperature: float
    status: EquipmentStatus
    recorded_at: UtcDatetime


# ===========================================================================
# ALERTA
# ===========================================================================


class AlertOut(BaseModel):
    """Um alerta, como sai da API.

    Traz equipment_identifier e client_company para a tela de alertas nao
    precisar de requisicoes extras. Esses campos vem de um JOIN feito na
    consulta -- nao estao duplicados na tabela alerts.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    reading_id: int
    alert_type: AlertType
    temperature: float
    message: str
    status: AlertStatus
    created_at: UtcDatetime

    equipment_identifier: str | None = None
    equipment_name: str | None = None
    client_company: str | None = None


class AlertStatusUpdate(BaseModel):
    """Corpo do PATCH /api/alerts/{id}/status."""

    status: AlertStatus

    model_config = ConfigDict(json_schema_extra={"example": {"status": "RESOLVIDO"}})


# ===========================================================================
# A RESPOSTA DO ENDPOINT DE LEITURA -- o coracao do Exercicio 3
# ===========================================================================


class ReadingCreatedResponse(BaseModel):
    """Resposta do POST /api/equipments/{id}/readings.

    ★ E' AQUI QUE O ENUNCIADO E' CUMPRIDO LITERALMENTE:
      "informar na resposta que uma condicao critica foi detectada".

    TRES CAMPOS, TRES PROPOSITOS:

      reading  -> a leitura que acabou de ser gravada, com o id do banco.
                  Prova que persistiu.

      critical_condition_detected -> um booleano explicito. O frontend nao
                  precisa comparar temperatura com 80 para saber se houve
                  problema -- o SERVIDOR ja respondeu essa pergunta.
                  ★ Isso e' importante: se o frontend fizesse a comparacao,
                    a regra estaria no lugar errado. Ele apenas LE a decisao
                    que o backend tomou.

      alert    -> o alerta criado, ou null se a temperatura estava normal.

    POR QUE DEVOLVER O ALERTA JUNTO: evita uma segunda requisicao. Quem
    enviou a leitura descobre na mesma resposta se gerou problema.
    """

    reading: ReadingOut
    critical_condition_detected: bool
    alert: AlertOut | None = None
    threshold: float = Field(description="Limite configurado, em graus Celsius")


class AnomalyItem(BaseModel):
    """Uma situacao anormal detectada (item 5 do Exercicio 3)."""

    equipment_id: int
    identifier: str
    name: str
    client_company: str
    anomaly_type: str
    severity: str
    detail: str
    last_temperature: float | None = None
    last_reading_at: UtcDatetime | None = None
