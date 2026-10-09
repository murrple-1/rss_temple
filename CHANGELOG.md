# Changelog

All notable changes to the RSS Temple backend. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions are the git tags, which are also the
`murraychristopherson/rss_temple` Docker image tags.

## [Unreleased]

### Added

- The `purgearchivedentries` management command, which deletes archived feed entries published before a cutoff
  (3 years ago by default). Favorited entries and entries with classifier label votes are kept. Dry-run by default;
  see the README.

## [0.10.0]

### Upgrading from 0.9.4

- **Database migration:** `0041` adds a `weight` column (default `1.0`) to the three calculated classifier label
  tables. Existing rows keep counting as one vote each.
- **Gunicorn `preload_app`:** the image's `gunicorn.conf.py` now loads the app once in the master process. As a
  result, `kill -HUP` no longer picks up new code: restart the container to deploy a change (`docker compose up -d`
  with a new image does this). Deploys that mount their own `gunicorn.conf.py` (such as the Ansible collection's
  `overrides/gunicorn.conf.py`) keep their own settings, and don't get the memory savings unless they set
  `preload_app = True` too.
- **Schedule:** `label_users` now runs at `30 0 * * *` by default, 30 minutes after `label_feeds`. A
  `schedulerdaemon.json` that sets its own `crontab` for either job is unaffected.

### Added

- The `purgebulkvotes` management command, which deletes every classifier label vote belonging to one account (for
  votes applied in bulk by a script rather than by people). Dry-run by default; see the README.
- Calculated classifier labels carry a `weight`, and label ordering sums the weights instead of counting rows. The
  `CLASSIFIER_LABEL_CALCULATED_WEIGHT` setting (`0.5`) caps a machine-calculated label at half a human vote.
- Gunicorn `preload_app`, with the URL resolver warmed up before workers are forked, so the workers share the loaded
  application's memory.

### Changed

- `label_feeds` and `label_users` are rewritten as chunked aggregate queries.
- The classifier label vote-count cache key is now `..._v2`, as the counts became floats. Old entries expire on
  their own.
- Dependency updates, including Django 6.0.6 → 6.1.2, Django REST framework 3.17.1 → 3.18.3, oauthlib 3.3.1 → 4.0.0,
  cryptography 49.0.0 → 50.0.2, urllib3 2.7.0 → 2.8.0 and sqlparse 0.5.5 → 0.6.0.
- CI runs the tests and lint before publishing an image (for `latest` and for tags), smoke-tests the built image
  with `manage.py check`, and fails if `Pipfile.lock`'s `default` and `develop` sections lock different versions.

### Fixed

- The server crashed at startup with `APP_ENABLE_SILK=false`: `api/signals.py` imported `silk.models`
  unconditionally. This affected every earlier release; Silk's signal handler now only loads when Silk is enabled.
- Images built from `master` after 0.9.4 shipped Django 6.1.1 with Django REST framework 3.17.2, which are
  incompatible, while CI tested Django 6.0.6 (`Pipfile.lock`'s `default` and `develop` sections had drifted apart).
  Both sections now lock Django 6.1.2 and DRF 3.18.3.
- Links in feed content now get `rel="noopener noreferrer"`, so an opened page can't reach back to the reader's tab
  through `window.opener` (reverse tabnabbing).
- `label_users` could see an empty table when it ran at the same time as `label_feeds`, which repopulates it.

### Removed

- The CSS sanitizer for feed content, which was redundant: `style` tags and attributes are already stripped.

## [0.9.4] - 2026-07-02

[0.10.0]: https://github.com/murrple-1/rss_temple/compare/0.9.4...0.10.0
[0.9.4]: https://github.com/murrple-1/rss_temple/releases/tag/0.9.4
