# /otp/request

`POST /otp/request` gera e envia OTP para usuario existente.

## Request

```json
{ "external_id": "327472d5-cd19-4564-89df-e2a4a662c54c" }
```

ou

```json
{ "phone": "43996648750" }
```

| Campo | Descricao |
|-------|-----------|
| `external_id` | ID do usuario (preferencial) |
| `phone` | telefone alternativo se nao tiver external_id |

Pelo menos um dos dois e obrigatorio. Se ambos forem enviados, `external_id` tem precedencia.

## Response

```json
{
  "status": "ok",
  "message": "otp enviado com sucesso",
  "external_id": "327472d5-cd19-4564-89df-e2a4a662c54c"
}
```

## Erros

| HTTP | Detalhe |
|------|---------|
| 400 | informe external_id ou phone |
| 404 | usuario nao encontrado |

Apos receber o OTP no WhatsApp, use `POST /login/`.
