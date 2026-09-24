"""Senha e token -- a parte do sistema que NAO pode ter atalho.

★ DECISAO: TUDO AQUI USA SO A BIBLIOTECA PADRAO DO PYTHON.

  Nao instalamos passlib, bcrypt nem python-jose. Dois motivos:

    1. Voce precisa conseguir explicar cada linha. Codigo de seguranca que
       voce nao entende e' pior do que codigo simples que voce domina --
       porque voce nao sabe quando ele esta configurado errado.

    2. hashlib e hmac fazem parte do Python desde sempre, sao mantidos pelo
       core da linguagem e implementam os algoritmos certos.

  O QUE ISSO **NAO** SIGNIFICA: nao significa que inventamos criptografia.
  Usamos PBKDF2-HMAC-SHA256 e HMAC-SHA256, que sao padroes publicos.
  Inventar algoritmo proprio seria o erro classico; usar os padroes da
  biblioteca padrao e' o caminho correto.

  EM PRODUCAO DE VERDADE, o que eu trocaria: PBKDF2 por Argon2id (mais
  resistente a ataque com placa de video) e o token proprio por JWT com
  uma biblioteca testada. Nao troquei aqui porque cada uma seria mais uma
  dependencia para explicar, e o mecanismo e' o mesmo.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

from backend.app.config import settings

# ---------------------------------------------------------------------------
# SENHA
# ---------------------------------------------------------------------------
# ★ A REGRA NUMERO UM: NUNCA guardar a senha.
#
#   Guardamos um HASH -- um resumo irreversivel. Dela sai o hash; do hash
#   nao sai ela. Se o banco vazar, o atacante leva os hashes e nao as senhas.
#
# ★ POR QUE NAO UM SHA256 SIMPLES:
#
#   SHA256 foi feito para ser RAPIDO. Uma placa de video testa bilhoes de
#   senhas por segundo contra um hash SHA256 -- as senhas comuns caem em
#   minutos.
#
#   PBKDF2 e' o mesmo SHA256 repetido 240.000 vezes de proposito. Fica
#   LENTO na medida certa: ~0,1s para voce fazer login uma vez (imperceptivel)
#   e 240.000 vezes mais caro para quem tenta bilhoes de tentativas.
#   Isso se chama "key stretching".
#
# ★ POR QUE O SALT:
#
#   Salt e' um valor aleatorio, diferente para CADA usuario, guardado junto
#   com o hash. Sem ele, dois usuarios com a senha "123456" teriam hashes
#   IGUAIS -- e o atacante quebraria os dois de uma vez, ou usaria uma
#   tabela pronta (rainbow table). Com salt, cada senha precisa ser atacada
#   individualmente, e tabelas prontas nao servem para nada.
# ---------------------------------------------------------------------------

_ALGORITMO = "pbkdf2_sha256"
_ITERACOES = 240_000


def hash_senha(senha: str) -> str:
    """Transforma a senha em texto guardavel no banco.

    FORMATO GRAVADO (tudo numa string so, separado por $):

        pbkdf2_sha256$240000$<salt em hex>$<hash em hex>

    Guardar o algoritmo e o numero de iteracoes JUNTO com o hash e' o que
    permite trocar os parametros no futuro sem invalidar as senhas antigas:
    ao conferir, lemos daqui como aquele hash foi feito.
    """
    salt = secrets.token_bytes(16)  # aleatorio criptografico, nao random comum
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, _ITERACOES)
    return f"{_ALGORITMO}${_ITERACOES}${salt.hex()}${derivado.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    """Confere a senha digitada contra o hash guardado.

    ★ hmac.compare_digest E NAO ==

      Comparar strings com == para na primeira letra diferente. Isso vaza
      informacao pelo TEMPO: uma senha errada no primeiro caractere e'
      recusada mais rapido que uma errada no ultimo. Medindo esses
      microssegundos, da' para descobrir o hash caractere a caractere --
      chama-se "timing attack".

      compare_digest gasta SEMPRE o mesmo tempo, acerte ou erre.
    """
    try:
        algoritmo, iteracoes, salt_hex, hash_hex = guardado.split("$")
    except (ValueError, AttributeError):
        return False  # hash corrompido ou formato desconhecido

    if algoritmo != _ALGORITMO:
        return False

    derivado = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), bytes.fromhex(salt_hex), int(iteracoes)
    )
    return hmac.compare_digest(derivado.hex(), hash_hex)


# ---------------------------------------------------------------------------
# TOKEN
# ---------------------------------------------------------------------------
# O PROBLEMA QUE O TOKEN RESOLVE: o HTTP nao tem memoria. Cada requisicao
# chega "limpa", sem saber quem a mandou. Se nao houvesse token, o navegador
# teria que reenviar e-mail e senha em TODA requisicao -- e a senha ficaria
# guardada no navegador o tempo todo.
#
# COMO FUNCIONA (e' a mesma ideia do JWT):
#
#   1. Voce faz login uma vez com e-mail e senha.
#   2. O servidor devolve um cracha ASSINADO dizendo "este e' o usuario 7,
#      papel ADMIN_EMPRESA, empresa 3, valido ate as 18h".
#   3. Toda requisicao seguinte manda o cracha no cabecalho Authorization.
#   4. O servidor confere a ASSINATURA. Se bate, confia no conteudo.
#
# ★ O PONTO QUE MAIS CAI EM PERGUNTA: O TOKEN NAO E' CRIPTOGRAFADO.
#
#   Qualquer um consegue LER o conteudo dele (e' base64, nao segredo).
#   Isso e' esperado -- nao ha nada secreto ali, so o id e o papel.
#
#   O que o token garante nao e' sigilo, e' INTEGRIDADE: ninguem consegue
#   ALTERAR o papel de ADMIN_EMPRESA para SUPER_ADMIN, porque nao tem a
#   chave secreta para refazer a assinatura. Trocar um caractere invalida
#   o token inteiro.
#
#   Por isso: NUNCA coloque senha ou dado sensivel dentro de um token.
# ---------------------------------------------------------------------------


def _assinar(mensagem: bytes) -> str:
    """Gera a assinatura HMAC-SHA256 da mensagem usando a chave secreta."""
    assinatura = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), mensagem, hashlib.sha256
    ).digest()
    return _b64(assinatura)


def _b64(dados: bytes) -> str:
    """base64 no formato 'urlsafe sem =' -- para o token caber numa URL."""
    return base64.urlsafe_b64encode(dados).decode("ascii").rstrip("=")


def _desb64(texto: str) -> bytes:
    """Desfaz _b64, recolocando o preenchimento '=' que foi retirado."""
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def criar_token(user_id: int, role: str, client_id: int | None) -> str:
    """Cria o cracha assinado do usuario.

    RETORNA algo como:  eyJzdWIiOjcsInJvbGUiOi4uLn0.KJ8xY2...
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^
                        o conteudo (legivel)       a assinatura
    """
    agora = int(time.time())
    conteudo = {
        "sub": user_id,                 # de quem e' o token
        "role": role,                   # o que ele pode fazer
        "client_id": client_id,         # de qual empresa ele enxerga os dados
        "iat": agora,                   # emitido em
        "exp": agora + settings.TOKEN_EXPIRE_MINUTES * 60,  # expira em
    }
    corpo = _b64(json.dumps(conteudo, separators=(",", ":")).encode("utf-8"))
    return f"{corpo}.{_assinar(corpo.encode('ascii'))}"


def ler_token(token: str) -> dict | None:
    """Confere a assinatura e a validade. Devolve o conteudo ou None.

    DEVOLVE None (e nao levanta erro) porque, do ponto de vista de quem
    chama, "token invalido", "token expirado" e "token adulterado" levam
    todos ao mesmo lugar: HTTP 401. Detalhar QUAL foi o problema so ajuda
    quem esta tentando atacar.
    """
    try:
        corpo, assinatura = token.split(".")
    except (ValueError, AttributeError):
        return None

    # 1) A assinatura confere? (de novo, comparacao em tempo constante)
    if not hmac.compare_digest(_assinar(corpo.encode("ascii")), assinatura):
        return None

    # 2) O conteudo e' um JSON valido?
    try:
        conteudo = json.loads(_desb64(corpo))
    except (ValueError, json.JSONDecodeError):
        return None

    # 3) Ainda esta no prazo?
    if int(conteudo.get("exp", 0)) < int(time.time()):
        return None

    return conteudo
