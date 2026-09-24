"""Erros de DOMINIO -- os erros da regra de negocio.

A IDEIA CENTRAL (e um dos melhores pontos para defender na banca):

    O service NAO SABE que existe HTTP.

    Quando o ticket_service percebe que o cliente 999 nao existe, ele levanta
    NotFoundError("Cliente", 999). Ele nao levanta HTTPException(404), porque
    "404" e' um conceito da web, e o service precisa continuar funcionando se
    amanha for chamado por um script de linha de comando, por uma fila de
    mensagens ou por um teste automatizado.

    Quem traduz erro de dominio -> codigo HTTP e' um unico exception handler
    registrado no main.py. Um lugar so.

FLUXO:
    service levanta NotFoundError
        -> handler no main.py captura
        -> devolve JSON {"error": "...", "detail": "..."} com status 404
        -> o frontend le a mensagem e mostra num toast
"""


class DomainError(Exception):
    """Classe base de todos os erros de negocio do projeto.

    Existe para que o main.py possa registrar handlers por TIPO e para que
    qualquer erro novo herde o comportamento padrao automaticamente.
    """

    status_code: int = 400
    error_code: str = "domain_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """Recurso pedido nao existe.  ->  HTTP 404 Not Found

    Exemplos de uso:
        NotFoundError("Cliente", 999)
        NotFoundError("Equipamento", 42)
    """

    status_code = 404
    error_code = "not_found"

    def __init__(self, resource: str, resource_id: object) -> None:
        super().__init__(f"{resource} com id {resource_id} nao foi encontrado.")
        self.resource = resource
        self.resource_id = resource_id


class ConflictError(DomainError):
    """A operacao conflita com o estado atual dos dados.  ->  HTTP 409 Conflict

    Usado em tres situacoes neste projeto:
        - e-mail de cliente ja cadastrado (coluna UNIQUE)
        - identificador de equipamento ja cadastrado (coluna UNIQUE)
        - tentar apagar um cliente que ainda possui chamados/equipamentos
    """

    status_code = 409
    error_code = "conflict"


class BusinessRuleError(DomainError):
    """A requisicao e' bem formada, mas viola uma regra do negocio.
    ->  HTTP 409 Conflict

    O caso principal: tentar mudar o status de um chamado FINALIZADO.
    Os dados enviados sao validos (FINALIZADO -> ABERTO sao dois status
    reais), o que nao e' valido e' a TRANSICAO. Por isso nao e' 422
    (formato invalido) e sim 409 (conflito com o estado atual).
    """

    status_code = 409
    error_code = "business_rule_violation"


class UnauthorizedError(DomainError):
    """Nao sabemos quem e' voce.  ->  HTTP 401 Unauthorized

    Token ausente, mal formado, expirado, adulterado, ou de um usuario que
    foi desativado. TODOS devolvem a mesma mensagem generica.

    ★ POR QUE A MENSAGEM E' SEMPRE IGUAL: se dissesse "usuario nao existe"
      num caso e "senha incorreta" no outro, um atacante descobriria quais
      e-mails estao cadastrados so testando o formulario de login. Isso se
      chama "user enumeration" e e' o vazamento mais comum em tela de login.

    NOME CONFUSO DO PADRAO HTTP: 401 se chama "Unauthorized", mas significa
    NAO AUTENTICADO. Quem esta autenticado e nao tem permissao leva 403.
    """

    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(DomainError):
    """Sabemos quem e' voce, e voce nao pode.  ->  HTTP 403 Forbidden

    Diferente do 401: fazer login de novo NAO resolve. O papel do usuario
    simplesmente nao permite aquela acao.

    Usado quando um ADMIN_EMPRESA tenta cadastrar cliente, ou tenta acessar
    um recurso de outra empresa.
    """

    status_code = 403
    error_code = "forbidden"
