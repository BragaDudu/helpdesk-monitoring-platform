"""Schemas das consultas analiticas (Exercicio 2).

Estes schemas nao correspondem a nenhuma tabela: eles descrevem o RESULTADO
de uma agregacao. Por isso nao tem "id" nem from_attributes -- sao montados
a partir de linhas devolvidas por um GROUP BY.

Repare que existe um schema por consulta. Poderiamos devolver um dicionario
solto, mas ai o Swagger nao documentaria nada e o frontend teria que
adivinhar os nomes dos campos. O schema E' a documentacao.
"""

from pydantic import BaseModel


class TicketsByClientItem(BaseModel):
    """Item 1 do Exercicio 2: quantidade de chamados por cliente."""

    client_id: int
    client_name: str
    company: str
    total: int
    abertos: int
    em_andamento: int
    finalizados: int


class TicketsByCategoryItem(BaseModel):
    """Item 2 do Exercicio 2: quantidade de chamados por categoria."""

    category: str
    total: int
    abertos: int
    em_andamento: int
    finalizados: int


class CustomerRankingItem(BaseModel):
    """Item 3 do Exercicio 2: ranking dos clientes com mais chamados."""

    position: int
    client_id: int
    client_name: str
    company: str
    total: int


class AverageResolutionTime(BaseModel):
    """Item 4 do Exercicio 2: tempo medio de fechamento dos chamados.

    Devolvemos o MESMO numero em tres formatos:
      average_hours -> para calculo e para graficos
      average_days  -> para leitura rapida de gestor
      formatted     -> texto pronto para a tela ("2d 6h")

    POR QUE NAO DEIXAR O FRONTEND FORMATAR? Porque se amanha existir um app
    mobile e um relatorio em PDF, cada um formataria de um jeito e os numeros
    da empresa apareceriam diferentes em cada lugar. Formatacao de dado de
    negocio pertence ao backend.

    total_finalizados diz sobre QUANTOS chamados a media foi calculada.
    Uma media sem o tamanho da amostra e' um numero perigoso: "3 horas" a
    partir de 2 chamados nao significa a mesma coisa que a partir de 60.
    """

    total_finalizados: int
    average_hours: float | None
    average_days: float | None
    formatted: str


class OpenTicketsSummary(BaseModel):
    """Item 5 do Exercicio 2: quantidade de chamados ainda abertos."""

    abertos: int
    em_andamento: int
    finalizados: int
    total: int
    # "nao finalizados" = abertos + em andamento. E' o numero que interessa
    # ao gestor: tudo que ainda demanda trabalho da equipe.
    pendentes: int
    por_prioridade: dict[str, int]


class CategoryResolutionTimeItem(BaseModel):
    """Item 6 do Exercicio 2: categoria com maior tempo medio de resolucao.

    A lista vem ordenada do MAIOR tempo para o menor, entao o primeiro item
    ja e' a resposta da pergunta do enunciado.
    """

    category: str
    total_finalizados: int
    average_hours: float
    average_days: float
    formatted: str


class DashboardSummary(BaseModel):
    """Todos os numeros do dashboard numa unica requisicao.

    POR QUE ESTE ENDPOINT EXISTE (nao estava no enunciado):
      Sem ele, a tela inicial precisaria de 7 requisicoes HTTP para pintar
      os cartoes. Cada requisicao tem custo de rede e abre uma conexao de
      banco. Uma so consulta que devolve o bloco inteiro e' mais rapida e
      mais honesta com o servidor.

      Os 6 endpoints individuais do enunciado CONTINUAM existindo -- este
      e' um atalho para a tela, nao um substituto.
    """

    total_clientes: int
    total_chamados: int
    chamados_abertos: int
    chamados_em_andamento: int
    chamados_finalizados: int
    total_equipamentos: int
    total_leituras: int
    alertas_criticos_abertos: int
    total_alertas: int
    tempo_medio_resolucao: AverageResolutionTime
    top_categoria: str | None
    top_cliente: str | None
