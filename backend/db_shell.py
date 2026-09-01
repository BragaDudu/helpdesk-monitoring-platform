"""Console SQL para explorar o banco do projeto.

O Windows nao vem com o programa 'sqlite3.exe', entao este script faz o
papel dele: abre o arquivo data/app.db e deixa voce digitar SQL direto.

COMO USAR (na raiz do projeto):

    python -m backend.db_shell                  # abre o console interativo
    python -m backend.db_shell "SELECT * FROM clients"   # roda 1 comando

DENTRO DO CONSOLE:
    .tabelas          lista as tabelas
    .schema clients   mostra como a tabela foi criada (colunas, FK, CHECK)
    .contar           conta os registros de todas as tabelas
    .sair             sai

★ PARA A APRESENTACAO: e' aqui que voce PROVA que o dado esta no banco.
  Cadastre um cliente pela tela, abra este console e rode
      SELECT * FROM clients;
  O cliente esta la. Isso mata qualquer duvida de "e mockup?".
"""

import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# ATENCAO: este arquivo usa SOMENTE a biblioteca padrao do Python
# (sqlite3 e pathlib). Ele NAO importa nada do resto do projeto.
#
# POR QUE ISSO E' PROPOSITAL: assim o console funciona mesmo sem o ambiente
# virtual ativado. Se ele importasse backend.app.config, precisaria do
# pydantic-settings instalado, e voce receberia
#     ModuleNotFoundError: No module named 'pydantic_settings'
# ao rodar com o Python do sistema. Uma ferramenta de emergencia (que serve
# para investigar o banco quando algo deu errado) nao pode depender de que
# tudo esteja instalado corretamente.
#
# O caminho e' calculado a partir da posicao deste arquivo:
#   __file__            -> backend/db_shell.py
#   .parents[0]         -> backend
#   .parents[1]         -> raiz do projeto
# ---------------------------------------------------------------------------
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"

# ---------------------------------------------------------------------------
# ACENTOS NO CONSOLE DO WINDOWS
# O terminal do Windows costuma usar a codificacao cp1252, enquanto o banco
# guarda texto em UTF-8. Sem esta linha, "Antonio" com acento apareceria como
# "�ntonio". reconfigure() forca a saida para UTF-8.
# errors="replace" garante que, se algum caractere ainda assim nao puder ser
# exibido, o programa mostre um simbolo em vez de quebrar.
# ---------------------------------------------------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass  # em terminais antigos, apenas segue sem reconfigurar
TABELAS = ["clients", "tickets", "equipments", "equipment_readings", "alerts"]


def mostrar(cursor) -> None:
    """Imprime o resultado de um SELECT em formato de tabela."""
    linhas = cursor.fetchall()
    if not linhas:
        print("  (nenhuma linha)")
        return
    colunas = [d[0] for d in cursor.description]
    largura = [
        max(len(str(c)), max((len(str(l[i])) for l in linhas), default=0))
        for i, c in enumerate(colunas)
    ]
    largura = [min(w, 34) for w in largura]  # nao deixa estourar a tela

    print("  " + " | ".join(str(c)[:w].ljust(w) for c, w in zip(colunas, largura)))
    print("  " + "-+-".join("-" * w for w in largura))
    for linha in linhas:
        print("  " + " | ".join(str(v)[:w].ljust(w) for v, w in zip(linha, largura)))
    print(f"  ({len(linhas)} linha(s))")


def executar(con: sqlite3.Connection, sql: str) -> None:
    """Executa um comando SQL e mostra o resultado (ou quantas linhas mudou)."""
    try:
        cur = con.execute(sql)
        if cur.description:          # tem colunas -> foi um SELECT
            mostrar(cur)
        else:                        # INSERT/UPDATE/DELETE
            con.commit()
            print(f"  OK. {cur.rowcount} linha(s) afetada(s).")
    except sqlite3.Error as erro:
        # O banco recusou. Isso e' bom: mostra as constraints funcionando.
        print(f"  ERRO DO BANCO: {erro}")


def comando_especial(con: sqlite3.Connection, entrada: str) -> bool:
    """Trata os atalhos que comecam com ponto. Devolve True se tratou."""
    cmd = entrada.strip().lower()

    if cmd in (".sair", ".exit", ".quit"):
        raise SystemExit(0)

    if cmd in (".tabelas", ".tables"):
        executar(con, "SELECT name FROM sqlite_master WHERE type='table' "
                      "AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return True

    if cmd == ".contar":
        print("  Registros por tabela:")
        for t in TABELAS:
            total = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"    {t:<20} {total:>6}")
        return True

    if cmd.startswith(".schema"):
        partes = entrada.split()
        alvo = partes[1] if len(partes) > 1 else None
        sql = "SELECT sql FROM sqlite_master WHERE type='table'"
        params = ()
        if alvo:
            sql += " AND name = ?"
            params = (alvo,)
        for (definicao,) in con.execute(sql, params):
            print(f"\n{definicao}\n")
        return True

    return False


def main() -> None:
    if not DB_PATH.exists():
        print(f"Banco nao encontrado em {DB_PATH}")
        print("Crie com:  python -m backend.init_db")
        return

    con = sqlite3.connect(DB_PATH)
    # Liga as foreign keys tambem aqui, para o console respeitar as mesmas
    # regras da aplicacao (a protecao ON DELETE RESTRICT vale aqui tambem).
    con.execute("PRAGMA foreign_keys=ON")

    # Modo "um comando so": python -m backend.db_shell "SELECT ..."
    if len(sys.argv) > 1:
        entrada = " ".join(sys.argv[1:])
        # os atalhos com ponto valem aqui tambem
        if not (entrada.startswith(".") and comando_especial(con, entrada)):
            if not entrada.startswith("."):
                executar(con, entrada.rstrip(";"))
        con.close()
        return

    print("=" * 66)
    print(f"Console SQL  |  {DB_PATH}")
    print("Atalhos: .tabelas  .schema <tabela>  .contar  .sair")
    print("=" * 66)
    while True:
        try:
            entrada = input("\nsql> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not entrada:
            continue
        if entrada.startswith("."):
            if comando_especial(con, entrada):
                continue
            print("  Atalho desconhecido.")
            continue
        executar(con, entrada.rstrip(";"))
    con.close()
    print("\nAte mais.")


if __name__ == "__main__":
    main()
