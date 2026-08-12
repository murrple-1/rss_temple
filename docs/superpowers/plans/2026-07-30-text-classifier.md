# Feed Entry Text Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically assign classifier labels to feed entries using a linear model trained off-box from seed-word weak supervision, adding under ~10MB resident to exactly one production process and no machine-learning dependency to the production image.

**Architecture:** Seed terms label a corpus off-box; scikit-learn trains a TF-IDF + one-vs-rest logistic regression from those weak labels; the fitted parameters are exported as a stdlib-loadable JSON artifact committed to the repo; a pure-Python inference module scores entries inside the dramatiq worker only, writing `ClassifierLabelFeedEntryCalculated` with a confidence weight.

**Tech Stack:** Django 6 + DRF, PostgreSQL 18 (SQLite for tests), dramatiq + APScheduler, scikit-learn (training box only, never in the production image), Python stdlib `json`/`base64`/`array`/`math`/`re` for inference.

**Spec:** `docs/superpowers/specs/2026-07-30-text-classifier-design.md`
**Depends on:** `docs/superpowers/plans/2026-07-30-classifier-reclamation.md` must be complete — this plan assumes `ClassifierLabelFeedEntryCalculated.weight` and `settings.CLASSIFIER_LABEL_CALCULATED_WEIGHT` exist.

## Global Constraints

- Python 3.14.
- **No `sklearn`, `numpy`, or `scipy` may be importable from anything under `api/`.** Training code lives in `scripts/` and is not installed in the production image. Inference is stdlib only.
- **`api/text_classifier/taxonomy.py`, `seed_labeler.py`, and `artifact.py` must be Django-free** — `scripts/train_classifier.py` imports them off-box without a Django settings module. Do not `from django.conf import settings` in those three files.
- **`api/text_classifier/classifier.py` must never be imported from `api/views/`.** Enforced by a test in Task 8. Violating it loads the model into every one of `cpu_count() * 2 + 1` gunicorn workers.
- Tests run against **SQLite**, production runs **PostgreSQL 18**. No PostgreSQL-only migration operations.
- **Test command.** The project's canonical runner is `./scripts/run_tests.sh [dotted.test.path]`,
  which wraps `pipenv run coverage run manage.py test`. On this machine `pipenv` is a pyenv shim
  resolving to a Python version that does not have it installed, so that script silently runs
  nothing and still exits 0. Use the project venv directly instead:

  ```sh
  /home/mchristo/.local/share/virtualenvs/rss_temple-pQQQnncW/bin/python manage.py test [dotted.test.path]
  ```

  Wherever a step below says `./scripts/run_tests.sh X`, run the venv-python form with the same
  argument. Likewise `pipenv run python manage.py ...` becomes the venv-python form.
- `pre-commit` runs `ruff --fix` and `ruff-format`. Let it reformat; re-stage if it does.
- After `makemigrations`, run `./scripts/post_makemigrations.sh`.
- Type annotations are checked by pyright. Prefer `defaultdict[K, float]` over `Counter` for float scores.
- **Decision thresholds are calibrated on raw decision scores, not probabilities.** `sigmoid(score)` is computed by our own code purely to produce the `weight` value, so nothing depends on sklearn's `predict_proba` normalisation behaviour. Parity fixtures target `decision_function`.

---

### Task 1: Taxonomy module with seed terms

**Files:**
- Create: `api/text_classifier/taxonomy.py`
- Modify: `api/management/commands/checkclassifierlabels.py` (delete `_EXPECTED_LABELS`, import instead)
- Test: `api/tests/test_text_classifier.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `SeedTerms` frozen dataclass with fields `strong: frozenset[str]`, `weak: frozenset[str]`, `exclude: frozenset[str]`
  - `TAXONOMY: dict[str, SeedTerms]` — 23 entries keyed by label text
  - `LABEL_NAMES: tuple[str, ...]` — sorted label texts
  - `taxonomy_fingerprint() -> str` — `"sha256:<hex>"` over the canonicalised term sets

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_text_classifier.py`:

```python
class TaxonomyTestCase(TestCase):
    def test_has_exactly_the_expected_labels(self):
        from api.text_classifier.taxonomy import LABEL_NAMES, TAXONOMY

        self.assertEqual(len(TAXONOMY), 23)
        self.assertEqual(LABEL_NAMES, tuple(sorted(TAXONOMY)))

    def test_every_label_has_strong_terms(self):
        from api.text_classifier.taxonomy import TAXONOMY

        for name, terms in TAXONOMY.items():
            with self.subTest(label=name):
                self.assertGreaterEqual(len(terms.strong), 8, name)

    def test_terms_are_lowercase_and_stripped(self):
        from api.text_classifier.taxonomy import TAXONOMY

        for name, terms in TAXONOMY.items():
            for term in terms.strong | terms.weak | terms.exclude:
                with self.subTest(label=name, term=term):
                    self.assertEqual(term, term.lower().strip())
                    self.assertTrue(term)

    def test_no_term_is_both_strong_and_weak_for_one_label(self):
        from api.text_classifier.taxonomy import TAXONOMY

        for name, terms in TAXONOMY.items():
            with self.subTest(label=name):
                self.assertEqual(terms.strong & terms.weak, frozenset())

    def test_fingerprint_is_stable_and_prefixed(self):
        from api.text_classifier.taxonomy import taxonomy_fingerprint

        first = taxonomy_fingerprint()
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(first, taxonomy_fingerprint())

    def test_module_does_not_import_django(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-c", "import api.text_classifier.taxonomy"],
            capture_output=True,
            env={"PATH": "/usr/bin:/bin"},
            cwd=".",
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
```

Add `from django.test import TestCase` if the file does not already import it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.TaxonomyTestCase`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.text_classifier.taxonomy'`.

- [ ] **Step 3: Write the taxonomy module**

Create `api/text_classifier/taxonomy.py`:

```python
"""Classifier label taxonomy and the seed terms used for weak supervision.

Deliberately free of any Django import: `scripts/train_classifier.py` imports
this module on a machine with no Django settings configured.

This module is the single source of truth for the label set.
`api/management/commands/checkclassifierlabels.py` imports LABEL_NAMES from
here and warns when the database drifts from it.
"""

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SeedTerms:
    """Terms that indicate a label.

    strong  -- a single match is sufficient evidence (score 2)
    weak    -- a single match is suggestive but not sufficient (score 1)
    exclude -- any match vetoes the label for that document entirely
    """

    strong: frozenset[str]
    weak: frozenset[str] = frozenset()
    exclude: frozenset[str] = frozenset()


def _terms(
    strong: list[str], weak: list[str] | None = None, exclude: list[str] | None = None
) -> SeedTerms:
    return SeedTerms(
        strong=frozenset(strong),
        weak=frozenset(weak or []),
        exclude=frozenset(exclude or []),
    )


TAXONOMY: dict[str, SeedTerms] = {
    "Anime & Manga": _terms(
        strong=[
            "anime", "manga", "shonen", "shounen", "seinen", "shoujo", "isekai",
            "otaku", "crunchyroll", "studio ghibli", "light novel", "mangaka",
            "myanimelist", "waifu",
        ],
        weak=["subtitled", "dubbed", "adaptation", "cosplay"],
    ),
    "Arts & Craft": _terms(
        strong=[
            "knitting", "crochet", "quilting", "embroidery", "woodworking",
            "pottery", "ceramics", "calligraphy", "scrapbooking", "origami",
            "cross stitch", "macrame", "needlework", "printmaking", "sculpture",
        ],
        weak=["handmade", "pattern", "craft", "watercolour", "watercolor"],
    ),
    "Automobile & Vehicles": _terms(
        strong=[
            "horsepower", "drivetrain", "camshaft", "odometer", "test drive",
            "dealership", "sedan", "suv", "motorcycle", "chassis",
            "transmission", "ev charging", "car review", "torque",
        ],
        weak=["vehicle", "mileage", "driver", "engine"],
        # "engine" is weak and heavily overloaded; veto the common non-automotive senses
        exclude=["search engine", "game engine", "engine of growth", "rendering engine"],
    ),
    "Books": _terms(
        strong=[
            "novelist", "paperback", "hardcover", "book review", "bestseller",
            "literary fiction", "poetry collection", "isbn", "goodreads",
            "booker prize", "audiobook", "bookstore", "memoir",
        ],
        weak=["novel", "publisher", "chapter", "reading"],
    ),
    "Business, Finance & Banking": _terms(
        strong=[
            "earnings", "ipo", "nasdaq", "hedge fund", "interest rate",
            "federal reserve", "mortgage", "dividend", "shareholder",
            "acquisition", "venture capital", "balance sheet", "inflation",
            "central bank", "valuation",
        ],
        weak=["market", "investor", "profit", "funding", "stock", "revenue"],
    ),
    "Celebrities & Culture": _terms(
        strong=[
            "red carpet", "paparazzi", "tabloid", "celebrity", "met gala",
            "socialite", "a-list", "kardashian", "gossip column", "tmz",
            "engagement ring", "publicist",
        ],
        weak=["rumour", "rumor", "spotted", "gossip"],
    ),
    "Computer Hardware & Software": _terms(
        strong=[
            "gpu", "cpu", "motherboard", "ssd", "benchmark", "nvidia",
            "ryzen", "overclock", "firmware", "thermal paste", "chipset",
            "raid array", "laptop review", "graphics card",
        ],
        weak=["hardware", "upgrade", "install", "peripheral"],
        exclude=["driver's licence", "driver's license"],
    ),
    "Education": _terms(
        strong=[
            "curriculum", "classroom", "school district", "undergraduate",
            "standardized test", "scholarship", "syllabus", "k-12", "tuition",
            "faculty", "professor", "phd programme", "phd program",
        ],
        weak=["student", "teacher", "learning", "course", "degree"],
    ),
    "Fashion & Beauty": _terms(
        strong=[
            "runway", "couture", "skincare", "mascara", "lipstick",
            "streetwear", "fashion week", "haircare", "manicure", "wardrobe",
            "moisturiser", "moisturizer", "sneakerhead",
        ],
        weak=["outfit", "boutique", "cosmetics", "styling"],
    ),
    "Food & Drink": _terms(
        strong=[
            "recipe", "preheat", "tablespoon", "teaspoon", "sourdough",
            "michelin star", "sommelier", "cocktail", "barista", "espresso",
            "marinade", "brewery", "restaurant review", "ingredients",
        ],
        weak=["kitchen", "cooking", "flavour", "flavor", "dish", "menu"],
    ),
    "Gaming": _terms(
        strong=[
            "video game", "video games", "playstation", "xbox", "nintendo",
            "esports", "speedrun", "roguelike", "steam deck", "mmorpg",
            "indie game", "game studio", "dlc",
        ],
        weak=["gameplay", "console", "multiplayer", "patch notes"],
        exclude=["board game", "the gaming commission"],
    ),
    "Health": _terms(
        strong=[
            "clinical trial", "vaccine", "cardiology", "mental health",
            "physician", "prescription", "diabetes", "cancer screening",
            "public health", "diagnosis", "symptoms", "epidemiology",
            "nutrition",
        ],
        weak=["patient", "treatment", "doctor", "disease", "wellness"],
    ),
    "Movies & TV": _terms(
        strong=[
            "box office", "screenplay", "netflix", "season finale",
            "showrunner", "film festival", "sundance", "blockbuster", "sitcom",
            "cinematography", "streaming series", "oscar",
        ],
        weak=["episode", "cast", "trailer", "director", "film"],
    ),
    "Music": _terms(
        strong=[
            "tracklist", "guitarist", "spotify", "concert tour",
            "billboard chart", "drummer", "vinyl", "songwriter", "grammy",
            "setlist", "bassline", "record label", "discography",
        ],
        weak=["album", "band", "song", "single"],
    ),
    "News & Weather": _terms(
        # Deliberately narrow. This label dominated the historical vote data;
        # generic newsroom vocabulary is intentionally absent.
        strong=[
            "hurricane", "tornado", "blizzard", "wildfire", "earthquake",
            "flood warning", "meteorologist", "evacuation order", "storm surge",
            "heatwave", "weather forecast", "tropical storm",
        ],
        weak=["forecast", "temperature", "officials said", "emergency services"],
    ),
    "Pets & Animals": _terms(
        strong=[
            "veterinarian", "puppy", "kitten", "animal shelter", "dog breed",
            "cat litter", "aquarium", "wildlife rescue", "pet food",
            "grooming", "leash", "adoption centre",
        ],
        weak=["pet", "breed", "owner", "paws"],
    ),
    "Photography": _terms(
        strong=[
            "aperture", "shutter speed", "mirrorless", "dslr", "lightroom",
            "bokeh", "focal length", "darkroom", "photographer", "tripod",
            "raw file", "telephoto",
        ],
        weak=["lens", "exposure", "camera", "photo"],
        exclude=["iso 27001", "iso standard", "iso 8601", "iso 9001"],
    ),
    "Politics": _terms(
        strong=[
            "parliament", "senator", "ballot", "legislation", "prime minister",
            "referendum", "filibuster", "coalition government", "impeach",
            "constituency", "electorate", "campaign trail", "congress",
        ],
        weak=["policy", "election", "government", "vote"],
    ),
    "Programming": _terms(
        strong=[
            "javascript", "typescript", "compiler", "refactor", "api endpoint",
            "git commit", "kubernetes", "pull request", "stack trace",
            "runtime error", "sql query", "open source", "docker",
        ],
        weak=["code", "function", "library", "developer", "repository"],
    ),
    "Religion": _terms(
        strong=[
            "theology", "scripture", "congregation", "sermon", "vatican",
            "rabbi", "imam", "buddhist", "liturgy", "pilgrimage", "parish",
            "quran", "torah", "monastery",
        ],
        weak=["faith", "church", "prayer", "spiritual"],
    ),
    "Science & Technology": _terms(
        strong=[
            "astrophysics", "quantum", "genome", "particle accelerator",
            "nasa", "peer-reviewed", "telescope", "neuroscience",
            "climate model", "biotech", "satellite", "arxiv", "hypothesis",
        ],
        weak=["research", "scientists", "discovery", "experiment", "laboratory"],
    ),
    "Sport": _terms(
        strong=[
            "goalkeeper", "touchdown", "premier league", "nba", "playoff",
            "marathon", "quarterback", "olympics", "formula 1", "midfielder",
            "fifa", "wicket", "striker",
        ],
        weak=["team", "match", "tournament", "coach", "season"],
    ),
    "Travel": _terms(
        strong=[
            "itinerary", "hostel", "airfare", "layover", "backpacking",
            "visa requirement", "tripadvisor", "boarding pass", "sightseeing",
            "national park", "airbnb", "all-inclusive resort",
        ],
        weak=["hotel", "flight", "destination", "tourist"],
    ),
}

LABEL_NAMES: tuple[str, ...] = tuple(sorted(TAXONOMY))


def taxonomy_fingerprint() -> str:
    """Stable hash of the taxonomy, embedded in trained artifacts.

    A CI check compares this against the fingerprint recorded in the committed
    model artifact, so seed terms and the shipped model cannot drift apart
    silently.
    """
    canonical = {
        name: {
            "strong": sorted(terms.strong),
            "weak": sorted(terms.weak),
            "exclude": sorted(terms.exclude),
        }
        for name, terms in sorted(TAXONOMY.items())
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Point `checkclassifierlabels` at the taxonomy**

In `api/management/commands/checkclassifierlabels.py`, delete the `_EXPECTED_LABELS` list literal and replace it with:

```python
from api.text_classifier.taxonomy import LABEL_NAMES

