# /user/{external_id}/transition

`POST /user/{external_id}/transition` executa transicao de role transitoria.

## Request

```json
{ "role": "lead" }
```

| Campo | Descricao |
|-------|-----------|
| `role` | role transitoria de origem |

## Response

```json
{
  "external_id": "327472d5-cd19-4564-89df-e2a4a662c54c",
  "roles": ["student"]
}
```

## Regras

- A role de origem deve ser `is_transitory=true` e ter `transitions_to` definido
- O usuario precisa ter a role de origem ativa
- Desativa a role de origem e ativa a role destino na mesma transacao
- A role destino passa pela validacao de incompatibilidade

## Transicoes definidas

| Origem | Destino |
|--------|---------|
| `lead` | `student` |
| `candidato` | `promotor` |

## Erros

| HTTP | Detalhe |
|------|---------|
| 404 | usuario ou role nao encontrada |
| 400 | role nao e transitoria / nao tem `transitions_to` / usuario nao possui a role |
