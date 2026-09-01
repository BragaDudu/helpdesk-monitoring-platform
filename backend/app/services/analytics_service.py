"""Consultas analiticas -- o Exercicio 2 inteiro.

PRINCIPIO QUE VALE PARA TODO ESTE ARQUIVO:

    TODA agregacao acontece DENTRO DO BANCO.

    A alternativa preguicosa seria trazer os 100 chamados para a memoria e
    contar com um "for" em Python. Isso funciona com 100 registros e explode
    com 100.000: gastaria rede, memoria e tempo para fazer o que o banco faz
    em milissegundos, com indice.

    Contar, somar e agrupar e' EXATAMENTE para o que um banco relacional foi
    criado. Usar o banco so como "lugar onde os dados ficam" e' desperdicar
    a ferramenta.
"""

from sqlalchemy import Float, and_, case, cast, func, select
from sqlalchemy.orm import Session

from backend.app.database import engine
from backend.app.enums import TicketStatus
from backend.app.models import Alert, Client, Equipment, EquipmentReading, Ticket
from backend.app.schemas.analytics import (
    AverageResolutionTime,
    CategoryResolutionTimeItem,
    CustomerRankingItem,
    DashboardSummary,
    OpenTicketsSummary,
    TicketsByCategoryItem,
    TicketsByClientItem,
)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _count_if(condition) -> object:
    """Conta quantas linhas do grupo satisfazem uma condicao.

    Gera o SQL:   SUM(CASE WHEN <condicao> THEN 1 ELSE 0 END)

    POR QUE ISSO E' UTIL: permite trazer, numa UNICA consulta, o total de
    chamados de um cliente E quantos estao abertos E quantos finalizados.
    Sem CASE, seriam tres consultas separadas (uma por status) e depois um
    trabalho de juntar tudo em Python.

    Este padrao se chama "agregacao condicional" ou "pivot". E' um dos
    truques de SQL que mais impressionam numa banca, porque muita gente
    resolveria com tres queries.
    """
    return func.sum(case((condition, 1), else_=0))


def _resolution_hours_expr():
    """Expressao SQL que calcula, em HORAS, quanto tempo um chamado levou.

    ★ AQUI EXISTE UM PROBLEMA REAL DE PORTABILIDADE, E ELE E' TRATADO.

    Bancos diferentes subtraem datas de formas diferentes:

      SQLite     -> nao tem tipo DATE nativo (guarda texto). Usa-se
                    julianday(), que converte a data para um numero de dias
                    fracionario. A diferenca * 24 da o total de horas.

      PostgreSQL -> subtrair dois timestamps devolve um INTERVAL.
                    EXTRACT(EPOCH FROM intervalo) devolve segundos;
                    dividido por 3600, vira horas.

    Em vez de escrever SQL cru de um dos dois (o que quebraria a promessa
    de "trocar para PostgreSQL mudando so o .env"), a funcao consulta o
    DIALETO ativo e devolve a expressao correta.

    A troca de banco continua sendo uma linha no .env. A unica coisa que
    precisou de tratamento especifico foi a aritmetica de datas, que e'
    genuinamente diferente entre os dois -- e esta isolada nesta funcao.
    """
    if engine.dialect.name == "sqlite":
        return (
            func.julianday(Ticket.closed_at) - func.julianday(Ticket.opened_at)
        ) * 24.0
    # PostgreSQL, MySQL 8+ e outros com aritmetica nativa de timestamp
    return cast(
        func.extract("epoch", Ticket.closed_at - Ticket.opened_at), Float
    ) / 3600.0


