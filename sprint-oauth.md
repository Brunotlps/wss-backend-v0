# Sprint: OAuth 2.0 + OIDC com Google

**Projeto:** WSS Backend — LMS API (NousFlow)
**Feature:** Registro e Login com conta Google
**Status:** Planejamento aprovado — implementação pendente
**Branch:** `claude-edits`

---

## Objetivo

Disponibilizar autenticação via Google como alternativa ao registro/login com email+senha. O backend controla o fluxo OAuth completo (Authorization Code Flow) e emite seus próprios JWTs após autenticação bem-sucedida. O Google não participa das requisições subsequentes.

---

## Fluxo Completo

```
1. Frontend → GET /api/auth/google/
2. Backend: gera state (anti-CSRF) + nonce (anti-replay)
            salva na sessão Django
            redireciona para https://accounts.google.com/o/oauth2/auth?...

3. Usuário autentica e autoriza no Google

4. Google → GET /api/auth/google/callback/?code=...&state=...

5. Backend:
   a. Valida state (bate com o salvo na sessão)
   b. Troca code por tokens via POST server-to-server para Google
   c. Valida id_token:
      - Assinatura via JWKS (google-auth cuida disso)
      - iss == "accounts.google.com"
      - aud == GOOGLE_OAUTH_CLIENT_ID
      - exp (não expirado)
      - nonce (bate com o salvo na sessão)
      - email_verified == true
   d. findOrCreateUser no banco
   e. Emite JWT pair próprio (access + refresh)
   f. Redireciona: FRONTEND_URL/auth/callback#access=...&refresh=...

6. Frontend lê tokens de window.location.hash — nunca vai ao servidor
7. Requisições futuras: Authorization: Bearer <access_token>
   O Google não está mais envolvido.
```

---

## Decisões de Arquitetura

### Biblioteca: `google-auth` + `google-auth-oauthlib` (oficial Google)

**Por quê não django-allauth:**
- allauth impõe schema próprio (SocialAccount, SocialToken, SocialApp) que sobrepõe ao nosso modelo de User já estabelecido
- Adiciona ~8 dependências pesadas
- Dificulta integração limpa com simplejwt existente
- Muito "magic" — difícil debugar em produção

**Por quê google-auth oficial:**
- Libs mínimas (~2 deps), oficiais, mantidas pelo Google
- Controle total de cada passo do fluxo — cada verificação de segurança é explícita
- Integração limpa com simplejwt e User model existente
- Testável unitariamente sem mocks complexos

### State Storage: Sessão Django

- `SessionMiddleware` já está no `MIDDLEWARE` — sem infra extra
- Alternativa (Redis diretamente) adicionaria acoplamento desnecessário

### Entrega de Tokens ao Frontend: Fragment URL

```
FRONTEND_URL/auth/callback#access=eyJ...&refresh=eyJ...
```

- Fragment (`#`) nunca é enviado ao servidor — não aparece em logs
- Frontend lê via `window.location.hash`
- Alternativa (query string `?`) expõe tokens em logs de Nginx e browser history
- Alternativa (cookie HttpOnly) exigiria mudanças em CORS e proteção CSRF adicional

### PKCE: não na v1

- PKCE é mais relevante quando o client-side inicia o fluxo (SPA/mobile sem backend)
- No nosso fluxo, o backend controla o code exchange — state + nonce são suficientes
- `google-auth-oauthlib` suporta PKCE; pode ser adicionado na v2 sem breaking changes

### Tokens do Google: não persistir

- O Google refresh_token seria necessário para operações contínuas (acessar Gmail, Calendar)
- Para registro/login, o id_token é descartado após validação
- Simplifica modelo de segurança: sem tokens de terceiro no banco

---

## Estrutura de Arquivos

### Novos arquivos

```
backend/apps/users/
├── services/
│   ├── __init__.py
│   └── google_oauth.py          ← GoogleOAuthService
├── tests/
│   ├── test_google_oauth.py     ← testes do service (unitários + integração)
│   └── test_google_views.py     ← testes dos endpoints
```

### Arquivos modificados

```
backend/apps/users/
├── models.py        ← + SocialAccount model
├── views.py         ← + GoogleLoginView, GoogleCallbackView
├── urls.py          ← + /auth/google/, /auth/google/callback/
├── admin.py         ← + SocialAccountAdmin

backend/config/settings/
├── base.py          ← + GOOGLE_OAUTH_*, FRONTEND_URL

requirements.txt     ← + google-auth, google-auth-oauthlib
.env.local           ← + variáveis de ambiente (não comitar)
```

---

## Model: SocialAccount

```python
class SocialAccount(TimeStampedModel):
    class Provider(models.TextChoices):
        GOOGLE = 'google', 'Google'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='social_accounts'
    )
    provider = models.CharField(max_length=50, choices=Provider.choices)
    uid = models.CharField(max_length=255)  # Google "sub" claim — imutável
    extra_data = models.JSONField(default=dict)  # email, name, picture (sync na autenticação)

    class Meta:
        unique_together = [['provider', 'uid']]
```

