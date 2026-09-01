/*
 * alertas.js -- anomalias (diagnóstico do agora) e histórico de alertas.
 *
 * Diferenca que esta pagina deixa clara:
 *   ANOMALIA = diagnostico do momento, calculado na hora (GET /anomalies)
 *   ALERTA   = evento gravado no banco quando passou de 80 (GET /alerts)
 */

// Painel superior: anomalias detectadas agora.
async function loadAnomalies() {
  const box = document.getElementById("anomalies");
  try {
    const items = await api.get("/equipments/anomalies");
    if (!items.length) {
      box.innerHTML = `<div class="state state--empty" style="color:var(--green)">✓ Nenhuma situação anormal no momento.</div>`;
      return;
    }
    box.innerHTML = items
      .map(
        (a) => `
        <div class="detail-row">
          <dt>
            <span class="sev sev--${a.severity.toLowerCase()}">[${a.severity}]</span>
            <strong>${escapeHtml(a.identifier)}</strong> — ${escapeHtml(a.anomaly_type)}
          </dt>
          <dd class="muted" style="font-weight:400">${escapeHtml(a.detail)}</dd>
        </div>`
      )
      .join("");
  } catch (error) {
    showErrorState(box, error.detail || error.message);
  }
}

// Painel inferior: histórico de alertas, com filtro por status.
async function loadAlerts() {
  const box = document.getElementById("alerts-table");
  showLoading(box);

  const status = document.getElementById("f-alert-status").value;
  const qs = status ? `?status=${status}` : "";

  try {
    const alerts = await api.get(`/alerts${qs}`);
    if (!alerts.length) return showEmpty(box, "Nenhum alerta com esse filtro.");

    const rows = alerts
      .map(
        (a) => `
        <tr>
          <td class="num">${a.id}</td>
          <td>${escapeHtml(a.equipment_identifier || "—")}</td>
          <td>${escapeHtml(a.client_company || "—")}</td>
          <td class="num"><span class="temp temp--hot">${a.temperature}&deg;C</span></td>
          <td>${badge(a.status)}</td>
          <td class="muted">${formatDate(a.created_at)}</td>
          <td>${alertActions(a)}</td>
        </tr>`
      )
      .join("");

    box.innerHTML = `
      <table>
        <thead>
          <tr><th>ID</th><th>Equipamento</th><th>Empresa</th><th>Temp.</th>
              <th>Status</th><th>Detectado em</th><th></th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (error) {
    showErrorState(box, error.detail || error.message);
  }
}

// Botoes de ciclo de vida conforme o status atual do alerta.
function alertActions(alert) {
  if (alert.status === "RESOLVIDO") {
    return `<span class="muted">—</span>`;
  }
  const buttons = [];
  if (alert.status === "ABERTO") {
    buttons.push(
      `<button class="btn btn--ghost btn--sm" onclick="setAlert(${alert.id}, 'RECONHECIDO')">Reconhecer</button>`
    );
  }
  buttons.push(
    `<button class="btn btn--sm" onclick="setAlert(${alert.id}, 'RESOLVIDO')">Resolver</button>`
  );
  return buttons.join(" ");
}

/*
 * setAlert -- PATCH /api/alerts/{id}/status.
 * Alerta nunca e' apagado, so muda de status. Um resolvido some da
 * contagem de pendencias mas continua no historico.
 */
async function setAlert(alertId, status) {
  try {
    await api.patch(`/alerts/${alertId}/status`, { status });
    toast(`Alerta #${alertId} marcado como ${status}.`);
    loadAlerts();
    loadAnomalies(); // um alerta resolvido pode mudar o quadro de anomalias
  } catch (error) {
    handleError(error);
  }
}

// ---- LIGACOES DE EVENTOS ----
document.addEventListener("DOMContentLoaded", () => {
  loadAnomalies();
  loadAlerts();
  document.getElementById("f-alert-status").addEventListener("change", loadAlerts);
});
