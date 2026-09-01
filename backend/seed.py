"""Popula o banco com dados realistas para demonstracao.

COMO USAR (sempre a partir da RAIZ do projeto):

    python -m backend.seed            # popula (recusa se ja houver dados)
    python -m backend.seed --reset    # APAGA TUDO e popula de novo
    python -m backend.seed --status   # so mostra o que existe hoje

O QUE E' CRIADO:
    20 clientes  |  100 chamados  |  18 equipamentos
    ~400 leituras  |  alertas gerados pela REGRA (nao inseridos na mao)

--------------------------------------------------------------------------
IDEMPOTENCIA -- a pergunta "e se eu rodar duas vezes?"
--------------------------------------------------------------------------
Rodar sem argumentos duas vezes NAO duplica nada: na segunda vez o script
detecta que ja existem dados, avisa e sai sem tocar em nada.

Escolhi isso em vez de "apagar e recriar automaticamente" porque apagar
dados por engano e' irreversivel. Se voce quer mesmo recomecar do zero,
precisa dizer explicitamente: --reset.

--------------------------------------------------------------------------
★ DECISAO IMPORTANTE: O SEED USA OS MESMOS SERVICES DA API
--------------------------------------------------------------------------
As leituras sao gravadas chamando monitoring_service.register_reading() --
exatamente a funcao que o endpoint POST /api/equipments/{id}/readings usa.

CONSEQUENCIA: os alertas do banco NAO foram inseridos na mao. Eles nasceram
da MESMA regra de negocio ("temperatura > 80 gera alerta"), executada pelo
mesmo codigo.

POR QUE ISSO IMPORTA NA APRESENTACAO: se eu inserisse os alertas
manualmente com um INSERT, os dados poderiam ficar coerentes por acidente
e ninguem perceberia se a regra estivesse quebrada. Usando o service, o
proprio seed vira um teste da regra: se ela parar de funcionar, o banco
nasce sem alertas e isso salta aos olhos.

--------------------------------------------------------------------------
★ A EXCECAO: OS CHAMADOS SAO CRIADOS DIRETO PELO MODEL
--------------------------------------------------------------------------
Chamados precisam de datas HISTORICAS (abertos ha 60 dias, fechados ha 58).
O service create_ticket carimba opened_at = agora, de proposito -- para que
o frontend nao possa forjar datas.

Entao aqui uso o model diretamente, e isso e' honesto: o seed nao e' um
usuario da API, e' um script administrativo simulando um historico que
"aconteceu" antes do sistema existir. Se eu usasse o service, os 100
chamados nasceriam todos no mesmo minuto e o relatorio de tempo medio de
resolucao ficaria sem sentido.
"""

import random
import sys
import time
from datetime import timedelta

from sqlalchemy import func, select

from backend.app.config import settings
from backend.app.database import Base, SessionLocal, engine
from backend.app.enums import EquipmentStatus, TicketPriority, TicketStatus
from backend.app.models import Alert, Client, Equipment, EquipmentReading, Ticket
from backend.app.schemas.equipment import ReadingCreate
from backend.app.services import monitoring_service
from backend.app.utils import utcnow

# ---------------------------------------------------------------------------
# SEMENTE FIXA: garante que rodar o seed hoje e amanha produza EXATAMENTE os
# mesmos dados. Isso importa para a apresentacao (os numeros que voce
# ensaiou sao os que vao aparecer) e para os testes (resultado previsivel).
#
# random.Random(42) cria um gerador PROPRIO, isolado. Se usassemos
# random.seed(42) global, mexeriamos no gerador de todo o programa.
# ---------------------------------------------------------------------------
rng = random.Random(42)

