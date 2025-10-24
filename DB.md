# Backup

```sh
docker compose exec postgresql pg_dumpall -c --if-exists -U postgres | gzip > dump.sql.gz
```

# Restore

```sh
zcat dump.sql.gz | docker compose exec -T postgresql psql -U postgres
docker compose exec postgresql psql -U postgres
> ALTER USER postgres WITH PASSWORD 'password';
```

# Update

Done using https://github.com/pgautoupgrade/docker-pgautoupgrade

```sh
docker compose stop
docker compose up -d postgresql
docker compose exec postgresql pg_dumpall -c --if-exists -U postgres | gzip > backup.sql.gz
docker compose down
docker run --rm --mount type=volume,src=rss_temple_db_data,dst=/var/lib/postgresql -e POSTGRES_PASSWORD=<PG_ADMIN_PASSWORD> -e PGAUTO_ONESHOT=yes pgautoupgrade/pgautoupgrade:<NEW_PG_VERSION>-alpine
git pull
docker compose up -d
```
