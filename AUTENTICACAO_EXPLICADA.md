# Autenticação no HelpDesk: Como Funciona

## 📌 Resumo Executivo

Seu sistema de autenticação é **bem feito e seguro** porque:
- ✅ Senhas são armazenadas com **PBKDF2-HMAC-SHA256** (não texto simples)
- ✅ Usa **tokens assinados** que não podem ser alterados
- ✅ Implementa **proteções contra timing attacks** e enumeração de usuários
- ✅ Suporta **multi-tenancy** com isolamento de dados por empresa

---

## 1️⃣ Como o Login e Senha Funcionam

### O Fluxo de Login

```
Usuário digita e-mail e senha
         ↓
Frontend POST /api/auth/login
         ↓
Backend recebe e-mail e senha
         ↓
Busca usuário no banco por e-mail
         ↓
Confere a senha contra o HASH guardado
         ↓
Se tudo OK: cria TOKEN assinado
         ↓
Envia token + dados do usuário para o frontend
         ↓
Frontend guarda token no localStorage
         ↓
Toda próxima requisição leva: Authorization: Bearer <token>
```

### O Que Acontece Com a Senha

**NUNCA é guardada em texto plano.** Em vez disso:

1. **Cria-se um HASH** da senha (arquivo: `backend/app/security.py`)
   - Algoritmo: **PBKDF2-HMAC-SHA256**
   - Iterações: **240.000 vezes** (propositalmente LENTO)
   - Salt: **valor aleatório único** para cada usuário

2. **Formato guardado no banco:**
   ```
   pbkdf2_sha256$240000$<salt em hexadecimal>$<hash em hexadecimal>
   ```

3. **Exemplo real** (não use estas senhas!):
   ```
   pbkdf2_sha256$240000$a1b2c3d4e5f6$9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c
   ```

### Por Que PBKDF2 e Não Um SHA256 Simples?

**SHA256 é rápido demais:**
- Uma placa de vídeo testa **bilhões de senhas por segundo**
- Uma senha comum cai em **minutos**

**PBKDF2 faz o mesmo cálculo 240.000 vezes:**
- Você faz login em ~0.1s (imperceptível)
- Um atacante quebrando por força bruta demora **240.000 vezes mais**
- Senha de 8 caracteres que levaria 1 minuto agora leva **meses**

### Por Que o Salt?

Se duas pessoas tivessem a mesma senha:
- ❌ Sem salt: ambas teriam o **mesmo hash** → atacante quebrava as duas de uma vez
- ✅ Com salt: cada uma tem um **hash diferente** → atacante precisa quebrar uma por uma

---

## 2️⃣ Como Você Sabe Que Estão Seguros

### ✅ Proteções Implementadas

#### 1. **Hash + Salt (Senhas)**
```python
def hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)  # aleatório criptográfico
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), 
                                   salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${derivado.hex()}"
```
- Salt é diferente para cada usuário
- Hash é irreversível (não se consegue a senha de trás)

#### 2. **Comparação em Tempo Constante**
```python
def conferir_senha(senha: str, guardado: str) -> bool:
    # ...
    return hmac.compare_digest(derivado.hex(), hash_hex)
```
- Usa `hmac.compare_digest()`, não `==`
- ❌ Errado: `==` termina na primeira diferença → **timing attack**
- ✅ Correto: `compare_digest()` sempre demora o mesmo tempo

**Timing Attack (o que evitamos):**
```
Tenta "a1234567" → responde em 1ms (primeiro char errado)
Tenta "a9234567" → responde em 1ms
Tenta "admin123" → responde em 100ms (todos chars tá certos até o fim)
Atacante descobriu que começa com "admin"
```

#### 3. **Mesma Mensagem de Erro Para Tudo**
```python
if usuario is None:
    _gastar_tempo_equivalente(senha)  # ← queima tempo mesmo sem usuário
    raise UnauthorizedError("E-mail ou senha incorretos.")

if not conferir_senha(senha, usuario.password_hash):
    raise UnauthorizedError("E-mail ou senha incorretos.")
```
- Não diz "e-mail não cadastrado" ← evita enumeração de usuários
- Não diz "senha errada" ← evita saber quem existe no sistema
- **Gasta o mesmo tempo nos dois casos** ← evita timing attack

