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


class TicketCategory(str, Enum):
    """Categoria do problema relatado no chamado.

    ★ POR QUE ISSO VIROU ENUM (antes era texto livre, String(40))

      Com texto livre, nada impedia que chegassem "Rede", "rede", "REDE" e
      "Rede " como quatro categorias DIFERENTES. O relatorio "chamados por
      categoria" faz GROUP BY nessa coluna -- ou seja, ele contaria as
      quatro separadas e o grafico mentiria, sem ninguem perceber.

      Um campo que alimenta relatorio precisa de dominio fechado. Se o
      usuario pode digitar, o relatorio nao e' confiavel.

      Agora sao as mesmas tres barreiras dos outros enums: Pydantic recusa
      com 422, o SQLAlchemy gera CHECK constraint, e o SQLite recusa o
      INSERT mesmo escrito na mao.
    """

    ACESSO_E_SENHA = "ACESSO_E_SENHA"
    EMAIL = "EMAIL"
    REDE = "REDE"
    IMPRESSORA = "IMPRESSORA"
    TELEFONIA = "TELEFONIA"
    SEGURANCA = "SEGURANCA"
    BACKUP = "BACKUP"
    SOFTWARE = "SOFTWARE"
    HARDWARE = "HARDWARE"
    INFRAESTRUTURA = "INFRAESTRUTURA"


# ---------------------------------------------------------------------------
# ROTULOS PARA EXIBICAO
#
# O banco guarda ACESSO_E_SENHA (estavel, sem acento, sem espaco -- seguro
# para comparar e agrupar). A tela mostra "Acesso e Senha".
#
# POR QUE SEPARAR: se o valor gravado fosse o texto bonito, mudar o rotulo
# na tela ("Acesso e Senha" -> "Contas e Acessos") exigiria um UPDATE em
# todas as linhas do historico. Assim, muda-se so este dicionario.
# ---------------------------------------------------------------------------
CATEGORY_LABELS: dict[TicketCategory, str] = {
    TicketCategory.ACESSO_E_SENHA: "Acesso e Senha",
    TicketCategory.EMAIL: "E-mail",
    TicketCategory.REDE: "Rede",
    TicketCategory.IMPRESSORA: "Impressora",
    TicketCategory.TELEFONIA: "Telefonia",
    TicketCategory.SEGURANCA: "Seguranca",
    TicketCategory.BACKUP: "Backup",
    TicketCategory.SOFTWARE: "Software",
    TicketCategory.HARDWARE: "Hardware",
    TicketCategory.INFRAESTRUTURA: "Infraestrutura",
}


# ---------------------------------------------------------------------------
# SUBCATEGORIAS -- o "problema especifico" dentro da categoria
#
# Isto e' o que permite a tela ter DOIS selects encadeados: escolheu
# Hardware, aparecem os problemas de hardware.
#
# POR QUE UM DICIONARIO E NAO OUTRO ENUM: a subcategoria so faz sentido
# DENTRO de uma categoria ("Fonte queimada" nao existe em Telefonia). Um
# enum unico com 40 valores nao expressaria esse vinculo, e nada impediria
# a combinacao invalida. Aqui a estrutura carrega a regra, e o validador do
# schema so precisa perguntar: "essa subcategoria pertence a essa
# categoria?".
# ---------------------------------------------------------------------------
TICKET_SUBCATEGORIES: dict[TicketCategory, list[str]] = {
    TicketCategory.ACESSO_E_SENHA: [
        "Usuario bloqueado", "Redefinicao de senha", "Novo acesso",
        "Permissao negada", "Autenticacao em dois fatores",
    ],
    TicketCategory.EMAIL: [
        "Nao sincroniza", "Indo para spam", "Cota excedida",
        "Assinatura incorreta", "Lista de distribuicao",
    ],
    TicketCategory.REDE: [
        "Lentidao", "Wi-Fi instavel", "Sem acesso a internet",
        "Cabo ou porta com defeito", "VPN nao conecta",
    ],
    TicketCategory.IMPRESSORA: [
        "Nao imprime em rede", "Atolamento de papel", "Toner nao reconhecido",
        "Fila travada", "Qualidade de impressao",
    ],
    TicketCategory.TELEFONIA: [
        "Ramal sem audio", "PABX nao completa ligacao", "Headset com ruido",
        "Transferencia falhando", "Correio de voz",
    ],
    TicketCategory.SEGURANCA: [
        "Alerta de antivirus", "Tentativa de phishing", "Firewall bloqueando",
        "Revisao de permissoes", "Suspeita de invasao",
    ],
    TicketCategory.BACKUP: [
        "Rotina falhou", "Restauracao de arquivo", "Espaco insuficiente",
        "Backup sem log", "Teste de recuperacao",
    ],
    TicketCategory.SOFTWARE: [
        "Erro ao emitir nota", "Aplicacao fecha sozinha", "Licenca expirada",
        "Instalacao ou atualizacao", "Bug em relatorio",
    ],
    TicketCategory.HARDWARE: [
        "Fonte queimada", "HD com defeito", "Memoria insuficiente",
        "Monitor sem imagem", "Teclado ou mouse",
    ],
    TicketCategory.INFRAESTRUTURA: [
        "Servidor fora do ar", "Nobreak com falha", "Ar-condicionado do rack",
        "Cabeamento estruturado", "Energia eletrica",
    ],
}


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


class UserRole(str, Enum):
    """Quem e' quem no sistema -- a base do controle de acesso.

    ★ SAO DOIS MUNDOS DIFERENTES, e essa distincao e' o coracao do
      multi-empresa:

      SUPER_ADMIN  -- a EMPRESA DE TI que opera a plataforma.
                      Ve todos os clientes, todos os chamados, todos os
                      equipamentos. E' o tecnico e o dono da operacao.
                      Nao tem client_id: ele nao pertence a empresa nenhuma,
                      ele atende todas.

      ADMIN_EMPRESA -- o responsavel de UMA empresa atendida.
                      Ve exclusivamente os dados da empresa dele.
                      Tem client_id preenchido, e e' esse campo que limita
                      tudo o que ele enxerga.

    ★ POR QUE O PAPEL E' UM ENUM E NAO UM booleano "is_admin":
      porque papel cresce. Amanha nascem TECNICO (ve tudo mas nao apaga) e
      LEITOR (so consulta). Com booleano, cada papel novo vira mais uma
      coluna e uma combinacao impossivel de auditar.
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN_EMPRESA = "ADMIN_EMPRESA"
