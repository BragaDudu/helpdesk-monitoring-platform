"""Popula o banco com dados realistas para demonstracao.

COMO USAR (sempre a partir da RAIZ do projeto):

    python -m backend.seed            # popula (recusa se ja houver dados)
    python -m backend.seed --reset    # APAGA TUDO e popula de novo
    python -m backend.seed --status   # so mostra o que existe hoje
    python -m backend.seed --wipe     # ESVAZIA o banco (nao popula nada)

O QUE E' CRIADO (volume base):
    20 clientes  |  100 chamados  |  18 equipamentos
    ~400 leituras  |  alertas gerados pela REGRA (nao inseridos na mao)

--------------------------------------------------------------------------
VOLUME -- para provar que o sistema aguenta carga
--------------------------------------------------------------------------
    python -m backend.seed --reset --scale 50      # 5.000 chamados
    python -m backend.seed --reset --chamados 5000 # numero exato

--scale N multiplica TODOS os volumes base por N. Os argumentos explicitos
(--clientes, --chamados, --equipamentos) vencem o --scale quando os dois
aparecem juntos.

MEDIDO: com 5.000 chamados o banco fica com ~2,6 MB e o dashboard inteiro
(as 7 consultas) responde em ~25 ms. O gargalo so aparece perto de 200 mil,
e nao e' o tamanho do arquivo: e' o dashboard recalcular tudo a cada acesso.

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

import argparse
import random
import sys
import time
from datetime import timedelta

from sqlalchemy import func, select

from backend.app.config import settings
from backend.app.database import Base, SessionLocal, engine
from backend.app.enums import (
    TICKET_SUBCATEGORIES,
    EquipmentStatus,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from backend.app.models import Alert, Client, Equipment, EquipmentReading, Ticket, User
from backend.app.schemas.equipment import ReadingCreate
from backend.app.security import hash_senha
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

# ---------------------------------------------------------------------------
# PECAS PARA GERAR CLIENTES EM VOLUME (--scale)
#
# Sao listas de tamanhos DIFERENTES e primos entre si de proposito. Como a
# combinacao usa o resto da divisao (indice % len), tamanhos diferentes
# fazem os nomes se repetirem so depois de muitas combinacoes, em vez de
# ciclarem juntos a cada 10 registros.
# ---------------------------------------------------------------------------
NOMES = [
    "Adriana", "Bernardo", "Camila", "Daniel", "Elaine", "Felipe", "Giovana",
    "Heitor", "Ingrid", "Julio", "Larissa", "Marcelo", "Natalia",
]
SOBRENOMES = [
    "Almeida", "Barros", "Cardoso", "Dias", "Esteves", "Fonseca", "Gomes",
    "Henriques", "Iglesias", "Junqueira", "Klein",
]
PREFIXOS_EMPRESA = [
    "Vertex", "Norte", "Prisma", "Atlas", "Orion", "Vega", "Solaris",
]
RAMOS_EMPRESA = [
    "Tecnologia", "Logistica", "Comercio", "Industria", "Servicos",
    "Consultoria", "Engenharia", "Distribuidora", "Telecom",
]

# Categoria -> (horas minimas, horas maximas) para resolver.
# Os intervalos sao DIFERENTES de proposito: e' isso que faz o item 6 do
# Exercicio 2 ("categoria com maior tempo medio") ter uma resposta com
# significado real, em vez de todas as categorias empatadas.
CATEGORIAS = {
    TicketCategory.ACESSO_E_SENHA: (0.5, 3),
    TicketCategory.EMAIL: (1, 6),
    TicketCategory.REDE: (1, 10),
    TicketCategory.IMPRESSORA: (2, 14),
    TicketCategory.TELEFONIA: (3, 20),
    TicketCategory.SEGURANCA: (4, 28),
    TicketCategory.BACKUP: (6, 40),
    TicketCategory.SOFTWARE: (8, 56),
    TicketCategory.HARDWARE: (12, 80),
    TicketCategory.INFRAESTRUTURA: (24, 140),
}

TITULOS = {
    TicketCategory.ACESSO_E_SENHA: ["Usuario bloqueado no sistema", "Redefinicao de senha do ERP",
                       "Novo acesso para colaborador", "Permissao negada em pasta de rede"],
    TicketCategory.EMAIL: ["Caixa de entrada nao sincroniza", "E-mails indo para spam",
               "Assinatura de e-mail incorreta", "Cota de armazenamento excedida"],
    TicketCategory.REDE: ["Lentidao na rede do 2o andar", "Wi-Fi cai intermitentemente",
             "Sem acesso a internet na recepcao", "Switch com porta queimada"],
    TicketCategory.IMPRESSORA: ["Impressora nao imprime em rede", "Atolamento constante de papel",
                   "Toner nao reconhecido", "Fila de impressao travada"],
    TicketCategory.TELEFONIA: ["Ramal sem audio", "PABX nao completa ligacoes externas",
                  "Headset com ruido", "Transferencia de chamada falhando"],
    TicketCategory.SEGURANCA: ["Alerta de antivirus em estacao", "Tentativa de phishing reportada",
                  "Firewall bloqueando aplicacao interna", "Revisao de permissoes de acesso"],
    TicketCategory.BACKUP: ["Backup diario falhou", "Restauracao de arquivo excluido",
               "Espaco insuficiente no storage", "Rotina de backup sem log"],
    TicketCategory.SOFTWARE: ["ERP apresenta erro ao emitir nota", "Sistema fecha sozinho",
                 "Atualizacao quebrou relatorio", "Licenca expirada do software"],
    TicketCategory.HARDWARE: ["Notebook nao liga", "Disco com setores defeituosos",
                 "Memoria RAM com falha", "Fonte do desktop queimada"],
    TicketCategory.INFRAESTRUTURA: ["Servidor de arquivos fora do ar", "Nobreak com bateria vencida",
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
    # ORDEM IMPORTA: filhos antes dos pais, senao a FK recusa o DELETE.
    # users vem antes de clients porque users.client_id aponta para la.
    for model in (Alert, EquipmentReading, Equipment, Ticket, User, Client):
        db.query(model).delete()
    db.commit()


def _print_status(db) -> None:
    """Mostra quantos registros existem em cada tabela."""
    print("  Conteudo atual do banco:")
    for label, model in [
        ("clientes", Client), ("chamados", Ticket), ("equipamentos", Equipment),
        ("leituras", EquipmentReading), ("alertas", Alert), ("usuarios", User),
    ]:
        total = db.scalar(select(func.count()).select_from(model)) or 0
        print(f"    {label:<14} {total:>5}")


# ---------------------------------------------------------------------------
# CRIACAO DOS DADOS
# ---------------------------------------------------------------------------


def _gerar_cliente(indice: int) -> tuple[str, str]:
    """Inventa um par (pessoa, empresa) para volumes acima dos 20 fixos.

    POR QUE ISSO EXISTE: a lista CLIENTES tem 20 nomes escritos a mao, que
    e' o suficiente para a demonstracao. Quando pedimos volume (--scale),
    precisamos de centenas ou milhares -- e escrever isso a mao seria
    inviavel.

    A COMBINACAO E' DETERMINISTICA: o mesmo indice sempre produz o mesmo
    nome e o mesmo e-mail. Isso mantem a promessa da semente fixa (rodar
    duas vezes gera exatamente o mesmo banco) e garante e-mail unico sem
    depender de sorteio -- o indice entra no e-mail, entao nao ha como
    colidir com a constraint UNIQUE.
    """
    nome = f"{NOMES[indice % len(NOMES)]} {SOBRENOMES[indice % len(SOBRENOMES)]}"
    empresa = (
        f"{PREFIXOS_EMPRESA[indice % len(PREFIXOS_EMPRESA)]} "
        f"{RAMOS_EMPRESA[indice % len(RAMOS_EMPRESA)]} {indice:04d}"
    )
    return nome, empresa


def _create_clients(db, total: int = 20) -> list[Client]:
    """Cria os clientes do Exercicio 2.

    Os 20 primeiros vem da lista escrita a mao (nomes plausiveis, bons para
    a demonstracao). A partir do 21o, sao gerados por _gerar_cliente.
    """
    clients = []
    for index in range(total):
        if index < len(CLIENTES):
            name, company = CLIENTES[index]
            slug = company.split()[0].lower()
            email = f"contato@{slug}.com.br"
        else:
            name, company = _gerar_cliente(index)
            # O indice entra no e-mail: unicidade garantida sem sorteio.
            email = f"contato{index:05d}@{PREFIXOS_EMPRESA[index % len(PREFIXOS_EMPRESA)].lower()}.com.br"

        clients.append(
            Client(
                name=name,
                company=company,
                email=email,
                phone=f"(11) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
                created_at=utcnow() - timedelta(days=rng.randint(120, 400)),
            )
        )

    db.add_all(clients)
    db.commit()
    for client in clients:
        db.refresh(client)
    return clients


def _create_tickets(db, clients: list[Client], total: int = 100) -> list[Ticket]:
    """Cria os chamados com historico realista.

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
    # Peso decrescente ao longo de TODA a lista (nao so dos 20 primeiros).
    # Assim o ranking "clientes que mais abrem chamado" continua contando uma
    # historia em qualquer volume: com peso fixo, mil clientes empatariam.
    pesos = [len(elegiveis) - i for i in range(len(elegiveis))]

    fator_prioridade = {
        TicketPriority.ALTA: 0.6,
        TicketPriority.MEDIA: 1.0,
        TicketPriority.BAIXA: 1.5,
    }

    tickets = []
    for _ in range(total):
        client = rng.choices(elegiveis, weights=pesos, k=1)[0]
        category = rng.choice(list(CATEGORIAS.keys()))
        # Subcategoria sorteada DENTRO da categoria -- combinacao sempre
        # valida, do mesmo dicionario que o schema usa para validar.
        subcategory = rng.choice(TICKET_SUBCATEGORIES[category])
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
                    f"{client.company}. Problema: {subcategory}. "
                    f"O usuario relatou o problema e solicitou atendimento."
                ),
                category=category,
                subcategory=subcategory,
                priority=priority,
                status=status,
                opened_at=opened_at,
                closed_at=closed_at,
            )
        )

    db.add_all(tickets)
    db.commit()
    return tickets


