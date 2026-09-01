/*
 * chamados.js -- listagem com filtros, abertura e mudanca de status.
 *
 * Demonstra os 5 requisitos do Exercicio 1 do lado do frontend:
 *   listar, abrir, filtrar, ver detalhes, alterar status.
 */

/*
 * loadTickets -- busca chamados aplicando os filtros selecionados.
 *
 * ★ OS FILTROS VAO NA URL E SAO PROCESSADOS PELO BANCO.
 *   Montamos /api/tickets?status=ABERTO&priority=ALTA e o backend traduz
 *   isso em WHERE. NAO buscamos tudo para filtrar em JavaScript -- isso
 *   seria lento e traria dados a toa pela rede.
 */
async function loadTickets() {
  const box = document.getElementById("tickets-table");
  showLoading(box);

  const status = document.getElementById("f-status").value;
  const priority = document.getElementById("f-priority").value;

  // URLSearchParams monta a querystring corretamente, sem concatenar na mao.
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);
  const qs = params.toString() ? `?${params.toString()}` : "";

  try {
    const tickets = await api.get(`/tickets${qs}`);
    if (!tickets.length) {
      return showEmpty(box, "Nenhum chamado com esses filtros.");
    }

    const rows = tickets
      .map(
        (t) => `
        <tr>
          <td class="num">${t.id}</td>
          <td>${escapeHtml(t.title)}</td>
          <td>${escapeHtml(t.client.company)}</td>
          <td>${escapeHtml(t.category)}</td>
          <td>${badge(t.priority)}</td>
          <td>${badge(t.status)}</td>
          <td class="muted">${formatDateShort(t.opened_at)}</td>
          <td><button class="btn btn--ghost btn--sm" onclick="showTicket(${t.id})">Detalhes</button></td>
        </tr>`
      )
      .join("");

    box.innerHTML = `
      <table>
        <thead>
          <tr><th>ID</th><th>Título</th><th>Empresa</th><th>Categoria</th>
              <th>Prioridade</th><th>Status</th><th>Abertura</th><th></th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (error) {
    showErrorState(box, error.detail || error.message);
  }
}

/*
 * fillClientSelect -- popula o <select> de clientes do formulario.
 * Prova que ate as opcoes do dropdown vem do banco, nao estao no HTML.
 */
async function fillClientSelect() {
  const select = document.querySelector("#form-ticket select[name=client_id]");
  try {
    const clients = await api.get("/clients?limit=500");
    select.innerHTML =
      `<option value="">Selecione...</option>` +
      clients
        .map((c) => `<option value="${c.id}">${escapeHtml(c.company)} — ${escapeHtml(c.name)}</option>`)
        .join("");
  } catch (error) {
    select.innerHTML = `<option value="">Erro ao carregar clientes</option>`;
    handleError(error);
  }
}

/*
 * createTicket -- abre um chamado novo.
 */
async function createTicket(event) {
  event.preventDefault();
  const form = event.target;

  const payload = {
    client_id: Number(form.client_id.value), // converte texto do select em numero
    title: form.title.value.trim(),
    description: form.description.value.trim(),
    category: form.category.value.trim(),
    priority: form.priority.value,
  };

  try {
    const created = await api.post("/tickets", payload);
    toast(`Chamado #${created.id} aberto com sucesso.`);
    form.reset();
    closeModal("modal-ticket");
    loadTickets();
  } catch (error) {
    handleError(error); // ex.: cliente inexistente -> 404
  }
}

/*
 * showTicket -- detalhe com os botoes de mudanca de status.
 * Os botoes disponiveis dependem do status atual (espelha a maquina de
 * estados do backend). Mas quem MANDA e' o backend: se o usuario burlar e
 * pedir uma transicao invalida, a API responde 409 e mostramos o erro.
 */
async function showTicket(ticketId) {
  const body = document.getElementById("td-body");
  document.getElementById("td-title").textContent = "Chamado #" + ticketId;
  body.innerHTML = `<div class="state state--loading">Carregando...</div>`;
  openModal("modal-ticket-detail");

  try {
    const t = await api.get(`/tickets/${ticketId}`);

    // Botoes coerentes com a maquina de estados (enums.py do backend).
    const actions = [];
    if (t.status !== "FINALIZADO") {
      if (t.status !== "EM_ANDAMENTO") {
        actions.push(btnStatus(t.id, "EM_ANDAMENTO", "Iniciar atendimento"));
      }
      if (t.status !== "ABERTO") {
        actions.push(btnStatus(t.id, "ABERTO", "Voltar para aberto"));
      }
      actions.push(btnStatus(t.id, "FINALIZADO", "Finalizar"));
    } else {
      actions.push(`<span class="muted">Chamado finalizado — não pode ser reaberto.</span>`);
    }

    body.innerHTML = `
      <dl>
        <div class="detail-row"><dt>Cliente</dt><dd>${escapeHtml(t.client.company)}</dd></div>
        <div class="detail-row"><dt>Título</dt><dd>${escapeHtml(t.title)}</dd></div>
        <div class="detail-row"><dt>Categoria</dt><dd>${escapeHtml(t.category)}</dd></div>
        <div class="detail-row"><dt>Prioridade</dt><dd>${badge(t.priority)}</dd></div>
        <div class="detail-row"><dt>Status</dt><dd>${badge(t.status)}</dd></div>
        <div class="detail-row"><dt>Aberto em</dt><dd>${formatDate(t.opened_at)}</dd></div>
        <div class="detail-row"><dt>Fechado em</dt><dd>${formatDate(t.closed_at)}</dd></div>
      </dl>
      <p style="margin:16px 0 8px;color:var(--text-soft)">${escapeHtml(t.description)}</p>
      <div class="form-actions" style="justify-content:flex-start;flex-wrap:wrap">${actions.join("")}</div>`;
  } catch (error) {
    body.innerHTML = `<div class="state state--error">${escapeHtml(error.detail || error.message)}</div>`;
  }
}

function btnStatus(ticketId, status, label) {
  return `<button class="btn btn--sm" onclick="changeStatus(${ticketId}, '${status}')">${label}</button>`;
}

/*
 * changeStatus -- PATCH /api/tickets/{id}/status.
 * A regra da transicao mora no backend; aqui so enviamos o pedido.
 */
async function changeStatus(ticketId, status) {
  try {
    await api.patch(`/tickets/${ticketId}/status`, { status });
    toast(`Status alterado para ${status}.`);
    closeModal("modal-ticket-detail");
    loadTickets(); // recarrega a lista com o status novo vindo do banco
  } catch (error) {
    handleError(error); // ex.: transicao invalida -> 409
  }
}

// ---- LIGACOES DE EVENTOS ----
document.addEventListener("DOMContentLoaded", () => {
  loadTickets();
  fillClientSelect();
  document.getElementById("form-ticket").addEventListener("submit", createTicket);
  document.getElementById("f-status").addEventListener("change", loadTickets);
  document.getElementById("f-priority").addEventListener("change", loadTickets);
});
