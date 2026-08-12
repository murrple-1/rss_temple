# Spec 2: Feed Entry Text Classifier

**Date:** 2026-07-30
**Status:** Approved for planning
**Depends on:** `2026-07-30-classifier-reclamation-design.md` (spec 1) — the `weight` column and
`CLASSIFIER_LABEL_CALCULATED_WEIGHT` setting must exist first.

## Context

`ClassifierLabelFeedEntryCalculated` has no writer. `api/text_classifier/` contains 59 lines:
lingua-based language detection and a `prep_for_classification` that is
`prep_for_lang_detection` with a `# TODO more here needs to be done` on top.
`api/management/commands/entriescsv.py` exports training data to CSV "for machine learning" and
nothing brings predictions back. Every calculated label downstream derives from human votes.

There are effectively no usable human labels to train on. Four accounts have ever voted; after
spec 1 purges the bulk-import rows, close to zero remain. Eleven of the 23 labels have never
been applied. A supervised classifier trained on the existing votes is not possible, and would
not be desirable if it were — those votes were applied at feed granularity, so a model trained
on them learns to recognise publications rather than topics.

The labels must therefore be manufactured. Two options were considered:

- **A — LLM-labelled real entries**, distilled into a small linear model. Higher label quality,
  covers all 23 labels, one-time cost of roughly $10–25 over the Batches API.
- **B — Seed-word weak supervision**, distilled into the same model. Free, fully offline, no
  external dependency, lower quality ceiling.

**This spec implements B**, deliberately as a first pass. A and B differ in exactly one stage of
an otherwise identical pipeline (export → *produce labels* → train → artifact → ship → infer),
so B builds and proves the whole pipeline against a free label source, and A remains a drop-in
replacement for a single module if seed words plateau. That substitution point is called *the
seam* below and is a design constraint, not an accident.

## Goals

1. Automatically assign classifier labels to feed entries, writing
   `ClassifierLabelFeedEntryCalculated` with a confidence weight.
2. Add under ~10MB resident to exactly one process on the ~2GB production VM.
3. No machine-learning dependency in the production image. Training happens off-box.
4. Work out of the box for self-hosters after `docker pull`, with no training step required.
5. Provide an honest measurement of whether the model is any good.

## Non-goals

- Non-English entries. Seed terms are English; the pipeline filters to `language_id = "ENG"`.
  The corpus is overwhelmingly English (253,730 of ~255,500 labelled entries).
- The recommendation engine (`ExploreView`). Separate future spec.
- Exposing confidence through the API. See spec 1 non-goals.
- Retraining on the production box, ever.

## Architecture

Split by where code runs. This split is what keeps the memory budget honest.

| Component | Runs on | Notes |
| --- | --- | --- |
| `api/text_classifier/taxonomy.py` | shared | Label set + seed terms. Django-free. |
| `api/text_classifier/seed_labeler.py` | shared | **The seam.** Text → set of label names. |
| `api/management/commands/exportcorpus.py` | production | Dumps JSONL for `scp`. No ML deps. |
| `scripts/train_classifier.py` | training box | scikit-learn. Django-free, not a management command. |
| `scripts/eval_classifier.py` | training box | Scores an artifact against the gold set. |
| `api/text_classifier/classifier.py` | production | Pure-Python inference. stdlib only. |
| `api/tasks/label_feed_entries.py` | production | Scheduled task, writes calculated labels. |

Training code lives in `scripts/` rather than as a management command specifically so that
nothing importable by the deployed application can `import sklearn` — it is not in the
production image at all.

**Hard invariant:** `api/text_classifier/classifier.py` is imported only from `api/tasks/`,
never from `api/views/`. This confines the model to the single dramatiq process instead of
loading it into each of `cpu_count() * 2 + 1` gunicorn workers. It is enforced by a test, because
it is one careless import away from silently costing ~10MB per web worker with nothing to
indicate it.

---

## 1. `api/text_classifier/taxonomy.py`

Becomes the single source of truth for the label set. `checkclassifierlabels.py` currently
hardcodes the 23 labels as `_EXPECTED_LABELS` and warns on drift against the database; it is
changed to import the list from here, preserving the drift check with one definition.

A Python module rather than a JSON or TOML data file, because seed-term lists need comments.
`# "apple" excluded — fruit vs company` is what stops a bad term being re-added six months later.