# ---------------------------------------------------------------------------
# DADOS BASE
# ---------------------------------------------------------------------------
CLIENTES = [
    ("Ana Paula Ribeiro", "Alfa Tecnologia LTDA"),
    ("Bruno Carvalho", "Beta Sistemas e Servicos"),
    ("Carla Menezes", "Gama Solucoes Digitais"),
    ("Diego Nascimento", "Delta Engenharia"),
    ("Eduarda Lopes", "Epsilon Contabilidade"),
    ("Fabio Andrade", "Zeta Logistica"),
    ("Gabriela Torres", "Eta Comercio de Alimentos"),
    ("Henrique Barbosa", "Theta Industria Metalurgica"),
    ("Isabela Freitas", "Iota Servicos Medicos"),
    ("Joao Pedro Martins", "Kappa Transportes"),
    ("Karina Duarte", "Lambda Consultoria"),
    ("Lucas Ferreira", "Mu Distribuidora"),
    ("Mariana Souza", "Nu Educacao"),
    ("Nelson Aguiar", "Xi Construtora"),
    ("Olivia Castro", "Omicron Farmaceutica"),
    ("Paulo Ricardo Lima", "Pi Agroindustria"),
    ("Queila Moreira", "Rho Seguros"),
    ("Rafael Pinheiro", "Sigma Telecom"),
    ("Sabrina Rocha", "Tau Hotelaria"),
    ("Thiago Correa", "Upsilon Automacao"),
]

# Categoria -> (horas minimas, horas maximas) para resolver.
# Os intervalos sao DIFERENTES de proposito: e' isso que faz o item 6 do
# Exercicio 2 ("categoria com maior tempo medio") ter uma resposta com
# significado real, em vez de todas as categorias empatadas.
CATEGORIAS = {
    "Acesso e Senha": (0.5, 3),
    "E-mail": (1, 6),
    "Rede": (1, 10),
    "Impressora": (2, 14),
    "Telefonia": (3, 20),
    "Seguranca": (4, 28),
    "Backup": (6, 40),
    "Software": (8, 56),
    "Hardware": (12, 80),
    "Infraestrutura": (24, 140),
}

TITULOS = {
    "Acesso e Senha": ["Usuario bloqueado no sistema", "Redefinicao de senha do ERP",
                       "Novo acesso para colaborador", "Permissao negada em pasta de rede"],
    "E-mail": ["Caixa de entrada nao sincroniza", "E-mails indo para spam",
               "Assinatura de e-mail incorreta", "Cota de armazenamento excedida"],
    "Rede": ["Lentidao na rede do 2o andar", "Wi-Fi cai intermitentemente",
             "Sem acesso a internet na recepcao", "Switch com porta queimada"],
    "Impressora": ["Impressora nao imprime em rede", "Atolamento constante de papel",
                   "Toner nao reconhecido", "Fila de impressao travada"],
    "Telefonia": ["Ramal sem audio", "PABX nao completa ligacoes externas",
                  "Headset com ruido", "Transferencia de chamada falhando"],
    "Seguranca": ["Alerta de antivirus em estacao", "Tentativa de phishing reportada",
                  "Firewall bloqueando aplicacao interna", "Revisao de permissoes de acesso"],
    "Backup": ["Backup diario falhou", "Restauracao de arquivo excluido",
               "Espaco insuficiente no storage", "Rotina de backup sem log"],
    "Software": ["ERP apresenta erro ao emitir nota", "Sistema fecha sozinho",
                 "Atualizacao quebrou relatorio", "Licenca expirada do software"],
    "Hardware": ["Notebook nao liga", "Disco com setores defeituosos",
                 "Memoria RAM com falha", "Fonte do desktop queimada"],
    "Infraestrutura": ["Servidor de arquivos fora do ar", "Nobreak com bateria vencida",
                       "Ar-condicionado do rack desligado", "Cabeamento estruturado danificado"],
}

EQUIPAMENTOS_MODELOS = [
    ("Servidor Rack", "Sala de servidores"),
    ("Nobreak Central", "Sala tecnica"),
    ("Switch Core", "Rack principal"),
    ("Storage NAS", "Sala de servidores"),
    ("Ar-condicionado Rack", "Sala tecnica"),
    ("Servidor de Backup", "Sala de servidores"),
]


# ---------------------------------------------------------------------------
# FUNCOES AUXILIARES
# ---------------------------------------------------------------------------


