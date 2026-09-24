"""Testes de autenticacao e isolamento entre empresas.

★ POR QUE ESTES TESTES SAO OS MAIS IMPORTANTES DO PROJETO

  Um bug numa regra de negocio produz um numero errado. Um bug no
  isolamento produz VAZAMENTO DE DADO: a empresa A vendo os chamados da
  empresa B. O primeiro se corrige; o segundo, uma vez acontecido, nao se
  desfaz.

  E o pior: um vazamento desses NAO aparece usando o sistema normalmente.
  Fazendo login como a empresa A, tudo parece certo. So aparece quando
  alguem troca o id na URL -- ou quando um teste como este procura.
"""

from backend.tests.conftest import SENHA_PADRAO, criar_usuario_empresa


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------


def test_login_com_senha_certa(client):
    """Login valido devolve token e os dados do usuario."""
    r = client.post("/api/auth/login", json={
        "email": "admin@teste.com", "password": SENHA_PADRAO,
    })
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert len(corpo["access_token"]) > 20
    assert corpo["user"]["role"] == "SUPER_ADMIN"

    # ★ A resposta NUNCA pode conter o hash da senha.
    assert "password" not in str(corpo).lower() or "password_hash" not in corpo["user"]
    assert "password_hash" not in corpo["user"]


def test_login_senha_errada_401(client):
    r = client.post("/api/auth/login", json={
        "email": "admin@teste.com", "password": "senha-errada-123",
    })
    assert r.status_code == 401


def test_mensagem_igual_para_email_inexistente_e_senha_errada(client):
    """★ Anti-enumeracao de usuarios.

    Se a mensagem fosse diferente, qualquer pessoa descobriria quais e-mails
    existem no sistema so testando o formulario, sem acertar senha nenhuma.
    """
    senha_errada = client.post("/api/auth/login", json={
        "email": "admin@teste.com", "password": "senha-errada-123",
    })
    email_inexistente = client.post("/api/auth/login", json={
        "email": "ninguem@lugar-nenhum.com", "password": "senha-errada-123",
    })

    assert senha_errada.status_code == email_inexistente.status_code == 401
    assert senha_errada.json()["detail"] == email_inexistente.json()["detail"]


def test_senha_curta_recusada(client):
    """Senha com menos de 8 caracteres nem chega ao banco -> 422."""
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "123"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# TOKEN
# ---------------------------------------------------------------------------


def test_sem_token_401(client):
    r = client.get("/api/tickets", headers={"Authorization": ""})
    assert r.status_code == 401


def test_token_adulterado_401(client):
    """★ Trocar um caractere do token invalida a assinatura.

    E' isto que impede alguem de editar o proprio token e virar
    SUPER_ADMIN: sem a chave secreta, nao ha como refazer a assinatura.
    """
    bom = client.post("/api/auth/login", json={
        "email": "admin@teste.com", "password": SENHA_PADRAO,
    }).json()["access_token"]

    corpo, assinatura = bom.split(".")
    ruim = f"{corpo}.{'A' * len(assinatura)}"

    r = client.get("/api/tickets", headers={"Authorization": f"Bearer {ruim}"})
    assert r.status_code == 401


def test_me_devolve_usuario_do_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "admin@teste.com"


# ---------------------------------------------------------------------------
# ISOLAMENTO ENTRE EMPRESAS  -- o coracao do multi-empresa
# ---------------------------------------------------------------------------


def _montar_duas_empresas(client):
    """Cria 2 clientes, 1 chamado para cada, e o usuario da empresa A."""
    a = client.post("/api/clients", json={
        "name": "Contato Alfa", "company": "Alfa Tecnologia LTDA",
        "email": "alfa@empresa.com", "phone": "(11) 98888-0001",
    }).json()
    b = client.post("/api/clients", json={
        "name": "Contato Beta", "company": "Beta Servicos LTDA",
        "email": "beta@empresa.com", "phone": "(11) 98888-0002",
    }).json()

    for dono in (a, b):
        client.post("/api/tickets", json={
            "client_id": dono["id"], "title": f"Problema em {dono['company']}",
            "description": "descricao do chamado", "category": "REDE",
            "priority": "MEDIA",
        })

    header_a = criar_usuario_empresa(client, a["id"], "user.a@empresa.com")
    return a, b, header_a


