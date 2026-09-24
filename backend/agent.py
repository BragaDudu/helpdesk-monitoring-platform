"""AGENTE COLETOR -- o "sensor" que mede os equipamentos sozinho.

===========================================================================
 O PROBLEMA QUE ESTE ARQUIVO RESOLVE
===========================================================================

Ate agora, uma leitura de temperatura so entrava no sistema se ALGUEM
digitasse na tela. Isso nao se sustenta como negocio: ninguem vai contratar
uma pessoa para ir de sala em sala anotar a temperatura de 900 servidores,
todo dia, para sempre.

E o efeito de nao ter coleta automatica e' MEDIVEL: com STALE_READING_HOURS
em 24, todo equipamento que passa um dia sem leitura vira anomalia
"SEM_COMUNICACAO". Sem este agente, o painel do cliente amanhece com
centenas de alarmes falsos -- e um painel que grita o tempo todo e' um
painel que ninguem olha.

===========================================================================
 ★ O QUE ESTE AGENTE E', E O QUE ELE NAO E'
===========================================================================

ELE E': um programa separado, que roda fora da aplicacao web, autentica na
API como qualquer outro cliente e envia leituras periodicamente.

ELE NAO E': parte do servidor. Repare que ele NAO importa o
monitoring_service nem toca no banco. Ele fala HTTP, exatamente como o
navegador -- so que sem navegador nenhum.

★ E E' AQUI QUE O PROJETO INTEIRO SE JUSTIFICA:

  Voce ja dizia na apresentacao que "a regra dos 80 graus esta no backend
  porque um sensor chamaria a API sem navegador". Este arquivo E' esse
  sensor. Ele prova a frase em vez de so afirma-la.

  Se a regra estivesse no JavaScript da pagina, este agente enviaria 95
  graus e NENHUM alerta nasceria -- porque nao ha JavaScript rodando aqui.

===========================================================================
 EM PRODUCAO, O QUE MUDA
===========================================================================

Num cliente real, este programa rodaria DENTRO da empresa dele, num
computador da rede, lendo os sensores de verdade (IPMI, SNMP, um sensor
USB). A unica linha que mudaria e' a que gera a temperatura: em vez de
simular, leria o hardware.

Todo o resto -- autenticar, montar o pacote, tratar erro, tentar de novo
quando a rede cair -- ja esta pronto aqui e continuaria igual. Por isso a
simulacao fica isolada numa funcao so (`medir_temperatura`).

===========================================================================
 COMO USAR
===========================================================================

    python -m backend.agent                     # ciclo a cada 60s
    python -m backend.agent --intervalo 10      # mais rapido, para demonstrar
    python -m backend.agent --uma-vez           # roda UM ciclo e sai
    python -m backend.agent --lote 200          # quantos equipamentos por ciclo

Ou duplo clique em COLETOR.bat.
"""

import argparse
import random
import sys
import time
import urllib.error
import urllib.request
import json

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------
# O agente fala com a API pela REDE, entao so precisa da URL e de credenciais.
# Ele nao sabe onde fica o banco, e nem deveria.
#
# ★★★ POR QUE 127.0.0.1 E NAO "localhost" -- MEDIDO, NAO ACHISMO ★★★
#
#   Trocando so essa palavra, o tempo de cada requisicao caiu de 2.041 ms
#   para 5 ms. Quatrocentas vezes mais rapido. O motivo:
#
#     "localhost" e' um NOME, e precisa ser traduzido para um endereco.
#     No Windows ele traduz para DOIS: ::1 (IPv6) e 127.0.0.1 (IPv4),
#     e o IPv6 vem primeiro na fila.
#
#     O servidor (uvicorn) esta escutando so em IPv4. Entao o Python tenta
#     o ::1, espera dar tempo limite (~2 segundos), e SO ENTAO tenta o
#     IPv4 -- que funciona. Dois segundos jogados fora em toda requisicao.
#
#     "127.0.0.1" ja E' o endereco IPv4. Nao ha nome para traduzir, nao ha
#     tentativa errada, nao ha espera.
#
#   POR QUE O NAVEGADOR NAO SOFRE COM ISSO: navegadores usam uma tecnica
#   chamada "Happy Eyeballs" -- disparam IPv4 e IPv6 ao mesmo tempo e ficam
#   com quem responder primeiro. O urllib do Python nao faz isso; ele tenta
#   em ordem.
#
#   ★ LICAO GERAL: quando algo esta lento de forma CONSTANTE (todas as
#     chamadas com exatamente o mesmo tempo), o problema quase nunca e' a
#     consulta -- e' conexao, tempo limite ou espera. Consulta lenta varia
#     conforme o volume de dados; espera de rede e' sempre igual.
API = "http://127.0.0.1:8010/api"