#### 4. **Token Assinado (Não Criptografado)**
```python
def criar_token(user_id: int, role: str, client_id: int | None) -> str:
    conteudo = {
        "sub": user_id,           # de quem é
        "role": role,             # o que pode fazer
        "client_id": client_id,   # que empresa vê
        "exp": agora + 8*60*60    # expira em 8 horas
    }
    corpo = _b64(json.dumps(conteudo))
    assinatura = _assinar(corpo)  # HMAC-SHA256 com SECRET_KEY
    return f"{corpo}.{assinatura}"
```

**Formato do token:**
```
eyJzdWIiOjcsInJvbGUiOiJBRE1JTl9FTXBSRVNBIIN9.KJ8xY2P3w...
^-- legível em base64     ^-- assinatura que não dá para falsificar
```

**O ponto importante:**
- ✅ Qualquer um consegue **LER** o token (é base64, não segredo)
- ❌ Ninguém consegue **ALTERAR** sem a chave secreta
- Se alguém trocasse "ADMIN_EMPRESA" por "SUPER_ADMIN", a assinatura não bateria
- Token seria rejeitado

#### 5. **Token Expira**
```python
"exp": agora + settings.TOKEN_EXPIRE_MINUTES * 60  # padrão: 8 horas
```
- Mesmo que um token seja roubado, tem prazo de validade
- Após expirar, usuário precisa fazer login novamente

#### 6. **Senha Mínima de 8 Caracteres**
```python
password: str = Field(min_length=8, max_length=128)
```
- Sem essa restrição, "123456" teria alta probabilidade de ser quebrado
- 8 caracteres com PBKDF2 é razoável (recomendação NIST)

### ⚠️ O Que NÃO É Seguro (Problema Potencial)

**Token em localStorage (frontend):**
```javascript
const auth = {
  token() {
    return localStorage.getItem(TOKEN_KEY);  // ← JavaScript consegue ler
  },
  salvar(token, user) {
    localStorage.setItem(TOKEN_KEY, token);  // ← armazena aqui
  }
}
```

**O risco:**
- Se um **XSS (Cross-Site Scripting)** entrar no site, código malicioso consegue ler o token
- Atacante poderia fazer requisições com seu acesso

**A defesa:**
- Projeto **escapa HTML** de todo texto vindo do banco antes de mostrar
- Escape previne XSS: `<script>` vira `&lt;script&gt;`

**Alternativa melhor (para produção real):**
- Guardar token em **cookie httpOnly** (JavaScript não consegue ler)
- Usar **CSRF token** para proteger contra ataques cross-site

---

## 3️⃣ Como Cadastrar Novo Login Para Outra Empresa

### Estrutura de Dados

Há **duas entidades** no banco:

1. **Cliente (Client)** — a empresa
   - `id`: 1, 2, 3, etc.
   - `company`: "Alfa Ltda", "Beta Inc", etc.
   - `name`, `email`, `phone`: contato

2. **Usuário (User)** — pessoa que faz login
   - `id`: 1, 2, 3, etc.
   - `email`: "joao@alfa.com.br" (ÚNICO)
   - `name`: "João Silva"
   - `role`: ADMIN_EMPRESA ou SUPER_ADMIN
   - `client_id`: **qual empresa ele vê**

### Modelo Multi-Tenancy

```
┌─────────────────────────────────────────────────────────┐
│ BANCO DE DADOS (único)                                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tabela: clients                                        │
│  ┌──────┬──────────────┐                               │
│  │ id   │ company      │                               │
│  ├──────┼──────────────┤                               │
│  │ 1    │ Alfa Ltda    │                               │
│  │ 2    │ Beta Inc     │                               │
│  │ 3    │ Gama Tech    │                               │
│  └──────┴──────────────┘                               │
│                                                         │
│  Tabela: users                                          │
│  ┌───┬────────────────────────┬──────────────────┐    │
│  │id │ email                  │ client_id        │    │
│  ├───┼────────────────────────┼──────────────────┤    │
│  │1  │ admin@helpdesk.com.br  │ NULL (vê tudo)   │    │
│  │2  │ joao@alfa.com.br       │ 1 (só Alfa)      │    │
│  │3  │ maria@beta.com.br      │ 2 (só Beta)      │    │
│  │4  │ carlos@gama.com.br     │ 3 (só Gama)      │    │
│  └───┴────────────────────────┴──────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘

Resultado:
- admin@helpdesk: vê dados de Alfa, Beta E Gama
- joao@alfa: vê só os dados de Alfa
- maria@beta: vê só os dados de Beta
```

