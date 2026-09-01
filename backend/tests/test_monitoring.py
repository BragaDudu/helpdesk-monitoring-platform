"""Testes de Monitoramento (Exercicio 3) -- a regra dos 80 graus.

Sao os testes mais importantes do projeto: provam que a regra critica
funciona e que ela mora no backend.
"""


def _reading(client, equipment_id, temp):
    return client.post(f"/api/equipments/{equipment_id}/readings",
                       json={"temperature": temp, "status": "ONLINE"})


# --- EQUIPAMENTO ------------------------------------------------------------


def test_criar_equipamento(client, sample_client):
    r = client.post("/api/equipments", json={
        "client_id": sample_client["id"], "identifier": "EQP-001", "name": "Servidor",
    })
    assert r.status_code == 201
    assert r.json()["status"] == "ONLINE"


def test_identifier_duplicado_409(client, sample_equipment, sample_client):
    r = client.post("/api/equipments", json={
        "client_id": sample_client["id"], "identifier": "EQP-TEST-01", "name": "Outro",
    })
    assert r.status_code == 409


# --- LEITURA E A REGRA DOS 80 GRAUS ----------------------------------------


def test_registrar_leitura(client, sample_equipment):
    """(registrar leitura) -> 201 e a leitura persiste."""
    r = _reading(client, sample_equipment["id"], 45.0)
    assert r.status_code == 201
    assert r.json()["reading"]["temperature"] == 45.0


def test_leitura_abaixo_do_limite_nao_gera_alerta(client, sample_equipment):
    """(nao gerar alerta quando <= 80) -- inclui o limite EXATO 80.0."""
    for temp in (45.0, 79.9, 80.0):
        r = _reading(client, sample_equipment["id"], temp)
        assert r.status_code == 201
        assert r.json()["critical_condition_detected"] is False
        assert r.json()["alert"] is None


def test_leitura_acima_do_limite_gera_alerta(client, sample_equipment):
    """(gerar alerta quando > 80) -- 80.1 ja dispara."""
    r = _reading(client, sample_equipment["id"], 80.1)
    assert r.status_code == 201
    body = r.json()
    assert body["critical_condition_detected"] is True
    assert body["alert"] is not None
    assert body["alert"]["temperature"] == 80.1
    assert body["alert"]["status"] == "ABERTO"


def test_alerta_persiste_e_associa_leitura(client, sample_equipment):
    """O alerta gravado aponta para a leitura que o causou."""
    r = _reading(client, sample_equipment["id"], 90.0).json()
    reading_id = r["reading"]["id"]
    alert = r["alert"]
    assert alert["reading_id"] == reading_id

    lista = client.get(f"/api/equipments/{sample_equipment['id']}/alerts").json()
    assert len(lista) == 1
    assert lista[0]["temperature"] == 90.0


def test_leitura_para_equipamento_inexistente_404(client):
    """(impedir leitura para equipamento inexistente) -> 404."""
    r = _reading(client, 9999, 50.0)
    assert r.status_code == 404


def test_temperatura_invalida_422(client, sample_equipment):
    """Temperatura fora da faixa fisica -> 422."""
    r = _reading(client, sample_equipment["id"], 9999)
    assert r.status_code == 422


def test_temperatura_nao_numerica_422(client, sample_equipment):
    r = client.post(f"/api/equipments/{sample_equipment['id']}/readings",
                    json={"temperature": "quente"})
    assert r.status_code == 422


def test_historico_ordenado(client, sample_equipment):
    """Historico vem do mais recente para o mais antigo."""
    for t in (40.0, 50.0, 60.0):
        _reading(client, sample_equipment["id"], t)
    hist = client.get(f"/api/equipments/{sample_equipment['id']}/readings").json()
    assert len(hist) == 3
    assert hist[0]["temperature"] == 60.0  # ultima enviada, primeira da lista


def test_temperatura_atual_na_listagem(client, sample_equipment):
    """A listagem traz a temperatura da ultima leitura."""
    _reading(client, sample_equipment["id"], 55.5)
    eq = client.get(f"/api/equipments/{sample_equipment['id']}").json()
    assert eq["last_temperature"] == 55.5


# --- CICLO DE VIDA DO ALERTA -----------------------------------------------


def test_resolver_alerta(client, sample_equipment):
    alert = _reading(client, sample_equipment["id"], 85.0).json()["alert"]
    r = client.patch(f"/api/alerts/{alert['id']}/status", json={"status": "RESOLVIDO"})
    assert r.status_code == 200
    assert r.json()["status"] == "RESOLVIDO"
    # some da contagem de abertos
    assert len(client.get("/api/alerts?status=ABERTO").json()) == 0
