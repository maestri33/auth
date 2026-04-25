# Auth

Servico FastAPI de autenticacao via OTP e JWT.

Fonte de verdade para identidade e roles. Downstream apps validam tokens e consultam roles aqui.

## Fluxo do usuario

```
POST /check/      →  verifica se telefone existe
POST /register/   →  cadastra como lead ou candidato
POST /otp/request →  envia OTP via WhatsApp
POST /login/      →  valida OTP, retorna access + refresh tokens
POST /refresh/    →  renova tokens expirados
```

## Estrutura

```
auth/
├── main.py                # app, lifespan, CORS, routers
├── routers/
│   ├── auth.py            # /check/, /register/, /otp/request, /login/, /refresh/, /.well-known/auth
│   ├── users.py           # /roles/, /user/{id}/roles, /user/{id}/transition
│   └── config.py          # /config/
├── services.py            # logica de negocio
├── models.py              # SQLAlchemy ORM
├── schemas.py             # Pydantic request/response
├── security.py            # OTP + JWT (HMAC-SHA256)
├── notify_client.py       # cliente HTTP async para Notify
├── database.py            # engine e sessao
├── config.py              # settings via env vars
└── docs.py                # leitor de markdown
```

## Rodar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn auth.main:app --host 0.0.0.0 --port 80
```

Docs interativas: `http://localhost:80/docs`
Discovery: `http://localhost:80/.well-known/auth`

## Variaveis de ambiente

```bash
AUTH_JWT_SECRET_KEY="troque-isto"
AUTH_NOTIFY_BASE_URL="http://10.10.10.119:8000"
AUTH_NOTIFY_CLI="notify"
AUTH_ACCESS_TOKEN_MINUTES=1440
AUTH_REFRESH_TOKEN_DAYS=7
AUTH_OTP_TTL_MINUTES=15
AUTH_NOTIFY_TIMEOUT_SECONDS=10.0
```

## Endpoints

### Configuracao

| Método | Path | Descricao |
|--------|------|-----------|
| GET | `/config/` | consultar configuracao |
| POST | `/config/` | atualizar configuracao |

### Autenticacao

| Método | Path | Descricao |
|--------|------|-----------|
| GET | `/check/` | doc |
| POST | `/check/` | verifica telefone no Notify e localmente (read-only) |
| GET | `/register/` | doc |
| POST | `/register/` | cadastra usuario (`lead` ou `candidato`) |
| GET | `/otp/request` | doc |
| POST | `/otp/request` | gera e envia OTP via WhatsApp |
| GET | `/login/` | doc |
| POST | `/login/` | valida OTP, retorna tokens JWT |
| GET | `/refresh/` | doc |
| POST | `/refresh/` | renova tokens |

### Roles

| Método | Path | Descricao |
|--------|------|-----------|
| GET | `/roles/` | doc |
| GET | `/roles/list/` | lista todas as roles |
| POST | `/roles/` | cria role |
| GET | `/user/transition` | doc |
| POST | `/user/{external_id}/transition` | transicao (`lead→student`, `candidato→promotor`) |
| GET | `/user/{external_id}/roles` | roles ativas do usuario |
| PATCH | `/user/{external_id}/roles` | ativa/desativa role no usuario |

### Discovery

| Método | Path | Descricao |
|--------|------|-----------|
| GET | `/.well-known/auth` | algoritmo JWT, roles, endpoints |

## JWT

Algoritmo HMAC-SHA256. Access token 24h, refresh token 7d.

Payload:
```json
{
  "sub": "external_id",
  "roles": ["student", "promotor"],
  "type": "access",
  "exp": 1777178824
}
```

## Roles

| Role | Tipo | Regra |
|------|------|-------|
| `lead` | transitory | → `student`, incompativel com `student` |
| `candidato` | transitory | → `promotor`, incompativel com `promotor` |
| `student` | permanente | incompativel com `lead` |
| `promotor` | permanente | incompativel com `candidato` |
| `coordenador` | staff | exige `promotor` |
