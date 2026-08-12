# Classifier Aggregation and Resource Reclamation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give machine-generated classifier labels a confidence weight, stop discarding scores the labelling tasks already compute, cut those tasks from O(rows) queries to O(chunks), purge 253k bulk-import votes, and reclaim gunicorn worker memory.

**Architecture:** Add a `weight` FloatField to the three `ClassifierLabel*Calculated` tables. Change the vote-count aggregation from `COUNT(*)` to `COALESCE(SUM(weight), 0)` and bump the cache key. Rewrite `label_feeds`/`label_users` from one-query-per-entity to chunked two-query aggregates. Add an operator-run purge command. Enable `preload_app` in gunicorn.

**Tech Stack:** Django 6 + DRF, PostgreSQL 18 (SQLite for tests), Valkey/Redis via `django-redis`, dramatiq + APScheduler, `manage.py test` with `coverage`.

**Spec:** `docs/superpowers/specs/2026-07-30-classifier-reclamation-design.md`

## Global Constraints

- Python 3.14. `itertools.batched` is available and preferred over hand-rolled chunking.
- Tests run against **SQLite**, production runs **PostgreSQL 18**. Any raw SQL must work on both — `api/cache_utils/classifier_label_vote_counts.py` already has a `connection.vendor == "sqlite"` branch for UUID parameter binding. Do not add PostgreSQL-only migration operations (e.g. `AddIndexConcurrently`).
- **Test command.** The project's canonical runner is `./scripts/run_tests.sh [dotted.test.path]`,
  which wraps `pipenv run coverage run manage.py test`. On this machine `pipenv` is a pyenv shim
  resolving to a Python version that does not have it installed, so that script silently runs
  nothing and still exits 0. Use the project venv directly instead:

  ```sh
  /home/mchristo/.local/share/virtualenvs/rss_temple-pQQQnncW/bin/python manage.py test [dotted.test.path]
  ```

  Baseline on a clean tree: **334 tests, 0 failures, ~11s**. Wherever a step below says
  `./scripts/run_tests.sh X`, run the venv-python form with the same argument.
- `pre-commit` runs `ruff --fix` and `ruff-format` on commit. Let it reformat; re-stage if it does.
- After `makemigrations`, run `./scripts/post_makemigrations.sh` to fix file ownership/permissions.
- Type annotations are checked by pyright. Do not use `collections.Counter` for float scores — `Counter[T]` is typed for int values. Use `defaultdict[K, float]`.
- Existing test style: `django.test.TestCase`, class-level logger suppression (see `api/tests/tasks/test_label_feeds.py`). Follow it.
- Human votes are implicitly weight `1.0`. `ClassifierLabelFeedEntryVote` gets **no** weight column.

---

### Task 1: Add `weight` to the three calculated-label tables

