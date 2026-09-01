"""Cria as tabelas no banco de dados.

COMO USAR (a partir da RAIZ do projeto):

    python -m backend.init_db          # cria o que faltar
    python -m backend.init_db --drop   # APAGA TUDO e recria (pede confirmacao)

E' SEGURO RODAR VARIAS VEZES?
    Sim. create_all() so cria tabelas que AINDA NAO EXISTEM. Ele nunca apaga
    dados e nunca sobrescreve uma tabela existente. Por isso o main.py tambem
    o chama ao iniciar: se o banco ja existe, nada acontece; se e' a primeira
    execucao, o banco nasce pronto.

E MIGRACOES (Alembic)?
    create_all() cria tabelas NOVAS, mas NAO altera tabelas existentes. Se um
    dia acrescentarmos uma coluna a "tickets", o create_all nao vai perceber.
    Nesse momento entra o Alembic, que gera scripts de migracao versionados.
    Nao foi incluido agora porque o schema nasce fechado e Alembic e' mais
    uma ferramenta a explicar sem ganho real nesta fase. Consta no README
    como o proximo passo natural.
"""

import sys

from sqlalchemy import inspect

from backend.app.config import settings
from backend.app.database import Base, engine

# ESTA LINHA E' OBRIGATORIA: importa os models para que eles se registrem em
# Base.metadata. Sem ela, create_all() nao criaria nenhuma tabela.
import backend.app.models  # noqa: F401


def create_tables(drop_first: bool = False) -> None:
    """Cria (e opcionalmente recria) o schema do banco."""
    if drop_first:
        print("!! ATENCAO: isto vai APAGAR todas as tabelas e todos os dados.")
        answer = input("   Digite APAGAR para confirmar: ").strip()
        if answer != "APAGAR":
            print("Cancelado. Nada foi alterado.")
            return
        Base.metadata.drop_all(bind=engine)
        print("Tabelas removidas.")

    Base.metadata.create_all(bind=engine)

    # inspect() pergunta ao banco REAL quais tabelas existem agora.
    # Nao e' um "confio que deu certo": e' uma leitura do arquivo .db.
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())

    print(f"Banco: {settings.DATABASE_URL_RESOLVED}")
    print(f"Tabelas existentes ({len(tables)}):")
    for table in tables:
        columns = inspector.get_columns(table)
        fks = inspector.get_foreign_keys(table)
        indexes = inspector.get_indexes(table)
        print(f"  - {table}: {len(columns)} colunas, {len(fks)} FK, {len(indexes)} indices")


if __name__ == "__main__":
    create_tables(drop_first="--drop" in sys.argv)
