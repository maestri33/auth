# /refresh/

`POST /refresh/` renova tokens de acesso.

## Request

```json
{ "refresh_token": "eyJ..." }
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

Mesmo formato do `POST /login/`. Gera novo par de tokens com as roles atuais do usuario.

## Erros

| HTTP | Detalhe |
|------|---------|
| 401 | token invalido ou expirado |
| 404 | usuario nao encontrado (deletado apos emissao) |