def _create_equipments(db, clients: list[Client], total: int = 18) -> list[Equipment]:
    """Cria os equipamentos distribuidos entre os clientes.

    TRES CASOS ESPECIAIS SAO PLANTADOS DE PROPOSITO, para que a deteccao
    de anomalias tenha o que encontrar na demonstracao:

      - um equipamento OFFLINE      -> anomalia EQUIPAMENTO_OFFLINE
      - um em MANUTENCAO
      - um que nunca recebera leitura -> anomalia SEM_LEITURA

    Sem esses casos, a tela de anomalias apareceria vazia e voce nao teria
    o que mostrar.
    """
    equipments = []
    for index in range(1, total + 1):
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
    # Em volume, cada leitura e' um COMMIT proprio (o service confirma a
    # transacao a cada chamada). Isso e' mais lento do que um add_all em
    # bloco -- e a lentidao e' o PRECO de manter a regra de negocio no
    # caminho. Preferimos pagar: e' o que garante que os alertas nasceram
    # da regra. O progresso abaixo existe so para nao parecer travado.
    marco = max(1, len(equipments) // 10)

    for index, equipment in enumerate(equipments):
        if index % marco == 0 and len(equipments) > 50:
            print(f"        equipamento {index}/{len(equipments)} "
                  f"({total_readings} leituras, {total_alerts} alertas)")

        if index == 17:
            continue  # equipamento sem nenhuma leitura, de proposito

        # ---------------------------------------------------------------
        # PERFIS TERMICOS -- PROPORCIONAIS, nao fixos.
        #
        # Os indices 2, 7, 13 e 4 continuam plantados a mao: sao os casos
        # que voce mostra na demonstracao com o volume base.
        #
        # ★ Para os equipamentos ALEM do conjunto base, o perfil vem do
        #   resto da divisao (index % 7). Sem isso, ao rodar --scale 50 o
        #   banco teria 900 equipamentos e ainda so 3 quentes -- os alertas
        #   praticamente sumiriam do dashboard, e o volume nao provaria
        #   nada. A proporcao (~1 em 7 quente) tem que valer em qualquer
        #   escala, senao o dado grande conta uma historia falsa.
        # ---------------------------------------------------------------
        alem_do_base = index >= 18
        if index in (2, 7, 13) or (alem_do_base and index % 7 == 2):
            base, amplitude = limite - 8, 16      # quente: vai passar do limite
        elif index == 4 or (alem_do_base and index % 7 == 4):
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


def _create_users(db, clients: list[Client]) -> list[User]:
    """Cria os usuarios de acesso.

    ★ AS SENHAS SAO FRACAS E ISSO E' PROPOSITAL -- mas so aqui.

      "admin12345" existe para a demonstracao: quem for testar o sistema
      precisa conseguir entrar. Em producao, o certo e' o primeiro acesso
      obrigar a troca, ou a senha inicial ser gerada aleatoria e enviada
      por outro canal.

      O que NAO muda entre demo e producao: a senha nunca e' guardada. Vai
      para o banco ja como hash PBKDF2 com salt (ver security.py).
    """
    usuarios = [
        # A empresa de TI -- ve tudo, nao pertence a cliente nenhum.
        User(
            name="Administrador da Plataforma",
            email="admin@helpdesk.com.br",
            password_hash=hash_senha("admin12345"),
            role=UserRole.SUPER_ADMIN,
            client_id=None,
        ),
    ]

    # Um responsavel para cada uma das 3 primeiras empresas atendidas.
    # Sao eles que provam o multi-empresa na demonstracao: entrando com o
    # da empresa 1, os dados da empresa 2 desaparecem da tela.
    for indice, client in enumerate(clients[:3], start=1):
        usuarios.append(
            User(
                name=f"Responsavel {client.company}",
                email=f"empresa{indice}@cliente.com.br",
                password_hash=hash_senha(f"empresa{indice}2345"),
                role=UserRole.ADMIN_EMPRESA,
                client_id=client.id,
            )
        )

    db.add_all(usuarios)
    db.commit()
    for u in usuarios:
        db.refresh(u)
    return usuarios


# ---------------------------------------------------------------------------
# ORQUESTRACAO
# ---------------------------------------------------------------------------


# Volumes base -- o que o seed cria quando voce nao pede escala nenhuma.
# Sao os numeros pensados para a DEMONSTRACAO: pequenos o bastante para
# caber na tela, grandes o bastante para os relatorios contarem uma historia.
BASE_CLIENTES = 20
BASE_CHAMADOS = 100
BASE_EQUIPAMENTOS = 18


def run(
    reset: bool = False,
    clientes: int = BASE_CLIENTES,
    chamados: int = BASE_CHAMADOS,
    equipamentos: int = BASE_EQUIPAMENTOS,
) -> None:
    """Executa o seed completo com os volumes pedidos."""
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

        print(f"  [1/4] criando {clientes} clientes...")
        clients = _create_clients(db, clientes)

        print(f"  [2/5] criando {chamados} chamados com datas historicas...")
        _create_tickets(db, clients, chamados)

        print(f"  [3/5] criando {equipamentos} equipamentos...")
        equipments = _create_equipments(db, clients, equipamentos)

        print("  [4/5] enviando leituras pelo monitoring_service (a regra roda aqui)...")
        readings, alerts = _create_readings(db, equipments)

        print("  [5/5] criando usuarios de acesso...")
        usuarios = _create_users(db, clients)

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
        print()
        print("  ACESSOS CRIADOS:")
        print("    admin@helpdesk.com.br      / admin12345      (ve TUDO)")
        for i, u in enumerate(usuarios[1:], start=1):
            empresa = u.client.company if u.client else "-"
            print(f"    empresa{i}@cliente.com.br    / empresa{i}2345    (so {empresa})")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    if "--wipe" in sys.argv:
        # ESVAZIA o banco sem popular nada. Use quando quiser apresentar o
        # sistema partindo do ZERO e inserir os dados voce mesmo, pela tela.
        # A ordem de exclusao respeita as foreign keys (filhos antes dos pais).
        session = SessionLocal()
        try:
            print("Esvaziando o banco (todas as tabelas)...")
            _wipe(session)
            print("Banco vazio. Agora so tera os dados que VOCE inserir.")
            _print_status(session)
        finally:
            session.close()
    elif "--status" in sys.argv:
        session = SessionLocal()
        try:
            print(f"Banco: {settings.DATABASE_URL_RESOLVED}")
            _print_status(session)
        finally:
            session.close()
    else:
        # -------------------------------------------------------------------
        # ARGUMENTOS DE VOLUME
        #
        #   --scale N   multiplica TODOS os volumes base por N.
        #               E' o atalho: --scale 50 gera 5.000 chamados.
        #
        #   --clientes / --chamados / --equipamentos
        #               controle direto, para quando voce quer um numero
        #               exato de um deles. Vence o --scale se os dois vierem.
        #
        # POR QUE OS DOIS JEITOS: --scale e' pratico para "quero 50x mais";
        # os explicitos sao para "quero exatamente 5.000 chamados". Um nao
        # substitui o outro.
        # -------------------------------------------------------------------
        parser = argparse.ArgumentParser(
            prog="python -m backend.seed",
            description="Popula o banco com dados realistas.",
        )
        parser.add_argument("--reset", action="store_true",
                            help="APAGA os dados existentes antes de popular")
        parser.add_argument("--scale", type=int, default=1, metavar="N",
                            help="multiplica todos os volumes base por N "
                                 "(ex.: --scale 50 = 5.000 chamados)")
        parser.add_argument("--clientes", type=int, default=None, metavar="N")
        parser.add_argument("--chamados", type=int, default=None, metavar="N")
        parser.add_argument("--equipamentos", type=int, default=None, metavar="N")
        args = parser.parse_args()

        if args.scale < 1:
            parser.error("--scale precisa ser 1 ou maior.")

        run(
            reset=args.reset,
            clientes=args.clientes or BASE_CLIENTES * args.scale,
            chamados=args.chamados or BASE_CHAMADOS * args.scale,
            equipamentos=args.equipamentos or BASE_EQUIPAMENTOS * args.scale,
        )
