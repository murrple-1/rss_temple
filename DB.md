# Backup

```sh
docker compose exec postgresql pg_dumpall -c --if-exists -U postgres | gzip > dump.sql.gz`
```

# Restore

```sh
gunzip dump.sql.gz
docker compose exec -T postgresql psql -U postgres < dump.sql
docker compose exec postgresql psql -U postgres
> ALTER USER postgres WITH PASSWORD 'password';
```