**Files:**
- Modify: `api/models.py` (imports; `ClassifierLabelFeedEntryCalculated`, `ClassifierLabelFeedCalculated`, `ClassifierLabelUserCalculated`)
- Modify: `rss_temple/settings.py:493` (after `LABELING_EXPIRY_INTERVAL`)
- Create: `api/migrations/0041_*.py` (generated)
- Test: `api/tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ClassifierLabelFeedEntryCalculated.weight: float`, `ClassifierLabelFeedCalculated.weight: float`, `ClassifierLabelUserCalculated.weight: float`, all `default=1.0`, all validated `>= 0.0`. Setting `settings.CLASSIFIER_LABEL_CALCULATED_WEIGHT: float = 0.5`.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_models.py`:

```python
class ClassifierLabelWeightTestCase(TestCase):
    def test_calculated_weight_defaults_to_one(self):
        now = timezone.now()
        label = ClassifierLabel.objects.create(text="Label 1")
        feed = Feed.objects.create(
            feed_url="http://example.com/rss.xml",
            title="Sample Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entry = FeedEntry.objects.create(
            feed=feed,
            published_at=now,
            title="Entry",
            url="http://example.com/entry.html",
            content="content",
            author_name="John Doe",
            db_updated_at=None,
            is_archived=False,
        )
        user = User.objects.create_user("weight@test.com", None)

        entry_calc = ClassifierLabelFeedEntryCalculated.objects.create(
            classifier_label=label,
            feed_entry=feed_entry,
            expires_at=now + datetime.timedelta(days=7),
        )
        feed_calc = ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label,
            feed=feed,
            expires_at=now + datetime.timedelta(days=7),
        )
        user_calc = ClassifierLabelUserCalculated.objects.create(
            classifier_label=label,
            user=user,
            expires_at=now + datetime.timedelta(days=7),
        )

        self.assertEqual(entry_calc.weight, 1.0)
        self.assertEqual(feed_calc.weight, 1.0)
        self.assertEqual(user_calc.weight, 1.0)

    def test_calculated_weight_rejects_negative(self):
        now = timezone.now()
        label = ClassifierLabel.objects.create(text="Label 2")
        feed = Feed.objects.create(
            feed_url="http://example.com/rss2.xml",
            title="Sample Feed 2",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        obj = ClassifierLabelFeedCalculated(
            classifier_label=label,
            feed=feed,
            expires_at=now + datetime.timedelta(days=7),
            weight=-0.5,
        )
        with self.assertRaises(ValidationError):
            obj.full_clean()
```

Add whatever of these imports `api/tests/test_models.py` is missing at the top: `datetime`, `django.core.exceptions.ValidationError`, `django.utils.timezone`, and from `api.models`: `ClassifierLabel`, `ClassifierLabelFeedCalculated`, `ClassifierLabelFeedEntryCalculated`, `ClassifierLabelUserCalculated`, `Feed`, `FeedEntry`, `User`.

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/run_tests.sh api.tests.test_models.ClassifierLabelWeightTestCase`
Expected: FAIL — `TypeError: ClassifierLabelFeedEntryCalculated() got unexpected keyword arguments: 'weight'` (or `AttributeError` on `.weight`).

- [ ] **Step 3: Add the field to all three models**

In `api/models.py`, add to the existing `django.core.validators` import (create the import line if absent):

```python
from django.core.validators import MinValueValidator
```

Then add this identical line to `ClassifierLabelFeedEntryCalculated`, `ClassifierLabelFeedCalculated`, and `ClassifierLabelUserCalculated`, immediately after each class's `expires_at` field:

```python
    weight = models.FloatField(default=1.0, validators=[MinValueValidator(0.0)])
```

- [ ] **Step 4: Generate and tidy the migration**

```bash
pipenv run python manage.py makemigrations api
./scripts/post_makemigrations.sh
```

Expected: one new file, `api/migrations/0041_<autogenerated_name>.py`, containing three `AddField` operations. Open it and confirm there are exactly three and nothing else — if `makemigrations` picked up unrelated drift, stop and investigate before continuing.

- [ ] **Step 5: Add the setting**

In `rss_temple/settings.py`, immediately after `LABELING_EXPIRY_INTERVAL = datetime.timedelta(days=7)` (line 493):

```python
# Multiplier applied to a classifier's predicted probability when it is written
# to ClassifierLabelFeedEntryCalculated.weight. Caps a maximally-confident
# machine label at half a human vote. Consumed by the classifier (spec 2).
CLASSIFIER_LABEL_CALCULATED_WEIGHT = 0.5
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.test_models.ClassifierLabelWeightTestCase`
Expected: PASS, 2 tests.

- [ ] **Step 7: Verify the migration is behaviourally a no-op**

Run: `./scripts/run_tests.sh api.tests.tasks.test_label_feeds api.tests.tasks.test_label_users api.tests.views.test_classifier_label`
Expected: PASS, unchanged. `default=1.0` means existing behaviour is preserved exactly — if any of these fail, the field definition is wrong.

- [ ] **Step 8: Commit**

```bash
git add api/models.py api/migrations/ rss_temple/settings.py api/tests/test_models.py
git commit -m "add weight column to calculated classifier label tables"
```

---

### Task 2: Weighted vote-count aggregation and cache key bump

**Files:**
- Modify: `api/cache_utils/classifier_label_vote_counts.py`
- Modify: `api/views/classifier_label.py:58-71` (the `Case`/`When` annotation and its imports)
- Test: `api/tests/views/test_classifier_label.py`

**Interfaces:**
- Consumes: `ClassifierLabelFeedEntryCalculated.weight` (Task 1).
- Produces: `get_classifier_label_vote_counts_from_cache(feed_entry_uuids, cache) -> _GetClassifierLabelVoteCountsFromCacheResults` where `classifier_label_vote_counts` is now `dict[UUID, dict[UUID, float]]` (was `dict[UUID, dict[UUID, int]]`). Cache keys are now prefixed `classifier_label_vote_counts_v2__`.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/views/test_classifier_label.py` (inside the existing test case class, or as a new `TestCase` reusing the same setup style):

```python
    def test_calculated_weight_contributes_fractionally(self):
        now = timezone.now()
        label1 = ClassifierLabel.objects.create(text="Weighted Label 1")
        label2 = ClassifierLabel.objects.create(text="Weighted Label 2")

        feed = Feed.objects.create(
            feed_url="http://example.com/weighted.xml",
            title="Weighted Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entry = FeedEntry.objects.create(
            feed=feed,
            published_at=now,
            title="Entry",
            url="http://example.com/weighted-entry.html",
            content="content",
            author_name="John Doe",
            db_updated_at=None,
            is_archived=False,
        )

        # label1: one human vote  -> 1.0
        ClassifierLabelFeedEntryVote.objects.create(
            classifier_label=label1, feed_entry=feed_entry, user=self.user
        )
        # label2: two calculated labels at 0.25 -> 0.5, so label1 must rank higher
        ClassifierLabelFeedEntryCalculated.objects.create(
            classifier_label=label2,
            feed_entry=feed_entry,
            expires_at=now + datetime.timedelta(days=7),
            weight=0.25,
        )

        cache = caches["default"]
        cache.clear()

        counts, _ = get_classifier_label_vote_counts_from_cache(
            (feed_entry.uuid,), cache
        )
        vote_counts = counts[feed_entry.uuid]

        self.assertAlmostEqual(vote_counts[label1.uuid], 1.0)
        self.assertAlmostEqual(vote_counts[label2.uuid], 0.25)

    def test_cache_key_is_versioned(self):
        self.assertTrue(
            _CACHE_KEY_PREFIX.startswith("classifier_label_vote_counts_v2__")
        )
```

Add imports as needed: `from django.core.cache import caches`, and from `api.cache_utils.classifier_label_vote_counts`: `_CACHE_KEY_PREFIX`, `get_classifier_label_vote_counts_from_cache`. Replace `self.user` with whatever the surrounding test case uses (the existing file uses a class attribute `ClassifierLabelTestCase.user`).

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/run_tests.sh api.tests.views.test_classifier_label`
Expected: FAIL — `ImportError: cannot import name '_CACHE_KEY_PREFIX'`, and once that is stubbed, the weight assertion fails because the current SQL counts rows (`1.0`) rather than summing weights (`0.25`).

- [ ] **Step 3: Update the cache util**

In `api/cache_utils/classifier_label_vote_counts.py`:

Add a module constant below the imports:

```python
# Bumped to _v2 when calculated labels gained a `weight` column and vote counts
# became floats. Old int-valued entries under the _v1 key expire untouched.
_CACHE_KEY_PREFIX = "classifier_label_vote_counts_v2__"
```

Replace the two hardcoded key literals. In `_generate_cached_entries`:

```python
    cache_entries: dict[str, dict[uuid_.UUID, float] | None] = cache.get_many(
        f"{_CACHE_KEY_PREFIX}{fe_uuid}" for fe_uuid in feed_entry_uuids
    )

    for key, entry in cache_entries.items():
        if entry is not None:
            feed_entry_uuid = uuid_.UUID(key.removeprefix(_CACHE_KEY_PREFIX))
            yield feed_entry_uuid, entry
```

And in `get_classifier_label_vote_counts_from_cache`'s `cache.set_many` call:

```python
        cache.set_many(
            {
                f"{_CACHE_KEY_PREFIX}{feed_entry_uuid}": vote_counts
                for feed_entry_uuid, vote_counts in missing_classifier_label_vote_counts.items()
            },
            _CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS,
        )
```

Change the second subquery in the raw SQL from a row count to a weight sum:

```sql
                ) + (
                    SELECT
                        COALESCE(SUM(u2."weight"), 0)
                    FROM
                        {ClassifierLabelFeedEntryCalculated._meta.db_table} AS u2
                    WHERE
                        u2."classifier_label_id" = t1."uuid"
                        AND u2."feed_entry_id" = t2."uuid"
                )
```

Change every `int` in the vote-count type annotations to `float`:
- `_generate_cached_entries` return type: `Generator[tuple[uuid_.UUID, dict[uuid_.UUID, float]], None, None]`
- `_GetClassifierLabelVoteCountsFromCacheResults.classifier_label_vote_counts: dict[uuid_.UUID, dict[uuid_.UUID, float]]`
- the local `classifier_label_vote_counts` and `missing_classifier_label_vote_counts` declarations

- [ ] **Step 4: Update the view annotation**

In `api/views/classifier_label.py`, change the import of `IntegerField` to `FloatField` (verify `IntegerField` is not used elsewhere in the file first — as of writing it is not), and in `ClassifierLabelListView.get`:

```python
            classifier_labels = ClassifierLabel.objects.annotate(
                vote_count=Case(
                    *(
                        When(condition=Q(uuid=uuid), then=Value(count))
                        for uuid, count in vote_counts.items()
                    ),
                    default=Value(-1.0),
                    output_field=FloatField(),
                )
            ).order_by("-vote_count", "?")
```

`ClassifierLabelListByEntryView` needs no change — it sorts `(vote_count, random.random())` tuples in Python, which works unchanged with floats.

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.views.test_classifier_label`
Expected: PASS, including the pre-existing tests.

- [ ] **Step 6: Run the broader suite**

Run: `./scripts/run_tests.sh api.tests.views api.tests.tasks`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/cache_utils/classifier_label_vote_counts.py api/views/classifier_label.py api/tests/views/test_classifier_label.py
git commit -m "sum calculated label weights instead of counting rows"
```

---

### Task 3: Rewrite `label_feeds` as a chunked aggregate

**Files:**
- Modify: `api/tasks/label_feeds.py` (full rewrite)
- Test: `api/tests/tasks/test_label_feeds.py`

**Interfaces:**
- Consumes: `ClassifierLabelFeedEntryCalculated.weight` (Task 1).
- Produces: `label_feeds(top_x: int, expiry_interval: datetime.timedelta, chunk_size: int = 500) -> None`. Writes `ClassifierLabelFeedCalculated` rows carrying `weight` = the feed's summed score for that label.

**Behaviour change to be aware of:** the current implementation builds a `Counter` over *all* labels (most with a count of zero) and writes `top_x` of them regardless, so every feed in the database ends up claiming `top_x` topics even with no evidence. The rewrite writes rows **only for (feed, label) pairs with a non-zero score**, and drives iteration from feeds that actually have votes or calculated entry labels rather than from "every feed lacking a row". Zero-weight rows would be actively harmful once a recommender ranks by weight.

- [ ] **Step 1: Write the failing test**

Add to `api/tests/tasks/test_label_feeds.py` (the file already defines `TaskTestCase` with logger suppression — add these as methods on it):

```python
    def test_label_feeds_populates_weight(self):
        now = timezone.now()
        user = User.objects.create_user("weight-feeds@test.com", None)
        label1 = ClassifierLabel.objects.create(text="Label 1")
        label2 = ClassifierLabel.objects.create(text="Label 2")

        feed = Feed.objects.create(
            feed_url="http://example.com/weight.xml",
            title="Weight Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entries = FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Entry {i}",
                url=f"http://example.com/w{i}.html",
                content=f"content {i}",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )
            for i in range(4)
        )

        # label1: 2 human votes -> 2.0
        ClassifierLabelFeedEntryVote.objects.bulk_create(
            ClassifierLabelFeedEntryVote(
                feed_entry=fe, classifier_label=label1, user=user
            )
            for fe in feed_entries[0:2]
        )
        # label2: 2 calculated at 0.25 -> 0.5
        ClassifierLabelFeedEntryCalculated.objects.bulk_create(
            ClassifierLabelFeedEntryCalculated(
                feed_entry=fe,
                classifier_label=label2,
                expires_at=now + datetime.timedelta(days=7),
                weight=0.25,
            )
            for fe in feed_entries[2:4]
        )

        label_feeds(3, datetime.timedelta(days=7))

        rows = {
            r.classifier_label_id: r.weight
            for r in ClassifierLabelFeedCalculated.objects.filter(feed=feed)
        }
        self.assertAlmostEqual(rows[label1.uuid], 2.0)
        self.assertAlmostEqual(rows[label2.uuid], 0.5)

    def test_label_feeds_skips_feeds_without_signal(self):
        now = timezone.now()
        Feed.objects.create(
            feed_url="http://example.com/silent.xml",
            title="Silent Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )

        label_feeds(3, datetime.timedelta(days=7))

        self.assertEqual(ClassifierLabelFeedCalculated.objects.count(), 0)

    def test_label_feeds_respects_top_x(self):
        now = timezone.now()
        user = User.objects.create_user("topx@test.com", None)
        labels = [
            ClassifierLabel.objects.create(text=f"Top Label {i}") for i in range(5)
        ]
        feed = Feed.objects.create(
            feed_url="http://example.com/topx.xml",
            title="TopX Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entry = FeedEntry.objects.create(
            feed=feed,
            published_at=now,
            title="Entry",
            url="http://example.com/topx-entry.html",
            content="content",
            author_name="John Doe",
            db_updated_at=None,
            is_archived=False,
        )
        for label in labels:
            ClassifierLabelFeedEntryVote.objects.create(
                feed_entry=feed_entry, classifier_label=label, user=user
            )

        label_feeds(2, datetime.timedelta(days=7))

        self.assertEqual(
            ClassifierLabelFeedCalculated.objects.filter(feed=feed).count(), 2
        )

    def test_label_feeds_chunk_boundaries(self):
        now = timezone.now()
        user = User.objects.create_user("chunks@test.com", None)
        label = ClassifierLabel.objects.create(text="Chunk Label")

        for i in range(3):
            feed = Feed.objects.create(
                feed_url=f"http://example.com/chunk{i}.xml",
                title=f"Chunk Feed {i}",
                home_url="http://example.com",
                published_at=now,
                updated_at=None,
                db_updated_at=None,
            )
            feed_entry = FeedEntry.objects.create(
                feed=feed,
                published_at=now,
                title=f"Entry {i}",
                url=f"http://example.com/chunk-entry{i}.html",
                content="content",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )
            ClassifierLabelFeedEntryVote.objects.create(
                feed_entry=feed_entry, classifier_label=label, user=user
            )

        label_feeds(3, datetime.timedelta(days=7), chunk_size=2)

        self.assertEqual(ClassifierLabelFeedCalculated.objects.count(), 3)
```

Add `ClassifierLabelFeedCalculated` to the existing `api.models` import in that file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.tasks.test_label_feeds`
Expected: FAIL — `test_label_feeds_populates_weight` fails (weights are all `1.0` from the default, not the summed score), `test_label_feeds_skips_feeds_without_signal` fails (the current implementation writes zero-score rows for every feed), and `test_label_feeds_chunk_boundaries` fails with `TypeError: label_feeds() got an unexpected keyword argument 'chunk_size'`.

- [ ] **Step 3: Rewrite `api/tasks/label_feeds.py`**

Replace the entire file with:

```python
import datetime
import uuid as uuid_
from collections import defaultdict
from itertools import batched

from django.db.models import Count, Sum
from django.db.models.functions import Now
from django.utils import timezone

from api.models import (
    ClassifierLabelFeedCalculated,
    ClassifierLabelFeedEntryCalculated,
    ClassifierLabelFeedEntryVote,
)


def label_feeds(
    top_x: int, expiry_interval: datetime.timedelta, chunk_size: int = 500
) -> None:
    ClassifierLabelFeedCalculated.objects.filter(expires_at__lte=Now()).delete()

    expires_at = timezone.now() + expiry_interval

    already_labelled = set(
        ClassifierLabelFeedCalculated.objects.values_list("feed_id", flat=True)
    )

    candidate_feed_ids = (
        set(
            ClassifierLabelFeedEntryVote.objects.values_list(
                "feed_entry__feed_id", flat=True
            ).distinct()
        )
        | set(
            ClassifierLabelFeedEntryCalculated.objects.values_list(
                "feed_entry__feed_id", flat=True
            ).distinct()
        )
    ) - already_labelled

    for feed_id_chunk in batched(sorted(candidate_feed_ids), chunk_size):
        scores: defaultdict[uuid_.UUID, defaultdict[uuid_.UUID, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        for row in (
            ClassifierLabelFeedEntryVote.objects.filter(
                feed_entry__feed_id__in=feed_id_chunk
            )
            .values("feed_entry__feed_id", "classifier_label_id")
            .annotate(score=Count("uuid"))
            .iterator()
        ):
            scores[row["feed_entry__feed_id"]][row["classifier_label_id"]] += float(
                row["score"]
            )

        for row in (
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry__feed_id__in=feed_id_chunk
            )
            .values("feed_entry__feed_id", "classifier_label_id")
            .annotate(score=Sum("weight"))
            .iterator()
        ):
            scores[row["feed_entry__feed_id"]][row["classifier_label_id"]] += float(
                row["score"] or 0.0
            )

        ClassifierLabelFeedCalculated.objects.bulk_create(
            ClassifierLabelFeedCalculated(
                classifier_label_id=classifier_label_id,
                feed_id=feed_id,
                expires_at=expires_at,
                weight=score,
            )
            for feed_id, label_scores in scores.items()
            for classifier_label_id, score in sorted(
                label_scores.items(), key=lambda t: t[1], reverse=True
            )[:top_x]
        )
```

`sorted(candidate_feed_ids)` makes chunking deterministic, which matters for reproducible tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.tasks.test_label_feeds`
Expected: PASS, including the pre-existing `test_label_feeds`.

- [ ] **Step 5: Commit**

```bash
git add api/tasks/label_feeds.py api/tests/tasks/test_label_feeds.py
git commit -m "rewrite label_feeds as chunked aggregate, persist weights"
```

---

### Task 4: Rewrite `label_users` as a chunked aggregate

**Files:**
- Modify: `api/tasks/label_users.py` (full rewrite)
- Test: `api/tests/tasks/test_label_users.py`

**Interfaces:**
- Consumes: `ClassifierLabelFeedCalculated.weight` (Task 3 writes it; Task 1 defines it).
- Produces: `label_users(top_x: int, expiry_interval: datetime.timedelta, chunk_size: int = 500) -> None`. Writes `ClassifierLabelUserCalculated` rows carrying `weight` = summed `ClassifierLabelFeedCalculated.weight` across the user's subscribed feeds.

Same behaviour change as Task 3: only users with actual signal get rows, and only non-zero (user, label) pairs are written.

- [ ] **Step 1: Write the failing test**

Add to `api/tests/tasks/test_label_users.py`:

```python
    def test_label_users_sums_feed_weights(self):
        now = timezone.now()
        user = User.objects.create_user("weight-users@test.com", None)
        label1 = ClassifierLabel.objects.create(text="User Label 1")
        label2 = ClassifierLabel.objects.create(text="User Label 2")

        feed_a = Feed.objects.create(
            feed_url="http://example.com/a.xml",
            title="Feed A",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_b = Feed.objects.create(
            feed_url="http://example.com/b.xml",
            title="Feed B",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        SubscribedFeedUserMapping.objects.create(feed=feed_a, user=user)
        SubscribedFeedUserMapping.objects.create(feed=feed_b, user=user)

        expires = now + datetime.timedelta(days=7)
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label1, feed=feed_a, expires_at=expires, weight=2.0
        )
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label1, feed=feed_b, expires_at=expires, weight=0.5
        )
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label2, feed=feed_b, expires_at=expires, weight=1.25
        )

        label_users(10, datetime.timedelta(days=7))

        rows = {
            r.classifier_label_id: r.weight
            for r in ClassifierLabelUserCalculated.objects.filter(user=user)
        }
        self.assertAlmostEqual(rows[label1.uuid], 2.5)
        self.assertAlmostEqual(rows[label2.uuid], 1.25)

    def test_label_users_skips_users_without_subscriptions(self):
        User.objects.create_user("nosubs@test.com", None)

        label_users(10, datetime.timedelta(days=7))

        self.assertEqual(ClassifierLabelUserCalculated.objects.count(), 0)

    def test_label_users_chunk_boundaries(self):
        now = timezone.now()
        label = ClassifierLabel.objects.create(text="Chunk User Label")
        feed = Feed.objects.create(
            feed_url="http://example.com/shared.xml",
            title="Shared Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        ClassifierLabelFeedCalculated.objects.create(
            classifier_label=label,
            feed=feed,
            expires_at=now + datetime.timedelta(days=7),
            weight=1.0,
        )
        for i in range(3):
            user = User.objects.create_user(f"chunkuser{i}@test.com", None)
            SubscribedFeedUserMapping.objects.create(feed=feed, user=user)

        label_users(10, datetime.timedelta(days=7), chunk_size=2)

        self.assertEqual(ClassifierLabelUserCalculated.objects.count(), 3)
```

Add `ClassifierLabelFeedCalculated`, `ClassifierLabelUserCalculated`, and `SubscribedFeedUserMapping` to the file's `api.models` import as needed.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.tasks.test_label_users`
Expected: FAIL — weights are `1.0` rather than summed, users with no subscriptions still get rows, and `chunk_size` is not a parameter.

- [ ] **Step 3: Rewrite `api/tasks/label_users.py`**

Replace the entire file with:

```python
import datetime
import uuid as uuid_
from collections import defaultdict
from itertools import batched

from django.db.models.functions import Now
from django.utils import timezone

from api.models import (
    ClassifierLabelFeedCalculated,
    ClassifierLabelUserCalculated,
    SubscribedFeedUserMapping,
)


def label_users(
    top_x: int, expiry_interval: datetime.timedelta, chunk_size: int = 500
) -> None:
    ClassifierLabelUserCalculated.objects.filter(expires_at__lte=Now()).delete()

    expires_at = timezone.now() + expiry_interval

    already_labelled = set(
        ClassifierLabelUserCalculated.objects.values_list("user_id", flat=True)
    )

    candidate_user_ids = (
        set(
            SubscribedFeedUserMapping.objects.filter(
                feed_id__in=ClassifierLabelFeedCalculated.objects.values("feed_id")
            )
            .values_list("user_id", flat=True)
            .distinct()
        )
        - already_labelled
    )

    for user_id_chunk in batched(sorted(candidate_user_ids), chunk_size):
        # feed -> users, for this chunk only
        feed_users: defaultdict[uuid_.UUID, list[uuid_.UUID]] = defaultdict(list)
        for mapping in (
            SubscribedFeedUserMapping.objects.filter(user_id__in=user_id_chunk)
            .values("user_id", "feed_id")
            .iterator()
        ):
            feed_users[mapping["feed_id"]].append(mapping["user_id"])

        scores: defaultdict[uuid_.UUID, defaultdict[uuid_.UUID, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        for row in (
            ClassifierLabelFeedCalculated.objects.filter(
                feed_id__in=feed_users.keys()
            )
            .values("feed_id", "classifier_label_id", "weight")
            .iterator()
        ):
            for user_id in feed_users[row["feed_id"]]:
                scores[user_id][row["classifier_label_id"]] += float(row["weight"])

        ClassifierLabelUserCalculated.objects.bulk_create(
            ClassifierLabelUserCalculated(
                classifier_label_id=classifier_label_id,
                user_id=user_id,
                expires_at=expires_at,
                weight=score,
            )
            for user_id, label_scores in scores.items()
            for classifier_label_id, score in sorted(
                label_scores.items(), key=lambda t: t[1], reverse=True
            )[:top_x]
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.tasks.test_label_users`
Expected: PASS, including the pre-existing `test_label_users`.

- [ ] **Step 5: Run the full task suite**

Run: `./scripts/run_tests.sh api.tests.tasks`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/tasks/label_users.py api/tests/tasks/test_label_users.py
git commit -m "rewrite label_users as chunked aggregate, persist weights"
```

---

### Task 5: `purgebulkvotes` management command

**Files:**
- Create: `api/management/commands/purgebulkvotes.py`
- Create: `api/tests/management/__init__.py`
- Create: `api/tests/management/commands/__init__.py`
- Create: `api/tests/management/commands/test_purgebulkvotes.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `manage.py purgebulkvotes --user-email <email> [--dry-run | --no-dry-run] [--batch-size N]`. Dry-run is the **default**.

Note the deliberate divergence from `redetectlanguages.py`, which uses opt-in `--dry-run`. This command deletes a quarter-million rows, so it defaults to safe and requires `--no-dry-run` to act.

**Fix round 1 note:** the `--before` flag described in an earlier draft of this task was removed during implementation, because `uuid_extensions.uuid7` does not use the RFC 9562 48-bit-millisecond layout the removed `_uuid7_upper_bound` helper assumed, making any time bound built on it compare incorrectly.

- [ ] **Step 1: Write the failing test**

Create `api/tests/management/__init__.py` and `api/tests/management/commands/__init__.py` as empty files, then create `api/tests/management/commands/test_purgebulkvotes.py`:

```python
import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryVote,
    Feed,
    FeedEntry,
    User,
)


class PurgeBulkVotesTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.bulk_user = User.objects.create_user("bulk@test.com", None)
        self.real_user = User.objects.create_user("real@test.com", None)
        self.label = ClassifierLabel.objects.create(text="Label 1")

        feed = Feed.objects.create(
            feed_url="http://example.com/purge.xml",
            title="Purge Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        self.feed_entries = FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Entry {i}",
                url=f"http://example.com/purge{i}.html",
                content="content",
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )
            for i in range(4)
        )

        ClassifierLabelFeedEntryVote.objects.bulk_create(
            ClassifierLabelFeedEntryVote(
                feed_entry=fe, classifier_label=self.label, user=self.bulk_user
            )
            for fe in self.feed_entries[0:3]
        )
        ClassifierLabelFeedEntryVote.objects.create(
            feed_entry=self.feed_entries[3],
            classifier_label=self.label,
            user=self.real_user,
        )

    def test_dry_run_is_the_default_and_deletes_nothing(self):
        out = StringIO()
        call_command("purgebulkvotes", "--user-email", "bulk@test.com", stderr=out)

        self.assertEqual(ClassifierLabelFeedEntryVote.objects.count(), 4)
        self.assertIn("3", out.getvalue())

    def test_no_dry_run_deletes_only_the_named_account(self):
        call_command(
            "purgebulkvotes",
            "--user-email",
            "bulk@test.com",
            "--no-dry-run",
            stderr=StringIO(),
        )

        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(user=self.bulk_user).count(), 0
        )
        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(user=self.real_user).count(), 1
        )

    def test_unknown_email_raises(self):
        with self.assertRaises(CommandError):
            call_command(
                "purgebulkvotes",
                "--user-email",
                "nobody@test.com",
                stderr=StringIO(),
            )

    def test_batching_deletes_everything(self):
        call_command(
            "purgebulkvotes",
            "--user-email",
            "bulk@test.com",
            "--no-dry-run",
            "--batch-size",
            "1",
            stderr=StringIO(),
        )

        self.assertEqual(
            ClassifierLabelFeedEntryVote.objects.filter(user=self.bulk_user).count(), 0
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.management.commands.test_purgebulkvotes`
Expected: FAIL — `CommandError: Unknown command: 'purgebulkvotes'`.

- [ ] **Step 3: Write the command**

Create `api/management/commands/purgebulkvotes.py`:

```python
import argparse
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from api.models import ClassifierLabelFeedEntryVote, User


class Command(BaseCommand):
    help = (
        "Delete classifier label votes belonging to a single account. Intended for "
        "removing bulk-import votes that were applied by a script rather than by "
        "users. Dry-run by default."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--user-email", required=True)
        parser.add_argument(
            "--dry-run", action=argparse.BooleanOptionalAction, default=True
        )
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args: Any, **options: Any) -> None:
        user_email: str = options["user_email"]
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]

        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            raise CommandError(f"no user with email '{user_email}'")

        qs = ClassifierLabelFeedEntryVote.objects.filter(user=user)

        breakdown = Counter(
            qs.values_list("classifier_label__text", flat=True).iterator()
        )
        total = sum(breakdown.values())

        for label_text, count in breakdown.most_common():
            self.stderr.write(self.style.NOTICE(f"{label_text}: {count}"))
        self.stderr.write(self.style.NOTICE(f"total: {total}"))

        if dry_run:
            self.stderr.write(
                self.style.WARNING("dry run; nothing deleted. pass --no-dry-run to act")
            )
            return

        deleted = 0
        while True:
            with transaction.atomic():
                batch_uuids = list(
                    qs.values_list("uuid", flat=True)[:batch_size]
                )
                if not batch_uuids:
                    break
                count, _ = ClassifierLabelFeedEntryVote.objects.filter(
                    uuid__in=batch_uuids
                ).delete()
                deleted += count

        self.stderr.write(self.style.SUCCESS(f"deleted {deleted} vote(s)"))
        self.stderr.write(
            self.style.NOTICE(
                "classifier_label_vote_counts_v2__* cache entries will expire within "
                "CLASSIFIER_LABEL_VOTE_COUNTS_CACHE_TIMEOUT_SECONDS"
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.management.commands.test_purgebulkvotes`
Expected: PASS, 4 tests.

- [ ] **Step 5: Document the command in the README**

Add this near the existing `checkclassifierlabels` reference (around line 262):

````markdown
### Purging bulk-applied classifier votes

`ClassifierLabelFeedEntryVote` is meant to record human votes. If labels were
ever applied in bulk by a script, those rows outweigh real votes in the label
ordering the voting UI presents. `purgebulkvotes` removes every vote belonging
to one account.

It is **dry-run by default** — it prints a per-label breakdown and deletes
nothing:

```sh
docker compose exec rss_temple python ./manage.py purgebulkvotes \
  --user-email you@example.com
```

Pass `--no-dry-run` to actually delete:

```sh
docker compose exec rss_temple python ./manage.py purgebulkvotes \
  --user-email you@example.com --no-dry-run
```

**Take a backup first** — see `DB.md`. This is not reversible.
````

- [ ] **Step 6: Commit**

```bash
git add api/management/commands/purgebulkvotes.py api/tests/management/ README.md
git commit -m "add purgebulkvotes command for removing script-applied votes"
```

---

### Task 6: Enable `preload_app` in gunicorn

**Files:**
- Modify: `gunicorn.conf.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing importable. Deployment configuration only.

This task has no unit test — it is a runtime configuration change whose effect is memory, not behaviour. It is verified by measurement, so do it last, where a regression is unambiguously attributable.

- [ ] **Step 1: Audit for fork-unsafe imports**

Database and cache connections do not survive `fork()`. With `preload_app`, the application is imported in the master process *before* forking, so anything that opens a connection at import time will hand a broken socket to every worker.

Search for module-level connection use:

```bash
grep -rn "connection\.\|\.cursor()\|caches\[" --include='*.py' api/ rss_temple/ \
  | grep -v "def \|tests/" | head -40
```

Inspect each hit and confirm it is inside a function or class method, not at module scope. Pay particular attention to `django-silk`, `django-apscheduler`, `dj-rest-auth`, and `allauth`, which are imported via `INSTALLED_APPS`. Write down what you checked — the reviewer needs it.

- [ ] **Step 2: Measure baseline worker RSS**

With the dev stack running:

```bash
docker compose -f docker-compose.yml -f docker-compose.override.dev.yml up -d
sleep 30
docker compose exec rss_temple sh -c "ps -o pid,rss,comm -C python"
```

Record total RSS across the gunicorn worker processes.

- [ ] **Step 3: Enable preload**

In `gunicorn.conf.py`, add below the existing `workers` line:

```python
# Load the application once in the master process and fork, so the ~126MB
# per-worker Django import cost is shared copy-on-write rather than duplicated
# across `cpu_count() * 2 + 1` workers. Requires that nothing opens a database
# or cache connection at import time, since connections do not survive fork().
preload_app = True
```

- [ ] **Step 4: Verify the app still serves requests**

```bash
docker compose -f docker-compose.yml -f docker-compose.override.dev.yml restart rss_temple
sleep 30
curl -fsS http://localhost:8000/api/classifierlabels -o /dev/null -w '%{http_code}\n'
```

Expected: `200`. Then exercise a database-touching authenticated path and confirm no
`InterfaceError: connection already closed` or similar appears in
`docker compose logs rss_temple`.

- [ ] **Step 5: Measure again**

Repeat Step 2's `ps` command. Record the new total.

Expected: a meaningful reduction in total RSS. If total RSS is unchanged, `preload_app` is not taking effect — check that the dev compose command is not overriding the config file (it passes explicit flags, so confirm `gunicorn.conf.py` is still being read).

- [ ] **Step 6: Run the full test suite**

Run: `./scripts/run_tests.sh`
Expected: PASS. (Tests do not exercise gunicorn, but this is the last task — confirm nothing across the whole plan regressed.)

- [ ] **Step 7: Commit**

```bash
git add gunicorn.conf.py
git commit -m "enable gunicorn preload_app to share worker memory"
```

Include the before/after RSS numbers and the Step 1 audit findings in the commit body or PR description.

---

## Done criteria

- [ ] `./scripts/run_tests.sh` passes in full.
- [ ] Migration `0041_*` applies cleanly and contains exactly three `AddField` operations.
- [ ] Before/after gunicorn worker RSS recorded.
- [ ] `purgebulkvotes` documented in the README.
- [ ] Spec 2 (`docs/superpowers/specs/2026-07-30-text-classifier-design.md`) can now assume `ClassifierLabelFeedEntryCalculated.weight` and `settings.CLASSIFIER_LABEL_CALCULATED_WEIGHT` exist.