def _database_is_empty(db) -> bool:
    """Verifica se ja existem dados. Base da idempotencia."""
    return (db.scalar(select(func.count()).select_from(Client)) or 0) == 0


def _wipe(db) -> None:
    """Apaga todos os dados, na ORDEM CORRETA.

    ★ A ORDEM IMPORTA POR CAUSA DAS FOREIGN KEYS.

      alerts aponta para readings e equipments.
      readings aponta para equipments.
      equipments e tickets apontam para clients.

      Se tentassemos apagar clients primeiro, o banco recusaria com
      "FOREIGN KEY constraint failed" -- que e' exatamente a protecao
      ON DELETE RESTRICT funcionando.

      Entao apagamos dos FILHOS para os PAIS. Esta ordem invertida e' a
      prova visivel de que o modelo relacional esta correto.
    """
    for model in (Alert, EquipmentReading, Equipment, Ticket, Client):
        db.query(model).delete()
    db.commit()


def _print_status(db) -> None:
    """Mostra quantos registros existem em cada tabela."""
    print("  Conteudo atual do banco:")
    for label, model in [
        ("clientes", Client), ("chamados", Ticket), ("equipamentos", Equipment),
        ("leituras", EquipmentReading), ("alertas", Alert),
    ]:
        total = db.scalar(select(func.count()).select_from(model)) or 0
        print(f"    {label:<14} {total:>5}")


# ---------------------------------------------------------------------------
# CRIACAO DOS DADOS
# ---------------------------------------------------------------------------


def _create_clients(db) -> list[Client]:
    """Cria os 20 clientes do Exercicio 2."""
    clients = []
    for index, (name, company) in enumerate(CLIENTES, start=1):
        # E-mail derivado do nome da empresa: sempre unico, sempre plausivel.
        slug = company.split()[0].lower()
        clients.append(
            Client(
                name=name,
                company=company,
                email=f"contato@{slug}.com.br",
                phone=f"(11) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
                created_at=utcnow() - timedelta(days=rng.randint(120, 400)),
            )
        )
    db.add_all(clients)
    db.commit()
    for client in clients:
        db.refresh(client)
    return clients


def _create_tickets(db, clients: list[Client]) -> list[Ticket]:
    """Cria os 100 chamados com historico realista.

    DISTRIBUICAO PROPOSITAL (nao e' aleatoria pura):

      - os pesos fazem alguns clientes concentrarem muitos chamados e outros
        pouquissimos. Um ranking em que todos tem 5 chamados nao mostra nada.

      - os DOIS ULTIMOS clientes ficam com ZERO chamados. Isso e' de
        proposito: e' o que prova, na demonstracao, que o relatorio "chamados
        por cliente" usa LEFT JOIN -- eles aparecem com total 0 em vez de
        sumir da lista.

      - ~60% finalizados, ~20% em andamento, ~20% abertos. Se todos
        estivessem finalizados, nao haveria o que mostrar em "chamados
        pendentes"; se nenhum estivesse, o tempo medio seria "sem dados".

      - o tempo de resolucao varia por CATEGORIA e por PRIORIDADE:
        chamados de prioridade ALTA sao resolvidos mais rapido (fator 0.6),
        os de BAIXA demoram mais (fator 1.5). E' assim no mundo real, e faz
        o relatorio contar uma historia coerente.
    """
    elegiveis = clients[:-2]  # os 2 ultimos ficam sem chamado
    pesos = [max(1, 20 - i) for i in range(len(elegiveis))]

    fator_prioridade = {
        TicketPriority.ALTA: 0.6,
        TicketPriority.MEDIA: 1.0,
        TicketPriority.BAIXA: 1.5,
    }

    tickets = []
    for _ in range(100):
        client = rng.choices(elegiveis, weights=pesos, k=1)[0]
        category = rng.choice(list(CATEGORIAS.keys()))
        priority = rng.choices(
            [TicketPriority.BAIXA, TicketPriority.MEDIA, TicketPriority.ALTA],
            weights=[25, 45, 30],
            k=1,
        )[0]
        status = rng.choices(
            [TicketStatus.FINALIZADO, TicketStatus.EM_ANDAMENTO, TicketStatus.ABERTO],
            weights=[60, 20, 20],
            k=1,
        )[0]

        # Abertura em algum momento dos ultimos 180 dias.
        opened_at = utcnow() - timedelta(
            days=rng.randint(1, 180),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )

        closed_at = None
        if status == TicketStatus.FINALIZADO:
            low, high = CATEGORIAS[category]
            horas = rng.uniform(low, high) * fator_prioridade[priority]
            closed_at = opened_at + timedelta(hours=horas)
            # Um chamado nao pode ter fechado no futuro.
            if closed_at > utcnow():
                closed_at = utcnow() - timedelta(hours=1)

        tickets.append(
            Ticket(
                client_id=client.id,
                title=rng.choice(TITULOS[category]),
                description=(
                    f"Chamado registrado pela equipe de suporte para "
                    f"{client.company}. Categoria: {category}. "
                    f"O usuario relatou o problema e solicitou atendimento."
                ),
                category=category,
                priority=priority,
                status=status,
                opened_at=opened_at,
                closed_at=closed_at,
            )
        )

    db.add_all(tickets)
    db.commit()
    return tickets


