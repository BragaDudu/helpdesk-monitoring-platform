"""Testes de Clientes e Chamados (Exercicio 1).

Cada funcao test_* e' um caso. O padrao e' sempre: faz a requisicao, depois
'assert' no status HTTP e no corpo. Se um assert falhar, o pytest mostra
exatamente o que era esperado e o que veio.
"""


# --- CLIENTES ---------------------------------------------------------------


def test_criar_cliente(client):
    """(1) Criar cliente -> 201 e o banco gera id e created_at."""
    r = client.post("/api/clients", json={
        "name": "Ana Ribeiro", "company": "Alfa Tecnologia LTDA", "email": "ana@alfa.com",
        "phone": "(11) 98888-7777",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["id"] > 0
    assert body["company"] == "Alfa Tecnologia LTDA"
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
        "name": "Outro Contato", "company": "XPTO Servicos LTDA", "email": "teste@empresa.com",
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
        "name": "   ", "company": "ACME Servicos LTDA", "email": "a@b.com", "phone": "(11) 98888-7777",
    })
    assert r.status_code == 422


def test_excluir_cliente_com_chamado_409(client, sample_client):
    """Excluir cliente que tem chamado -> 409 (nao apaga historico)."""
    client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Problema", "description": "Descricao do problema",
        "category": "REDE", "priority": "ALTA",
    })
    r = client.delete(f"/api/clients/{sample_client['id']}")
    assert r.status_code == 409


# --- CHAMADOS ---------------------------------------------------------------


def test_criar_chamado(client, sample_client):
    """(3) Abrir chamado -> 201, nasce ABERTO, sem closed_at."""
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Servidor caiu",
        "description": "O servidor de arquivos parou.", "category": "INFRAESTRUTURA", "priority": "ALTA",
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
        "category": "REDE", "priority": "ALTA",
    })
    assert r.status_code == 404


def test_prioridade_invalida_422(client, sample_client):
    """Prioridade fora do Enum -> 422."""
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "abc", "description": "descricao valida",
        "category": "REDE", "priority": "URGENTE",
    })
    assert r.status_code == 422


def test_listar_chamados_de_cliente(client, sample_client):
    """(4) Consultar chamados de um cliente -> 200 com a lista dele."""
    for i in range(3):
        client.post("/api/tickets", json={
            "client_id": sample_client["id"], "title": f"Chamado {i}",
            "description": "descricao do chamado", "category": "REDE", "priority": "MEDIA",
        })
    r = client.get(f"/api/clients/{sample_client['id']}/tickets")
    assert r.status_code == 200
    # A listagem agora vem paginada: {items, total, limit, offset, has_more}
    pagina = r.json()
    assert len(pagina["items"]) == 3
    assert pagina["total"] == 3
    assert pagina["has_more"] is False


def test_filtrar_chamados_por_status(client, sample_client):
    """Filtro por status roda no banco e devolve so o que bate."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "REDE", "priority": "MEDIA",
    }).json()
    client.patch(f"/api/tickets/{t['id']}/status", json={"status": "EM_ANDAMENTO"})

    assert client.get("/api/tickets?status=EM_ANDAMENTO").json()["total"] == 1
    assert client.get("/api/tickets?status=FINALIZADO").json()["total"] == 0


# --- MAQUINA DE ESTADOS -----------------------------------------------------


def test_alterar_status_carimba_closed_at(client, sample_client):
    """(5) Alterar status para FINALIZADO -> closed_at e' preenchido."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "REDE", "priority": "MEDIA",
    }).json()
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "FINALIZADO"})
    assert r.status_code == 200
    assert r.json()["closed_at"] is not None


def test_transicao_invalida_409(client, sample_client):
    """FINALIZADO nao volta para ABERTO -> 409 (regra de transicao)."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "REDE", "priority": "MEDIA",
    }).json()
    client.patch(f"/api/tickets/{t['id']}/status", json={"status": "FINALIZADO"})
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "ABERTO"})
    assert r.status_code == 409


def test_status_inexistente_422(client, sample_client):
    """Status que nao existe -> 422 (Enum barra antes do service)."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "REDE", "priority": "MEDIA",
    }).json()
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "CANCELADO"})
    assert r.status_code == 422


def test_status_idempotente(client, sample_client):
    """Repetir o mesmo status -> 200, sem erro (PATCH idempotente)."""
    t = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Teste", "description": "descricao",
        "category": "REDE", "priority": "MEDIA",
    }).json()
    client.patch(f"/api/tickets/{t['id']}/status", json={"status": "EM_ANDAMENTO"})
    r = client.patch(f"/api/tickets/{t['id']}/status", json={"status": "EM_ANDAMENTO"})
    assert r.status_code == 200


