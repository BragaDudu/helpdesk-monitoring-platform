/*
 * ui.js -- FUNCOES DE INTERFACE REUTILIZADAS POR TODAS AS PAGINAS
 * ================================================================
 * Formatacao de data, "badges" de status, mensagens (toast), estados de
 * carregamento e erro. Ficam aqui para nao serem reescritas em cada pagina.
 */

/*
 * formatDate -- converte a data ISO da API para o fuso do usuario.
 *
 * ★ AQUI ACONTECE A CONVERSAO DE FUSO HORARIO.
 *   O backend manda "2026-09-01T14:32:10Z". O "Z" diz que e' UTC.
 *   new Date(...) entende isso e converte para o horario LOCAL do
 *   navegador. toLocaleString('pt-BR') formata no padrao brasileiro.
 *
 *   E' a unica etapa do sistema onde o horario deixa de ser UTC. No banco,
 *   na API e no trafego, tudo e' UTC. So na TELA vira horario de Brasilia.
 */
function formatDate(isoString) {
  if (!isoString) return "—"; // travessao para "nao ha data"
  const date = new Date(isoString);
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateShort(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleDateString("pt-BR");
}

/*
 * badge -- gera o HTML de uma etiqueta colorida de status/prioridade.
 * A cor vem de uma classe CSS derivada do proprio valor
 * (ex.: status "ABERTO" -> classe "badge--aberto").
 */
function badge(value) {
  if (!value) return "";
  const cls = "badge--" + String(value).toLowerCase().replace(/_/g, "-");
  return `<span class="badge ${cls}">${escapeHtml(value)}</span>`;
}

/*
 * escapeHtml -- PROTECAO CONTRA XSS.
 *
 * ★ SEGURANCA: nomes de clientes, titulos de chamados etc. vem do banco e
 *   sao inseridos no HTML. Se um cliente se chamasse
 *       <script>algo()</script>
 *   e jogassemos direto no innerHTML, o navegador EXECUTARIA esse script.
 *   Isso e' um ataque XSS. Esta funcao troca < > & " por entidades HTML,
 *   entao o texto aparece como texto, nunca como codigo.
 *
 *   Toda vez que colocamos dado do usuario no HTML, passa por aqui.
 */
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/*
 * toast -- mensagem temporaria no canto da tela (sucesso ou erro).
 * Substitui o alert(): nao trava a pagina e some sozinha.
 */
function toast(message, type = "success") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }
  const el = document.createElement("div");
  el.className = `toast toast--${type}`;
  el.textContent = message;
  container.appendChild(el);

  // Remove depois de alguns segundos (erros ficam mais tempo).
  setTimeout(() => el.remove(), type === "error" ? 6000 : 3500);
}

/*
 * handleError -- traduz um erro do api.js em uma mensagem para o usuario.
 * Chamado no catch de toda operacao. Nunca deixa o erro silencioso no
 * console (o enunciado pede isso explicitamente).
 */
function handleError(error) {
  console.error(error); // registra tambem no console, para depurar
  const message = error.detail || error.message || "Ocorreu um erro inesperado.";
  toast(message, "error");
}

/*
 * Estados de uma area de conteudo: carregando / vazio / erro.
 * Usados enquanto o fetch nao volta, ou quando nao ha dados.
 */
function showLoading(el) {
  el.innerHTML = `<div class="state state--loading">Carregando...</div>`;
}
function showEmpty(el, message = "Nenhum registro encontrado.") {
  el.innerHTML = `<div class="state state--empty">${escapeHtml(message)}</div>`;
}
function showErrorState(el, message) {
  el.innerHTML = `<div class="state state--error">${escapeHtml(message)}</div>`;
}

/*
 * Modal simples: abre/fecha pelo atributo hidden. Sem biblioteca.
 */
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.hidden = false;
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.hidden = true;
}

/*
 * markActiveNav -- destaca o link da pagina atual no menu lateral.
 * Compara o nome do arquivo da URL com o data-page de cada link.
 */
function markActiveNav() {
  const current = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll("[data-page]").forEach((link) => {
    if (link.dataset.page === current) link.classList.add("active");
  });
}

document.addEventListener("DOMContentLoaded", markActiveNav);
