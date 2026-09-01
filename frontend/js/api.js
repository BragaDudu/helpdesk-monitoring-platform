/*
 * api.js -- A CAMADA UNICA DE COMUNICACAO COM O BACKEND
 * =====================================================
 *
 * TODA chamada HTTP do frontend passa por aqui. Nenhuma outra pagina chama
 * fetch() diretamente. Por que centralizar?
 *
 *   1. TRATAMENTO DE ERRO NUM LUGAR SO. Se o backend responde 404 ou 422,
 *      e' aqui que o JSON de erro vira uma excecao com mensagem legivel.
 *      Sem isso, cada pagina repetiria "if (!response.ok) ..." e alguma
 *      esqueceria.
 *
 *   2. SE A URL BASE MUDAR, muda em um lugar. Hoje usamos caminho relativo
 *      ('/api/...') porque o FastAPI serve o proprio frontend -- mesma
 *      origem, sem CORS.
 *
 *   3. O CODIGO DAS PAGINAS FICA LIMPO: elas dizem "api.get('/clients')",
 *      nao se preocupam com cabecalhos, JSON.stringify nem status HTTP.
 *
 * FLUXO: pagina -> api.get/post/patch -> fetch -> FastAPI -> ... -> banco
 */

// Prefixo de todas as rotas. Relativo de proposito: funciona em localhost,
// em rede local ou em producao, sem alterar nada.
const API_BASE = "/api";

/*
 * ApiError -- um erro que carrega o status HTTP e a mensagem do backend.
 *
 * Quando o backend responde com erro, ele manda um JSON no formato
 *     { "error": "not_found", "detail": "Cliente com id 999..." }
 * (formato garantido pelos handlers do main.py). Guardamos os dois:
 * 'detail' e' o que mostramos ao usuario; 'code' e' para o codigo decidir.
 */
class ApiError extends Error {
  constructor(status, code, detail) {
    super(detail || `Erro HTTP ${status}`);
    this.name = "ApiError";
    this.status = status; // 404, 409, 422, 500...
    this.code = code; // "not_found", "conflict"...
    this.detail = detail; // mensagem em portugues
  }
}

/*
 * request() -- o motor. Todas as outras funcoes chamam esta.
 *
 * RECEBE: metodo (GET/POST/...), caminho ('/clients'), corpo opcional.
 * RETORNA: o JSON da resposta ja convertido em objeto (ou null se vazio).
 * LANCA:   ApiError se o backend responder com status de erro (>= 400);
 *          Error generico se a rede cair (o servidor nem respondeu).
 */
async function request(method, path, body) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };

  // So enviamos corpo em POST/PATCH/PUT. GET e DELETE nao tem corpo.
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (networkError) {
    // Caimos aqui se o servidor esta fora do ar: o fetch nem chegou a
    // receber resposta. E' diferente de um erro 500 (onde o servidor
    // respondeu). Mensagem clara evita o usuario achar que o dado sumiu.
    throw new Error(
      "Nao foi possivel conectar ao servidor. Verifique se o backend " +
        "esta rodando (uvicorn backend.app.main:app --reload)."
    );
  }

  // 204 No Content (usado no DELETE): sucesso, sem corpo para ler.
  if (response.status === 204) {
    return null;
  }

  // Tenta ler o JSON. Se o corpo vier vazio ou nao for JSON, seguimos.
  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  // response.ok e' true para status 200-299. Qualquer coisa fora disso
  // (404, 409, 422, 500) vira uma excecao que a pagina vai capturar.
  if (!response.ok) {
    const detail =
      (data && (data.detail || data.error)) ||
      `Erro ${response.status} ao acessar ${path}`;
    const code = (data && data.error) || "http_error";
    throw new ApiError(response.status, code, detail);
  }

  return data;
}

/*
 * A API PUBLICA -- e' isto que as paginas usam.
 * Repare como fica legivel: api.get('/clients'), api.post('/tickets', {...}).
 */
const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  patch: (path, body) => request("PATCH", path, body),
  delete: (path) => request("DELETE", path),
};