```python
@dataclass(frozen=True)
class SeedTerms:
    strong: frozenset[str]
    weak: frozenset[str]
    exclude: frozenset[str] = frozenset()

TAXONOMY: dict[str, SeedTerms] = {
    "Gaming": SeedTerms(
        strong={"video game", "video games", "playstation", "xbox", "nintendo",
                "esports", "speedrun", "roguelike"},
        weak={"gameplay", "console", "multiplayer", "patch notes"},
        exclude={"board game"},
    ),
    ...  # all 23 labels
}
```

All 23 labels get terms, including the eleven that have never been used. Writing them is a real
work item, not boilerplate.

## 2. `api/text_classifier/seed_labeler.py` — the seam

```
score = 2 * distinct_strong_matches + 1 * distinct_weak_matches
fires if score >= SEED_LABEL_THRESHOLD (default 2) and no exclusion term matches
```

`SEED_LABEL_THRESHOLD` and `SEED_LABEL_MAX_CHARS` are **module constants, not Django settings** —
this module must stay Django-free so `scripts/train_classifier.py` can import it off-box.

One strong term is sufficient; one weak term is not; two weak terms are. One tuning knob.

Per-term float weights were considered and rejected: the seed terms only need to be precise
enough to bootstrap, and the logistic regression relearns richer term weights from the corpus
afterwards. Float weights would add 23 lists' worth of tuning surface for no downstream gain.

### Matching mechanics

- **Word-boundary regex, never substring.** One compiled alternation per (label, tier), terms
  `re.escape`d, wrapped as `\b(?:…)\b`, `re.IGNORECASE`. Substring matching is the primary
  failure mode of keyword labelling — `"ai"` matching *said*, *chain*, *maintain* would poison
  Science & Technology across the entire corpus.
- **No stemming.** Plurals and variants are listed explicitly. A suffix-stripper that turns
  *bus* into *bu* fails silently and produces a worse model with no diagnostic signal.
- **Content truncated** to the first `SEED_LABEL_MAX_CHARS` (default 4000) characters after HTML
  stripping via the existing `prep_for_classification`.
- **Title weighting is deferred, not rejected.** A term in the title is stronger evidence than
  one in paragraph nine, and `prep_for_classification` currently flattens both into one string.
  Whether it helps is measurable with the eval harness (§8); it goes in as a knob to test, not a
  baked-in assumption.

### Abstention (correctness-critical)

When no label fires, the document is **dropped from training entirely**. It is *not* a negative
example. Absence of a seed match is not evidence of absence of topic; treating it as such would
teach the model that anything outside the seed vocabulary belongs to no category.

Negatives come from other labels: for one-vs-rest label *L*, positives are documents where *L*
fired, negatives are documents where some *other* label fired but *L* did not. A document
confidently labelled Gaming is a sound negative for Food & Drink. The multi-label structure is
load-bearing here, not incidental.

Accepted cost: the model is trained toward the seed-word decision boundary and inherits its
blind spots. §8 measures this; approach A is the fix.

## 3. `manage.py exportcorpus`

Writes JSONL to stdout so it composes:

```sh
python manage.py exportcorpus | gzip > corpus.jsonl.gz
```

One object per line: `uuid`, `title`, `content`, `feed_id`, `language`, and any human votes on
that entry. The votes are **not consumed by the seed-word training path** — after spec 1's purge
there will be almost none. They are exported so that a later pass (approach A, or once real
votes accumulate) can use them without changing the export format.

**Sampling is per-feed, not global random.** `entriescsv` uses `.order_by("?")`, a full sort over
every row — on a 2GB box sharing RAM with Postgres (`shm_size: 256m`) that is a query to avoid.
Instead: for each feed, take the most recent *N* non-archived entries of the target language,
which is index-friendly and streams. This also implements the per-feed cap (§4) at the point
where it additionally saves disk and transfer, and produces a corpus balanced across
publications rather than dominated by a handful of high-volume newswires.

Flags: `--per-feed` (default 50), `--max-total`, `--language` (default `ENG`),
`--max-content-chars` (default 4000, truncating at export).

Implementation must stream: `.values(...).iterator(chunk_size=...)`, writing line by line.
Nothing accumulates in memory.

