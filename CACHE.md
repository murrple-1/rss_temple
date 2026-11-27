# List Keys

```sh
docker compose exec valkey valkey-cli -n <DB_NUM>
> KEYS *
```

# Purge Keys

```sh
docker compose exec valkey valkey-cli -n <DB_NUM>
> FLUSHDB
# or
> FLUSHALL
```