def _create_equipments(db, clients: list[Client]) -> list[Equipment]:
    """Cria 18 equipamentos distribuidos entre os clientes.

    TRES CASOS ESPECIAIS SAO PLANTADOS DE PROPOSITO, para que a deteccao
    de anomalias tenha o que encontrar na demonstracao:

      - um equipamento OFFLINE      -> anomalia EQUIPAMENTO_OFFLINE
      - um em MANUTENCAO
      - um que nunca recebera leitura -> anomalia SEM_LEITURA

    Sem esses casos, a tela de anomalias apareceria vazia e voce nao teria
    o que mostrar.
    """
    equipments = []
    for index in range(1, 19):
        client = clients[index % len(clients)]
        modelo, local = EQUIPAMENTOS_MODELOS[index % len(EQUIPAMENTOS_MODELOS)]

        if index == 5:
            status = EquipmentStatus.OFFLINE
        elif index == 11:
            status = EquipmentStatus.MANUTENCAO
        else:
            status = EquipmentStatus.ONLINE

        equipments.append(
            Equipment(
                client_id=client.id,
                identifier=f"EQP-{index:04d}",
                name=f"{modelo} {index:02d}",
                location=local,
                status=status,
                created_at=utcnow() - timedelta(days=rng.randint(60, 300)),
            )
        )

    db.add_all(equipments)
    db.commit()
    for equipment in equipments:
        db.refresh(equipment)
    return equipments