**To verify during implementation:** whether `api/tasks/archive_feed_entries.py` clears entry
content or only sets `is_archived`. If content is stripped, archived entries must be excluded or
they become silent empty rows in the training set.

## 4. `scripts/train_classifier.py`

Django-free. Reads corpus JSONL → applies `seed_labeler` → drops unlabelled documents → applies
caps → splits train/dev **by feed** → TF-IDF → one-vs-rest logistic regression → calibrates
per-label thresholds → writes the artifact and parity fixtures.

### Caps and balance

- **Per-label cap** (~5,000 positives, randomly sampled with a fixed seed). Without it, News &
  Weather swamps the model exactly as it does the vote data.
- **Per-feed-per-label cap** (~200). The leakage guard: the corpus is dominated by a few
  high-volume feeds, and without a cap the model learns publication boilerplate.
- `class_weight="balanced"` in the estimator.

### Feed-wise split

Entries from a given feed all land on one side of the train/dev split. An entry-wise split would
let a model that has learned "this is Ars Technica boilerplate" score well on the dev set, which
is the specific failure this whole design is guarding against.

### Vectorizer

`TfidfVectorizer` with `ngram_range=(1, 2)`, `max_features=30000`, `sublinear_tf=True`,
`norm="l2"`, English stop words. The exact configuration is recorded in the artifact (§5) and
verified at load time (§6).

### Per-label thresholds

Each label gets the decision threshold that maximises its dev-set F1, stored in the artifact. A
single global 0.5 would be wrong for nearly every label given how skewed the class frequencies
are.

### Dependencies

Pinned in `scripts/requirements-train.txt`, **not** in the `Pipfile`. `scikit-learn` + `scipy` +
`numpy` is 200MB+; adding it to `[dev-packages]` would put it in the dev image for everyone who
just wants to run the test suite. The training box is a genuinely separate environment.

Document the workflow in the README: export on prod → `scp` → train → commit artifact.

## 5. Artifact format

A single JSON file with base64-encoded float32 blobs, at
`api/text_classifier/model/classifier.json`.

```json
{
  "format_version": 1,
  "labels": ["Anime & Manga", "..."],
  "vocabulary": "term\nterm\n...",
  "idf_b64": "...",
  "coef_b64": "...",
  "intercept_b64": "...",
  "thresholds_b64": "...",
  "vectorizer": {
    "token_pattern": "(?u)\\b\\w\\w+\\b",
    "ngram_range": [1, 2],
    "lowercase": true,
    "sublinear_tf": true,
    "norm": "l2",
    "stop_words": ["a", "about", "..."]
  },
  "taxonomy_fingerprint": "sha256:...",
  "model_fingerprint": "sha256:...",
  "training": {"n_docs": 48213, "labeler": "seed_terms_v1", "trained_at": "..."}
}
```

- `vocabulary` is newline-joined; index is position. `labels` index is the coefficient row.
- `coef_b64` decodes to `n_labels * n_features` float32, row-major.
- `stop_words` is the **resolved** list, not the string `"english"` — the production side must
  not have to reproduce sklearn's built-in list from memory.
- `taxonomy_fingerprint` hashes the seed terms the artifact was trained from. A CI check compares
  it to the current `taxonomy.py`. Without it, someone tunes a term list, tests pass, and
  production silently keeps running a model trained on the old vocabulary.
- `model_fingerprint` hashes the artifact and is what §7 stores on `FeedEntry`.

Roughly 4.5MB on disk, ~10MB resident once loaded (the vocabulary dict dominates; the
23 × 30,000 coefficient matrix is 2.8MB).

**Explicitly not pickle.** Pickle is fragile across Python and sklearn versions, and unpickling
is arbitrary code execution. Given the twenty most recent commits on this repo are a
security-hardening pass, adding a deserialise-at-runtime format would be incongruous. JSON plus
base64 is inert.

### Delivery

Committed to the repo, riding into the image via the existing `COPY . /code/`, so a self-hoster
gets a working classifier from `docker pull` with no extra setup — the README's stated goal. A
`CLASSIFIER_MODEL_PATH` setting defaults to the bundled file and lets an operator point at their
own model on a volume without rebuilding.

Accepted cost: each retrain adds ~4.5MB to git history permanently, and base64'd float data
compresses poorly. At a retrain every few months this is acceptable; git-lfs is the escape hatch
if it stops being, at the price of setup friction for self-hosters.