**Por quê SocialAccount separado e não campos no User:**
- Suporta múltiplos providers futuros (GitHub, Apple) sem migração de schema
- Mantém o model `User` focado em identidade — sem poluição de campos OAuth
- `unique_together` garante que um uid do Google não pode ser vinculado a dois usuários

---

## Service: GoogleOAuthService

```
google_oauth.py
└── class GoogleOAuthService
    ├── get_authorization_url(request) → str
    │     Gera state + nonce com secrets.token_urlsafe(32)
    │     Salva na sessão: request.session['google_oauth_state'] e ['google_oauth_nonce']
    │     Retorna URL de autorização do Google
    │
    ├── handle_callback(request, code, state) → User
    │     Valida state contra sessão (ValueError se inválido)
    │     Chama _exchange_code(code) → tokens dict
    │     Chama _validate_id_token(id_token, nonce) → claims dict
    │     Chama _find_or_create_user(claims) → (User, created)
    │     Retorna User
    │
    ├── _exchange_code(code) → dict          [privado]
    │     POST para https://oauth2.googleapis.com/token
    │     Retorna {access_token, id_token, token_type, ...}
    │
    ├── _validate_id_token(id_token, nonce) → dict   [privado]
    │     google.oauth2.id_token.verify_oauth2_token()
    │     Verifica: assinatura, iss, aud, exp (automático pela lib)
    │     Verifica manualmente: nonce, email_verified
    │     Levanta ValueError em qualquer falha
    │
    └── _find_or_create_user(claims) → tuple[User, bool]   [privado]
          1. Busca SocialAccount(provider='google', uid=claims['sub'])
          2. Se existe → retorna user vinculado
          3. Se não existe → busca User(email=claims['email'])
             (apenas se email_verified=True — garantido pelo passo anterior)
          4. Se User existe → cria SocialAccount e vincula
          5. Se nenhum → cria User + Profile (via signal) + SocialAccount
```

**Lógica de find-or-create detalhada:**

```
claims['sub'] → uid no Google (imutável, primário)
claims['email'] + email_verified=True → fallback para vincular conta existente

Prioridade de busca:
  SocialAccount(uid=sub) → usuário já usou Google antes
  ↓ (não encontrado)
  User(email=email) + email_verified → mesmo email no nosso banco
  ↓ (não encontrado)
  Criar novo User + SocialAccount
```

**Por que email_verified é obrigatório para vincular:**
- Google não exige verificação para criar uma conta
- Um atacante poderia registrar no Google com seu email e tentar sequestrar sua conta
- Sem `email_verified=True`, nunca vinculamos por email

---

## Views

### GoogleLoginView — `GET /api/auth/google/`

```python
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        service = GoogleOAuthService()
        url = service.get_authorization_url(request)
        return redirect(url)
```

### GoogleCallbackView — `GET /api/auth/google/callback/`

```python
class GoogleCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state')

        # Validações básicas de presença
        if not code or not state:
            return redirect(f"{FRONTEND_URL}/auth/error?reason=missing_params")

        try:
            user = GoogleOAuthService().handle_callback(request, code, state)
        except ValueError as e:
            return redirect(f"{FRONTEND_URL}/auth/error?reason=oauth_failed")

        # Emite JWT pair via simplejwt
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        # Fragment — nunca vai ao servidor, não aparece em logs
        return redirect(
            f"{FRONTEND_URL}/auth/callback"
            f"#access={access}&refresh={str(refresh)}"
        )
```

---

## Endpoints

| Método | URL | Permissão | Descrição |
|--------|-----|-----------|-----------|
| GET | `/api/auth/google/` | AllowAny | Inicia fluxo OAuth, redireciona para Google |
| GET | `/api/auth/google/callback/` | AllowAny | Callback do Google, emite JWT e redireciona frontend |

---

## Dependências

```
# requirements.txt
google-auth==2.38.0
google-auth-oauthlib==1.2.1
```

---

## Variáveis de Ambiente

```bash
# .env.local (nunca comitar)
GOOGLE_OAUTH_CLIENT_ID=<client_id_do_google_cloud_console>
GOOGLE_OAUTH_CLIENT_SECRET=<client_secret_do_google_cloud_console>
GOOGLE_OAUTH_REDIRECT_URI=https://api.nousflow.com.br/api/auth/google/callback/
FRONTEND_URL=https://nousflow.com.br

# Para desenvolvimento local
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/google/callback/
FRONTEND_URL=http://localhost:3000
```

**No Google Cloud Console:**
- Authorized redirect URIs:
  - `https://api.nousflow.com.br/api/auth/google/callback/`
  - `http://localhost:8000/api/auth/google/callback/`

---