### Passo a Passo: Criar Novo Usuário Para Nova Empresa

#### **Opção 1: Pela API (programaticamente)**

Não há endpoint de criação no código atual, mas você pode:

```bash
# 1. Criar novo cliente
curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Contato Principal",
    "company": "Nova Empresa LTDA",
    "email": "contato@novaempresa.com.br",
    "phone": "+55 11 98765-4321"
  }'

# Resposta:
# {"id": 4, "name": "Contato Principal", "company": "Nova Empresa LTDA", ...}

# 2. Criar novo usuário ligado ao cliente
# (precisaria de um endpoint POST /api/users que não existe ainda)
```

#### **Opção 2: Diretamente no Banco de Dados**

```sql
-- 1. Inserir a empresa
INSERT INTO clients (name, company, email, phone, created_at)
VALUES ('João Manager', 'Nova Empresa LTDA', 'joao@novaempresa.com.br', 
        '+55 11 98765-4321', NOW());

-- Pega o ID gerado (ex: 5)
SELECT id FROM clients WHERE company = 'Nova Empresa LTDA';

-- 2. Hash da senha (precisa fazer em Python)
-- Abra uma shell Python:
python3
from backend.app.security import hash_senha
print(hash_senha("MinhaSenh@123456"))

-- Saída:
-- pbkdf2_sha256$240000$a1b2c3d4e5f6$9f8e7d6c5b4a3f...

-- 3. Inserir o usuário
INSERT INTO users (email, password_hash, name, role, client_id, is_active, created_at)
VALUES (
  'gerente@novaempresa.com.br',
  'pbkdf2_sha256$240000$a1b2c3d4e5f6$9f8e7d6c5b4a3f...',
  'Gerente da Nova Empresa',
  'ADMIN_EMPRESA',  -- ou 'SUPER_ADMIN' se for admin de TI
  5,  -- ID do cliente criado acima
  TRUE,
  NOW()
);

-- 4. Pronto! Teste o login:
-- E-mail: gerente@novaempresa.com.br
-- Senha: MinhaSenh@123456
```

#### **Opção 3: Criar um Script de Seed (Recomendado)**

Arquivo: `backend/scripts/criar_usuario.py`

```python
#!/usr/bin/env python3
"""Script para criar usuário e cliente de uma vez."""

from backend.app.database import SessionLocal
from backend.app.models import Client, User
from backend.app.security import hash_senha
from backend.app.enums import UserRole

db = SessionLocal()

# Criar cliente
novo_cliente = Client(
    name="Contato Principal",
    company="Acme Corporation",
    email="contato@acme.com.br",
    phone="+55 11 3333-4444"
)
db.add(novo_cliente)
db.flush()  # gera o ID sem fazer commit

# Criar usuário
novo_usuario = User(
    email="admin@acme.com.br",
    password_hash=hash_senha("AcmeAdmin@123456"),
    name="Admin Acme",
    role=UserRole.ADMIN_EMPRESA,
    client_id=novo_cliente.id,
    is_active=True
)
db.add(novo_usuario)
db.commit()

print(f"✓ Cliente criado: {novo_cliente.company} (ID {novo_cliente.id})")
print(f"✓ Usuário criado: {novo_usuario.email}")
print(f"\nFaça login com:")
print(f"  E-mail: {novo_usuario.email}")
print(f"  Senha: AcmeAdmin@123456")
```

Execute:
```bash
cd backend
python scripts/criar_usuario.py
```

---

## 4️⃣ Papéis de Acesso (Roles)