# ★ EM PRODUCAO ISTO VIRIA DE VARIAVEL DE AMBIENTE, nunca escrito no codigo.
#   Aqui esta fixo porque e' o usuario de demonstracao, criado pelo seed.
#   O certo seria uma conta de servico com permissao SO de enviar leitura --
#   este admin pode fazer tudo, e um agente que roda sozinho na rede do
#   cliente nao deveria ter esse poder. Fica anotado como proximo passo.
EMAIL = "admin@helpdesk.com.br"
SENHA = "admin12345"

rng = random.Random()


# ---------------------------------------------------------------------------
# COMUNICACAO COM A API
# ---------------------------------------------------------------------------
# Usamos urllib (biblioteca padrao) em vez de requests para o agente nao
# precisar de nenhuma dependencia instalada. Ele tem que rodar numa maquina
# qualquer do cliente, com o Python mais pelado possivel.
# ---------------------------------------------------------------------------


def _chamar(metodo: str, caminho: str, corpo=None, token=None):
    """Faz uma requisicao HTTP e devolve o JSON da resposta."""
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(f"{API}{caminho}", data=dados, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        # O MESMO cabecalho que o navegador manda. Para a API, este agente
        # e' apenas mais um cliente autenticado.
        req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=15) as resp:
        texto = resp.read().decode("utf-8")
        return json.loads(texto) if texto else None


def entrar() -> str:
    """Autentica e devolve o token."""
    resposta = _chamar("POST", "/auth/login", {"email": EMAIL, "password": SENHA})
    return resposta["access_token"]


# ---------------------------------------------------------------------------
# A "MEDICAO"
# ---------------------------------------------------------------------------


def medir_temperatura(equipamento: dict) -> float:
    """★ A UNICA FUNCAO QUE MUDARIA NUM SENSOR DE VERDADE.

    Hoje ela INVENTA um numero plausivel. Num equipamento real, aqui
    haveria uma leitura de hardware -- e o resto do agente continuaria
    exatamente igual.

    COMO A SIMULACAO FUNCIONA: partimos da ultima temperatura conhecida e
    variamos pouco (+-2 graus). Isso produz uma curva CONTINUA, como um
    equipamento de verdade -- em vez de numeros aleatorios pulando de 40
    para 90, que nao enganariam ninguem num grafico.

    Uma vez a cada ~40 leituras forcamos um pico. Sem isso, o sistema
    ficaria sem alertas novos e a tela de monitoramento nunca teria o que
    mostrar durante a demonstracao.
    """
    anterior = equipamento.get("last_temperature")
    if anterior is None:
        # Primeira leitura deste equipamento: comeca numa faixa normal.
        return round(rng.uniform(38, 52), 1)

    # Passeio aleatorio ("random walk"): pequena variacao sobre o valor anterior.
    nova = anterior + rng.uniform(-2.0, 2.0)

    if rng.random() < 0.025:          # ~2,5% das leituras: um pico
        nova = rng.uniform(81, 95)
    elif nova > 78:                    # tende a esfriar depois de esquentar
        nova -= rng.uniform(2, 6)

    # Limites fisicos: nenhum servidor opera a -10 ou a 200 graus.
    return round(max(20.0, min(99.0, nova)), 1)


# ---------------------------------------------------------------------------
# O CICLO
# ---------------------------------------------------------------------------


