# /login/

`POST /login/` recebe `external_id` e `otp`.

OTP: 6 digitos, 15 minutos de validade, uso unico.

## Request

```json
{
  "external_id": "327472d5-cd19-4564-89df-e2a4a662c54c",
  "otp": "123456"
}
```

## Response

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "external_id": "327472d5-cd19-4564-89df-e2a4a662c54c",
  "roles": ["student", "promotor"]
}
```

| Campo | Descricao |
|-------|-----------|
| `access_token` | JWT HS256, 24h |
| `refresh_token` | JWT HS256, 7d |
| `token_type` | "bearer" |
| `external_id` | ID do usuario |
| `roles` | roles ativas do usuario |

## JWT payload

```json
{
  "sub": "327472d5...",
  "roles": ["student", "promotor"],
  "type": "access",
  "exp": 1777178824
}
```

## Rotacao de tokens

Use `POST /refresh/` com o `refresh_token` para obter um novo par.