## 6. `api/text_classifier/classifier.py` — inference

stdlib only: `json`, `base64`, `array`, `math`, `re`.

```
tokens  = tokenize(lowercase(title + " " + content))   # sklearn-compatible
tokens  = remove_stop_words(tokens)
terms   = unigrams + bigrams(tokens)                   # stop words removed FIRST
counts  = Counter(t for t in terms if t in vocabulary)
x[j]    = (1 + ln(counts[j])) * idf[j]                 # sublinear_tf
x       = x / ||x||₂                                   # L2 normalise
score_l = intercept_l + Σⱼ x[j] · coef[l][j]
p_l     = sigmoid(score_l)                             # guarded against overflow
emit    = top CLASSIFIER_MAX_LABELS_PER_ENTRY labels where p_l >= threshold_l
```

Cost per document is ~23 × (number of distinct in-vocabulary terms) multiply-adds — trivial.
Dense coefficient storage is fine because lookup is by `(label, term_index)`; the full matrix is
never iterated.

### Tokenizer parity — the largest correctness risk in this spec

The learned parameters (`idf`, `coef`, `intercept`) are exported verbatim and carry no risk. The
risk is entirely in `tokenize` and the tf weighting, which are *code* living inside scikit-learn
on the training box and are **not** exported. Training defines the document → column-index
mapping; inference must reproduce it exactly. The vocabulary is a wire format and the tokenizer
is the encoder that produced it.

**It fails silently.** Terms absent from the vocabulary are dropped, not errors — necessarily,
since real documents contain unseen words. A subtly wrong tokenizer produces terms that miss the
lookup and vanish; the feature vector gets sparser, scores drift toward the intercept, and
predictions degrade. No exception, no log line, nothing comparing the features training saw
against the features inference computes.

Known divergence points: stop-word removal must happen **before** bigram assembly (otherwise
`"the quick brown fox"` yields `"the quick"` as a feature and the real bigrams shift); L2
normalisation, if omitted, scales every score by document length and invalidates every
calibrated threshold; `sublinear_tf` is natural log, not base 10; and whether sklearn's
one-vs-rest `predict_proba` normalises across labels depends on how it infers the multi-label
nature of the target array at fit time.

**Two required guards:**

1. **Parity fixtures.** `train_classifier.py` emits ~50 documents together with their
   sklearn-computed score vectors to `api/text_classifier/model/parity_fixtures.json`. A unit
   test asserts the pure-Python path reproduces them within float tolerance. Because the fixtures
   capture the *end* of the pipeline they catch divergence at any step, and because they are
   generated by the pinned sklearn version rather than written from documentation, they do not
   depend on anyone's reading of sklearn's internals being correct. The document set must be
   adversarial: unicode and accents, heavy punctuation, repeated words (exercising
   `sublinear_tf`), stop-word-adjacent bigrams, a one-word document, an empty document.
2. **Config assertion at load.** The loader validates the artifact's `vectorizer` block against
   what it implements and **refuses to load** on mismatch. If someone retrains with
   `ngram_range=(1, 3)`, that must fail loudly at startup rather than score wrong indefinitely.

An ONNX export of the whole pipeline was considered — it would compile the tokenizer into the
model and eliminate this risk class — and rejected: `onnxruntime` is a ~50MB native dependency
and `skl2onnx`'s `TfidfVectorizer` support has its own mismatch quirks, trading a testable risk
for an untestable one.

### Loading discipline

- Lazy module-global, loaded on **first call inside the task function**, never at import time.
  `lang_detector.py` builds its detector at import; that pattern is what put lingua into every
  gunicorn worker.
- Test asserting `api.views` does not transitively import `classifier`.
- `dramatiq` defaults to `cpu_count()` worker *processes*, so the artifact loads once per
  process. At ~10MB on a 1–2 vCPU box that is 10–20MB, acceptable — but confirm the actual
  process count on deploy rather than assuming. `--processes 1` is available if needed.

## 7. `api/tasks/label_feed_entries.py`

