# Colinha de apresentação

## Comandos (na ordem, um por vez)

```bash
.\.venv\Scripts\Activate.ps1
```
```bash
python -m backend.seed --status
```
```bash
uvicorn backend.app.main:app --reload --port 8010
```

Abrir: **http://localhost:8010** · Swagger: **http://localhost:8010/docs**

> A porta 8000 tem outro app nesta máquina — por isso uso a 8010.

## Roteiro de 5 minutos

1. **Dashboard** — "Todos esses números vêm da API, não estão no HTML." (F5 na frente deles.)
2. **Clientes** — cadastrar um cliente → aparece na lista. F5 → continua lá.
3. **Chamados** — filtrar por status (mostrar na aba Rede do navegador que vira `?status=`). Abrir um chamado, finalizar → `closed_at` carimbado.
4. **Equipamentos** — abrir um, enviar leitura **75°C** (sem alerta), depois **85°C** → alerta vermelho na hora.
5. **Alertas** — o alerta de 85°C está lá. Mostrar as anomalias.
6. **Prova final** — parar o servidor (Ctrl+C), subir de novo, mostrar que tudo continua.

## Frases-chave para dizer

- "A regra dos 80 graus está no **backend**, não no JavaScript — um sensor IoT chama a API sem navegador."
- "O chamado guarda só o `client_id`; não copio nome nem e-mail — isso é **normalização**."
- "`closed_at` é NULL enquanto aberto; a ausência de dado **é** informação."
- "Leitura e alerta são gravados na **mesma transação**: impossível ter leitura de 90° sem alerta."
- "Trocar para PostgreSQL é mudar uma linha no `.env`."

## Se pedirem para alterar uma regra ao vivo

- **"Permita reabrir chamado finalizado"** → `backend/app/enums.py`, trocar
  `TicketStatus.FINALIZADO: set()` por `{TicketStatus.ABERTO}`.
- **"Mude o limite de temperatura"** → `.env`, `TEMPERATURE_ALERT_THRESHOLD=70`, reiniciar.
- **"Crie um endpoint"** → copiar o padrão de `routers/clients.py` (router → service → schema).

## Onde está cada coisa (se pedirem para abrir)

| Pergunta | Arquivo |
|---|---|
| Regra dos 80°C | `services/monitoring_service.py` → `register_reading` |
| Máquina de estados | `enums.py` → `TICKET_STATUS_TRANSITIONS` |
| Foreign keys ativas | `database.py` → `PRAGMA foreign_keys` |
| Tradução de erro → HTTP | `main.py` → `handle_domain_error` |
| As 6 análises | `services/analytics_service.py` |
| Camada única de fetch | `frontend/js/api.js` |