def _create_readings(db, equipments: list[Equipment]) -> tuple[int, int]:
    """Gera as leituras CHAMANDO O SERVICE -- e portanto a regra de negocio.

    ★ ESTA E' A PARTE MAIS IMPORTANTE DO SEED.

      Cada leitura passa por monitoring_service.register_reading(), que e'
      exatamente a funcao chamada pelo endpoint da API. Logo:

        - a regra "temperatura > 80 gera alerta" e' aplicada aqui
        - os alertas do banco nasceram da regra, nao de um INSERT manual
        - se a regra quebrar, o banco nasce sem alertas -- e isso e' visivel

    PERFIS DE EQUIPAMENTO (para os dados contarem uma historia):
      - a maioria opera entre 35 e 60 C, normal
      - tres equipamentos sao "quentes": chegam a passar de 80 C e geram
        alertas de verdade
      - um fica na zona de atencao (70-79 C): aparece como TEMPERATURA_ELEVADA
        nas anomalias, sem gerar alerta
      - um para de enviar leituras ha 3 dias -> anomalia SEM_COMUNICACAO
      - um nunca envia leitura              -> anomalia SEM_LEITURA

    RETORNA: (total de leituras, total de alertas gerados)
    """
    limite = settings.TEMPERATURE_ALERT_THRESHOLD
    total_readings = 0
    total_alerts = 0

    for index, equipment in enumerate(equipments):
        if index == 17:
            continue  # equipamento sem nenhuma leitura, de proposito

        if index in (2, 7, 13):
            base, amplitude = limite - 8, 16      # quente: vai passar do limite
        elif index == 4:
            base, amplitude = limite - 8, 5       # zona de atencao, sem estourar
        else:
            base, amplitude = 42, 14              # operacao normal

        # Equipamento 9 parou de reportar ha 3 dias (sem comunicacao).
        offset_final = timedelta(days=3) if index == 9 else timedelta(0)

        quantidade = rng.randint(18, 26)
        for passo in range(quantidade):
            # Leituras espacadas ~8h, indo do passado para o presente.
            momento = (
                utcnow()
                - offset_final
                - timedelta(hours=8 * (quantidade - passo), minutes=rng.randint(0, 59))
            )

            temperatura = round(rng.uniform(base - 4, base + amplitude), 1)
            # ★ Cada leitura reporta o status OPERACIONAL do proprio
            #   equipamento. Isso importa por causa de um detalhe da regra:
            #   register_reading SINCRONIZA equipments.status com o status da
            #   leitura (a leitura e' a fonte da verdade sobre o estado atual).
            #   Se enviassemos sempre ONLINE, o equipamento OFFLINE que
            #   plantamos viraria ONLINE na primeira leitura -- e a anomalia
            #   EQUIPAMENTO_OFFLINE nunca apareceria. Enviando o status real,
            #   OFFLINE continua OFFLINE e MANUTENCAO continua MANUTENCAO.
            status = equipment.status

            resultado = monitoring_service.register_reading(
                db,
                equipment.id,
                ReadingCreate(
                    temperature=temperatura, status=status, recorded_at=momento
                ),
            )
            total_readings += 1
            if resultado["critical_condition_detected"]:
                total_alerts += 1

    return total_readings, total_alerts


# ---------------------------------------------------------------------------
# ORQUESTRACAO
# ---------------------------------------------------------------------------


def run(reset: bool = False) -> None:
    """Executa o seed completo."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    inicio = time.perf_counter()

    try:
        if not _database_is_empty(db):
            if not reset:
                print("=" * 70)
                print("O banco JA POSSUI DADOS. Nada foi alterado.")
                print("=" * 70)
                _print_status(db)
                print()
                print("  Para recomecar do zero (APAGA TUDO):")
                print("      python -m backend.seed --reset")
                print("=" * 70)
                return
            print("Apagando dados existentes (--reset)...")
            _wipe(db)

        print("=" * 70)
        print(f"Banco: {settings.DATABASE_URL_RESOLVED}")
        print(f"Limite de alerta configurado: {settings.TEMPERATURE_ALERT_THRESHOLD} C")
        print("=" * 70)

        print("  [1/4] criando 20 clientes...")
        clients = _create_clients(db)

        print("  [2/4] criando 100 chamados com datas historicas...")
        _create_tickets(db, clients)

        print("  [3/4] criando 18 equipamentos...")
        equipments = _create_equipments(db, clients)

        print("  [4/4] enviando leituras pelo monitoring_service (a regra roda aqui)...")
        readings, alerts = _create_readings(db, equipments)

        duracao = time.perf_counter() - inicio
        print()
        print("=" * 70)
        print(f"SEED CONCLUIDO em {duracao:.1f}s")
        print("=" * 70)
        _print_status(db)
        print()
        print(f"  Dos {readings} envios de leitura, {alerts} ultrapassaram "
              f"{settings.TEMPERATURE_ALERT_THRESHOLD} C e geraram alerta")
        print("  -- pela regra do monitoring_service, nao por INSERT manual.")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    if "--status" in sys.argv:
        session = SessionLocal()
        try:
            print(f"Banco: {settings.DATABASE_URL_RESOLVED}")
            _print_status(session)
        finally:
            session.close()
    else:
        run(reset="--reset" in sys.argv)
