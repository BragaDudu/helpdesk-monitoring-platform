"""Configuracao central da aplicacao.

TUDO que pode variar entre ambientes (sua maquina, a maquina do avaliador,
um servidor de producao) mora AQUI e vem de variavel de ambiente / arquivo
.env -- nunca fica escrito no meio do codigo.

Isso resolve dois problemas de uma vez:
  1. Segredos (senha de banco) nao vao para o Git.
  2. Trocar SQLite por PostgreSQL vira uma linha de configuracao, nao um
     refactor.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# BASE_DIR = a raiz do projeto (a pasta que contem backend/, frontend/, data/)
#
# __file__ ................ backend/app/config.py
# .resolve() .............. caminho absoluto
# .parents[0] ............. backend/app
# .parents[1] ............. backend
# .parents[2] ............. RAIZ DO PROJETO  <-- e' o que queremos
#
# Calcular o caminho assim (em vez de escrever "C:/Users/Gui/...") faz o
# projeto funcionar em qualquer pasta e em qualquer sistema operacional.
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = BASE_DIR / "data"
FRONTEND_DIR: Path = BASE_DIR / "frontend"

# Garante que a pasta data/ exista antes de o SQLite tentar criar o arquivo.
# O SQLite cria o ARQUIVO sozinho, mas nao cria a PASTA.
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Todas as configuracoes da aplicacao, validadas pelo Pydantic.

    COMO FUNCIONA: ao instanciar Settings(), o pydantic-settings procura cada
    atributo abaixo (1) nas variaveis de ambiente do sistema e (2) no arquivo
    .env. Se nao achar, usa o valor padrao escrito aqui. Se achar algo do tipo
    errado (ex.: TEMPERATURE_ALERT_THRESHOLD=abc), ele DERRUBA a aplicacao na
    inicializacao com uma mensagem clara -- e' melhor falhar ao subir do que
    descobrir o erro em producao.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variaveis do .env que nao usamos
    )

    APP_NAME: str = "HelpDesk & Monitoring Platform"
    APP_VERSION: str = "1.0.0"

    # String vazia = usar o SQLite padrao (montado em DATABASE_URL_RESOLVED).
    DATABASE_URL: str = ""

    # ★ A regra de negocio mais importante do projeto vive parametrizada aqui.
    #   Acima deste valor, uma leitura gera alerta critico.
    TEMPERATURE_ALERT_THRESHOLD: float = 80.0

    # Margem de "zona de atencao": temperaturas entre
    # (limite - margem) e o limite ainda nao geram alerta, mas aparecem
    # na deteccao de anomalias como AVISO. Serve para agir ANTES de virar
    # problema -- monitoramento existe para prevenir, nao so para constatar.
    TEMPERATURE_WARNING_MARGIN: float = 10.0

    # Quantas horas sem receber leitura fazem um equipamento ser
    # considerado "sem comunicacao". Um sensor mudo tambem e' uma anomalia:
    # pode significar queda de energia, cabo solto ou aparelho queimado.
    STALE_READING_HOURS: int = 24

    # Se True, o SQLAlchemy imprime no terminal cada SQL executado.
    SQL_ECHO: bool = False

    # -----------------------------------------------------------------------
    # ★ CHAVE DE ASSINATURA DOS TOKENS
    #
    #   E' com ela que o servidor assina o cracha de login e confere se um
    #   token e' legitimo. Quem tem esta chave consegue FABRICAR um token de
    #   super administrador -- ou seja, ela vale tanto quanto todas as senhas
    #   juntas.
    #
    #   POR ISSO ela mora no .env (que esta no .gitignore) e NAO no codigo.
    #   O valor padrao abaixo serve so para o projeto subir na primeira vez.
    #
    #   TROCAR A CHAVE derruba todos os tokens emitidos -- todo mundo precisa
    #   entrar de novo. E' exatamente o que se quer num vazamento.
    # -----------------------------------------------------------------------
    SECRET_KEY: str = "troque-esta-chave-em-producao-com-um-valor-aleatorio-longo"

    # Quanto tempo o login dura antes de pedir senha de novo.
    # 480 min = 8 horas = um turno de trabalho. Curto demais irrita o
    # usuario; longo demais deixa um token roubado util por semanas.
    TOKEN_EXPIRE_MINUTES: int = 480

    @property
    def DATABASE_URL_RESOLVED(self) -> str:
        """A URL de conexao que sera realmente usada.

        Se o .env definiu DATABASE_URL, respeitamos. Senao, montamos a URL do
        SQLite apontando para <raiz>/data/app.db.

        FORMATO DA URL:  sqlite:///C:/caminho/para/data/app.db
                         ^^^^^^ dialeto (qual banco)
                                ^^^ tres barras = caminho absoluto

        Usamos .as_posix() para gerar barras normais mesmo no Windows, porque
        a URL do SQLAlchemy nao aceita barra invertida.
        """
        if self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        return f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"


# Instancia unica, importada por todo o resto do projeto:
#     from backend.app.config import settings
settings = Settings()
