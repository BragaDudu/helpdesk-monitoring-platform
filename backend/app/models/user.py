"""Model User -- tabela "users".

Quem pode entrar no sistema, e o que cada um enxerga.

★ A COLUNA QUE FAZ O MULTI-EMPRESA FUNCIONAR E' client_id.

    role = SUPER_ADMIN    -> client_id NULO   -> enxerga TUDO
    role = ADMIN_EMPRESA  -> client_id = 3    -> enxerga so a empresa 3

  Nao ha "banco separado por empresa" nem "tabela por cliente". E' UMA base
  com uma coluna de dono, e todo SELECT filtra por ela. Esse desenho se
  chama multi-tenancy por COLUNA discriminadora, e e' o mais comum em SaaS:
  simples de operar, barato de manter e -- o ponto critico -- so e' seguro
  se NENHUMA consulta esquecer o filtro.

  E' por isso que o filtro nao fica solto em cada rota: ele nasce de uma
  dependencia unica (backend/app/deps.py) e desce para os services. Um
  lugar para acertar, um lugar para auditar.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.enums import UserRole
from backend.app.utils import utcnow

if TYPE_CHECKING:
    from backend.app.models.client import Client


class User(Base):
    """Uma pessoa que faz login na plataforma."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # UNIQUE: o e-mail e' o "nome de usuario". Dois cadastros com o mesmo
    # e-mail tornariam o login ambiguo -- qual dos dois autenticar?
    # A garantia esta no banco, nao num "if" (mesmo argumento do cliente).
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )

    # ★ O NOME DA COLUNA E' password_HASH, NAO password.
    #   Isso nao e' preciosismo: e' documentacao dentro do schema. Quem
    #   abrir o banco ve na hora que ali NAO ha senha nenhuma guardada.
    #   O formato e' pbkdf2_sha256$240000$<salt>$<hash> -- ver security.py.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False, create_constraint=True,
               length=20, name="user_role_enum"),
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------------------------
    # ★ A COLUNA DO MULTI-EMPRESA
    #
    #   NULL  -> usuario da empresa de TI (SUPER_ADMIN): ve tudo
    #   9     -> responsavel da empresa 9: ve so os dados dela
    #
    #   Fica NULA de proposito para o SUPER_ADMIN. A alternativa seria um
    #   client_id = 0 fingindo "todos" -- um valor magico que alguem um dia
    #   compararia errado. NULL diz literalmente "nao se aplica".
    #
    #   ondelete="RESTRICT": nao da' para apagar uma empresa que ainda tem
    #   usuario ligado a ela. Apagar deixaria a pessoa com acesso a um
    #   client_id que nao existe mais.
    # -----------------------------------------------------------------------
    client_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # Desligar sem apagar. Apagar o usuario perderia o rastro de quem ele
    # era; is_active=False bloqueia o login e preserva o historico.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    client: Mapped[Optional["Client"]] = relationship()

    @property
    def ve_tudo(self) -> bool:
        """True quando o usuario nao esta preso a uma empresa.

        Existe para o resto do codigo perguntar `user.ve_tudo` em vez de
        repetir `user.role == UserRole.SUPER_ADMIN` em dez lugares. No dia
        em que nascer um papel TECNICO que tambem ve tudo, muda-se AQUI.
        """
        return self.role == UserRole.SUPER_ADMIN

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