_EXPECTED_LABELS = list(LABEL_NAMES)
```

Leave the rest of the command unchanged — the duplicate check, the missing-labels warning, and the extra-labels warning all still apply.

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.TaxonomyTestCase`
Expected: PASS, 6 tests.

- [ ] **Step 6: Verify the taxonomy matches the database fixture**

Run: `pipenv run python manage.py checkclassifierlabels`
Expected: no warnings. If it reports missing or extra labels, the `TAXONOMY` keys do not match `api/fixtures/default.json` — reconcile the two before continuing, keeping the fixture's exact label text.

- [ ] **Step 7: Commit**

```bash
git add api/text_classifier/taxonomy.py api/management/commands/checkclassifierlabels.py api/tests/test_text_classifier.py
git commit -m "add classifier taxonomy with seed terms"
```

---

### Task 2: Seed labeler

**Files:**
- Create: `api/text_classifier/seed_labeler.py`
- Test: `api/tests/test_text_classifier.py`

**Interfaces:**
- Consumes: `api.text_classifier.taxonomy.TAXONOMY` (Task 1).
- Produces:
  - `SEED_LABEL_THRESHOLD: int = 2`, `SEED_LABEL_MAX_CHARS: int = 4000` (module constants, **not** Django settings)
  - `label_text(text: str) -> frozenset[str]` — label names that fire for already-prepped plain text
  - `score_text(text: str) -> dict[str, int]` — per-label scores before thresholding, for debugging and tuning

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_text_classifier.py`:

```python
class SeedLabelerTestCase(TestCase):
    def test_single_strong_term_fires(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertIn("Gaming", label_text("A review of the new Nintendo handheld."))

    def test_single_weak_term_does_not_fire(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertNotIn("Gaming", label_text("The gameplay was fine."))

    def test_two_weak_terms_fire(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertIn("Gaming", label_text("The gameplay on this console is fine."))

    def test_exclusion_vetoes_the_label(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertNotIn(
            "Gaming", label_text("Nintendo made a board game once, apparently.")
        )

    def test_matching_is_word_bounded(self):
        from api.text_classifier.seed_labeler import score_text

        # "ai" is not a term, but this guards the general principle: a term must
        # not match inside a longer word. "nba" must not match "unbalanced".
        self.assertEqual(score_text("The load was unbalanced.").get("Sport", 0), 0)

    def test_multi_word_phrases_match(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertIn("Movies & TV", label_text("It topped the box office again."))

    def test_multi_label(self):
        from api.text_classifier.seed_labeler import label_text

        labels = label_text(
            "The soundtrack guitarist also scored the box office hit."
        )
        self.assertIn("Music", labels)
        self.assertIn("Movies & TV", labels)

    def test_empty_input_fires_nothing(self):
        from api.text_classifier.seed_labeler import label_text

        self.assertEqual(label_text(""), frozenset())
        self.assertEqual(label_text("   "), frozenset())

    def test_distinct_terms_not_repeats(self):
        from api.text_classifier.seed_labeler import score_text

        # The same weak term ten times is still one distinct weak match.
        repeated = " ".join(["gameplay"] * 10)
        self.assertEqual(score_text(repeated).get("Gaming", 0), 1)

    def test_truncates_long_input(self):
        from api.text_classifier.seed_labeler import SEED_LABEL_MAX_CHARS, label_text

        padding = "x " * SEED_LABEL_MAX_CHARS
        self.assertNotIn("Gaming", label_text(padding + " nintendo"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.SeedLabelerTestCase`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.text_classifier.seed_labeler'`.

- [ ] **Step 3: Write the seed labeler**

Create `api/text_classifier/seed_labeler.py`:

```python
"""Weak supervision: assign classifier labels from seed terms.

This module is *the seam*. It exists so that the training pipeline has a
pluggable source of labels. Replacing it with LLM-produced labels (approach A
in the spec) changes nothing else in the pipeline.

Deliberately free of any Django import — `scripts/train_classifier.py` imports
this on a machine with no Django settings configured.
"""

import re
from functools import lru_cache

from api.text_classifier.taxonomy import TAXONOMY

SEED_LABEL_THRESHOLD = 2
SEED_LABEL_MAX_CHARS = 4000

_STRONG_SCORE = 2
_WEAK_SCORE = 1


def _compile(terms: frozenset[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    # Longest first so that "video games" wins over "video game" when both are
    # present; findall returns non-overlapping matches in scan order.
    alternation = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternation})\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _patterns() -> dict[str, tuple[re.Pattern[str] | None, ...]]:
    return {
        name: (
            _compile(terms.strong),
            _compile(terms.weak),
            _compile(terms.exclude),
        )
        for name, terms in TAXONOMY.items()
    }


def _distinct_match_count(pattern: re.Pattern[str] | None, text: str) -> int:
    if pattern is None:
        return 0
    return len({m.lower() for m in pattern.findall(text)})


def score_text(text: str) -> dict[str, int]:
    """Per-label seed score. Excluded labels score 0."""
    text = text[:SEED_LABEL_MAX_CHARS]

    scores: dict[str, int] = {}
    for name, (strong, weak, exclude) in _patterns().items():
        if exclude is not None and exclude.search(text):
            scores[name] = 0
            continue

        scores[name] = _STRONG_SCORE * _distinct_match_count(
            strong, text
        ) + _WEAK_SCORE * _distinct_match_count(weak, text)

    return scores


def label_text(text: str) -> frozenset[str]:
    """Label names whose seed score meets the threshold."""
    return frozenset(
        name
        for name, score in score_text(text).items()
        if score >= SEED_LABEL_THRESHOLD
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.SeedLabelerTestCase`
Expected: PASS, 10 tests.

If `test_exclusion_vetoes_the_label` fails, the exclusion check is running after scoring rather than as a veto — it must `continue` before any strong/weak counting for that label.

- [ ] **Step 5: Commit**

```bash
git add api/text_classifier/seed_labeler.py api/tests/test_text_classifier.py
git commit -m "add seed-term weak labeler"
```

---

### Task 3: Model artifact format

**Files:**
- Create: `api/text_classifier/artifact.py`
- Test: `api/tests/test_text_classifier.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ARTIFACT_FORMAT_VERSION: int = 1`
  - `VectorizerConfig` frozen dataclass: `token_pattern: str`, `ngram_range: tuple[int, int]`, `lowercase: bool`, `sublinear_tf: bool`, `norm: str`, `stop_words: tuple[str, ...]`
  - `Artifact` frozen dataclass: `labels: tuple[str, ...]`, `vocabulary: dict[str, int]`, `idf: array`, `coef: array`, `intercept: array`, `thresholds: array`, `vectorizer: VectorizerConfig`, `taxonomy_fingerprint: str`, `model_fingerprint: str`, `training: dict`
  - `dump_artifact(path, *, labels, vocabulary_terms, idf, coef, intercept, thresholds, vectorizer, taxonomy_fingerprint, training) -> str` — writes the file, returns the computed `model_fingerprint`
  - `load_artifact(path) -> Artifact` — raises `ArtifactError` on unsupported format or config
  - `ArtifactError(Exception)`

`coef` is flat, row-major, length `len(labels) * len(vocabulary)`. Coefficient for label `l`, feature `j` is `coef[l * n_features + j]`.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_text_classifier.py`:

```python
class ArtifactTestCase(TestCase):
    def _write(self, tmpdir, **overrides):
        from api.text_classifier.artifact import VectorizerConfig, dump_artifact

        kwargs = {
            "labels": ["Alpha", "Beta"],
            "vocabulary_terms": ["cat", "dog", "cat dog"],
            "idf": [1.0, 2.0, 3.0],
            "coef": [0.1, 0.2, 0.3, -0.1, -0.2, -0.3],
            "intercept": [0.5, -0.5],
            "thresholds": [0.0, 0.25],
            "vectorizer": VectorizerConfig(
                token_pattern=r"(?u)\b\w\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                norm="l2",
                stop_words=("the", "a"),
            ),
            "taxonomy_fingerprint": "sha256:deadbeef",
            "training": {"n_docs": 3},
        }
        kwargs.update(overrides)
        path = os.path.join(tmpdir, "artifact.json")
        fingerprint = dump_artifact(path, **kwargs)
        return path, fingerprint

    def test_round_trip(self):
        from api.text_classifier.artifact import load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, fingerprint = self._write(tmpdir)
            artifact = load_artifact(path)

            self.assertEqual(artifact.labels, ("Alpha", "Beta"))
            self.assertEqual(artifact.vocabulary, {"cat": 0, "dog": 1, "cat dog": 2})
            self.assertEqual(list(artifact.idf), [1.0, 2.0, 3.0])
            self.assertEqual(len(artifact.coef), 6)
            self.assertAlmostEqual(artifact.coef[0], 0.1, places=6)
            self.assertAlmostEqual(artifact.coef[5], -0.3, places=6)
            self.assertEqual(list(artifact.intercept), [0.5, -0.5])
            self.assertEqual(artifact.model_fingerprint, fingerprint)
            self.assertEqual(artifact.taxonomy_fingerprint, "sha256:deadbeef")

    def test_fingerprint_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, first = self._write(tmpdir)
        with tempfile.TemporaryDirectory() as tmpdir:
            _, second = self._write(tmpdir)
        self.assertEqual(first, second)

    def test_fingerprint_changes_with_coefficients(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, first = self._write(tmpdir)
        with tempfile.TemporaryDirectory() as tmpdir:
            _, second = self._write(
                tmpdir, coef=[0.9, 0.2, 0.3, -0.1, -0.2, -0.3]
            )
        self.assertNotEqual(first, second)

    def test_rejects_unsupported_format_version(self):
        from api.text_classifier.artifact import ArtifactError, load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, _ = self._write(tmpdir)
            with open(path, "r") as f:
                raw = json.load(f)
            raw["format_version"] = 999
            with open(path, "w") as f:
                json.dump(raw, f)

            with self.assertRaises(ArtifactError):
                load_artifact(path)

    def test_rejects_unsupported_vectorizer_config(self):
        from api.text_classifier.artifact import ArtifactError, load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, _ = self._write(tmpdir)
            with open(path, "r") as f:
                raw = json.load(f)
            raw["vectorizer"]["ngram_range"] = [1, 3]
            with open(path, "w") as f:
                json.dump(raw, f)

            with self.assertRaises(ArtifactError):
                load_artifact(path)

    def test_rejects_truncated_arrays(self):
        from api.text_classifier.artifact import ArtifactError, load_artifact

        with tempfile.TemporaryDirectory() as tmpdir:
            path, _ = self._write(tmpdir)
            with open(path, "r") as f:
                raw = json.load(f)
            raw["labels"] = ["Alpha", "Beta", "Gamma"]  # coef no longer 3 x 3
            with open(path, "w") as f:
                json.dump(raw, f)

            with self.assertRaises(ArtifactError):
                load_artifact(path)
```

Add `import json`, `import os`, `import tempfile` to the top of the test file if absent.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.ArtifactTestCase`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.text_classifier.artifact'`.

- [ ] **Step 3: Write the artifact module**

Create `api/text_classifier/artifact.py`:

```python
"""Read and write the trained classifier artifact.

Deliberately stdlib-only and Django-free: written by
`scripts/train_classifier.py` on the training box, read by
`api/text_classifier/classifier.py` in production. Keeping both sides in one
module is what stops the format drifting.

Not pickle, on purpose. Pickle is fragile across Python and scikit-learn
versions, and unpickling is arbitrary code execution.
"""

import base64
import hashlib
import json
from array import array
from dataclasses import asdict, dataclass
from typing import Any, Sequence

ARTIFACT_FORMAT_VERSION = 1

# What the pure-Python inference path in classifier.py actually implements.
# Anything else must fail loudly at load rather than score incorrectly.
_SUPPORTED_TOKEN_PATTERN = r"(?u)\b\w\w+\b"
_SUPPORTED_NGRAM_RANGE = (1, 2)
_SUPPORTED_NORM = "l2"


class ArtifactError(Exception):
    pass


@dataclass(frozen=True)
class VectorizerConfig:
    token_pattern: str
    ngram_range: tuple[int, int]
    lowercase: bool
    sublinear_tf: bool
    norm: str
    stop_words: tuple[str, ...]


@dataclass(frozen=True)
class Artifact:
    labels: tuple[str, ...]
    vocabulary: dict[str, int]
    idf: array
    coef: array
    intercept: array
    thresholds: array
    vectorizer: VectorizerConfig
    taxonomy_fingerprint: str
    model_fingerprint: str
    training: dict[str, Any]


def _encode(values: Sequence[float]) -> str:
    return base64.b64encode(array("f", values).tobytes()).decode("ascii")


def _decode(blob: str) -> array:
    decoded = array("f")
    decoded.frombytes(base64.b64decode(blob))
    return decoded


def dump_artifact(
    path: str,
    *,
    labels: Sequence[str],
    vocabulary_terms: Sequence[str],
    idf: Sequence[float],
    coef: Sequence[float],
    intercept: Sequence[float],
    thresholds: Sequence[float],
    vectorizer: VectorizerConfig,
    taxonomy_fingerprint: str,
    training: dict[str, Any],
) -> str:
    """Write the artifact and return its model fingerprint."""
    n_labels = len(labels)
    n_features = len(vocabulary_terms)

    if len(idf) != n_features:
        raise ArtifactError(f"idf has {len(idf)} entries, expected {n_features}")
    if len(coef) != n_labels * n_features:
        raise ArtifactError(
            f"coef has {len(coef)} entries, expected {n_labels * n_features}"
        )
    if len(intercept) != n_labels or len(thresholds) != n_labels:
        raise ArtifactError("intercept and thresholds must have one entry per label")
    if any("\n" in term for term in vocabulary_terms):
        raise ArtifactError("vocabulary terms may not contain newlines")

    body: dict[str, Any] = {
        "format_version": ARTIFACT_FORMAT_VERSION,
        "labels": list(labels),
        "vocabulary": "\n".join(vocabulary_terms),
        "idf_b64": _encode(idf),
        "coef_b64": _encode(coef),
        "intercept_b64": _encode(intercept),
        "thresholds_b64": _encode(thresholds),
        "vectorizer": {
            **asdict(vectorizer),
            "ngram_range": list(vectorizer.ngram_range),
            "stop_words": list(vectorizer.stop_words),
        },
        "taxonomy_fingerprint": taxonomy_fingerprint,
        "training": training,
    }

    fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    body["model_fingerprint"] = fingerprint

    with open(path, "w") as f:
        json.dump(body, f, sort_keys=True)

    return fingerprint


def load_artifact(path: str) -> Artifact:
    with open(path, "r") as f:
        body = json.load(f)

    version = body.get("format_version")
    if version != ARTIFACT_FORMAT_VERSION:
        raise ArtifactError(
            f"artifact format_version {version!r} is not supported "
            f"(this build reads {ARTIFACT_FORMAT_VERSION})"
        )

    raw_vectorizer = body["vectorizer"]
    vectorizer = VectorizerConfig(
        token_pattern=raw_vectorizer["token_pattern"],
        ngram_range=tuple(raw_vectorizer["ngram_range"]),  # type: ignore[arg-type]
        lowercase=raw_vectorizer["lowercase"],
        sublinear_tf=raw_vectorizer["sublinear_tf"],
        norm=raw_vectorizer["norm"],
        stop_words=tuple(raw_vectorizer["stop_words"]),
    )

    if vectorizer.token_pattern != _SUPPORTED_TOKEN_PATTERN:
        raise ArtifactError(f"unsupported token_pattern {vectorizer.token_pattern!r}")
    if vectorizer.ngram_range != _SUPPORTED_NGRAM_RANGE:
        raise ArtifactError(f"unsupported ngram_range {vectorizer.ngram_range!r}")
    if vectorizer.norm != _SUPPORTED_NORM:
        raise ArtifactError(f"unsupported norm {vectorizer.norm!r}")
    if not vectorizer.lowercase or not vectorizer.sublinear_tf:
        raise ArtifactError("lowercase and sublinear_tf must both be enabled")

    labels = tuple(body["labels"])
    terms = body["vocabulary"].split("\n") if body["vocabulary"] else []
    vocabulary = {term: index for index, term in enumerate(terms)}

    idf = _decode(body["idf_b64"])
    coef = _decode(body["coef_b64"])
    intercept = _decode(body["intercept_b64"])
    thresholds = _decode(body["thresholds_b64"])

    n_labels = len(labels)
    n_features = len(vocabulary)
    if len(idf) != n_features:
        raise ArtifactError("idf length does not match vocabulary size")
    if len(coef) != n_labels * n_features:
        raise ArtifactError("coef length does not match labels x vocabulary")
    if len(intercept) != n_labels or len(thresholds) != n_labels:
        raise ArtifactError("intercept/thresholds length does not match label count")

    return Artifact(
        labels=labels,
        vocabulary=vocabulary,
        idf=idf,
        coef=coef,
        intercept=intercept,
        thresholds=thresholds,
        vectorizer=vectorizer,
        taxonomy_fingerprint=body["taxonomy_fingerprint"],
        model_fingerprint=body["model_fingerprint"],
        training=body["training"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.ArtifactTestCase`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add api/text_classifier/artifact.py api/tests/test_text_classifier.py
git commit -m "add classifier model artifact format"
```

---

### Task 4: Pure-Python inference

**Files:**
- Create: `api/text_classifier/classifier.py`
- Test: `api/tests/test_text_classifier.py`

**Interfaces:**
- Consumes: `api.text_classifier.artifact.Artifact`, `load_artifact` (Task 3).
- Produces:
  - `analyze(text: str, vectorizer: VectorizerConfig) -> list[str]` — the sklearn-compatible term list (unigrams + bigrams, stop words removed before bigram assembly)
  - `decision_scores(artifact: Artifact, text: str) -> list[float]` — one raw score per label, in `artifact.labels` order
  - `Prediction` NamedTuple: `label: str`, `score: float`, `probability: float`
  - `predict(artifact: Artifact, text: str, max_labels: int) -> list[Prediction]` — labels whose score meets their threshold, highest score first, truncated
  - `sigmoid(x: float) -> float` — overflow-guarded

Thresholds compare against **raw decision scores**. `probability` is `sigmoid(score)` and exists only to produce the `weight` value written to the database.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_text_classifier.py`:

```python
class ClassifierInferenceTestCase(TestCase):
    def _artifact(self):
        """A hand-built two-label, three-feature artifact with known answers."""
        from api.text_classifier.artifact import VectorizerConfig, dump_artifact, load_artifact

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        path = os.path.join(self.tmpdir.name, "artifact.json")
        dump_artifact(
            path,
            labels=["Alpha", "Beta"],
            vocabulary_terms=["cat", "dog", "cat dog"],
            idf=[1.0, 1.0, 1.0],
            # Alpha keys on "cat", Beta keys on "dog"
            coef=[10.0, 0.0, 0.0, 0.0, 10.0, 0.0],
            intercept=[0.0, 0.0],
            thresholds=[1.0, 1.0],
            vectorizer=VectorizerConfig(
                token_pattern=r"(?u)\b\w\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                norm="l2",
                stop_words=("the",),
            ),
            taxonomy_fingerprint="sha256:test",
            training={},
        )
        return load_artifact(path)

    def test_analyze_removes_stop_words_before_bigrams(self):
        from api.text_classifier.artifact import VectorizerConfig
        from api.text_classifier.classifier import analyze

        config = VectorizerConfig(
            token_pattern=r"(?u)\b\w\w+\b",
            ngram_range=(1, 2),
            lowercase=True,
            sublinear_tf=True,
            norm="l2",
            stop_words=("the",),
        )
        terms = analyze("the cat dog", config)
        self.assertEqual(terms, ["cat", "dog", "cat dog"])
        self.assertNotIn("the cat", terms)

    def test_analyze_drops_single_character_tokens(self):
        from api.text_classifier.artifact import VectorizerConfig
        from api.text_classifier.classifier import analyze

        config = VectorizerConfig(
            token_pattern=r"(?u)\b\w\w+\b",
            ngram_range=(1, 2),
            lowercase=True,
            sublinear_tf=True,
            norm="l2",
            stop_words=(),
        )
        self.assertEqual(analyze("a cat", config), ["cat"])

    def test_l2_normalisation_makes_length_irrelevant(self):
        from api.text_classifier.classifier import decision_scores

        artifact = self._artifact()
        short = decision_scores(artifact, "cat")
        long = decision_scores(artifact, "cat " * 20)
        # Repeating one term must not change the unit vector's direction.
        self.assertAlmostEqual(short[0], long[0], places=5)

    def test_predict_returns_only_labels_over_threshold(self):
        from api.text_classifier.classifier import predict

        artifact = self._artifact()
        predictions = predict(artifact, "cat", max_labels=3)
        self.assertEqual([p.label for p in predictions], ["Alpha"])

    def test_predict_orders_by_score_and_truncates(self):
        from api.text_classifier.classifier import predict

        artifact = self._artifact()
        predictions = predict(artifact, "cat dog", max_labels=1)
        self.assertEqual(len(predictions), 1)

    def test_probability_is_between_zero_and_one(self):
        from api.text_classifier.classifier import predict

        artifact = self._artifact()
        for prediction in predict(artifact, "cat dog", max_labels=3):
            self.assertGreater(prediction.probability, 0.0)
            self.assertLess(prediction.probability, 1.0)

    def test_sigmoid_does_not_overflow(self):
        from api.text_classifier.classifier import sigmoid

        self.assertAlmostEqual(sigmoid(-10000.0), 0.0)
        self.assertAlmostEqual(sigmoid(10000.0), 1.0)

    def test_empty_and_out_of_vocabulary_text_scores_the_intercept(self):
        from api.text_classifier.classifier import decision_scores

        artifact = self._artifact()
        self.assertEqual(decision_scores(artifact, ""), [0.0, 0.0])
        self.assertEqual(decision_scores(artifact, "zebra"), [0.0, 0.0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.ClassifierInferenceTestCase`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.text_classifier.classifier'`.

- [ ] **Step 3: Write the inference module**

Create `api/text_classifier/classifier.py`:

```python
"""Pure-Python inference for the trained classifier.

MUST NOT be imported from `api/views/`. It is loaded lazily inside the dramatiq
task so the model lives in exactly one process rather than in every gunicorn
worker. `api/tests/test_text_classifier.py` enforces this.

The tokenization and TF-IDF weighting here must match scikit-learn's
TfidfVectorizer exactly, because the vocabulary was fitted by scikit-learn and
this code has to reproduce the same feature indices. Divergence fails silently:
mismatched terms simply miss the vocabulary lookup and vanish. The parity
fixtures generated by `scripts/train_classifier.py` are what catch it.
"""

import math
import re
from array import array
from collections import Counter
from functools import lru_cache
from typing import NamedTuple

from api.text_classifier.artifact import Artifact, VectorizerConfig


class Prediction(NamedTuple):
    label: str
    score: float
    probability: float


@lru_cache(maxsize=4)
def _token_re(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def analyze(text: str, vectorizer: VectorizerConfig) -> list[str]:
    """Reproduce scikit-learn's word analyzer.

    Order is load-bearing: lowercase, tokenize, remove stop words, THEN build
    bigrams. Building bigrams before removing stop words produces a different
    feature set ("the cat" instead of "cat dog") and silently degrades scoring.
    """
    if vectorizer.lowercase:
        text = text.lower()

    tokens = _token_re(vectorizer.token_pattern).findall(text)

    stop_words = set(vectorizer.stop_words)
    if stop_words:
        tokens = [t for t in tokens if t not in stop_words]

    min_n, max_n = vectorizer.ngram_range
    terms: list[str] = list(tokens) if min_n == 1 else []

    n_tokens = len(tokens)
    for n in range(max(min_n, 2), min(max_n, n_tokens) + 1):
        for i in range(n_tokens - n + 1):
            terms.append(" ".join(tokens[i : i + n]))

    return terms


def _tfidf(artifact: Artifact, text: str) -> dict[int, float]:
    """Sparse L2-normalised TF-IDF vector, keyed by feature index."""
    counts = Counter(
        artifact.vocabulary[term]
        for term in analyze(text, artifact.vectorizer)
        if term in artifact.vocabulary
    )
    if not counts:
        return {}

    vector: dict[int, float] = {}
    for index, count in counts.items():
        tf = 1.0 + math.log(count) if artifact.vectorizer.sublinear_tf else float(count)
        vector[index] = tf * artifact.idf[index]

    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm > 0.0:
        for index in vector:
            vector[index] /= norm

    return vector


def decision_scores(artifact: Artifact, text: str) -> list[float]:
    """Raw one-vs-rest decision score per label, in artifact.labels order."""
    vector = _tfidf(artifact, text)
    n_features = len(artifact.vocabulary)
    coef: array = artifact.coef

    scores: list[float] = []
    for label_index in range(len(artifact.labels)):
        offset = label_index * n_features
        total = float(artifact.intercept[label_index])
        for feature_index, value in vector.items():
            total += value * coef[offset + feature_index]
        scores.append(total)

    return scores


def predict(artifact: Artifact, text: str, max_labels: int) -> list[Prediction]:
    scores = decision_scores(artifact, text)

    predictions = [
        Prediction(
            label=artifact.labels[i],
            score=score,
            probability=sigmoid(score),
        )
        for i, score in enumerate(scores)
        if score >= artifact.thresholds[i]
    ]
    predictions.sort(key=lambda p: p.score, reverse=True)
    return predictions[:max_labels]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.ClassifierInferenceTestCase`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add api/text_classifier/classifier.py api/tests/test_text_classifier.py
git commit -m "add pure-python classifier inference"
```

---

### Task 5: `exportcorpus` management command

**Files:**
- Create: `api/management/commands/exportcorpus.py`
- Test: `api/tests/management/commands/test_exportcorpus.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `manage.py exportcorpus [--per-feed N] [--max-total N] [--language ISO] [--max-content-chars N]`, writing JSONL to stdout. Each line: `{"uuid", "title", "content", "feed_id", "language", "vote_labels"}`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/management/commands/test_exportcorpus.py`:

```python
import datetime
import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryVote,
    Feed,
    FeedEntry,
    Language,
    User,
)


class ExportCorpusTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.english, _ = Language.objects.get_or_create(
            iso639_3="ENG", defaults={"iso639_1": "en", "name": "English"}
        )
        self.french, _ = Language.objects.get_or_create(
            iso639_3="FRA", defaults={"iso639_1": "fr", "name": "French"}
        )
        self.user = User.objects.create_user("corpus@test.com", None)
        self.label = ClassifierLabel.objects.create(text="Label 1")

        self.feed = Feed.objects.create(
            feed_url="http://example.com/corpus.xml",
            title="Corpus Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        self.entries = FeedEntry.objects.bulk_create(
            FeedEntry(
                feed=self.feed,
                published_at=now + datetime.timedelta(days=-i),
                title=f"Entry {i}",
                url=f"http://example.com/corpus{i}.html",
                content="x" * 100,
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
                language=self.english,
            )
            for i in range(5)
        )
        FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="French Entry",
            url="http://example.com/fr.html",
            content="bonjour",
            author_name="Jean",
            db_updated_at=None,
            is_archived=False,
            language=self.french,
        )
        ClassifierLabelFeedEntryVote.objects.create(
            feed_entry=self.entries[0], classifier_label=self.label, user=self.user
        )

    def _run(self, *args):
        out = StringIO()
        call_command("exportcorpus", *args, stdout=out, stderr=StringIO())
        return [json.loads(line) for line in out.getvalue().splitlines() if line]

    def test_emits_one_json_object_per_entry(self):
        rows = self._run()
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(
                set(row),
                {"uuid", "title", "content", "feed_id", "language", "vote_labels"},
            )

    def test_filters_to_the_requested_language(self):
        rows = self._run()
        self.assertTrue(all(row["language"] == "ENG" for row in rows))

    def test_respects_per_feed(self):
        rows = self._run("--per-feed", "2")
        self.assertEqual(len(rows), 2)

    def test_respects_max_total(self):
        rows = self._run("--max-total", "3")
        self.assertEqual(len(rows), 3)

    def test_truncates_content(self):
        rows = self._run("--max-content-chars", "10")
        self.assertTrue(all(len(row["content"]) <= 10 for row in rows))

    def test_includes_vote_labels(self):
        rows = self._run()
        by_uuid = {row["uuid"]: row for row in rows}
        self.assertEqual(
            by_uuid[str(self.entries[0].uuid)]["vote_labels"], ["Label 1"]
        )

    def test_excludes_archived_entries(self):
        FeedEntry.objects.filter(uuid=self.entries[0].uuid).update(is_archived=True)
        rows = self._run()
        self.assertEqual(len(rows), 4)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.management.commands.test_exportcorpus`
Expected: FAIL — `CommandError: Unknown command: 'exportcorpus'`.

- [ ] **Step 3: Write the command**

Create `api/management/commands/exportcorpus.py`:

```python
import json
import uuid as uuid_
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import ClassifierLabelFeedEntryVote, Feed, FeedEntry


class Command(BaseCommand):
    help = (
        "Export feed entries as JSONL for off-box classifier training. "
        "Sampling is per-feed rather than globally random, which is both "
        "index-friendly and produces a corpus balanced across publications. "
        "Pipe to gzip: `manage.py exportcorpus | gzip > corpus.jsonl.gz`"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--per-feed", type=int, default=50)
        parser.add_argument("--max-total", type=int, default=200_000)
        parser.add_argument("--language", default="ENG")
        parser.add_argument("--max-content-chars", type=int, default=4000)

    def handle(self, *args: Any, **options: Any) -> None:
        per_feed: int = options["per_feed"]
        max_total: int = options["max_total"]
        language: str = options["language"]
        max_content_chars: int = options["max_content_chars"]
        verbosity: int = options["verbosity"]

        written = 0

        for feed_uuid in Feed.objects.values_list("uuid", flat=True).iterator():
            if written >= max_total:
                break

            remaining = max_total - written
            entries = list(
                FeedEntry.objects.filter(
                    feed_id=feed_uuid,
                    language_id=language,
                    is_archived=False,
                )
                .order_by("-published_at")
                .values("uuid", "title", "content", "feed_id")[
                    : min(per_feed, remaining)
                ]
            )
            if not entries:
                continue

            votes = self._vote_labels([e["uuid"] for e in entries])

            for entry in entries:
                self.stdout.write(
                    json.dumps(
                        {
                            "uuid": str(entry["uuid"]),
                            "title": entry["title"],
                            "content": entry["content"][:max_content_chars],
                            "feed_id": str(entry["feed_id"]),
                            "language": language,
                            "vote_labels": votes.get(entry["uuid"], []),
                        },
                        separators=(",", ":"),
                    )
                )
                written += 1

        if verbosity >= 1:
            self.stderr.write(self.style.SUCCESS(f"exported {written} entry(s)"))

    def _vote_labels(
        self, feed_entry_uuids: list[uuid_.UUID]
    ) -> dict[uuid_.UUID, list[str]]:
        labels: defaultdict[uuid_.UUID, list[str]] = defaultdict(list)
        for row in (
            ClassifierLabelFeedEntryVote.objects.filter(
                feed_entry_id__in=feed_entry_uuids
            )
            .values("feed_entry_id", "classifier_label__text")
            .iterator()
        ):
            labels[row["feed_entry_id"]].append(row["classifier_label__text"])
        return labels
```

`Feed.objects.values_list(...).iterator()` streams the feed list; entries are fetched one feed at a time with a `LIMIT`, so nothing proportional to the corpus is ever held in memory.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.management.commands.test_exportcorpus`
Expected: PASS, 7 tests.

- [ ] **Step 5: Verify archived-entry content behaviour**

Read `api/tasks/archive_feed_entries.py`. Determine whether archiving clears `content` or only sets `is_archived`. The command already excludes archived entries, which is correct either way — record in the commit message which it turned out to be, since it affects how much corpus is available.

- [ ] **Step 6: Commit**

```bash
git add api/management/commands/exportcorpus.py api/tests/management/commands/test_exportcorpus.py
git commit -m "add exportcorpus command for off-box training data"
```

---

### Task 6: Training script, artifact, and parity fixtures

**Files:**
- Create: `scripts/requirements-train.txt`
- Create: `scripts/train_classifier.py`
- Create: `api/text_classifier/model/.gitkeep`
- Modify: `.pre-commit-config.yaml`
- Modify: `README.md`
- Test: `api/tests/test_text_classifier.py` (parity test)

**Interfaces:**
- Consumes: `seed_labeler.label_text` (Task 2), `artifact.dump_artifact` / `VectorizerConfig` (Task 3), `taxonomy.taxonomy_fingerprint` (Task 1).
- Produces: `api/text_classifier/model/classifier.json` and `api/text_classifier/model/parity_fixtures.json` (a list of `{"text": str, "scores": [float, ...]}` objects).

- [ ] **Step 1: Allow the artifact past the large-file hook**

`check-added-large-files` defaults to a 500kB limit and the artifact is roughly 4.5MB — without this the commit in Step 7 is rejected. In `.pre-commit-config.yaml`:

```yaml
    - id: check-added-large-files
      exclude: ^api/text_classifier/model/classifier\.json$
```

- [ ] **Step 2: Pin the training dependencies**

Create `scripts/requirements-train.txt`:

```
scikit-learn==1.7.2
scipy==1.16.2
numpy==2.3.3
```

Deliberately **not** in the `Pipfile`. These total 200MB+; adding them to `[dev-packages]` would put them in the dev image for everyone running the test suite.

- [ ] **Step 3: Write the training script**

Create `scripts/train_classifier.py`:

```python
#!/usr/bin/env python
"""Train the feed entry classifier from a corpus JSONL export.

Runs on a training box, never in production. Requires
`pip install -r scripts/requirements-train.txt`.

    python manage.py exportcorpus | gzip > corpus.jsonl.gz     # on prod
    scp prod:corpus.jsonl.gz .                                  # transfer
    python scripts/train_classifier.py corpus.jsonl.gz          # here
"""

import argparse
import datetime
import gzip
import json
import os
import random
import sys
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.text_classifier.artifact import VectorizerConfig, dump_artifact  # noqa: E402
from api.text_classifier.seed_labeler import label_text  # noqa: E402
from api.text_classifier.taxonomy import LABEL_NAMES, taxonomy_fingerprint  # noqa: E402

SEED = 20260730
TOKEN_PATTERN = r"(?u)\b\w\w+\b"
NGRAM_RANGE = (1, 2)
MAX_FEATURES = 30_000

PARITY_DOCUMENTS = [
    "",
    "cat",
    "The quick brown fox jumps over the lazy dog.",
    "nintendo nintendo nintendo nintendo",  # exercises sublinear_tf
    "the a an of and",  # stop words only
    "Café naïve résumé — Zürich Ångström",  # unicode and accents
    "C++ isn't C#; see foo_bar/baz.qux?a=1&b=2",  # punctuation
    "Box office receipts climbed as the season finale aired on Netflix.",
    "GPU benchmarks show the new chipset beating last year's motherboard.",
    "zzzz yyyy xxxx wwww",  # entirely out of vocabulary
]


def read_corpus(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def build_dataset(path, per_label_cap, per_feed_per_label_cap):
    """Weak-label the corpus and apply caps.

    Documents where no label fires are DROPPED, not treated as negatives.
    Absence of a seed match is not evidence of absence of topic. Negatives for
    label L come from documents where some other label fired but L did not.
    """
    rng = random.Random(SEED)

    per_label: defaultdict[str, list] = defaultdict(list)
    per_feed_label: defaultdict[tuple[str, str], int] = defaultdict(int)
    dropped = 0

    for row in read_corpus(path):
        text = f"{row['title']} {row['content']}"
        labels = label_text(text)
        if not labels:
            dropped += 1
            continue

        for label in labels:
            key = (row["feed_id"], label)
            if per_feed_label[key] >= per_feed_per_label_cap:
                continue
            per_feed_label[key] += 1
            per_label[label].append((row["feed_id"], text, labels))

    documents: dict[str, tuple[str, str, frozenset]] = {}
    for label, rows in per_label.items():
        sampled = rows if len(rows) <= per_label_cap else rng.sample(rows, per_label_cap)
        for feed_id, text, labels in sampled:
            documents[text] = (feed_id, text, labels)

    print(f"kept {len(documents)} document(s); dropped {dropped} unlabelled", file=sys.stderr)
    for label in LABEL_NAMES:
        print(f"  {label}: {len(per_label.get(label, []))}", file=sys.stderr)

    return list(documents.values())


def feed_wise_split(rows, dev_fraction=0.2):
    """Split by feed, never by entry.

    An entry-wise split lets a model that has learned a publication's
    boilerplate score well on the dev set, which is the exact failure this
    whole design guards against.
    """
    rng = random.Random(SEED)
    feed_ids = sorted({feed_id for feed_id, _, _ in rows})
    rng.shuffle(feed_ids)
    dev_feeds = set(feed_ids[: max(1, int(len(feed_ids) * dev_fraction))])

    train = [r for r in rows if r[0] not in dev_feeds]
    dev = [r for r in rows if r[0] in dev_feeds]
    return train, dev


def to_matrix(rows, labels):
    texts = [text for _, text, _ in rows]
    y = np.zeros((len(rows), len(labels)), dtype=np.int8)
    for i, (_, _, row_labels) in enumerate(rows):
        for j, label in enumerate(labels):
            if label in row_labels:
                y[i, j] = 1
    return texts, y


def best_threshold(scores, truth):
    """Decision-score threshold maximising F1 for one label on the dev set."""
    candidates = np.unique(np.concatenate([scores, [scores.min() - 1.0]]))
    best, best_f1 = 0.0, -1.0
    for threshold in candidates:
        predicted = (scores >= threshold).astype(np.int8)
        _, _, f1, _ = precision_recall_fscore_support(
            truth, predicted, average="binary", zero_division=0
        )
        if f1 > best_f1:
            best, best_f1 = float(threshold), float(f1)
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument(
        "--out", default="api/text_classifier/model/classifier.json"
    )
    parser.add_argument(
        "--fixtures", default="api/text_classifier/model/parity_fixtures.json"
    )
    parser.add_argument("--per-label-cap", type=int, default=5000)
    parser.add_argument("--per-feed-per-label-cap", type=int, default=200)
    args = parser.parse_args()

    rows = build_dataset(
        args.corpus, args.per_label_cap, args.per_feed_per_label_cap
    )
    train_rows, dev_rows = feed_wise_split(rows)
    print(f"train={len(train_rows)} dev={len(dev_rows)}", file=sys.stderr)

    labels = list(LABEL_NAMES)
    train_texts, train_y = to_matrix(train_rows, labels)
    dev_texts, dev_y = to_matrix(dev_rows, labels)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        token_pattern=TOKEN_PATTERN,
        ngram_range=NGRAM_RANGE,
        max_features=MAX_FEATURES,
        sublinear_tf=True,
        norm="l2",
        stop_words="english",
    )
    x_train = vectorizer.fit_transform(train_texts)
    x_dev = vectorizer.transform(dev_texts)

    n_features = len(vectorizer.vocabulary_)
    coef = np.zeros((len(labels), n_features), dtype=np.float64)
    intercept = np.zeros(len(labels), dtype=np.float64)
    thresholds = np.zeros(len(labels), dtype=np.float64)

    for j, label in enumerate(labels):
        if train_y[:, j].sum() == 0:
            print(f"WARNING: no positives for {label!r}; label will never fire",
                  file=sys.stderr)
            thresholds[j] = float("inf")
            continue

        estimator = LogisticRegression(
            class_weight="balanced", max_iter=2000, random_state=SEED
        )
        estimator.fit(x_train, train_y[:, j])
        coef[j] = estimator.coef_[0]
        intercept[j] = estimator.intercept_[0]

        if dev_y[:, j].sum() > 0:
            thresholds[j] = best_threshold(
                estimator.decision_function(x_dev), dev_y[:, j]
            )
        else:
            thresholds[j] = 0.0

    # Vocabulary in index order.
    terms = [""] * n_features
    for term, index in vectorizer.vocabulary_.items():
        terms[index] = term

    idf = vectorizer.idf_

    config = VectorizerConfig(
        token_pattern=TOKEN_PATTERN,
        ngram_range=NGRAM_RANGE,
        lowercase=True,
        sublinear_tf=True,
        norm="l2",
        stop_words=tuple(sorted(ENGLISH_STOP_WORDS)),
    )

    fingerprint = dump_artifact(
        args.out,
        labels=labels,
        vocabulary_terms=terms,
        idf=[float(v) for v in idf],
        coef=[float(v) for v in coef.reshape(-1)],
        intercept=[float(v) for v in intercept],
        thresholds=[float(v) for v in thresholds],
        vectorizer=config,
        taxonomy_fingerprint=taxonomy_fingerprint(),
        training={
            "n_docs": len(rows),
            "n_train": len(train_rows),
            "n_dev": len(dev_rows),
            "labeler": "seed_terms_v1",
            "trained_at": datetime.datetime.now(datetime.UTC).isoformat(),
        },
    )
    print(f"wrote {args.out} ({fingerprint})", file=sys.stderr)

    # Parity fixtures: sklearn's own decision scores for a set of adversarial
    # documents. The pure-Python inference path must reproduce these exactly,
    # which is what stops a tokenizer divergence degrading the model silently.
    fixture_x = vectorizer.transform(PARITY_DOCUMENTS)
    fixture_scores = (fixture_x @ coef.T) + intercept

    with open(args.fixtures, "w") as f:
        json.dump(
            [
                {"text": text, "scores": [float(v) for v in fixture_scores[i]]}
                for i, text in enumerate(PARITY_DOCUMENTS)
            ],
            f,
            indent=2,
        )
    print(f"wrote {args.fixtures}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

Note `fixture_scores` is computed as an explicit `X @ coef.T + intercept` rather than via `estimator.decision_function`, so the fixtures test exactly the quantity `classifier.decision_scores` computes and nothing depends on how scikit-learn's one-vs-rest wrapper normalises `predict_proba`.

- [ ] **Step 4: Write the parity test**

Create `api/text_classifier/model/.gitkeep` (empty) so the directory exists before an artifact is trained, then append to `api/tests/test_text_classifier.py`:

```python
class ParityTestCase(TestCase):
    ARTIFACT = "api/text_classifier/model/classifier.json"
    FIXTURES = "api/text_classifier/model/parity_fixtures.json"

    def test_pure_python_matches_sklearn(self):
        if not (os.path.exists(self.ARTIFACT) and os.path.exists(self.FIXTURES)):
            self.skipTest("no trained artifact; run scripts/train_classifier.py")

        from api.text_classifier.artifact import load_artifact
        from api.text_classifier.classifier import decision_scores

        artifact = load_artifact(self.ARTIFACT)
        with open(self.FIXTURES, "r") as f:
            fixtures = json.load(f)

        self.assertGreaterEqual(len(fixtures), 10)

        for fixture in fixtures:
            with self.subTest(text=fixture["text"][:40]):
                actual = decision_scores(artifact, fixture["text"])
                self.assertEqual(len(actual), len(fixture["scores"]))
                for label, expected_score, actual_score in zip(
                    artifact.labels, fixture["scores"], actual
                ):
                    self.assertAlmostEqual(
                        actual_score, expected_score, places=4, msg=label
                    )

    def test_artifact_matches_current_taxonomy(self):
        if not os.path.exists(self.ARTIFACT):
            self.skipTest("no trained artifact")

        from api.text_classifier.artifact import load_artifact
        from api.text_classifier.taxonomy import taxonomy_fingerprint

        artifact = load_artifact(self.ARTIFACT)
        self.assertEqual(
            artifact.taxonomy_fingerprint,
            taxonomy_fingerprint(),
            "seed terms have changed since this model was trained; retrain",
        )
```

The `skipTest` guards let the suite pass before the first model is trained. Once an artifact is committed they become live and stay live.

- [ ] **Step 5: Train a model**

On the training box:

```bash
pip install -r scripts/requirements-train.txt
# corpus.jsonl.gz produced by `manage.py exportcorpus` on production
python scripts/train_classifier.py corpus.jsonl.gz
```

Read the per-label document counts it prints. Any label with zero positives will warn and be permanently disabled — that is the signal to go back to `taxonomy.py` and add terms for it before continuing.

- [ ] **Step 6: Run the parity test**

Run: `./scripts/run_tests.sh api.tests.test_text_classifier.ParityTestCase`
Expected: PASS, 2 tests, neither skipped.

**If parity fails**, the divergence is in `analyze` or `_tfidf` in `api/text_classifier/classifier.py`, not in the training script. Check in this order: stop-word removal happening before bigram assembly; `sublinear_tf` using `math.log` (natural) rather than `log10`; L2 normalisation applied after multiplying by idf; single-character tokens excluded by the token pattern.

- [ ] **Step 7: Document the workflow and commit**

Add this section to the README, after the scheduler section:

````markdown
## Training the classifier

The feed entry classifier ships as a pre-trained artifact at
`api/text_classifier/model/classifier.json`, committed to this repository, so a
`docker pull` gives you a working classifier with no setup. You only need to
retrain if you change the seed terms in `api/text_classifier/taxonomy.py`.

Training runs off-box. Nothing in the production image can import
scikit-learn.

**1. Export a corpus from the running deployment:**

```sh
docker compose exec -T rss_temple python ./manage.py exportcorpus \
  | gzip > corpus.jsonl.gz
```

**2. Copy it to a machine with the training dependencies:**

```sh
scp corpus.jsonl.gz training-box:~/
pip install -r scripts/requirements-train.txt
```

**3. Train:**

```sh
python scripts/train_classifier.py corpus.jsonl.gz
```

This writes `api/text_classifier/model/classifier.json` and
`api/text_classifier/model/parity_fixtures.json`. Read the per-label document
counts it prints — a label with no positives will never fire and needs better
seed terms.

**4. Verify and evaluate:**

```sh
./scripts/run_tests.sh api.tests.test_text_classifier
python scripts/eval_classifier.py
```

The parity test checks that the pure-Python inference path reproduces
scikit-learn's scores exactly; it must pass before you ship. `eval_classifier.py`
scores the model against the hand-labelled gold set and enforces two gates: the
model must beat the raw seed labeler, and no label may ship below the precision
floor.

**5. Commit both files.** Deploying the new artifact automatically re-labels the
existing corpus, because entries record the fingerprint of the model that
labelled them.
````

```bash
git add scripts/requirements-train.txt scripts/train_classifier.py \
        api/text_classifier/model/ .pre-commit-config.yaml \
        api/tests/test_text_classifier.py README.md
git commit -m "add classifier training script and trained artifact"
```

---

### Task 7: `FeedEntry.classifier_model_fingerprint`

**Files:**
- Modify: `api/models.py` (`FeedEntry`)
- Create: `api/migrations/00XX_*.py` (generated)
- Modify: `rss_temple/settings.py`
- Test: `api/tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `FeedEntry.classifier_model_fingerprint: str` (default `""`, indexed). Settings `CLASSIFIER_MODEL_PATH`, `CLASSIFIER_MAX_LABELS_PER_ENTRY`, `CLASSIFIER_LABEL_EXPIRY_INTERVAL`.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_models.py`:

```python
class FeedEntryClassifierFingerprintTestCase(TestCase):
    def test_defaults_to_empty_string(self):
        now = timezone.now()
        feed = Feed.objects.create(
            feed_url="http://example.com/fp.xml",
            title="FP Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        feed_entry = FeedEntry.objects.create(
            feed=feed,
            published_at=now,
            title="Entry",
            url="http://example.com/fp.html",
            content="content",
            author_name="John Doe",
            db_updated_at=None,
            is_archived=False,
        )
        self.assertEqual(feed_entry.classifier_model_fingerprint, "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/run_tests.sh api.tests.test_models.FeedEntryClassifierFingerprintTestCase`
Expected: FAIL — `AttributeError: 'FeedEntry' object has no attribute 'classifier_model_fingerprint'`.

- [ ] **Step 3: Add the field**

In `api/models.py`, on `FeedEntry`, immediately after `has_top_image_been_processed`:

```python
    classifier_model_fingerprint = models.CharField(
        max_length=64,
        default="",
        db_index=True,
        help_text=(
            "model_fingerprint of the classifier artifact that last labelled this "
            "entry. Empty means never labelled. Deliberately a fingerprint rather "
            "than a boolean (cf. has_top_image_been_processed) so that shipping a "
            "new model invalidates every entry automatically instead of needing a "
            "manual reset."
        ),
    )
```

`AddIndexConcurrently` is deliberately not used — it is PostgreSQL-only and the test suite runs on SQLite. At ~250k rows the index build takes about a second and briefly locks the table, which is acceptable during a deploy.

- [ ] **Step 4: Generate the migration**

```bash
pipenv run python manage.py makemigrations api
./scripts/post_makemigrations.sh
```

Expected: one new migration with a single `AddField` (plus its index).

- [ ] **Step 5: Add the settings**

In `rss_temple/settings.py`, after `CLASSIFIER_LABEL_CALCULATED_WEIGHT`:

```python
CLASSIFIER_MODEL_PATH = os.getenv(
    "APP_CLASSIFIER_MODEL_PATH",
    os.path.join(BASE_DIR, "api", "text_classifier", "model", "classifier.json"),
)
CLASSIFIER_MAX_LABELS_PER_ENTRY = int(
    os.getenv("APP_CLASSIFIER_MAX_LABELS_PER_ENTRY", "3")
)
# Deliberately NOT LABELING_EXPIRY_INTERVAL (7 days). Model output does not
# decay with time -- it only changes when the model changes -- so a short
# expiry would force a full re-classification of the entire corpus every week.
# Real invalidation is driven by classifier_model_fingerprint. This is a safety
# net only.
CLASSIFIER_LABEL_EXPIRY_INTERVAL = datetime.timedelta(days=365)
```

Confirm `BASE_DIR` and `os` are already available in the settings module (they are — `BASE_DIR` is used by the SQLite config at line ~118).

- [ ] **Step 6: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.test_models`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/models.py api/migrations/ rss_temple/settings.py api/tests/test_models.py
git commit -m "add classifier model fingerprint marker to feed entries"
```

---

### Task 8: `label_feed_entries` task, registration, and the import guard

**Files:**
- Create: `api/tasks/label_feed_entries.py`
- Modify: `api/tasks/__init__.py`
- Modify: `api_dramatiq/tasks.py`
- Modify: `api/management/commands/_schedulerdaemon_serializers.py`
- Modify: `schedulerdaemon.example.json`
- Modify: `README.md`
- Test: `api/tests/tasks/test_label_feed_entries.py`
- Test: `api/tests/test_text_classifier.py` (import guard)

**Interfaces:**
- Consumes: `classifier.predict` / `artifact.load_artifact` (Tasks 3–4), `FeedEntry.classifier_model_fingerprint` (Task 7), `ClassifierLabelFeedEntryCalculated.weight` (plan 1).
- Produces: `label_feed_entries(db_limit: int = 1000, large_backlog_threshold: int = 50_000) -> int` returning the number of entries processed.

- [ ] **Step 1: Write the failing test**

Create `api/tests/tasks/test_label_feed_entries.py`:

```python
import datetime
import json
import logging
import os
import tempfile
from typing import ClassVar

from django.test import TestCase, override_settings
from django.utils import timezone

from api.models import (
    ClassifierLabel,
    ClassifierLabelFeedEntryCalculated,
    Feed,
    FeedEntry,
    Language,
)
from api.tasks.label_feed_entries import label_feed_entries
from api.text_classifier.artifact import VectorizerConfig, dump_artifact


class LabelFeedEntriesTestCase(TestCase):
    old_app_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)

    def setUp(self):
        now = timezone.now()
        self.english, _ = Language.objects.get_or_create(
            iso639_3="ENG", defaults={"iso639_1": "en", "name": "English"}
        )
        self.french, _ = Language.objects.get_or_create(
            iso639_3="FRA", defaults={"iso639_1": "fr", "name": "French"}
        )
        self.gaming = ClassifierLabel.objects.create(text="Gaming")
        self.orphan = ClassifierLabel.objects.create(text="Music")

        self.feed = Feed.objects.create(
            feed_url="http://example.com/lfe.xml",
            title="LFE Feed",
            home_url="http://example.com",
            published_at=now,
            updated_at=None,
            db_updated_at=None,
        )
        self.matching = FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="nintendo",
            url="http://example.com/lfe1.html",
            content="nintendo",
            author_name="A",
            db_updated_at=None,
            is_archived=False,
            language=self.english,
        )
        self.non_matching = FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="zzzz",
            url="http://example.com/lfe2.html",
            content="zzzz",
            author_name="A",
            db_updated_at=None,
            is_archived=False,
            language=self.english,
        )
        self.french_entry = FeedEntry.objects.create(
            feed=self.feed,
            published_at=now,
            title="nintendo",
            url="http://example.com/lfe3.html",
            content="nintendo",
            author_name="A",
            db_updated_at=None,
            is_archived=False,
            language=self.french,
        )

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.model_path = os.path.join(self.tmpdir.name, "classifier.json")
        self.fingerprint = dump_artifact(
            self.model_path,
            labels=["Gaming", "Music", "Ghost Label"],
            vocabulary_terms=["nintendo"],
            idf=[1.0],
            # Gaming fires on "nintendo"; Music and Ghost Label never fire.
            coef=[10.0, -10.0, -10.0],
            intercept=[0.0, 0.0, 0.0],
            thresholds=[1.0, 1.0, 1.0],
            vectorizer=VectorizerConfig(
                token_pattern=r"(?u)\b\w\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                norm="l2",
                stop_words=(),
            ),
            taxonomy_fingerprint="sha256:test",
            training={},
        )

    def _settings(self, **overrides):
        base = {
            "CLASSIFIER_MODEL_PATH": self.model_path,
            "CLASSIFIER_MAX_LABELS_PER_ENTRY": 3,
            "CLASSIFIER_LABEL_CALCULATED_WEIGHT": 0.5,
            "CLASSIFIER_LABEL_EXPIRY_INTERVAL": datetime.timedelta(days=365),
        }
        base.update(overrides)
        return override_settings(**base)

    def test_writes_weighted_labels(self):
        with self._settings():
            label_feed_entries()

        rows = list(
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry=self.matching
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].classifier_label_id, self.gaming.uuid)
        self.assertGreater(rows[0].weight, 0.0)
        self.assertLessEqual(rows[0].weight, 0.5)

    def test_marks_entries_that_produce_no_labels(self):
        with self._settings():
            label_feed_entries()

        self.non_matching.refresh_from_db()
        self.assertEqual(
            self.non_matching.classifier_model_fingerprint, self.fingerprint
        )
        self.assertEqual(
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry=self.non_matching
            ).count(),
            0,
        )

    def test_is_idempotent(self):
        with self._settings():
            first = label_feed_entries()
            second = label_feed_entries()

        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry=self.matching
            ).count(),
            1,
        )

    def test_skips_non_english_entries(self):
        with self._settings():
            label_feed_entries()

        self.french_entry.refresh_from_db()
        self.assertEqual(self.french_entry.classifier_model_fingerprint, "")

    def test_respects_db_limit(self):
        with self._settings():
            processed = label_feed_entries(db_limit=1)
        self.assertEqual(processed, 1)

    def test_unknown_label_text_is_skipped_not_raised(self):
        # "Ghost Label" is in the artifact but not in the database.
        with self._settings():
            label_feed_entries()
        self.assertFalse(
            ClassifierLabel.objects.filter(text="Ghost Label").exists()
        )

    def test_expired_rows_reset_the_fingerprint_and_are_relabelled(self):
        with self._settings():
            label_feed_entries()

        ClassifierLabelFeedEntryCalculated.objects.filter(
            feed_entry=self.matching
        ).update(expires_at=timezone.now() - datetime.timedelta(days=1))

        with self._settings():
            label_feed_entries()

        # The entry must be re-labelled, not left permanently label-less.
        self.assertEqual(
            ClassifierLabelFeedEntryCalculated.objects.filter(
                feed_entry=self.matching
            ).count(),
            1,
        )

    def test_new_model_fingerprint_reprocesses_entries(self):
        with self._settings():
            label_feed_entries()

        other_path = os.path.join(self.tmpdir.name, "classifier2.json")
        dump_artifact(
            other_path,
            labels=["Gaming"],
            vocabulary_terms=["nintendo"],
            idf=[1.0],
            coef=[20.0],
            intercept=[0.0],
            thresholds=[1.0],
            vectorizer=VectorizerConfig(
                token_pattern=r"(?u)\b\w\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
                sublinear_tf=True,
                norm="l2",
                stop_words=(),
            ),
            taxonomy_fingerprint="sha256:test",
            training={},
        )

        with self._settings(CLASSIFIER_MODEL_PATH=other_path):
            processed = label_feed_entries()

        self.assertGreater(processed, 0)
```

And append the import guard to `api/tests/test_text_classifier.py`:

```python
class ImportGuardTestCase(TestCase):
    def test_views_do_not_import_the_classifier(self):
        """The model must live in the dramatiq worker, not in every web worker.

        `api.views` is imported by every one of `cpu_count() * 2 + 1` gunicorn
        workers. A transitive import of `classifier` here would load the ~10MB
        artifact into each of them, silently.
        """
        import subprocess
        import sys

        script = (
            "import os, django;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rss_temple.settings');"
            "django.setup();"
            "import api.views;"
            "import sys;"
            "assert 'api.text_classifier.classifier' not in sys.modules, "
            "'api.views transitively imports api.text_classifier.classifier'"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.tasks.test_label_feed_entries`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.tasks.label_feed_entries'`.

- [ ] **Step 3: Write the task**

Create `api/tasks/label_feed_entries.py`:

```python
import logging
import uuid as uuid_

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.db import transaction
from django.db.models.functions import Now
from django.utils import timezone

from api.lock_context import lock_context
from api.models import ClassifierLabel, ClassifierLabelFeedEntryCalculated, FeedEntry
from api.text_classifier.artifact import Artifact, load_artifact
from api.text_classifier.classifier import predict
from api.text_classifier.prep_content import prep_for_classification

_logger = logging.getLogger("rss_temple.tasks.label_feed_entries")

_artifact: Artifact | None = None
_artifact_path: str | None = None


def _get_artifact() -> Artifact:
    """Load lazily, on first call, never at import time.

    `api/text_classifier/lang_detector.py` builds its detector at module import;
    that is what put lingua into every gunicorn worker. Do not copy it.
    """
    global _artifact, _artifact_path

    path = str(settings.CLASSIFIER_MODEL_PATH)
    if _artifact is None or _artifact_path != path:
        _artifact = load_artifact(path)
        _artifact_path = path
        _logger.info(
            "loaded classifier artifact %s (%d labels, %d features)",
            _artifact.model_fingerprint,
            len(_artifact.labels),
            len(_artifact.vocabulary),
        )
    return _artifact


def _label_uuids_by_text(artifact: Artifact) -> dict[str, uuid_.UUID]:
    known = dict(
        ClassifierLabel.objects.filter(text__in=artifact.labels).values_list(
            "text", "uuid"
        )
    )
    for label in artifact.labels:
        if label not in known:
            _logger.warning(
                "artifact label %r is not in the database; predictions for it "
                "will be discarded (see `manage.py checkclassifierlabels`)",
                label,
            )
    return known


def _expire_stale_rows() -> int:
    """Delete expired calculated rows AND reset the affected fingerprints.

    Without the reset the entry still looks processed, is never re-selected,
    and permanently loses its labels.
    """
    with transaction.atomic():
        expired = ClassifierLabelFeedEntryCalculated.objects.filter(
            expires_at__lte=Now()
        )
        feed_entry_ids = list(
            expired.values_list("feed_entry_id", flat=True).distinct()
        )
        if not feed_entry_ids:
            return 0

        expired.delete()
        FeedEntry.objects.filter(uuid__in=feed_entry_ids).update(
            classifier_model_fingerprint=""
        )

    return len(feed_entry_ids)


def label_feed_entries(
    db_limit: int = 1000, large_backlog_threshold: int = 50_000
) -> int:
    cache: BaseCache = caches["default"]

    with lock_context(cache, "label_feed_entries_lock"):
        artifact = _get_artifact()

        reset = _expire_stale_rows()
        if reset:
            _logger.info("reset %d entry(s) whose labels expired", reset)

        label_uuids = _label_uuids_by_text(artifact)
        max_labels: int = settings.CLASSIFIER_MAX_LABELS_PER_ENTRY
        weight_multiplier: float = settings.CLASSIFIER_LABEL_CALCULATED_WEIGHT
        expires_at = timezone.now() + settings.CLASSIFIER_LABEL_EXPIRY_INTERVAL

        # No order_by: ordering would force a sort over the whole backlog for no
        # benefit, whereas an unordered LIMIT lets Postgres stop early.
        pending = FeedEntry.objects.filter(
            language_id="ENG", is_archived=False
        ).exclude(classifier_model_fingerprint=artifact.model_fingerprint)

        total_remaining = pending.count()
        if total_remaining > large_backlog_threshold:
            _logger.warning(
                "large label-feed-entries backlog: %d is larger than threshold %d",
                total_remaining,
                large_backlog_threshold,
            )

        entries = list(pending.values("uuid", "title", "content")[:db_limit])
        if not entries:
            return 0

        rows: list[ClassifierLabelFeedEntryCalculated] = []
        for entry in entries:
            text = prep_for_classification(entry["title"], entry["content"])
            for prediction in predict(artifact, text, max_labels):
                label_uuid = label_uuids.get(prediction.label)
                if label_uuid is None:
                    continue
                rows.append(
                    ClassifierLabelFeedEntryCalculated(
                        classifier_label_id=label_uuid,
                        feed_entry_id=entry["uuid"],
                        expires_at=expires_at,
                        weight=prediction.probability * weight_multiplier,
                    )
                )

        with transaction.atomic():
            ClassifierLabelFeedEntryCalculated.objects.bulk_create(
                rows, ignore_conflicts=True
            )
            FeedEntry.objects.filter(
                uuid__in=[e["uuid"] for e in entries]
            ).update(classifier_model_fingerprint=artifact.model_fingerprint)

        _logger.info("labelled %d entry(s), wrote %d row(s)", len(entries), len(rows))
        return len(entries)
```

- [ ] **Step 4: Export from `api/tasks/__init__.py`**

Add the import alphabetically among the existing ones:

```python
from .label_feed_entries import label_feed_entries
```

and add `"label_feed_entries",` to the `__all__` list, next to `"label_feeds"`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.tasks.test_label_feed_entries api.tests.test_text_classifier.ImportGuardTestCase`
Expected: PASS, 9 tests.

- [ ] **Step 6: Register the dramatiq actor**

In `api_dramatiq/tasks.py`, add the import alongside the existing `label_feeds_` / `label_users_` imports:

```python
from api.tasks import label_feed_entries as label_feed_entries_
```

and the actor, next to `label_feeds` / `label_users`:

```python
@dramatiq.actor(queue_name="rss_temple")
def label_feed_entries(
    *args: Any, db_limit=1000, large_backlog_threshold=50000, **kwargs: Any
) -> None:
    count = label_feed_entries_(db_limit, large_backlog_threshold)
    label_feed_entries.logger.info("labelled %d feed entry(s)", count)
```

- [ ] **Step 7: Register the scheduler serializer**

In `api/management/commands/_schedulerdaemon_serializers.py`, add this immediately after `_LabelUsersSerializer` (which ends around line 136):

```python
class _LabelFeedEntriesSerializer(serializers.Serializer):
    # Every 5 minutes: at db_limit 1000 a ~250,000-entry backlog needs 250 runs,
    # which is roughly a day at this cadence.
    crontab = serializers.CharField(default="*/5 * * * *")
    dbLimit = serializers.IntegerField(source="db_limit", default=1000)
    largeBacklogThreshold = serializers.IntegerField(
        source="large_backlog_threshold", default=50000
    )

    def create(self, validated_data: Any) -> Any:
        scheduler: BaseScheduler = self.context["scheduler"]
        job = scheduler.add_job(
            jobs.label_feed_entries,
            trigger=CronTrigger.from_crontab(validated_data["crontab"]),
            id="label_feed_entries",
            max_instances=1,
            replace_existing=True,
            coalesce=True,
            kwargs={
                "db_limit": validated_data["db_limit"],
                "large_backlog_threshold": validated_data[
                    "large_backlog_threshold"
                ],
            },
        )
        return job
```

Then add the field to `SetupSerializer` (around line 304), next to `label_feeds`:

```python
    label_feed_entries = _LabelFeedEntriesSerializer()
```

- [ ] **Step 8: Add to the example scheduler config and README**

In `schedulerdaemon.example.json`, alongside `"label_feeds"` and `"label_users"` (note: tab-indented, matching the existing file):

```json
	"label_feed_entries": {},
```

In the README's scheduler section (around line 342), add `"label_feed_entries": {},` to the example JSON block and this note beneath it:

```markdown
`label_feed_entries` runs the trained text classifier over unlabelled feed
entries. It processes `dbLimit` entries per run (default 1000) and marks each
one with the model's fingerprint, so shipping a new model automatically
re-labels the corpus. A backlog of ~250,000 entries takes around 250 runs to
clear — roughly a day at the default five-minute cadence, or ten days if you
lower it to hourly. A warning is logged when the backlog exceeds
`largeBacklogThreshold`.
```

- [ ] **Step 9: Run the full suite**

Run: `./scripts/run_tests.sh`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add api/tasks/label_feed_entries.py api/tasks/__init__.py api_dramatiq/tasks.py \
        api/management/commands/_schedulerdaemon_serializers.py \
        schedulerdaemon.example.json README.md \
        api/tests/tasks/test_label_feed_entries.py api/tests/test_text_classifier.py
git commit -m "add label_feed_entries task writing weighted machine labels"
```

---

### Task 9: Gold set and evaluation

**Files:**
- Create: `api/management/commands/exportgoldcandidates.py`
- Create: `api/text_classifier/gold/gold_set.jsonl`
- Create: `scripts/eval_classifier.py`
- Test: `api/tests/management/commands/test_exportgoldcandidates.py`
- Test: `api/tests/test_text_classifier.py` (gold set well-formedness)

**Interfaces:**
- Consumes: `taxonomy.LABEL_NAMES` (Task 1), `artifact.load_artifact` / `classifier.predict` (Tasks 3–4), `seed_labeler.label_text` (Task 2).
- Produces: `manage.py exportgoldcandidates --count N` writing a JSONL template; `scripts/eval_classifier.py` printing per-label precision/recall/F1 plus the two ship gates.

- [ ] **Step 1: Write the failing test**

Create `api/tests/management/commands/test_exportgoldcandidates.py`:

```python
import datetime
import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from api.models import Feed, FeedEntry, Language


class ExportGoldCandidatesTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        english, _ = Language.objects.get_or_create(
            iso639_3="ENG", defaults={"iso639_1": "en", "name": "English"}
        )
        for f in range(3):
            feed = Feed.objects.create(
                feed_url=f"http://example.com/gold{f}.xml",
                title=f"Gold Feed {f}",
                home_url="http://example.com",
                published_at=now,
                updated_at=None,
                db_updated_at=None,
            )
            FeedEntry.objects.bulk_create(
                FeedEntry(
                    feed=feed,
                    published_at=now + datetime.timedelta(days=-i),
                    title=f"Entry {f}-{i}",
                    url=f"http://example.com/gold{f}-{i}.html",
                    content="y" * 900,
                    author_name="A",
                    db_updated_at=None,
                    is_archived=False,
                    language=english,
                )
                for i in range(4)
            )

    def _run(self, *args):
        out = StringIO()
        call_command("exportgoldcandidates", *args, stdout=out, stderr=StringIO())
        return [json.loads(line) for line in out.getvalue().splitlines() if line]

    def test_emits_template_rows_with_empty_labels(self):
        rows = self._run("--count", "6")
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(
                set(row), {"uuid", "title", "content_excerpt", "feed_id", "labels"}
            )
            self.assertEqual(row["labels"], [])

    def test_stratifies_across_feeds(self):
        rows = self._run("--count", "6")
        self.assertEqual(len({row["feed_id"] for row in rows}), 3)

    def test_truncates_the_excerpt(self):
        rows = self._run("--count", "3", "--excerpt-chars", "50")
        self.assertTrue(all(len(r["content_excerpt"]) <= 50 for r in rows))
```

And append the gold-set well-formedness check to `api/tests/test_text_classifier.py`:

```python
class GoldSetTestCase(TestCase):
    PATH = "api/text_classifier/gold/gold_set.jsonl"

    def test_gold_set_is_well_formed(self):
        if not os.path.exists(self.PATH):
            self.skipTest("no gold set yet")

        from api.text_classifier.taxonomy import LABEL_NAMES

        with open(self.PATH, "r") as f:
            rows = [json.loads(line) for line in f if line.strip()]

        self.assertGreaterEqual(len(rows), 200)
        seen_uuids = set()
        for row in rows:
            self.assertEqual(
                set(row), {"uuid", "title", "content_excerpt", "feed_id", "labels"}
            )
            self.assertNotIn(row["uuid"], seen_uuids)
            seen_uuids.add(row["uuid"])
            for label in row["labels"]:
                self.assertIn(label, LABEL_NAMES)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/run_tests.sh api.tests.management.commands.test_exportgoldcandidates`
Expected: FAIL — `CommandError: Unknown command: 'exportgoldcandidates'`.

- [ ] **Step 3: Write the command**

Create `api/management/commands/exportgoldcandidates.py`:

```python
import json
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import Feed, FeedEntry


class Command(BaseCommand):
    help = (
        "Emit a JSONL template of feed entries for hand-labelling into a gold "
        "evaluation set. Fill in the empty `labels` array on each line, then "
        "save the result as api/text_classifier/gold/gold_set.jsonl. Entries "
        "are stratified across feeds."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--count", type=int, default=300)
        parser.add_argument("--language", default="ENG")
        parser.add_argument("--excerpt-chars", type=int, default=500)

    def handle(self, *args: Any, **options: Any) -> None:
        count: int = options["count"]
        language: str = options["language"]
        excerpt_chars: int = options["excerpt_chars"]

        feed_uuids = list(Feed.objects.values_list("uuid", flat=True))
        if not feed_uuids:
            return

        per_feed = max(1, count // len(feed_uuids))
        written = 0

        # Round-robin over feeds so a few high-volume publications cannot
        # dominate the gold set the way they dominate the corpus.
        while written < count:
            progressed = False
            for feed_uuid in feed_uuids:
                if written >= count:
                    break
                entries = FeedEntry.objects.filter(
                    feed_id=feed_uuid, language_id=language, is_archived=False
                ).order_by("-published_at")[written // len(feed_uuids) : ][:per_feed]
                for entry in entries:
                    if written >= count:
                        break
                    self.stdout.write(
                        json.dumps(
                            {
                                "uuid": str(entry.uuid),
                                "title": entry.title,
                                "content_excerpt": entry.content[:excerpt_chars],
                                "feed_id": str(entry.feed_id),
                                "labels": [],
                            },
                            separators=(",", ":"),
                        )
                    )
                    written += 1
                    progressed = True
            if not progressed:
                break

        self.stderr.write(self.style.SUCCESS(f"emitted {written} candidate(s)"))
```

- [ ] **Step 4: Write the evaluation script**

Create `scripts/eval_classifier.py`:

```python
#!/usr/bin/env python
"""Score a trained artifact against the hand-labelled gold set.

Runs on the training box. This is the only independent measurement in the
design: training labels are machine-generated, so "the model agrees with the
seed labeler" is not evidence of anything.

    python scripts/eval_classifier.py
"""

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.text_classifier.artifact import load_artifact  # noqa: E402
from api.text_classifier.classifier import predict  # noqa: E402
from api.text_classifier.seed_labeler import label_text  # noqa: E402
from api.text_classifier.taxonomy import LABEL_NAMES  # noqa: E402


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall) if precision + recall else 0.0
    )
    return precision, recall, f1


def score(predictions_by_uuid, gold_rows):
    tp: defaultdict[str, int] = defaultdict(int)
    fp: defaultdict[str, int] = defaultdict(int)
    fn: defaultdict[str, int] = defaultdict(int)
    covered = 0

    for row in gold_rows:
        predicted = predictions_by_uuid.get(row["uuid"], set())
        truth = set(row["labels"])
        if predicted:
            covered += 1
        for label in LABEL_NAMES:
            if label in predicted and label in truth:
                tp[label] += 1
            elif label in predicted:
                fp[label] += 1
            elif label in truth:
                fn[label] += 1

    per_label = {
        label: prf(tp[label], fp[label], fn[label]) for label in LABEL_NAMES
    }
    macro_f1 = sum(f for _, _, f in per_label.values()) / len(per_label)
    return per_label, macro_f1, covered / len(gold_rows) if gold_rows else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", default="api/text_classifier/model/classifier.json")
    parser.add_argument("--gold", default="api/text_classifier/gold/gold_set.jsonl")
    parser.add_argument("--max-labels", type=int, default=3)
    parser.add_argument("--precision-floor", type=float, default=0.5)
    args = parser.parse_args()

    artifact = load_artifact(args.artifact)
    with open(args.gold, "r") as f:
        gold_rows = [json.loads(line) for line in f if line.strip()]

    model_predictions = {}
    seed_predictions = {}
    for row in gold_rows:
        text = f"{row['title']} {row['content_excerpt']}"
        model_predictions[row["uuid"]] = {
            p.label for p in predict(artifact, text, args.max_labels)
        }
        seed_predictions[row["uuid"]] = set(label_text(text))

    model_per_label, model_macro, coverage = score(model_predictions, gold_rows)
    _, seed_macro, _ = score(seed_predictions, gold_rows)

    print(f"{'label':<32} {'prec':>6} {'rec':>6} {'f1':>6}")
    below_floor = []
    for label in LABEL_NAMES:
        precision, recall, f1 = model_per_label[label]
        flag = ""
        if precision < args.precision_floor:
            below_floor.append(label)
            flag = "  <-- BELOW PRECISION FLOOR"
        print(f"{label:<32} {precision:>6.3f} {recall:>6.3f} {f1:>6.3f}{flag}")

    print()
    print(f"macro-F1 (model):       {model_macro:.3f}")
    print(f"macro-F1 (seed labeler): {seed_macro:.3f}")
    print(f"coverage:               {coverage:.3f}")
    print()

    gate1 = model_macro > seed_macro
    print(f"GATE 1 model beats seed labeler: {'PASS' if gate1 else 'FAIL'}")
    if below_floor:
        print(
            f"GATE 2 precision floor: {len(below_floor)} label(s) below "
            f"{args.precision_floor}: {', '.join(below_floor)}"
        )
        print("  -> improve their seed terms, or exclude them from the artifact")
    else:
        print("GATE 2 precision floor: PASS")

    sys.exit(0 if gate1 and not below_floor else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/run_tests.sh api.tests.management.commands.test_exportgoldcandidates api.tests.test_text_classifier.GoldSetTestCase`
Expected: PASS. `GoldSetTestCase` skips until a gold set exists.

- [ ] **Step 6: Build the gold set**

```bash
pipenv run python manage.py exportgoldcandidates --count 300 > /tmp/gold_template.jsonl
```

Hand-label each line's `labels` array using only names from `LABEL_NAMES`. Leave the array empty where no label genuinely applies — that is a valid and informative answer. Save to `api/text_classifier/gold/gold_set.jsonl`.

This is the only independent measurement in the whole design. Budget an hour and do it carefully; a sloppy gold set makes every subsequent number meaningless.

- [ ] **Step 7: Evaluate and act on the gates**

```bash
python scripts/eval_classifier.py
```

- **Gate 1 fails** (the model does not beat the seed labeler): the training step is adding nothing. Do not ship it. Either improve seed-term coverage and retrain, or reconsider approach A.
- **Gate 2 fails** for some labels: improve those labels' seed terms and retrain, or exclude them from the artifact. Shipping 15 labels that work beats 23 where a third are noise — a label that is usually wrong propagates into the feed and user tiers.

Record the full table output in the PR description.

- [ ] **Step 8: Run the full suite and commit**

Run: `./scripts/run_tests.sh`
Expected: PASS, with `GoldSetTestCase` now live rather than skipped.

```bash
git add api/management/commands/exportgoldcandidates.py \
        api/text_classifier/gold/gold_set.jsonl scripts/eval_classifier.py \
        api/tests/management/commands/test_exportgoldcandidates.py \
        api/tests/test_text_classifier.py
git commit -m "add gold evaluation set and classifier eval harness"
```

---

## Done criteria

- [ ] `./scripts/run_tests.sh` passes in full, with `ParityTestCase` and `GoldSetTestCase` live rather than skipped.
- [ ] `pipenv run python manage.py checkclassifierlabels` reports no drift.
- [ ] `scripts/eval_classifier.py` passes both gates, and its output is recorded in the PR.
- [ ] A trained `classifier.json` is committed and the artifact's `taxonomy_fingerprint` matches the committed taxonomy.
- [ ] `import api.views` does not pull in `api.text_classifier.classifier` (enforced by test).
- [ ] `label_feed_entries` appears in `schedulerdaemon.example.json` and the README.
- [ ] Confirmed on deploy: dramatiq worker process count, and therefore how many copies of the ~10MB artifact are resident.

## Follow-ups

- **Approach A**: replace `api/text_classifier/seed_labeler.py` with LLM-produced labels. Everything else in the pipeline is unchanged — that is what the seam is for.
- Title weighting in the seed labeler, now measurable with `scripts/eval_classifier.py`.
- Per-language seed terms and per-language models.
- The recommendation engine consuming the feed and user tiers, replacing the static `_section_lookups` in `api/views/explore.py`.