**Modelled on `extract_top_images`, not on `label_feeds`.** That is the closest existing
analogue: a large `FeedEntry` backlog processed in bounded batches with a persisted
already-handled marker, a `db_limit` per run, and a `large_backlog_threshold` that warns when the
queue grows faster than it drains. `label_feeds` and `label_users` operate over hundreds of rows;
this operates over 250,000+, and copying their shape would be the same mistake at 500× scale.

### Marker column

```python
# FeedEntry
classifier_model_fingerprint = models.CharField(max_length=64, default="", db_index=True)
```

Selection: `.exclude(classifier_model_fingerprint=<loaded artifact fingerprint>)`.

A boolean (matching `has_top_image_been_processed`) would need a manual reset every time a new
model ships; forgetting it means the new model silently never runs on the existing corpus. A
fingerprint invalidates itself on deploy. This is a deliberate, documented divergence from local
convention.

Without *some* marker, entries where the model predicts nothing above threshold get no rows and
would be re-scored every run forever.

Adding a defaulted column is metadata-only on Postgres 18. The index build briefly locks the
table — approximately a second at this row count, acceptable during a deploy.
`AddIndexConcurrently` is deliberately **not** used: it is Postgres-only and the test suite runs
on sqlite.

### Task behaviour

1. Acquire `lock_context(cache, "label_feed_entries_lock")` — the same python-redis-lock helper
   `ExploreView` uses — so overlapping scheduler firings cannot double-process a batch.
2. Delete rows where `expires_at <= Now()` **and, in the same transaction, reset
   `classifier_model_fingerprint = ""` on the affected entries.** See the expiry note below —
   omitting the reset is a silent data-loss bug.
3. Warn if the backlog exceeds `large_backlog_threshold`.
4. Select up to `db_limit` (default 1000) entries with `language_id="ENG"` and a stale
   fingerprint. **No `order_by`** — unlike `extract_top_images`, ordering here would force a sort
   over the whole backlog for no benefit, whereas unordered selection with a `LIMIT` lets
   Postgres stop early.
5. Predict, `bulk_create` `ClassifierLabelFeedEntryCalculated` rows with
   `weight = probability * settings.CLASSIFIER_LABEL_CALCULATED_WEIGHT` and
   `expires_at = now + settings.CLASSIFIER_LABEL_EXPIRY_INTERVAL`.
6. Update `classifier_model_fingerprint` on every processed entry, including those that produced
   no labels.

### Expiry: a separate, long interval

The entry tier **must not** use the shared `LABELING_EXPIRY_INTERVAL` (7 days). Two reasons:

- **Correctness.** Deleting expired rows without resetting the fingerprint means the entry still
  looks processed, is never re-selected, and permanently loses its labels. Step 2 above resets the
  fingerprint precisely to close this.
- **Cost.** Model output does not decay with time; it only changes when the model changes. A
  7-day expiry would force a full re-classification of ~250,000 entries every week — a treadmill
  of recomputing identical answers on a 2GB box.

`CLASSIFIER_LABEL_EXPIRY_INTERVAL` therefore defaults to 365 days and acts as a safety net.
Real invalidation is driven by `model_fingerprint` changing on deploy.

`label_feeds` continues to use the 7-day `LABELING_EXPIRY_INTERVAL` for the feed tier, which is
correct — feed labels should track a changing entry population.

### Backfill throughput

At `db_limit = 1000`, clearing a ~250,000-entry backlog takes 250 runs. Scheduled every 5
minutes that is roughly a day; hourly it is ten days. Pick the schedule accordingly, and note
that `large_backlog_threshold` exists to warn when new entries arrive faster than they drain.

Label text → `ClassifierLabel.uuid` is resolved at load time. The artifact stores label **texts**
because `ClassifierLabel.uuid` defaults to `uuid7()` and differs per deployment — a UUID-keyed
artifact would only work on the box that trained it. Any artifact label missing from the database
logs a warning, the same drift `checkclassifierlabels` already watches for.

### Registration touchpoints

Following existing convention exactly:

- `@dramatiq.actor(queue_name="rss_temple")` in `api_dramatiq/tasks.py`, delegating and logging a
  count.
- `_LabelFeedEntriesSerializer` in `api/management/commands/_schedulerdaemon_serializers.py`,
  wired onto `SetupSerializer`.
- `"label_feed_entries": {}` in `schedulerdaemon.example.json`.
- README scheduler section.

## 8. Evaluation

### Gold set