def _format_duration(hours: float | None) -> str:
    """Transforma um numero de horas em texto legivel: 54.5 -> '2d 6h'.

    Fica no BACKEND para que web, mobile e relatorio mostrem exatamente o
    mesmo texto. Formatacao de dado de negocio nao e' assunto de tela.
    """
    if hours is None:
        return "sem dados"
    if hours < 1:
        return f"{int(round(hours * 60))}min"
    if hours < 24:
        h = int(hours)
        m = int(round((hours - h) * 60))
        return f"{h}h {m}min" if m else f"{h}h"
    days = int(hours // 24)
    rest = int(round(hours % 24))
    return f"{days}d {rest}h" if rest else f"{days}d"


# ---------------------------------------------------------------------------
# 1) QUANTIDADE DE CHAMADOS POR CLIENTE
# ---------------------------------------------------------------------------
def tickets_by_client(db: Session) -> list[TicketsByClientItem]:
    """Item 1 do Exercicio 2.

    SQL GERADO (aproximado):

        SELECT c.id, c.name, c.company,
               COUNT(t.id)                                    AS total,
               SUM(CASE WHEN t.status='ABERTO' THEN 1 ELSE 0 END)      AS abertos,
               SUM(CASE WHEN t.status='EM_ANDAMENTO' THEN 1 ELSE 0 END) AS andamento,
               SUM(CASE WHEN t.status='FINALIZADO' THEN 1 ELSE 0 END)   AS finalizados
        FROM clients c
        LEFT JOIN tickets t ON t.client_id = c.id
        GROUP BY c.id, c.name, c.company
        ORDER BY total DESC, c.name

    ★ POR QUE **LEFT** JOIN E NAO JOIN COMUM?
        Um JOIN comum (INNER) so devolve clientes que TEM chamados. Clientes
        sem nenhum chamado sumiriam do relatorio -- e "o cliente X nao abriu
        nenhum chamado" e' justamente uma informacao valiosa para a empresa.
        LEFT JOIN mantem todos os clientes; quem nao tem chamado aparece
        com total = 0.

        Este e' o tipo de detalhe que separa um relatorio certo de um
        relatorio que parece certo.

    ★ POR QUE COUNT(t.id) E NAO COUNT(*)?
        COUNT(*) conta LINHAS. Num LEFT JOIN, um cliente sem chamados ainda
        produz uma linha (com os campos do chamado em NULL), entao COUNT(*)
        devolveria 1 para quem tem zero chamados. COUNT(t.id) ignora NULL e
        devolve 0 corretamente.

    RETORNA: lista ordenada do cliente com mais chamados para o com menos.
    """
    stmt = (
        select(
            Client.id,
            Client.name,
            Client.company,
            func.count(Ticket.id).label("total"),
            _count_if(Ticket.status == TicketStatus.ABERTO).label("abertos"),
            _count_if(Ticket.status == TicketStatus.EM_ANDAMENTO).label("andamento"),
            _count_if(Ticket.status == TicketStatus.FINALIZADO).label("finalizados"),
        )
        .select_from(Client)
        .outerjoin(Ticket, Ticket.client_id == Client.id)
        .group_by(Client.id, Client.name, Client.company)
        .order_by(func.count(Ticket.id).desc(), Client.name)
    )

    return [
        TicketsByClientItem(
            client_id=row.id,
            client_name=row.name,
            company=row.company,
            total=row.total,
            abertos=int(row.abertos or 0),
            em_andamento=int(row.andamento or 0),
            finalizados=int(row.finalizados or 0),
        )
        for row in db.execute(stmt)
    ]


# ---------------------------------------------------------------------------
# 2) QUANTIDADE DE CHAMADOS POR CATEGORIA
# ---------------------------------------------------------------------------
def tickets_by_category(db: Session) -> list[TicketsByCategoryItem]:
    """Item 2 do Exercicio 2.

    Aqui NAO ha JOIN: a categoria e' uma coluna da propria tabela tickets.
    E' o GROUP BY mais simples possivel -- agrupa por um campo e conta.

        SELECT category, COUNT(*) ... FROM tickets GROUP BY category

    Como a categoria e' texto livre (e nao Enum), este relatorio se adapta
    sozinho: se a empresa criar a categoria "Backup" amanha, ela aparece
    aqui sem nenhuma alteracao de codigo.
    """
    stmt = (
        select(
            Ticket.category,
            func.count(Ticket.id).label("total"),
            _count_if(Ticket.status == TicketStatus.ABERTO).label("abertos"),
            _count_if(Ticket.status == TicketStatus.EM_ANDAMENTO).label("andamento"),
            _count_if(Ticket.status == TicketStatus.FINALIZADO).label("finalizados"),
        )
        .group_by(Ticket.category)
        .order_by(func.count(Ticket.id).desc(), Ticket.category)
    )

    return [
        TicketsByCategoryItem(
            category=row.category,
            total=row.total,
            abertos=int(row.abertos or 0),
            em_andamento=int(row.andamento or 0),
            finalizados=int(row.finalizados or 0),
        )
        for row in db.execute(stmt)
    ]


# ---------------------------------------------------------------------------
# 3) RANKING DOS CLIENTES COM MAIS CHAMADOS
# ---------------------------------------------------------------------------
def customer_ranking(db: Session, limit: int = 10) -> list[CustomerRankingItem]:
    """Item 3 do Exercicio 2.

    DIFERENCA PARA O ITEM 1 (que tambem agrupa por cliente):
      - Item 1 = relatorio COMPLETO, inclui clientes com zero chamados
      - Item 3 = RANKING, so quem tem chamado, cortado nos N primeiros

    Por isso aqui e' JOIN comum (INNER): quem nao tem chamado nao entra num
    ranking de quem mais abre chamados.

    A "position" (1o, 2o, 3o) e' calculada em Python com enumerate.
    PODERIA ser feita em SQL com a funcao de janela RANK() OVER (...), mas:
      - a lista ja vem ordenada pelo banco, entao a posicao e' so contar
      - window function e' mais um conceito para defender na banca sem
        ganho pratico algum neste caso
    Escolha consciente de simplicidade.
    """
    stmt = (
        select(
            Client.id,
            Client.name,
            Client.company,
            func.count(Ticket.id).label("total"),
        )
        .select_from(Client)
        .join(Ticket, Ticket.client_id == Client.id)
        .group_by(Client.id, Client.name, Client.company)
        .order_by(func.count(Ticket.id).desc(), Client.name)
        .limit(limit)
    )

    return [
        CustomerRankingItem(
            position=index,
            client_id=row.id,
            client_name=row.name,
            company=row.company,
            total=row.total,
        )
        for index, row in enumerate(db.execute(stmt), start=1)
    ]


# ---------------------------------------------------------------------------
# 4) TEMPO MEDIO DE FECHAMENTO
# ---------------------------------------------------------------------------
def average_resolution_time(db: Session) -> AverageResolutionTime:
    """Item 4 do Exercicio 2.

    ★ O FILTRO MAIS IMPORTANTE DESTA CONSULTA:

          WHERE status = 'FINALIZADO' AND closed_at IS NOT NULL

      So entram na media os chamados que REALMENTE fecharam. Um chamado
      aberto nao tem duracao -- ele ainda esta acontecendo.

      Se incluissemos os abertos com closed_at NULL, o AVG do SQL os
      ignoraria no numerador mas... na verdade o AVG ja ignora NULL. O
      filtro explicito existe por CLAREZA: quem le a consulta entende
      imediatamente qual e' a populacao analisada. Codigo que depende de
      um comportamento implicito e' codigo que alguem quebra depois.

      ★ E' AQUI que a decisao de deixar closed_at NULL (Etapa 1) paga.
        Se tivessemos preenchido com uma data falsa, este numero estaria
        errado e ninguem perceberia.

    RETORNA: media em horas, em dias, e o texto formatado.
             Se nao houver nenhum chamado finalizado, devolve None e
             "sem dados" -- e NAO zero. Zero seria mentira: significaria
             "fecha instantaneamente".
    """
    condition = and_(
        Ticket.status == TicketStatus.FINALIZADO,
        Ticket.closed_at.is_not(None),
    )

    stmt = select(
        func.count(Ticket.id).label("total"),
        func.avg(_resolution_hours_expr()).label("avg_hours"),
    ).where(condition)

    row = db.execute(stmt).one()
    total = int(row.total or 0)
    avg_hours = float(row.avg_hours) if row.avg_hours is not None else None

    return AverageResolutionTime(
        total_finalizados=total,
        average_hours=round(avg_hours, 2) if avg_hours is not None else None,
        average_days=round(avg_hours / 24, 2) if avg_hours is not None else None,
        formatted=_format_duration(avg_hours),
    )


# ---------------------------------------------------------------------------
# 5) CHAMADOS AINDA ABERTOS
# ---------------------------------------------------------------------------
def open_tickets(db: Session) -> OpenTicketsSummary:
    """Item 5 do Exercicio 2.

    Uma unica passada na tabela devolve a contagem dos tres status, de novo
    com agregacao condicional. Depois, uma segunda consulta agrupa por
    prioridade apenas os chamados NAO finalizados -- porque saber que ha
    "12 pendentes, sendo 5 de prioridade ALTA" e' o que um gestor precisa.

    "pendentes" = abertos + em andamento. E' o numero que representa o
    trabalho que a equipe ainda tem pela frente.
    """
    row = db.execute(
        select(
            func.count(Ticket.id).label("total"),
            _count_if(Ticket.status == TicketStatus.ABERTO).label("abertos"),
            _count_if(Ticket.status == TicketStatus.EM_ANDAMENTO).label("andamento"),
            _count_if(Ticket.status == TicketStatus.FINALIZADO).label("finalizados"),
        )
    ).one()

    priority_rows = db.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.status != TicketStatus.FINALIZADO)
        .group_by(Ticket.priority)
    ).all()

    abertos = int(row.abertos or 0)
    andamento = int(row.andamento or 0)

    return OpenTicketsSummary(
        abertos=abertos,
        em_andamento=andamento,
        finalizados=int(row.finalizados or 0),
        total=int(row.total or 0),
        pendentes=abertos + andamento,
        # priority vem como Enum; .value converte para o texto "ALTA"
        por_prioridade={
            (p.value if hasattr(p, "value") else str(p)): int(qtd)
            for p, qtd in priority_rows
        },
    )


