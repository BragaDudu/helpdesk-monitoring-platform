"""Funcoes utilitarias pequenas e sem dependencia de nada do projeto.

Hoje so existe o tratamento de data/hora, que e' um assunto delicado o
suficiente para merecer um lugar proprio.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Retorna o instante ATUAL em UTC, sem informacao de fuso (naive).

    POR QUE UTC?
        Se guardassemos horario de Brasilia, todo o historico ficaria errado
        no dia em que o servidor mudasse de fuso ou a empresa abrisse filial
        em outro pais. Calculos como "tempo medio de fechamento" dariam
        resultados absurdos no horario de verao. UTC nao tem horario de verao
        e nao muda nunca: e' a unica referencia estavel.

    POR QUE SEM FUSO (naive)?
        O SQLite nao possui um tipo nativo de "data com fuso horario".
        Se guardassemos datas com fuso, o valor voltaria do banco sem ele e
        teriamos comparacoes inconsistentes (aware vs naive quebra em Python).
        A convencao adotada e' simples e explicita:

            TUDO que esta no banco esta em UTC.

        Na saida da API o schema Pydantic acrescenta o sufixo "Z" (padrao
        ISO-8601 para UTC) e so o JavaScript converte para o fuso do usuario,
        na hora de exibir na tela.

    QUEM CHAMA:
        - os models, como valor padrao das colunas created_at / opened_at
        - os services, ao carimbar closed_at e a data dos alertas
        - o seed, ao gerar datas historicas

    RETORNA: datetime em UTC, sem tzinfo.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
