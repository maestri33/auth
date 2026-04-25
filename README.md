# Auth

Servico FastAPI de autenticacao via OTP + JWT, com OAuth2 client_credentials para apps consumidores (M2M).

Fonte de verdade para identidade e roles. Apps downstream autenticam-se via M2M, validam tokens de usuario e consultam roles aqui.

## Stack

- FastAPI 0.115+, Pydantic v2, pydantic-settings
- SQLAlchemy 2.0 async (aiosqlite / asyncpg)
- Alembic para migracoes
- PyJWT (HS256, com `kid`)
- slowapi para rate limit
- pytest + httpx AsyncClient

## Estrutura (por dominio)

```
src/auth_service/
├── main.py                 # create_app(), CORS, slowapi, /healthz
├── core/
│   ├── config.py           # BaseSettings (pydantic-settings) + bootstrap do JWT secret
│   ├── database.py         # async engine, AsyncSession, Base
│   ├── security.py         # OTP (PBKDF2), JWT (PyJWT), client_secret hashing
│   ├── rate_limit.py       # slowapi Limiter
│   ├── deps.py             # DbSession, get_current_client, require_scopes
│   ├── docs.py             # leitor de markdown
│   └── exceptions.py
├── auth/                   # /check, /register, /otp/request, /login, /refresh, /.well-known/auth
├── users/                  # User, UserRole, OtpChallenge + /user/{id}/roles, /user/{id}/transition
├── roles/                  # Role, RoleIncompatibility + /roles/, /roles/list/
├── config_app/             # AppConfig + /config/
├── clients/                # OAuth2 client_credentials + /oauth/token, /oauth/clients/
└── notify/                 # cliente HTTP async + fallback CLI (com regex de seguranca)
alembic/                    # migracoes (initial em 0001)
tests/                      # pytest async + suite live opt-in
docs/                       # markdown servido nos GET das rotas
notify/                     # template otp.md
```

## Rodar (dev)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# aplica schema
.venv/bin/alembic upgrade head

# subir
.venv/bin/uvicorn auth_service.main:app --host 0.0.0.0 --port 80
```

Docs: `http://host/docs` · Discovery: `http://host/.well-known/auth` · Health: `http://host/healthz`

## Variaveis de ambiente

Veja `.env.example`. Principais:

| Var | Default | Notas |
|---|---|---|
| `AUTH_ENV` | `dev` | `prod` exige `AUTH_JWT_SECRET` ou arquivo populado |
| `AUTH_DATABASE_URL` | `sqlite+aiosqlite:///./auth.db` | troque para `postgresql+asyncpg://...` |
| `AUTH_JWT_SECRET` | — | preferido em prod |
| `AUTH_JWT_SECRET_FILE` | — | caminho para arquivo com o secret |
| `AUTH_STATE_DIR` | `./.state` | onde o secret e auto-gerado em dev |
| `AUTH_JWT_KEY_ID` | `v1` | enviado no header `kid` do JWT |
| `AUTH_ACCESS_TOKEN_MINUTES` | `60` | |
| `AUTH_REFRESH_TOKEN_DAYS` | `7` | |
| `AUTH_OTP_TTL_MINUTES` | `15` | |
| `AUTH_NOTIFY_BASE_URL` | `http://10.10.10.119:8000` | servico Notify |
| `AUTH_RATELIMIT_OTP` | `5/minute` | slowapi |
| `AUTH_RATELIMIT_LOGIN` | `10/minute` | |
| `AUTH_RATELIMIT_OAUTH` | `30/minute` | |

### Bootstrap do JWT secret

Prioridade: `AUTH_JWT_SECRET` > `AUTH_JWT_SECRET_FILE` > `<state_dir>/jwt_secret`. Em `dev`/`test`, se nada estiver setado, e auto-gerado (64 bytes urlsafe) e persistido com `0600`. Em `prod` falha rapido se ausente.

## Fluxo do usuario (OTP + JWT)

```
POST /check/         → existe no Notify? localmente?
POST /register/      → cria usuario (lead | candidato)
POST /otp/request    → gera OTP, envia via Notify (5/min)
POST /login/         → valida OTP, retorna access (60m) + refresh (7d) (10/min)
POST /refresh/       → renova ambos
```

OTP: PBKDF2-SHA256 (120k iter), comparison timing-safe. `consume_otp` e atomico (UPDATE…WHERE consumed_at IS NULL).

## M2M OAuth2 (client_credentials)

Apps consumidores autenticam-se com `client_id` + `client_secret` e recebem um token JWT do tipo `client` com escopos.

```http
POST /oauth/token
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "app-x",
  "client_secret": "<secret>",
  "scope": "admin"
}
```

Resposta:
```json
{ "access_token": "...", "token_type": "Bearer", "expires_in": 3600, "scope": "admin" }
```

Use em endpoints administrativos via `Authorization: Bearer <token>`.

### Endpoints protegidos por escopo `admin`

- `POST /config/`
- `POST /roles/`
- `PATCH /user/{id}/roles`
- `POST /user/{id}/transition`
- `GET  /oauth/clients/`
- `POST /oauth/clients/`

### Bootstrap de um client admin

Antes de tudo, crie o primeiro client direto no DB (ou via script). Exemplo Python ad hoc:

```python
import asyncio
from auth_service.clients.models import OAuthClient
from auth_service.core.database import SessionLocal
from auth_service.core.security import generate_client_secret, hash_client_secret

async def main():
    secret = generate_client_secret()
    async with SessionLocal() as db:
        db.add(OAuthClient(
            client_id="bootstrap",
            client_secret_hash=hash_client_secret(secret),
            name="bootstrap",
            scopes="admin",
        ))
        await db.commit()
    print("client_id=bootstrap")
    print("client_secret=", secret)

asyncio.run(main())
```

A partir dele, use `POST /oauth/clients/` para criar os demais (resposta retorna o secret em texto plano UMA vez).

## Roles

| Role | Tipo | Regra |
|------|------|-------|
| `lead` | transitory | → `student`, incompativel com `student` |
| `candidato` | transitory | → `promotor`, incompativel com `promotor` |
| `student` | permanente | incompativel com `lead` |
| `promotor` | permanente | incompativel com `candidato` |
| `coordenador` | staff | exige `promotor` |

## JWT

Header: `{"alg":"HS256","typ":"JWT","kid":"v1"}`. Payload comum:

```json
{
  "iss": "auth",
  "sub": "<external_id | client_id>",
  "roles":  ["student"],          // tokens de usuario
  "scopes": ["admin"],            // tokens M2M
  "type":  "access" | "refresh" | "client",
  "iat": 1777178824,
  "exp": 1777182424
}
```

`decode_token` rejeita token com `type` errado — refresh nao serve como access e vice-versa.

## Migracoes

```bash
.venv/bin/alembic upgrade head                       # aplicar
.venv/bin/alembic revision --autogenerate -m "msg"   # nova migration
```

## Testes

```bash
.venv/bin/pytest                          # suite normal (sem live)
.venv/bin/pytest -m notify_live           # exige Notify em AUTH_NOTIFY_BASE_URL
```

## Lint

```bash
.venv/bin/ruff check src tests
.venv/bin/ruff format src tests
```
