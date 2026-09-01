"""Testes de Clientes e Chamados (Exercicio 1).

Cada funcao test_* e' um caso. O padrao e' sempre: faz a requisicao, depois
'assert' no status HTTP e no corpo. Se um assert falhar, o pytest mostra
exatamente o que era esperado e o que veio.
"""


# --- CLIENTES ---------------------------------------------------------------


def test_criar_cliente(client):
    """(1) Criar cliente -> 201 e o banco gera id e created_at."""
    r = client.post("/api/clients", json={
        "name": "Ana", "company": "Alfa", "email": "ana@alfa.com",
        "phone": "(11) 98888-7777",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["id"] > 0
    assert body["company"] == "Alfa"
    assert body["created_at"].endswith("Z")  # UTC na saida


def test_buscar_cliente(client, sample_client):
    """(2) Buscar cliente existente -> 200."""
    r = client.get(f"/api/clients/{sample_client['id']}")
    assert r.status_code == 200
    assert r.json()["email"] == "teste@empresa.com"


def test_buscar_cliente_inexistente_404(client):
    """Cliente que nao existe -> 404 com formato de erro padrao."""
    r = client.get("/api/clients/9999")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


def test_email_duplicado_409(client, sample_client):
    """E-mail repetido -> 409 (garantido pela constraint UNIQUE)."""
    r = client.post("/api/clients", json={
        "name": "Outro", "company": "XPTO", "email": "teste@empresa.com",
        "phone": "(11) 91111-2222",
    })
    assert r.status_code == 409


def test_email_invalido_422(client):
    """E-mail sem formato valido -> 422 (barrado pelo Pydantic)."""
    r = client.post("/api/clients", json={
        "name": "X", "company": "Y", "email": "nao-eh-email", "phone": "(11) 98888-7777",
    })
    assert r.status_code == 422


def test_nome_vazio_422(client):
    """Nome so com espacos -> 422 (strip_whitespace)."""
    r = client.post("/api/clients", json={
        "name": "   ", "company": "ACME", "email": "a@b.com", "phone": "(11) 98888-7777",
    })
    assert r.status_code == 422


def test_excluir_cliente_com_chamado_409(client, sample_client):
    """Excluir cliente que tem chamado -> 409 (nao apaga historico)."""
    client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Problema", "description": "Descricao do problema",
        "category": "Rede", "priority": "ALTA",
    })
    r = client.delete(f"/api/clients/{sample_client['id']}")
    assert r.status_code == 409


# --- CHAMADOS ---------------------------------------------------------------


def test_criar_chamado(client, sample_client):
    """(3) Abrir chamado -> 201, nasce ABERTO, sem closed_at."""
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Servidor caiu",
        "description": "O servidor de arquivos parou.", "category": "Infra", "priority": "ALTA",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "ABERTO"       # servidor define
    assert body["closed_at"] is None        # ainda aberto
    assert body["client"]["company"] == "Empresa Teste LTDA"  # veio do JOIN


def test_chamado_para_cliente_inexistente_404(client):
    """Chamado apontando para cliente que nao existe -> 404."""
    r = client.post("/api/tickets", json={
        "client_id": 9999, "title": "abc", "description": "descricao valida",
        "category": "Rede", "priority": "ALTA",
    })
    assert r.status_code == 404


def test_prioridade_invalida_422(client, sample_client):
    """Prioridade fora do Enum -> 422."""
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "abc", "description": "descricao valida",
        "category": "Rede", "priority": "URGENTE",
    })
    assert r.status_code == 422


def test_listar_chamados_de_cliente(client, sample_client):
    """(4) Consultar chamados de um cliente -> 200 com a lista dele."""
    for i in range(3):
        client.post("/api/tickets", json={
            "client_id": sample_client["id"], "title": f"Chamado {i}",
            "description": "descricao do chamado", "category": "Rede", "priority": "MEDIA",
        })
    r = client.get(f"/api/clients/{sample_client['id']}/tickets")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_filtrar_chamados_por_status(client, sample_client):
    """Filtro por status roda no banco e devolve so o que bate."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "Rede", "priority": "MEDIA",
    }).json()
    client.patch(f"/api/tickets/{t['id']}/status", json={"status": "EM_ANDAMENTO"})

    assert len(client.get("/api/tickets?status=EM_ANDAMENTO").json()) == 1
    assert len(client.get("/api/tickets?status=FINALIZADO").json()) == 0


# --- MAQUINA DE ESTADOS -----------------------------------------------------


def test_alterar_status_carimba_closed_at(client, sample_client):
    """(5) Alterar status para FINALIZADO -> closed_at e' preenchido."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "Rede", "priority": "MEDIA",
    }).json()
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "FINALIZADO"})
    assert r.status_code == 200
    assert r.json()["closed_at"] is not None


def test_transicao_invalida_409(client, sample_client):
    """FINALIZADO nao volta para ABERTO -> 409 (regra de transicao)."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "Rede", "priority": "MEDIA",
    }).json()
    client.patch(f"/api/tickets/{t['id']}/status", json={"status": "FINALIZADO"})
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "ABERTO"})
    assert r.status_code == 409


def test_status_inexistente_422(client, sample_client):
    """Status que nao existe -> 422 (Enum barra antes do service)."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "Rede", "priority": "MEDIA",
    }).json()
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "CANCELADO"})
    assert r.status_code == 422


def test_status_idempotente(client, sample_client):
    """Repetir o mesmo status -> 200, sem erro (PATCH idempotente)."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "Rede", "priority": "MEDIA",
    }).json()
    client.patch(f"/api/tickets/{t['id']}/status", json={"status": "EM_ANDAMENTO"})
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "EM_ANDAMENTO"})
    assert r.status_code == 200
