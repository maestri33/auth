# /check/

`POST /check/` recebe `{ "phone": "..." }`.

Endpoint somente leitura -- nao gera OTP, nao cria usuarios, nao envia notificacoes.

## Request

```json
{ "phone": "43996648750" }
```

## Response

```json
{
  "found_in_notify": true,
  "found_locally": true,
  "notify_external_id": "id-no-notify",
  "local_external_id": "id-no-auth",
  "whatsapp_valid": true
}
```

| Campo | Descricao |
|-------|-----------|
| `found_in_notify` | telefone existe no Notify |
| `found_locally` | telefone existe em `auth.db` |
| `notify_external_id` | external_id no Notify (pode divergir do local) |
| `local_external_id` | external_id no Auth, fonte de verdade |
| `whatsapp_valid` | status WhatsApp: `true`, `false`, ou `null` |

## Proximos passos

- `found_locally=false` → `POST /register/`
- `found_locally=true` → `POST /otp/request` → `POST /login/`