# ---------------------------------------------------------------------------
# 6) CATEGORIA COM MAIOR TEMPO MEDIO DE RESOLUCAO
# ---------------------------------------------------------------------------
def category_resolution_time(db: Session) -> list[CategoryResolutionTimeItem]:
    """Item 6 do Exercicio 2.

    Combina as duas ideias anteriores: agrupa por categoria (item 2) e
    calcula media de duracao (item 4), sobre a mesma populacao filtrada
    de chamados finalizados.

        SELECT category, COUNT(*), AVG(<horas>)
        FROM tickets
        WHERE status = 'FINALIZADO' AND closed_at IS NOT NULL
        GROUP BY category
        ORDER BY AVG(<horas>) DESC

    A lista vem ordenada do MAIOR tempo medio para o menor, entao o
    PRIMEIRO item ja e' a resposta literal da pergunta do enunciado:
    "qual categoria demora mais para ser resolvida?".

    Na pratica isso responde uma pergunta de negocio real: onde a equipe
    esta perdendo mais tempo, e portanto onde vale investir em treinamento,
    ferramenta ou automacao.
    """
    hours = _resolution_hours_expr()

    stmt = (
        select(
            Ticket.category,
            func.count(Ticket.id).label("total"),
            func.avg(hours).label("avg_hours"),
        )
        .where(
            and_(
                Ticket.status == TicketStatus.FINALIZADO,
                Ticket.closed_at.is_not(None),
            )
        )
        .group_by(Ticket.category)
        .order_by(func.avg(hours).desc())
    )

    result = []
    for row in db.execute(stmt):
        avg_hours = float(row.avg_hours or 0)
        result.append(
            CategoryResolutionTimeItem(
                category=row.category,
                total_finalizados=int(row.total),
                average_hours=round(avg_hours, 2),
                average_days=round(avg_hours / 24, 2),
                formatted=_format_duration(avg_hours),
            )
        )
    return result


