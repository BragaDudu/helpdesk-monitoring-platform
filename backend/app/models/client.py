"""Model Client -- tabela "clients".

O CLIENTE E' A ENTIDADE CENTRAL DA PLATAFORMA: dele saem os chamados
(Exercicio 1 e 2) e os equipamentos monitorados (Exercicio 3).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.utils import utcnow

if TYPE_CHECKING:  # apenas para o editor/type checker, nao roda em runtime
    from backend.app.models.equipment import Equipment
    from backend.app.models.ticket import Ticket


class Client(Base):
    """Um cliente atendido pela empresa.

    MAPEAMENTO: cada atributo abaixo vira uma COLUNA da tabela "clients";
    cada instancia desta classe vira uma LINHA.
    """

    __tablename__ = "clients"

    # PRIMARY KEY: identificador tecnico, gerado pelo banco (AUTOINCREMENT).
    # Nunca muda e nunca se repete -- por isso e' ele que as foreign keys
    # das outras tabelas apontam.
    id: Mapped[int] = mapped_column(primary_key=True)

    # index=True cria um indice na coluna. Indice e' como o indice remissivo
    # de um livro: em vez de ler as 20.000 linhas para achar "Maria", o banco
    # vai direto. Custa um pouco de espaco e deixa o INSERT levemente mais
    # lento, entao so criamos onde realmente se busca/ordena.
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    # UNIQUE: o banco garante que nao existem dois clientes com o mesmo e-mail.
    # Se a API tentar inserir repetido, o INSERT falha e o service converte
    # isso em HTTP 409 Conflict. A garantia esta NO BANCO, nao num "if" do
    # Python -- um "if" sofreria race condition entre duas requisicoes
    # simultaneas; a constraint UNIQUE nao.
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    phone: Mapped[str] = mapped_column(String(20), nullable=False)

    # default=utcnow -> passamos a FUNCAO, sem parenteses. O SQLAlchemy a
    # chama no momento do INSERT. Se escrevessemos utcnow() (com parenteses),
    # a data seria calculada uma unica vez, quando o Python carregasse o
    # arquivo, e TODOS os clientes teriam a mesma data. Erro classico.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    # -----------------------------------------------------------------------
    # RELACIONAMENTOS (lado "1" do 1:N)
    #
    # Isto NAO cria coluna nenhuma. E' um atalho do ORM: escrevendo
    # cliente.tickets, o SQLAlchemy dispara sozinho o
    #     SELECT * FROM tickets WHERE client_id = <id do cliente>
    #
    # back_populates="client" liga este atributo ao atributo "client" do
    # model Ticket, mantendo os dois lados sincronizados na memoria.
    #
    # passive_deletes=True: nao tente apagar os filhos em cascata; deixe o
    # banco decidir. Como configuramos ON DELETE RESTRICT nas FKs, o banco
    # RECUSA apagar um cliente que ainda tem chamados -- e isso vira um
    # HTTP 409. Apagar historico de atendimento silenciosamente seria destruir
    # informacao de negocio.
    # -----------------------------------------------------------------------
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="client", passive_deletes=True
    )
    equipments: Mapped[list["Equipment"]] = relationship(
        back_populates="client", passive_deletes=True
    )

    def __repr__(self) -> str:  # ajuda muito ao depurar no terminal
        return f"<Client id={self.id} name={self.name!r} company={self.company!r}>"
