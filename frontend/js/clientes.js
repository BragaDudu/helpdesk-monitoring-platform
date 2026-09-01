/*
 * clientes.js -- CRUD de clientes consumindo a API.
 *
 * FLUXO COMPLETO QUE ESTA PAGINA DEMONSTRA (o pedido do enunciado):
 *   listar  -> GET  /api/clients
 *   criar   -> POST /api/clients  -> recarrega a lista
 *   detalhe -> GET  /api/clients/{id} + /api/clients/{id}/tickets
 *   excluir -> DELETE /api/clients/{id}
 */

// Guarda o texto da busca para nao recriar a cada tecla desnecessariamente.
let searchTerm = "";

/*
 * loadClients -- busca os clientes e desenha a tabela.
 * Chamada ao abrir a pagina, apos criar/excluir, e ao buscar.
 */
async function loadClients() {
  const box = document.getElementById("clients-table");
  showLoading(box);

  try {
    // Monta a querystring de busca (encodeURIComponent protege caracteres
    // especiais e evita quebrar a URL).
    const q = searchTerm ? `?search=${encodeURIComponent(searchTerm)}` : "";
    const clients = await api.get(`/clients${q}`);

    if (!clients.length) {
      return showEmpty(box, "Nenhum cliente encontrado.");
    }

    // Monta as linhas. TODO texto vindo do banco passa por escapeHtml
    // (protecao contra XSS -- ver ui.js).
    const rows = clients
      .map(
        (c) => `
        <tr>
          <td class="num">${c.id}</td>
          <td>${escapeHtml(c.name)}</td>
          <td>${escapeHtml(c.company)}</td>
          <td>${escapeHtml(c.email)}</td>
          <td>${escapeHtml(c.phone)}</td>
          <td>
            <button class="btn btn--ghost btn--sm" onclick="showDetail(${c.id})">Detalhes</button>
            <button class="btn btn--danger btn--sm" onclick="removeClient(${c.id}, '${escapeHtml(
          c.company
        ).replace(/'/g, "\\'")}')">Excluir</button>
          </td>
        </tr>`
      )
      .join("");

    box.innerHTML = `
      <table>
        <thead>
          <tr><th>ID</th><th>Nome</th><th>Empresa</th><th>E-mail</th><th>Telefone</th><th></th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (error) {
    showErrorState(box, error.detail || error.message);
  }
}

/*
 * createClient -- envia o formulario. Chamado no submit.
 */
async function createClient(event) {
  event.preventDefault(); // impede o navegador de recarregar a pagina

  const form = event.target;
  const payload = {
    name: form.name.value.trim(),
    company: form.company.value.trim(),
    email: form.email.value.trim(),
    phone: form.phone.value.trim(),
  };

  try {
    // Se o backend recusar (e-mail duplicado -> 409, dado invalido -> 422),
    // api.post LANCA um ApiError e caimos no catch. Nada e' salvo sem o
    // "OK" do servidor.
    const created = await api.post("/clients", payload);
    toast(`Cliente "${created.company}" cadastrado com sucesso.`);
    form.reset();
    closeModal("modal-client");
    loadClients(); // recarrega a lista JA COM o novo cliente vindo do banco
  } catch (error) {
    handleError(error); // mostra a mensagem do backend (ex.: "e-mail ja existe")
  }
}

/*
 * showDetail -- abre o modal com os dados do cliente E seus chamados.
 * Faz DUAS requisicoes: o cliente e a lista de chamados dele.
 */
async function showDetail(clientId) {
  const body = document.getElementById("detail-body");
  document.getElementById("detail-title").textContent = "Cliente #" + clientId;
  body.innerHTML = `<div class="state state--loading">Carregando...</div>`;
  openModal("modal-detail");

  try {
    // Promise.all dispara as duas requisicoes EM PARALELO e espera as duas.
    // Mais rapido do que uma depois da outra.
    const [client, tickets] = await Promise.all([
      api.get(`/clients/${clientId}`),
      api.get(`/clients/${clientId}/tickets`),
    ]);

    document.getElementById("detail-title").textContent = client.company;

    const ticketsHtml = tickets.length
      ? tickets
          .map(
            (t) => `
          <tr>
            <td>${escapeHtml(t.title)}</td>
            <td>${badge(t.priority)}</td>
            <td>${badge(t.status)}</td>
            <td class="muted">${formatDateShort(t.opened_at)}</td>
          </tr>`
          )
          .join("")
      : `<tr><td colspan="4" class="muted">Este cliente ainda não tem chamados.</td></tr>`;

    body.innerHTML = `
      <dl>
        <div class="detail-row"><dt>Nome</dt><dd>${escapeHtml(client.name)}</dd></div>
        <div class="detail-row"><dt>Empresa</dt><dd>${escapeHtml(client.company)}</dd></div>
        <div class="detail-row"><dt>E-mail</dt><dd>${escapeHtml(client.email)}</dd></div>
        <div class="detail-row"><dt>Telefone</dt><dd>${escapeHtml(client.phone)}</dd></div>
        <div class="detail-row"><dt>Cadastrado em</dt><dd>${formatDate(client.created_at)}</dd></div>
      </dl>
      <h3 style="margin:20px 0 10px;font-size:15px">Chamados (${tickets.length})</h3>
      <table>
        <thead><tr><th>Título</th><th>Prioridade</th><th>Status</th><th>Abertura</th></tr></thead>
        <tbody>${ticketsHtml}</tbody>
      </table>`;
  } catch (error) {
    body.innerHTML = `<div class="state state--error">${escapeHtml(
      error.detail || error.message
    )}</div>`;
  }
}

/*
 * removeClient -- exclui, com confirmacao.
 * O backend recusa (409) se o cliente tiver chamados/equipamentos -- e
 * mostramos essa mensagem. A protecao real esta no servidor; o confirm()
 * aqui e' so cortesia com o usuario.
 */
async function removeClient(clientId, company) {
  if (!confirm(`Excluir o cliente "${company}"?\n\nSó é possível se ele não tiver chamados nem equipamentos.`)) {
    return;
  }
  try {
    await api.delete(`/clients/${clientId}`);
    toast(`Cliente "${company}" excluído.`);
    loadClients();
  } catch (error) {
    handleError(error); // ex.: "possui 5 chamados vinculados"
  }
}

// ---- LIGACOES DE EVENTOS ----
document.addEventListener("DOMContentLoaded", () => {
  loadClients();
  document.getElementById("form-client").addEventListener("submit", createClient);

  // Busca com "debounce": espera 300ms apos parar de digitar antes de
  // chamar a API. Evita uma requisicao por tecla.
  let timer;
  document.getElementById("search").addEventListener("input", (e) => {
    clearTimeout(timer);
    searchTerm = e.target.value.trim();
    timer = setTimeout(loadClients, 300);
  });
});
