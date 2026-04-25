# /register/

`POST /register/` cadastra usuario no sistema.

## Request

```json
{
  "phone": "43996648750",
  "role": "lead"
}
```

| Campo | Descricao |
|-------|-----------|
| `phone` | telefone com DDD, 8 a 32 caracteres |
| `role` | role inicial: `lead` ou `candidato` |

## Regras

- Role deve ser uma das fases iniciais: `lead` ou `candidato`
- Telefone nao pode estar cadastrado (409 se duplicado)
- Cria recipient no Notify com o mesmo `external_id` gerado pelo Auth
- **Nao envia notificacao de boas-vindas**

## Response

```json
{
  "status": "ok",
  "message": "cadastro realizado com sucesso",
  "external_id": "327472d5-cd19-4564-89df-e2a4a662c54c",
  "role": "lead"
}
```

## Erros

| HTTP | Detalhe |
|------|---------|
| 404 | role nao encontrada |
| 400 | role nao e fase inicial |
| 409 | telefone ja cadastrado |
