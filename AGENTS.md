# AGENTS.md — rss_temple (backend)

Django + Django REST Framework backend for RSS Temple, a self-hostable RSS/Atom reader. It is one of four
repos; see [Sibling repositories](#sibling-repositories) for the others and when to read them.

## Layout

- `rss_temple/` — Django project: `settings.py` (all config, read from `APP_*` env vars), `urls.py`,
  `preload.py` (warms the URL resolver before gunicorn forks), `testrunner/`. An optional
  `rss_temple/local_settings.py` is star-imported at the end of `settings.py`.
- `api/` — the single main app: `models.py`, `serializers.py`, `views/`, `urls.py`, auth
  (`authentication.py`, `throttling.py`, `account_adapter.py`, `socialaccount_adapter.py`), feed handling
  (`feed_handler.py`, `rss_requests.py`, `content_sanitize.py`), `text_classifier/`, `captcha/`, `opml/`,
  `tasks/` (scheduled job logic), `management/commands/`, `tests/`.
- `api_dramatiq/` — Dramatiq worker (queue `rss_temple`; broker and results on Redis/Valkey dbs 5 and 6).
- `query_utils/` — search/sort/field-selection helpers for the `*/query` endpoints, with their own `tests/`.
- `webserver/Caddyfile.dev` — dev Caddy in front of gunicorn.
- `scripts/` — `run_tests.sh`, `run_tests_nocoverage.sh`, `check_lock_consistency.py`, `post_makemigrations.sh`.
- `docs/superpowers/` — design specs and plans. `DB.md` — Postgres backup, restore and major-version upgrade.

Runtime processes: gunicorn (web), a Dramatiq worker, and `manage.py schedulerdaemon <json>` (APScheduler;
jobs configured as in `schedulerdaemon.example.json`). With `APP_IN_DOCKER=true` the app uses PostgreSQL and
Valkey; otherwise it falls back to SQLite and a local cache (this is what tests use).

## Commands

```sh
pipenv sync --dev                                  # Python 3.14
pipenv run python manage.py test --parallel auto   # tests (Django runner, not pytest)
scripts/run_tests.sh [labels]                      # tests with coverage + HTML report
pipenv run ruff check . && pipenv run ruff format --check .
pipenv run python scripts/check_lock_consistency.py
pipenv run mypy .                                  # configured, not run in CI
```

`TEST_RUNNER_TYPE=timed` reports slow tests (threshold `TEST_SLOW_TEST_THRESHOLD`, default 0.5s).

Full dev stack: copy `.env.example.dev` to `.env`, then
`docker compose -f docker-compose.yml -f docker-compose.override.dev.yml up`. The API is on
`http://localhost:8000`; the web app's dev server expects it there.

CI is CircleCI only (`.circleci/config.yml`): tests, lint, then on `master` push
`murraychristopherson/rss_temple:latest`, and on tags push `:<tag>`.

## API

- `/api/` — everything in `api/urls.py` (routes take an optional trailing slash).
- `/schema/`, `/swagger/`, `/redoc/` — drf-spectacular OpenAPI, generated at runtime. No schema file is
  committed, and the frontend's client is written by hand, not generated from it.
- `/admin/`, and `/silk/` when `APP_ENABLE_SILK` is on (the default).
- Auth classes in order: expiring token, hardened HTTP Basic (`ThrottledVerifiedBasicAuthentication`),
  session. The web app uses session cookies + `X-CSRFToken`.

## Writing tests

- Tests use Django's unittest-style `TestCase` / `SimpleTestCase`, not pytest. App tests are in `api/tests/`.
  View tests are in `api/tests/views/`, and task and management-command tests are in `tasks/` and
  `management/` beside them. `query_utils/tests/` covers the query helpers.
- Shared helpers are in `api/tests/utils.py`, fixtures in `api/tests/fixtures/`, and sample feeds and files in
  `api/tests/test_files/`.
- Tests must not fetch real internet URLs. Tests that need HTTP fetch from Django's live test server
  (`live_server_url`) instead.
- Slow tests are tagged `@tag("slow")`. Pass `--exclude-tag slow` to skip them while you iterate.

## Definition of done

Before calling a change finished:

1. `pipenv run ruff check .` and `pipenv run ruff format --check .` pass.
2. The affected tests pass. Run the full suite if you touched models, settings, auth or `query_utils`.
3. If you changed a model: `pipenv run python manage.py makemigrations` creates the migration, and
   `makemigrations --check` then reports nothing.
4. If a user or operator would notice the change: an entry under `[Unreleased]` in `CHANGELOG.md`, plus an
   "Upgrading" note if operators must do something.
5. If you changed a setting, endpoint or frontend URL: follow the sibling checks below.

## Do not

- Edit a migration that has already shipped in a release tag. Add a new migration instead.
- Edit `Pipfile.lock` by hand. Use `pipenv lock`. CI checks that it matches `Pipfile`.
- Commit `db.sqlite3`, `.env`, `_silk_profiles/`, `rss_temple/local_settings.py` or coverage output.
- Create git tags or push images. A tag is a release, and CI publishes it to Docker Hub.

## Security-sensitive code

Get explicit approval before you weaken any of these:

- **Feed HTML sanitizing** (`api/content_sanitize.py`, bleach). The web app renders feed-entry HTML with
  Angular's sanitizer bypassed (`safeHtml` pipe), so this is the only defence against XSS from feed content.
- **SSRF guard** (`APP_RSS_REQUESTS_BLOCK_PRIVATE_ADDRESSES`, `api/rss_requests.py`). Users submit arbitrary
  feed URLs, so the server must not fetch private or internal addresses.
- **Download and body size limits** (`APP_DOWNLOAD_MAX_BYTE_COUNT`, `APP_USER_ATTRIBUTES_MAX_BYTE_COUNT`).
- **Authentication and throttling** (`api/authentication.py`, `api/throttling.py`, the `REST_FRAMEWORK`
  throttle rates). Throttling uses the client IP worked out from `APP_NUM_PROXIES`, so a wrong value there
  lets clients spoof their IP.
- **CORS, CSRF and cookie settings** in `rss_temple/settings.py`.

## Conventions

- Commit subjects: imperative, sentence case, no conventional-commit prefix.
- `CHANGELOG.md` follows Keep a Changelog. Versions are git tags and match Docker image tags. Add an
  "Upgrading from X" section when operators must act (migrations, gunicorn or schedule changes, new settings).
- `gunicorn.conf.py` uses `preload_app=True`: `kill -HUP` does not load new code; restart the container.
- `purgebulkvotes` and `purgearchivedentries` are dry-run by default; `--no-dry-run` deletes.

## Sibling repositories

RSS Temple is split across four repos, normally checked out side by side. Local paths are relative to this
repo's root. If a sibling is not checked out, use its GitHub URL (for example with `gh`).

| Repo | Local path | GitHub | What it provides |
| --- | --- | --- | --- |
| Backend (this repo) | `.` | https://github.com/murrple-1/rss_temple | Django API, workers, scheduler, `rss_temple` image |
| Frontend | `../rss_temple_ui` | https://github.com/murrple-1/rss_temple_ui | Angular web app and Eleventy landing site, `rss_temple_web_app` and `rss_temple_home` images |
| Deployment | `../ansible-collection-rss-temple` | https://github.com/murrple-1/ansible-collection-rss-temple | Ansible collection `murrple_1.rss_temple` that deploys all images on one server |
| Infrastructure | `../terraform-rss-temple` | https://github.com/murrple-1/terraform-rss-temple | Terraform for the Linode server and firewall |

### When to read them from here

- **Changing an endpoint, serializer or response shape** — the web app's API client is hand-written with zod
  validation: `../rss_temple_ui/rss-temple-web-app/src/app/services/data/*.service.ts`. A changed shape
  breaks it at runtime, not at build time. Check the callers there.
- **Adding or renaming an `APP_*` setting** — production values come from
  `../ansible-collection-rss-temple/roles/rss_temple/templates/.env.j2` and the prompts in
  `playbooks/rss_temple.yml` there. The playbooks never overwrite an existing config file, so a new setting
  also needs an "Upgrading" note in that repo's `CHANGELOG.md`.
- **Auth email links** (`APP_ACCOUNT_CONFIRM_EMAIL_URL`, `APP_PASSWORD_RESET_CONFIRM_URL_FORMAT`,
  `APP_SOCIAL_*_URL`, …) point at web-app routes defined in
  `../rss_temple_ui/rss-temple-web-app/src/app/app.routing.ts` (`/verify`, `/resetpassword`, `/register`,
  `/main/profile`). Keep the two in step.
- **Proxy, host and CORS behaviour** (`APP_NUM_PROXIES`, `APP_ALLOWED_HOSTS`, CSRF/CORS origins) — production
  runs behind two Caddy layers: the infra Caddy (`roles/pre_rss_temple`) and the backend's own Caddy
  (`roles/rss_temple/templates/Caddyfile.j2`) in the Ansible repo.
- **Compose, gunicorn or scheduler changes** — mirror them in the Ansible role's `docker-compose.yml.j2`,
  `gunicorn.conf.py.j2` and `schedulerdaemon.json.j2`.
- **Host-level questions** (OS image, open ports, server size) — `../terraform-rss-temple`.