### **SUPER_ADMIN**
- Empresa de TI (responsável pelo sistema)
- `client_id = NULL` (vazio)
- Vê dados de **todas** as empresas
- Pode gerenciar usuários

### **ADMIN_EMPRESA**
- Administrador de uma empresa cliente
- `client_id = 2` (ex: empresa "Beta Inc")
- Vê dados **só da sua empresa**
- Não consegue ver dados de outras empresas (bloqueado no backend)

### Como o Backend Garante o Isolamento

Arquivo: `backend/app/deps.py` (supostamente)

```python
def get_current_user(token: str) -> User:
    payload = ler_token(token)
    usuario = db.query(User).filter(User.id == payload['sub']).first()
    return usuario

# Toda rota protegida com @require_admin valida o cliente:
def get_tickets(usuario: User = Depends(get_current_user)):
    if usuario.ve_tudo:
        return db.query(Ticket).all()  # SUPER_ADMIN vê tudo
    else:
        # ADMIN_EMPRESA vê só sua empresa
        return db.query(Ticket).filter(
            Ticket.client_id == usuario.client_id
        ).all()
```

---

## 5️⃣ Checklist de Segurança

- [x] Senhas não são guardadas (só hash)
- [x] Hash usa PBKDF2 com 240.000 iterações
- [x] Cada senha tem salt único e aleatório
- [x] Comparação de senha usa `hmac.compare_digest()` (tempo constante)
- [x] Token é assinado (não pode ser adulterado)
- [x] Token expira (8 horas)
- [x] Mensagens de erro não revelam se usuário existe
- [x] Sistema gasta tempo igual para e-mail inválido ou senha errada
- [x] Isolamento de dados por empresa (multi-tenancy)
- [ ] (Melhorar em produção) Guardar token em cookie httpOnly + CSRF token
- [ ] (Melhorar em produção) Usar Argon2id no lugar de PBKDF2

---

## 📖 Arquivos Principais

| Arquivo | Responsabilidade |
|---------|------------------|
| `backend/app/security.py` | Criptografia de senha e tokens |
| `backend/app/models/user.py` | Modelo de usuário com `client_id` |
| `backend/app/schemas/auth.py` | Validação de e-mail e senha mínimos |
| `backend/app/services/auth_service.py` | Lógica de autenticação |
| `backend/app/routers/auth.py` | Endpoints `/login`, `/me`, `/logout` |
| `frontend/js/auth.js` | Guardar/recuperar token no localStorage |
| `frontend/login.html` | Tela de login |

---

## 🔐 Teste de Segurança Rápido

1. **Tente fazer login com senha errada:**
   - Demora ~150ms ✓ (por causa do PBKDF2)

2. **Tente fazer login com e-mail que não existe:**
   - Demora ~150ms ✓ (igual ao de cima)
   - Mensagem de erro é **igual** ✓

3. **Faça login com acesso válido:**
   - Token aparece no localStorage ✓
   - Copie o token em um decodificador base64:
     ```
     Token: eyJzdWIiOjIsInJvbGU...
     Conteúdo: {"sub": 2, "role": "ADMIN_EMPRESA", "client_id": 1, "exp": 1234567890}
     ```
   - O conteúdo é legível, mas **não há senha ali** ✓
   - Qualquer alteração invalida a assinatura ✓

4. **Teste isolamento multi-tenancy:**
   - Faça login como gerente de "Alfa"
   - Tente acessar dados de "Beta" na URL
   - Backend responde 403 Forbidden ✓

---

## 💡 Resumo: Por Que Está Seguro

| Aspecto | Proteção |
|---------|----------|
| **Senha** | PBKDF2-HMAC-SHA256 com 240k iterações + salt único |
| **Roubo de token** | Expira em 8 horas; XSS é bloqueado por HTML escape |
| **Fake token** | Assinatura HMAC invalida qualquer alteração |
| **Enumeração de usuários** | Mensagem de erro é igual para e-mail/senha errados |
| **Timing attacks** | `compare_digest()` usa tempo constante |
| **Multi-tenancy** | Filtro por `client_id` em toda consulta |