## Sequência TDD (RED → GREEN → REFACTOR)

### Etapa 1 — Model SocialAccount

```
[ ] RED:   test_social_account_created_with_valid_data
[ ] RED:   test_social_account_uid_unique_per_provider
[ ] RED:   test_social_account_cascade_delete_on_user_delete
[ ] GREEN: implementar SocialAccount model
[ ] GREEN: makemigrations + migrate
[ ] REFACTOR: admin, __str__, Meta
```

### Etapa 2 — GoogleOAuthService: authorization URL

```
[ ] RED:   test_get_authorization_url_returns_google_url
[ ] RED:   test_get_authorization_url_stores_state_in_session
[ ] RED:   test_get_authorization_url_stores_nonce_in_session
[ ] RED:   test_get_authorization_url_state_is_random (dois calls diferentes)
[ ] GREEN: implementar get_authorization_url
[ ] REFACTOR: extrair constantes, type hints, docstring
```

### Etapa 3 — GoogleOAuthService: validação e callback

```
[ ] RED:   test_handle_callback_invalid_state_raises_value_error
[ ] RED:   test_handle_callback_missing_state_in_session_raises
[ ] RED:   test_validate_id_token_invalid_token_raises (mock google verify)
[ ] RED:   test_validate_id_token_email_not_verified_raises
[ ] RED:   test_validate_id_token_nonce_mismatch_raises
[ ] GREEN: implementar _exchange_code + _validate_id_token
[ ] REFACTOR: tratamento de erros, logging
```

### Etapa 4 — GoogleOAuthService: find-or-create user

```
[ ] RED:   test_find_or_create_existing_social_account_returns_user
[ ] RED:   test_find_or_create_existing_email_links_social_account
[ ] RED:   test_find_or_create_new_user_creates_user_and_social_account
[ ] RED:   test_find_or_create_new_user_profile_created_via_signal
[ ] RED:   test_find_or_create_username_generated_from_email
[ ] GREEN: implementar _find_or_create_user
[ ] REFACTOR: extração de helpers, type hints
```

### Etapa 5 — Views e endpoints

```
[ ] RED:   test_google_login_view_redirects_to_google_url
[ ] RED:   test_google_login_view_sets_session_state
[ ] RED:   test_google_callback_missing_code_redirects_to_error
[ ] RED:   test_google_callback_invalid_state_redirects_to_error
[ ] RED:   test_google_callback_success_redirects_with_tokens_in_fragment
[ ] RED:   test_google_callback_new_user_created_in_db
[ ] RED:   test_google_callback_existing_user_receives_jwt
[ ] GREEN: implementar views + URLs
[ ] REFACTOR: tratamento de erros, logging, docstrings
```

### Etapa 6 — Settings e integração

```
[ ] Adicionar GOOGLE_OAUTH_* e FRONTEND_URL em base.py
[ ] Adicionar google-auth* em requirements.txt
[ ] Verificar INSTALLED_APPS (sessions já está)
[ ] Teste de smoke no ambiente de desenvolvimento
```

---

## Checklist de Segurança

Antes de qualquer deploy:

- [ ] `state` gerado com `secrets.token_urlsafe(32)` — nunca determinístico
- [ ] `nonce` gerado com `secrets.token_urlsafe(32)` — validado no id_token
- [ ] `email_verified=True` obrigatório antes de vincular por email
- [ ] `id_token` validado via JWKS (nunca decode ingênuo)
- [ ] `iss` == `"accounts.google.com"` verificado
- [ ] `aud` == `GOOGLE_OAUTH_CLIENT_ID` verificado
- [ ] `exp` verificado (biblioteca faz automaticamente)
- [ ] Sessão regenerada após autenticação (anti session fixation)
- [ ] `GOOGLE_OAUTH_CLIENT_SECRET` nunca logado ou exposto em resposta
- [ ] Redirect URI hardcoded na config do backend (nunca aceito do request)
- [ ] Tokens do Google (access/refresh) não persistidos no banco
- [ ] Erro genérico retornado ao frontend (não vazar detalhes internos)

---

## Fora do Escopo da v1

- **PKCE** — baixo risco no backend-driven flow; pode ser adicionado na v2
- **Endpoint de disconnect** (`DELETE /api/auth/google/disconnect/`) — requer validação de que user tem senha antes de desconectar
- **Outros providers** — GitHub, Apple (SocialAccount model já suporta)
- **Sync periódico** de avatar/nome via Google
- **One Tap Sign-In** (Google Identity Services — fluxo diferente, client-side)

---

## Referências

- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Google OAuth 2.0 Web Server](https://developers.google.com/identity/protocols/oauth2/web-server)
- [google-auth Python](https://pypi.org/project/google-auth/)
- [google-auth-oauthlib](https://pypi.org/project/google-auth-oauthlib/)
- [Discovery Document](https://accounts.google.com/.well-known/openid-configuration)
