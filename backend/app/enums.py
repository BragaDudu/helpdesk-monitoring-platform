"""Os estados validos do sistema.

POR QUE ENUM E NAO STRING SOLTA?
    Se "status" fosse apenas um texto livre, nada impediria que chegasse
    "aberto", "ABERTO ", "Aberto", "abrto" ou "banana" -- e a consulta
    "quantos chamados estao abertos?" passaria a mentir.

    Com Enum ganhamos TRES barreiras, em tres camadas diferentes:
      1. Pydantic  -> rejeita a requisicao HTTP com erro 422 (nem chega ao service)
      2. SQLAlchemy-> gera uma CHECK constraint na tabela
      3. SQLite    -> recusa o INSERT mesmo se alguem escrever direto no banco

    A terceira barreira e' a que responde a pergunta: "e se alguem burlar
    sua API e escrever direto no banco?".

DETALHE TECNICO: herdamos de (str, Enum) para que o valor seja tratado como
texto ao ser serializado em JSON. Sem o "str", o JSON sairia como
"TicketStatus.ABERTO" em vez de "ABERTO".

CONVENCAO: o NOME do membro e' igual ao VALOR (ABERTO = "ABERTO"). O
SQLAlchemy grava o NOME do membro no banco; mantendo nome == valor, o que
voce ve na API e' exatamente o que esta gravado na tabela. Sem surpresas.
"""

from enum import Enum


class TicketStatus(str, Enum):
    """Ciclo de vida de um chamado (Exercicio 1)."""

    ABERTO = "ABERTO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    FINALIZADO = "FINALIZADO"


class TicketPriority(str, Enum):
    """Prioridade de um chamado (Exercicio 1)."""

    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class EquipmentStatus(str, Enum):
    """Estado operacional de um equipamento (Exercicio 3)."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    MANUTENCAO = "MANUTENCAO"


class AlertStatus(str, Enum):
    """Ciclo de vida de um alerta.

    ABERTO      -> ninguem olhou ainda
    RECONHECIDO -> um tecnico assumiu, mas o problema continua
    RESOLVIDO   -> normalizado
    """

    ABERTO = "ABERTO"
    RECONHECIDO = "RECONHECIDO"
    RESOLVIDO = "RESOLVIDO"


class AlertType(str, Enum):
    """Motivo do alerta.

    Hoje so existe um tipo, mas ele e' um Enum (e nao uma constante) porque
    e' natural que amanhca surjam UMIDADE_CRITICA, EQUIPAMENTO_OFFLINE etc.
    Deixar preparado custa zero agora.
    """

    TEMPERATURA_CRITICA = "TEMPERATURA_CRITICA"


# ---------------------------------------------------------------------------
# MAQUINA DE ESTADOS DO CHAMADO
#
#   ABERTO ---------> EM_ANDAMENTO ---------> FINALIZADO
#      ^                    |                     |
#      +--------------------+                     X  (nao volta)
#
# Este dicionario diz, para cada status atual, para quais status e' permitido
# ir. Quem usa isso e' o ticket_service ao processar PATCH /tickets/{id}/status.
# Uma transicao proibida devolve HTTP 409 Conflict.
#
# POR QUE FINALIZADO NAO VOLTA? Porque ao finalizar carimbamos closed_at.
# Se pudesse reabrir, teriamos chamados "abertos" com data de fechamento
# preenchida -- e o calculo de tempo medio de resolucao ficaria incoerente.
# ---------------------------------------------------------------------------
TICKET_STATUS_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.ABERTO: {TicketStatus.EM_ANDAMENTO, TicketStatus.FINALIZADO},
    TicketStatus.EM_ANDAMENTO: {TicketStatus.ABERTO, TicketStatus.FINALIZADO},
    TicketStatus.FINALIZADO: set(),
}