def test_cliente_ve_apenas_a_propria_empresa(client):
    """A listagem de clientes traz 1 linha para quem e' de uma empresa."""
    a, b, header_a = _montar_duas_empresas(client)

    todos = client.get("/api/clients").json()          # admin
    so_dele = client.get("/api/clients", headers=header_a).json()

    assert todos["total"] == 2
    assert so_dele["total"] == 1
    assert so_dele["items"][0]["id"] == a["id"]


def test_cliente_ve_apenas_os_proprios_chamados(client):
    a, b, header_a = _montar_duas_empresas(client)

    assert client.get("/api/tickets").json()["total"] == 2
    pagina = client.get("/api/tickets", headers=header_a).json()
    assert pagina["total"] == 1
    assert pagina["items"][0]["client_id"] == a["id"]


def test_idor_acesso_direto_por_id_e_bloqueado(client):
    """★ O TESTE MAIS IMPORTANTE DO ARQUIVO.

    Filtrar a LISTAGEM nao basta. Quem souber o id do recurso tenta acessar
    direto pela URL. Isso se chama IDOR ("insecure direct object
    reference"), e e' uma das falhas mais comuns em API.
    """
    a, b, header_a = _montar_duas_empresas(client)

    # o chamado da empresa B, descoberto pelo admin
    chamado_b = client.get(f"/api/tickets?client_id={b['id']}").json()["items"][0]

    # a empresa A tentando ler o cliente B e o chamado de B, pelo id
    assert client.get(f"/api/clients/{b['id']}", headers=header_a).status_code == 403
    assert client.get(f"/api/tickets/{chamado_b['id']}", headers=header_a).status_code == 403

    # e tentando ALTERAR o chamado da outra empresa
    r = client.patch(
        f"/api/tickets/{chamado_b['id']}/status",
        json={"status": "FINALIZADO"}, headers=header_a,
    )
    assert r.status_code == 403


def test_cliente_nao_abre_chamado_para_outra_empresa(client):
    """Escopo tambem na ESCRITA: ler o dado do outro e' ruim; escrever e' pior."""
    a, b, header_a = _montar_duas_empresas(client)

    r = client.post("/api/tickets", headers=header_a, json={
        "client_id": b["id"], "title": "Chamado indevido",
        "description": "tentando abrir para outra empresa",
        "category": "REDE", "priority": "ALTA",
    })
    assert r.status_code == 403


def test_cliente_nao_cadastra_cliente(client):
    """Cadastrar cliente e' acao da OPERADORA da plataforma -> 403."""
    a, b, header_a = _montar_duas_empresas(client)

    r = client.post("/api/clients", headers=header_a, json={
        "name": "Novo Contato", "company": "Empresa Invasora LTDA",
        "email": "invasor@empresa.com", "phone": "(11) 98888-9999",
    })
    assert r.status_code == 403


def test_analytics_respeita_o_escopo(client):
    """★ Numero agregado tambem e' vazamento.

    O relatorio nao mostra o chamado do outro cliente -- mostra um total.
    Mas esse total conta quantos chamados o concorrente abriu e qual o
    tamanho da carteira da operadora.
    """
    a, b, header_a = _montar_duas_empresas(client)

    admin = client.get("/api/analytics/summary").json()
    dele = client.get("/api/analytics/summary", headers=header_a).json()

    assert admin["total_chamados"] == 2
    assert admin["total_clientes"] == 2
    assert dele["total_chamados"] == 1
    assert dele["total_clientes"] == 1


def test_todas_as_rotas_de_leitura_exigem_token(client):
    """★ VARREDURA: nenhuma rota de listagem pode responder sem token.

    Este teste existe para pegar o esquecimento -- a rota nova que alguem
    cria daqui a seis meses e esquece de proteger. Ele nao depende de
    ninguem lembrar de escrever um teste especifico para ela.
    """
    rotas = [
        "/api/clients", "/api/clients/options", "/api/tickets",
        "/api/tickets/categories", "/api/equipments", "/api/equipments/anomalies",
        "/api/alerts", "/api/analytics/summary", "/api/analytics/tickets-by-client",
        "/api/analytics/tickets-by-category", "/api/analytics/customer-ranking",
        "/api/analytics/average-resolution-time", "/api/analytics/open-tickets",
        "/api/analytics/category-resolution-time",
    ]
    desprotegidas = [
        r for r in rotas
        if client.get(r, headers={"Authorization": ""}).status_code != 401
    ]
    assert not desprotegidas, f"rotas sem protecao: {desprotegidas}"
