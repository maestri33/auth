# /config/

Configuracao do servico Auth.

## `GET /config/`

Retorna configuracao atual (banco ou defaults).

```json
{
  "notify_base_url": "http://10.10.10.119:8000",
  "notify_cli": "notify"
}
```

## `POST /config/`

Atualiza configuracao no banco. Ambos os campos sao opcionais.

```json
{
  "notify_base_url": "http://10.10.10.119:8000",
  "notify_cli": "notify"
}
```

| Campo | Descricao |
|-------|-----------|
| `notify_base_url` | URL base do servico Notify |
| `notify_cli` | caminho do binario `notify` para fallback |