def um_ciclo(token: str, tamanho_lote: int) -> tuple[int, int]:
    """Le um lote de equipamentos e envia uma leitura para cada.

    ★ POR QUE EM LOTE, E NAO TODOS DE UMA VEZ:
      com 900 equipamentos, mandar 900 requisicoes de uma vez a cada ciclo
      castigaria o servidor sem necessidade. Sensores reais tambem nao
      reportam todos no mesmo instante -- cada um tem seu proprio relogio.
      O lote rotativo imita isso e distribui a carga.

    RETORNA: (leituras enviadas, alertas gerados)
    """
    pagina = _chamar("GET", f"/equipments?limit=100", token=token)
    total = pagina["total"]

    # Sorteia de onde comecar: assim, ao longo de varios ciclos, todos os
    # equipamentos acabam sendo lidos.
    inicio = rng.randrange(0, max(1, total - tamanho_lote + 1))

    equipamentos = []
    while len(equipamentos) < tamanho_lote:
        faltam = min(100, tamanho_lote - len(equipamentos))
        p = _chamar(
            "GET",
            f"/equipments?limit={faltam}&offset={inicio + len(equipamentos)}",
            token=token,
        )
        if not p["items"]:
            break
        equipamentos.extend(p["items"])

    enviadas = alertas = 0
    for eq in equipamentos:
        # Equipamento em manutencao nao reporta -- esta desligado da tomada.
        if eq["status"] == "MANUTENCAO":
            continue

        try:
            resultado = _chamar(
                "POST",
                f"/equipments/{eq['id']}/readings",
                {"temperature": medir_temperatura(eq), "status": eq["status"]},
                token=token,
            )
            enviadas += 1
            if resultado.get("critical_condition_detected"):
                alertas += 1
                print(
                    f"    ALERTA  {eq['identifier']} "
                    f"{resultado['reading']['temperature']} C  "
                    f"({eq['client']['company']})"
                )
        except urllib.error.HTTPError as erro:
            # ★ UM EQUIPAMENTO COM PROBLEMA NAO PODE DERRUBAR O AGENTE.
            #   Se o equipamento foi apagado (404) ou a leitura foi recusada
            #   (422), registramos e seguimos para o proximo. Um coletor que
            #   morre no primeiro erro deixa de coletar TODO o resto.
            print(f"    erro em {eq['identifier']}: HTTP {erro.code}")

    return enviadas, alertas


def rodar(intervalo: int, tamanho_lote: int, uma_vez: bool) -> None:
    """Laco principal do agente."""
    print("=" * 68)
    print("  AGENTE COLETOR DE TEMPERATURA")
    print(f"  API: {API}")
    print(f"  Ciclo: a cada {intervalo}s  |  Lote: {tamanho_lote} equipamentos")
    print("  (Ctrl+C para parar)")
    print("=" * 68)

    try:
        token = entrar()
        print(f"  Autenticado como {EMAIL}\n")
    except Exception as erro:
        print(f"  FALHA AO AUTENTICAR: {erro}")
        print("  O servidor esta no ar? (INICIAR.bat)")
        sys.exit(1)

    ciclo = 0
    while True:
        ciclo += 1
        inicio = time.perf_counter()
        try:
            enviadas, alertas = um_ciclo(token, tamanho_lote)
            duracao = time.perf_counter() - inicio
            print(
                f"  ciclo {ciclo:>4}  |  {enviadas:>4} leituras  |  "
                f"{alertas:>3} alertas  |  {duracao:.1f}s"
            )
        except urllib.error.HTTPError as erro:
            if erro.code == 401:
                # ★ O TOKEN EXPIROU (8 horas). Um agente que roda por
                #   semanas PRECISA se reautenticar sozinho -- senao pararia
                #   silenciosamente na primeira madrugada.
                print("  token expirou, autenticando de novo...")
                token = entrar()
                continue
            print(f"  erro HTTP {erro.code}")
        except Exception as erro:
            # Rede caiu, servidor reiniciou: espera e tenta de novo.
            # Coletor bom e' coletor que sobrevive a queda do servidor.
            print(f"  erro: {erro} -- tentando de novo no proximo ciclo")

        if uma_vez:
            break
        time.sleep(intervalo)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="python -m backend.agent",
        description="Simula sensores enviando leituras de temperatura para a API.",
    )
    parser.add_argument("--intervalo", type=int, default=60,
                        help="segundos entre ciclos (padrao: 60)")
    parser.add_argument("--lote", type=int, default=150,
                        help="equipamentos lidos por ciclo (padrao: 150)")
    parser.add_argument("--uma-vez", action="store_true",
                        help="roda um ciclo so e encerra")
    args = parser.parse_args()

    try:
        rodar(args.intervalo, args.lote, args.uma_vez)
    except KeyboardInterrupt:
        print("\n  Agente encerrado.")