# --- CATEGORIA E SUBCATEGORIA -----------------------------------------------
# Estes testes cobrem a mudanca de category: era String(40) livre, virou Enum
# com subcategoria encadeada. Sao a rede de seguranca da regra "a subcategoria
# precisa pertencer a categoria".


def test_categoria_invalida_422(client, sample_client):
    """Categoria fora do enum e' recusada antes de chegar ao banco."""
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Problema",
        "description": "Descricao do problema",
        "category": "BANANA", "priority": "ALTA",
    })
    assert r.status_code == 422


def test_subcategoria_valida_201(client, sample_client):
    """Subcategoria que pertence a categoria e' aceita e volta na resposta."""
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Fonte pifou",
        "description": "A fonte do servidor queimou.",
        "category": "HARDWARE", "subcategory": "Fonte queimada",
        "priority": "ALTA",
    })
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["subcategory"] == "Fonte queimada"
    # O rotulo legivel e' calculado pelo backend, nao guardado no banco.
    assert corpo["category_label"] == "Hardware"


def test_subcategoria_de_outra_categoria_422(client, sample_client):
    """'Fonte queimada' existe em HARDWARE, nao em TELEFONIA -> 422.

    ★ E' a validacao que depende de DOIS campos ao mesmo tempo. Nenhum dos
      dois esta errado sozinho: o erro esta na COMBINACAO.
    """
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Ramal mudo",
        "description": "O ramal nao tem audio.",
        "category": "TELEFONIA", "subcategory": "Fonte queimada",
        "priority": "MEDIA",
    })
    assert r.status_code == 422
    assert "nao e' uma subcategoria" in r.json()["detail"]


def test_subcategoria_opcional_201(client, sample_client):
    """Chamado sem subcategoria continua valido -- o campo e' opcional."""
    r = client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Rede lenta",
        "description": "A rede esta lenta desde ontem.",
        "category": "REDE", "priority": "BAIXA",
    })
    assert r.status_code == 201
    assert r.json()["subcategory"] is None


def test_catalogo_de_categorias(client):
    """GET /api/tickets/categories entrega o catalogo para a tela.

    Prova tambem que a rota literal /categories nao foi capturada pela rota
    /{ticket_id} -- a ordem de declaracao no router importa.
    """
    r = client.get("/api/tickets/categories")
    assert r.status_code == 200
    catalogo = r.json()
    assert len(catalogo) == 10
    hardware = next(c for c in catalogo if c["value"] == "HARDWARE")
    assert hardware["label"] == "Hardware"
    assert "Fonte queimada" in hardware["subcategories"]


# --- PAGINACAO --------------------------------------------------------------


def test_paginacao_devolve_envelope(client, sample_client):
    """A listagem devolve {items, total, limit, offset, has_more}.

    ★ O 'total' e' o que responde "quantos existem no total?" -- e' ele que
      permite a tela escrever "1-20 de 5.000". Sem ele, o frontend recebe 20
      itens e nao tem como saber se ha mais.
    """
    for i in range(25):
        client.post("/api/tickets", json={
            "client_id": sample_client["id"], "title": f"Chamado {i:02d}",
            "description": "descricao do chamado", "category": "REDE",
            "priority": "MEDIA",
        })

    primeira = client.get("/api/tickets?limit=10&offset=0").json()
    assert primeira["total"] == 25
    assert len(primeira["items"]) == 10
    assert primeira["has_more"] is True

    ultima = client.get("/api/tickets?limit=10&offset=20").json()
    assert len(ultima["items"]) == 5
    # Na ultima pagina nao ha proxima -- e' o que desabilita o botao na tela.
    assert ultima["has_more"] is False


def test_busca_filtra_no_banco(client, sample_client):
    """A busca textual e' um WHERE ... LIKE, e o total reflete o filtro."""
    client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Impressora sem toner",
        "description": "trocar toner", "category": "IMPRESSORA",
        "priority": "BAIXA",
    })
    client.post("/api/tickets", json={
        "client_id": sample_client["id"], "title": "Rede lenta",
        "description": "wifi caindo", "category": "REDE", "priority": "BAIXA",
    })

    achou = client.get("/api/tickets?search=toner").json()
    assert achou["total"] == 1
    assert "toner" in achou["items"][0]["title"].lower()

    # Termo que nao existe devolve total 0, nao erro.
    assert client.get("/api/tickets?search=zzzzzz").json()["total"] == 0