# ---------------------------------------------------------------------------
# EXTRA) RESUMO PARA O DASHBOARD
# ---------------------------------------------------------------------------
def dashboard_summary(db: Session) -> DashboardSummary:
    """Reune os numeros da tela inicial numa unica requisicao.

    QUEM CHAMA: o dashboard.js, ao abrir a pagina inicial.

    POR QUE EXISTE: sem ele a tela faria 7 requisicoes HTTP. Cada uma com
    latencia de rede e uma conexao de banco. Uma so e' mais rapida e mais
    leve para o servidor.

    Os 6 endpoints do enunciado continuam existindo separadamente -- este
    e' um atalho para a tela, nao um substituto deles.
    """
    counters = db.execute(
        select(
            func.count(Ticket.id).label("total"),
            _count_if(Ticket.status == TicketStatus.ABERTO).label("abertos"),
            _count_if(Ticket.status == TicketStatus.EM_ANDAMENTO).label("andamento"),
            _count_if(Ticket.status == TicketStatus.FINALIZADO).label("finalizados"),
        )
    ).one()

    total_clientes = db.scalar(select(func.count()).select_from(Client)) or 0
    total_equipamentos = db.scalar(select(func.count()).select_from(Equipment)) or 0
    total_leituras = db.scalar(select(func.count()).select_from(EquipmentReading)) or 0
    total_alertas = db.scalar(select(func.count()).select_from(Alert)) or 0
    alertas_abertos = (
        db.scalar(
            select(func.count()).select_from(Alert).where(Alert.status == "ABERTO")
        )
        or 0
    )

    categorias = tickets_by_category(db)
    ranking = customer_ranking(db, limit=1)

    return DashboardSummary(
        total_clientes=total_clientes,
        total_chamados=int(counters.total or 0),
        chamados_abertos=int(counters.abertos or 0),
        chamados_em_andamento=int(counters.andamento or 0),
        chamados_finalizados=int(counters.finalizados or 0),
        total_equipamentos=total_equipamentos,
        total_leituras=total_leituras,
        alertas_criticos_abertos=alertas_abertos,
        total_alertas=total_alertas,
        tempo_medio_resolucao=average_resolution_time(db),
        top_categoria=categorias[0].category if categorias else None,
        top_cliente=ranking[0].company if ranking else None,
    )