200–400 entries, hand-labelled by the project owner, stratified across feeds, held out from
training. `manage.py exportgoldcandidates --count 300` emits a JSONL template with empty label
arrays to fill in.

Committed at `api/text_classifier/gold/gold_set.jsonl` with `uuid`, `title`, a ~500-character
content excerpt, and `labels` — self-contained so evaluation runs in CI without a database.

This is the only independent measurement in the entire design. Training labels are
machine-generated, so "the model agrees with the seed labeler" is not evidence of anything.

### Metrics

Precision, recall and F1 **per label**, plus macro-F1 and coverage (share of entries receiving at
least one label). Per-label reporting is required, not optional: the eleven labels with no
history are the most likely to be broken, and they would be invisible inside an average dominated
by News & Weather.

Evaluation splits by feed, never by entry.

### Two ship gates

1. **The model must beat the seed labeler it was trained from**, evaluated against the same gold
   set. If it does not, the training step is adding nothing and running the seed matcher directly
   would be simpler and more predictable.
2. **Per-label precision floor.** Any label below the floor is **excluded from the artifact
   entirely**. A label that is usually wrong is worse than a label that is absent, because it
   propagates into the feed and user tiers and would poison the recommender later. Shipping 15
   labels that work beats 23 where a third are noise, and it gives a concrete per-label target
   for the next round of seed-term work.

## Settings

```python
CLASSIFIER_MODEL_PATH = BASE_DIR / "api/text_classifier/model/classifier.json"
CLASSIFIER_MAX_LABELS_PER_ENTRY = 3
CLASSIFIER_LABEL_EXPIRY_INTERVAL = datetime.timedelta(days=365)
CLASSIFIER_LABEL_CALCULATED_WEIGHT = 0.5   # defined in spec 1
```

`SEED_LABEL_THRESHOLD` and `SEED_LABEL_MAX_CHARS` are deliberately *not* here — they are module
constants in `api/text_classifier/seed_labeler.py`, which must remain importable without Django.

## Testing

- **Parity fixtures** (§6) — the load-bearing test.
- Seed labeler: strong/weak threshold arithmetic, exclusion veto, word-boundary behaviour
  (`"ai"` must not match *said*), multi-word phrases, empty input.
- Artifact round-trip: write then load reproduces identical arrays; a mismatched `vectorizer`
  block is rejected; a truncated or corrupt artifact fails loudly.
- Import guard: `api.views` does not transitively import `classifier`.
- Task: idempotent across re-runs; entries producing no labels are still marked and not
  reprocessed; respects `db_limit`; skips non-English entries; a label text absent from the
  database warns and is skipped rather than raising.
- **Expiry round-trip**: an entry whose calculated rows have expired has its fingerprint reset
  and is re-labelled on the next run. This is the regression test for the silent data-loss bug
  described in §7 — without the reset, the entry's labels disappear permanently.
- Fingerprint invalidation: changing the artifact's `model_fingerprint` causes previously
  processed entries to be re-selected.
- `exportcorpus`: respects `--per-feed`, truncates content, emits valid JSONL, streams (assert no
  full-queryset materialisation).
- `taxonomy_fingerprint` CI check: committed artifact matches committed `taxonomy.py`.

## Risks

| Risk | Mitigation |
| --- | --- |
| Tokenizer parity divergence — silent model degradation | Generated parity fixtures; load-time config assertion |
| Seed words produce a mediocre model | Gold set + ship gates measure it; approach A is a one-module swap |
| Seed vocabulary blind spots baked into the model | Acknowledged and measured; inherent to approach B |
| Model loaded into gunicorn workers by a stray import | Import-guard test |
| Artifact and seed terms drift apart | `taxonomy_fingerprint` CI check |
| Expired rows deleted without fingerprint reset — labels vanish permanently | Reset is in the same transaction (§7); explicit regression test |
| Writing 23 sets of seed terms is a substantial manual task | Real work item, not boilerplate; per-label precision floor makes partial success shippable |

## Follow-ups (not in this spec)

- **Approach A**: replace `seed_labeler.py` with LLM-produced labels. Everything else is unchanged.
- Title weighting in the seed labeler, once the eval harness can measure it.
- Non-English support: per-language seed terms and per-language models.
- Recommendation engine consuming the feed and user tiers.
