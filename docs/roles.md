# Roles

## Modelo

| Campo | Descricao |
|-------|-----------|
| `name` | nome unico da role |
| `is_staff` | permissao interna/staff |
| `is_transitory` | role temporaria de entrada |
| `transitions_to` | role final ao fazer transicao |
| `requires_role` | role obrigatoria antes de ativar esta |
| `incompatible_roles` | roles que nao podem coexistir |
| `description` | texto livre |

## Roles padrão

| Role | Tipo | Regra |
|------|------|-------|
| `lead` | transitory | → `student`, incompativel com `student` |
| `candidato` | transitory | → `promotor`, incompativel com `promotor` |
| `student` | permanente | incompativel com `lead` |
| `promotor` | permanente | incompativel com `candidato` |
| `coordenador` | staff | exige `promotor`, nao substitui |

## Regras de negocio

- Registro: apenas `lead` ou `candidato` (fases iniciais)
- Transicao: `lead→student`, `candidato→promotor`
- Acumulo: um usuario pode estar nas duas trilhas (educacional + comercial)
- Coordenador: adicional sobre `promotor`, nunca sozinho

## Endpoints

### `GET /roles/`
Documentacao (este arquivo).

### `GET /roles/list/`
Lista todas as roles com suas incompatibilidades.

### `POST /roles/`
Cria nova role. Valida que `transitions_to`, `requires_role` e `incompatible_roles` referenciam roles existentes.

### `GET /user/{external_id}/roles`
Roles ativas do usuario.

### `PATCH /user/{external_id}/roles`
Ativa ou desativa uma role para o usuario. Valida `requires_role` e `incompatible_roles` ao ativar.

```json
{ "role": "promotor", "enabled": true }
```

### `POST /user/{external_id}/transition`
Executa transicao de role transitoria. Desativa a role de origem e ativa o destino na mesma transacao.

```json
{ "role": "lead" }
```
