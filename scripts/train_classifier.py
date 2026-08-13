#!/usr/bin/env python
"""Train the feed entry classifier from a corpus JSONL export.

Runs on a training box, never in production. Requires
`pip install -r scripts/requirements-train.txt`.

    python manage.py exportcorpus | gzip > corpus.jsonl.gz     # on prod
    scp prod:corpus.jsonl.gz .                                  # transfer
    python scripts/train_classifier.py corpus.jsonl.gz          # here

A normal run writes ONLY the shipping artifact (`--out`, default
`api/text_classifier/model/classifier.json`). It never touches the
committed parity fixtures -- pass `--emit-parity` to additionally generate
and write those (see `build_parity_documents` below); that is a separate,
explicit, maintainer-only operation, not part of the everyday retrain loop.
"""

import argparse
import datetime
import gzip
import json
import math
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.text_classifier.artifact import VectorizerConfig, dump_artifact  # noqa: E402
from api.text_classifier.prep_content import prep_for_classification  # noqa: E402
from api.text_classifier.seed_labeler import label_text  # noqa: E402
from api.text_classifier.taxonomy import LABEL_NAMES, taxonomy_fingerprint  # noqa: E402

SEED = 20260730
TOKEN_PATTERN = r"(?u)\b\w\w+\b"
NGRAM_RANGE = (1, 2)
MAX_FEATURES = 30_000

# These three are not the brief's TfidfVectorizer defaults by accident: they
# are the exact three values classifier.py's pure-Python analyzer implements
# (see the VectorizerConfig docstring in api/text_classifier/artifact.py).
# `load_artifact` validates all eight vectorizer fields at load time, so a
# training run that used anything else here would fail loudly on load rather
# than silently mis-scoring -- but only because the value actually used gets
# recorded below and compared, so keep this vectorizer's kwargs and the
# VectorizerConfig below in sync.
BINARY = False
STRIP_ACCENTS = None
ANALYZER = "word"

# `build_dataset` below feeds `prep_for_classification` the FULL, untruncated
# title/content -- see api/text_classifier/prep_content.py's docstring on
# MAX_CLASSIFICATION_CHARS for why truncation must happen only once, inside
# that function, on its OUTPUT, identically for every caller (this trainer
# today; a future production inference path later). Do not slice row["title"]
# / row["content"] before calling it, and do not re-truncate its return value
# here to a different length.


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

    Text is run through `prep_for_classification` -- the same function
    production calls before inference -- before it ever reaches the seed
    labeler or the vectorizer. Feeding raw `title`/`content` here would let
    the pure-Python inference path and the sklearn training path see
    genuinely different text (HTML tags, entities, etc.), a divergence the
    parity fixtures cannot detect because it happens upstream of both sides
    of the comparison.
    """
    rng = random.Random(SEED)

    per_label: defaultdict[str, list] = defaultdict(list)
    per_feed_label: defaultdict[tuple[str, str], int] = defaultdict(int)
    dropped = 0

    for row in read_corpus(path):
        text = prep_for_classification(row["title"], row["content"])
        labels = label_text(text)
        if not labels:
            dropped += 1
            continue

        # `labels` is a frozenset: iterating it directly would order
        # insertions into `per_label` (and therefore the draw order of the
        # `rng.sample()` calls below) by Python's per-process string hash
        # randomization instead of by content, making two runs over the
        # identical corpus with the identical SEED sample different rows.
        # Sorting makes the whole pipeline reproducible run-to-run.
        for label in sorted(labels):
            key = (row["feed_id"], label)
            if per_feed_label[key] >= per_feed_per_label_cap:
                continue
            per_feed_label[key] += 1
            per_label[label].append((row["feed_id"], text, labels))

    documents: dict[str, tuple[str, str, frozenset]] = {}
    for label, rows in per_label.items():
        sampled = (
            rows if len(rows) <= per_label_cap else rng.sample(rows, per_label_cap)
        )
        for feed_id, text, labels in sampled:
            documents[text] = (feed_id, text, labels)

    print(
        f"kept {len(documents)} document(s); dropped {dropped} unlabelled",
        file=sys.stderr,
    )
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


# ---------------------------------------------------------------------------
# Parity fixture generation.
#
# A fixture is only useful if it activates vocabulary features that a real
# divergence would actually touch. Six mutants were injected against a
# previous, hand-written fixture set and three went undetected: bigrams
# built before stop-word removal, an accent-strip, and single-character
# tokens leaking into bigram formation. In every miss, the differing
# analyzer output landed entirely OUTSIDE the fitted vocabulary, so both the
# correct and the buggy path scored identically -- the fixture tested only
# the intercept.
#
# So fixtures are not hand-written prose anymore. Each "engineered" fixture
# below is found by searching the ACTUAL fitted vocabulary for a text that
# provably produces a different in-vocabulary feature set under a small
# reference reimplementation of each specific bug ("mutant") than under
# correct analysis -- and generation FAILS LOUDLY (raises) if no such text
# exists, rather than silently shipping an inert fixture. The mutants below
# exist ONLY to validate fixture selection; they are deliberately not
# reused from (or by) classifier.py, which is the thing being validated.
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(TOKEN_PATTERN)  # matches classifier.py's real pattern
_WORD_RE_ACCEPTS_SINGLE_CHAR = re.compile(r"(?u)\b\w+\b")
_STOPWORDS = frozenset(ENGLISH_STOP_WORDS)


def _ngrams(tokens, n):
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _terms_correct(text):
    """What the correct analyzer (and the real fitted vectorizer) produces."""
    tokens = _WORD_RE.findall(text.lower())
    tokens = [t for t in tokens if t not in _STOPWORDS]
    return set(tokens) | set(_ngrams(tokens, 2))


def _terms_bigrams_before_stopwords(text):
    """Mutant: bigrams built from all tokens, stop words removed after."""
    tokens = _WORD_RE.findall(text.lower())
    bigrams = set(_ngrams(tokens, 2))
    unigrams = {t for t in tokens if t not in _STOPWORDS}
    return unigrams | bigrams


def _terms_accent_stripped(text):
    """Mutant: NFKD-folds accents away before tokenizing."""
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    tokens = _WORD_RE.findall(folded)
    tokens = [t for t in tokens if t not in _STOPWORDS]
    return set(tokens) | set(_ngrams(tokens, 2))


def _terms_single_char_tokens(text):
    """Mutant: token pattern accepts 1-character tokens too."""
    tokens = _WORD_RE_ACCEPTS_SINGLE_CHAR.findall(text.lower())
    tokens = [t for t in tokens if t not in _STOPWORDS]
    return set(tokens) | set(_ngrams(tokens, 2))


def _active(terms, vocabulary):
    return {t for t in terms if t in vocabulary}


def _n_active_features(text, vocabulary):
    return len(_active(_terms_correct(text), vocabulary))


def _distinguishes(text, mutant_fn, vocabulary):
    """True if `text` scores differently under `mutant_fn` than correctly.

    Only in-vocabulary terms matter: a differing token that never made it
    into the fitted vocabulary contributes nothing to either side's score,
    which is exactly the trap the original fixture set fell into.
    """
    correct = _active(_terms_correct(text), vocabulary)
    mutant = _active(mutant_fn(text), vocabulary)
    return correct != mutant


def _find_stopword_skip_fixture(vocabulary):
    """A document whose correct bigram spans a stop word the mutant keeps.

    E.g. vocabulary bigram "climbed season" from correct text "climbed as
    the season ...": the mutant instead emits "climbed as"/"as the"/
    "the season", none of which are the vocabulary bigram, so it drops that
    feature entirely while the correct analyzer keeps it.
    """
    bigram_terms = sorted(t for t in vocabulary if " " in t and t.count(" ") == 1)
    stopwords_to_try = ("the", "a", "an", "of", "and", "is", "in", "on", "as")
    for bigram in bigram_terms:
        a, b = bigram.split(" ")
        for sw in stopwords_to_try:
            candidate = f"{a} {sw} {b}"
            if _n_active_features(candidate, vocabulary) >= 2 and _distinguishes(
                candidate, _terms_bigrams_before_stopwords, vocabulary
            ):
                return candidate
    return None


def _find_single_char_fixture(vocabulary):
    """A document with a single-char token wedged between two vocab words.

    Correct: the token pattern drops the 1-char token (shorter than \\w\\w+),
    leaving the two real words adjacent and forming their vocabulary bigram.
    Mutant: the wider pattern keeps the 1-char token, breaking that
    adjacency and emitting two bigrams that (almost certainly) aren't in
    vocabulary instead.
    """
    bigram_terms = sorted(t for t in vocabulary if " " in t and t.count(" ") == 1)
    fillers = ("x", "q", "z", "j")
    for bigram in bigram_terms:
        a, b = bigram.split(" ")
        for filler in fillers:
            candidate = f"{a} {filler} {b}"
            if _n_active_features(candidate, vocabulary) >= 2 and _distinguishes(
                candidate, _terms_single_char_tokens, vocabulary
            ):
                return candidate
    return None


def _fold_accents(term):
    folded = unicodedata.normalize("NFKD", term)
    return "".join(c for c in folded if not unicodedata.combining(c))


def _find_accent_fixture(vocabulary):
    """A document combining an accented vocabulary term with another one.

    Requires the training corpus to have actually produced an accented
    vocabulary term -- if it hasn't, this (correctly) finds nothing and
    generation fails loudly rather than silently emitting an inert fixture,
    the same trap the original "Café naive resume" fixture fell into (it
    exercised zero in-vocabulary accented terms).
    """
    accented = sorted(t for t in vocabulary if _fold_accents(t) != t and " " not in t)
    plain = sorted(t for t in vocabulary if " " not in t)
    for term in accented:
        for other in plain:
            if other == term:
                continue
            candidate = f"{term} {other}"
            if _n_active_features(candidate, vocabulary) >= 2 and _distinguishes(
                candidate, _terms_accent_stripped, vocabulary
            ):
                return candidate
    return None


def _l2_normalize(vector):
    norm = math.sqrt(sum(v * v for v in vector.values()))
    if norm == 0.0:
        return vector
    return {k: v / norm for k, v in vector.items()}


def _tfidf_vector(text, vocabulary, idf, log_fn):
    tokens = _WORD_RE.findall(text.lower())
    tokens = [t for t in tokens if t not in _STOPWORDS]
    terms = tokens + _ngrams(tokens, 2)
    counts = Counter(vocabulary[t] for t in terms if t in vocabulary)
    vector = {
        index: (1.0 + log_fn(count)) * idf[index] for index, count in counts.items()
    }
    return _l2_normalize(vector)


def _sublinear_delta(text, vocabulary, idf):
    """Max absolute per-feature difference between natural-log and log10 tf.

    Computed directly against the real fitted vocabulary/idf, not assumed
    structurally, so "this fixture actually distinguishes the two log
    bases" is a measured fact rather than a guess -- which is exactly how
    the previous "recipe recipe recipe sourdough sourdough" fixture turned
    out to be inert (one of its two words was out of vocabulary, so it had
    only one active feature and the ratio-dependent divergence vanished).
    """
    natural = _tfidf_vector(text, vocabulary, idf, math.log)
    log10 = _tfidf_vector(text, vocabulary, idf, math.log10)
    keys = set(natural) | set(log10)
    if not keys:
        return 0.0
    return max(abs(natural.get(k, 0.0) - log10.get(k, 0.0)) for k in keys)


def _find_sublinear_fixtures(vocabulary, idf, count=2, min_delta=1e-4):
    """Documents whose L2-normalised direction provably depends on the
    sublinear_tf log base, verified numerically against the real idf."""
    unigrams = sorted(t for t in vocabulary if " " not in t)
    found = []
    for a in unigrams:
        for b in unigrams:
            if a == b:
                continue
            candidate = f"{a} {a} {a} {b} {b}"
            if _sublinear_delta(candidate, vocabulary, idf) >= min_delta:
                found.append(candidate)
                break
        if len(found) >= count:
            break
    return found


def build_parity_documents(vectorizer, train_texts, idf):
    """Build the parity fixture document list against the real fitted model.

    Returns (documents, report) where `report` is a dict describing which
    category each engineered fixture satisfies, for the training run's
    stderr log. Raises AssertionError if any required category can't be
    satisfied against this vocabulary -- fail the run, don't ship a fixture
    set that silently can't catch what it claims to catch.
    """
    vocabulary = vectorizer.vocabulary_
    report: dict[str, str] = {}
    documents: list[str] = []

    def add(text, category):
        if text not in documents:
            documents.append(text)
        report[category] = text

    # Deliberate zero/near-zero-feature edge cases. Kept because they're
    # worth having, but NOT counted toward the discriminating requirements
    # below -- that was precisely the previous set's mistake.
    add("", "edge_case_empty")
    add("zzzz yyyy xxxx wwww", "edge_case_out_of_vocabulary")
    single_feature = next(
        (t for t in sorted(vectorizer.vocabulary_) if " " not in t), None
    )
    if single_feature is not None:
        add(single_feature, "edge_case_single_active_feature")

    stopword_skip = _find_stopword_skip_fixture(vocabulary)
    assert stopword_skip is not None, (
        "could not find any document in the fitted vocabulary whose "
        "correct bigram spans a removed stop word; the "
        "bigrams-before-stopword-removal mutant would go undetected"
    )
    add(stopword_skip, "stopword_skip_bigram")

    single_char = _find_single_char_fixture(vocabulary)
    assert single_char is not None, (
        "could not find any document with a single-character token wedged "
        "between two vocabulary words; the token-pattern "
        "accepts-single-char-tokens mutant would go undetected"
    )
    add(single_char, "single_char_token_adjacency")

    accent = _find_accent_fixture(vocabulary)
    assert accent is not None, (
        "could not find any accented term in the fitted vocabulary to "
        "build an accent-stripping fixture from; the corpus needs at "
        "least one real training document containing an in-vocabulary "
        "accented word, or the NFKD-accent-strip mutant would go "
        "undetected"
    )
    add(accent, "accent_preservation")

    sublinear_fixtures = _find_sublinear_fixtures(vocabulary, idf, count=2)
    assert len(sublinear_fixtures) >= 2, (
        f"found only {len(sublinear_fixtures)} document(s) whose "
        "L2-normalised direction measurably depends on the sublinear_tf "
        "log base (need >= 2); the math.log-vs-math.log10 mutant could "
        "go undetected if the vocabulary shifts on a future retrain"
    )
    for i, text in enumerate(sublinear_fixtures):
        add(text, f"sublinear_tf_{i}")

    # Real training documents: guaranteed to hit vocabulary because they
    # were literally part of fitting it, unlike invented prose.
    real_docs = sorted(
        {t for t in train_texts if _n_active_features(t, vocabulary) >= 3}
    )
    for i, text in enumerate(real_docs[:4]):
        add(text, f"real_training_document_{i}")

    for category, text in report.items():
        if category.startswith("edge_case"):
            continue
        n_active = _n_active_features(text, vocabulary)
        assert n_active >= 2, (
            f"fixture for {category!r} activates only {n_active} "
            "in-vocabulary feature(s); every discriminating fixture must "
            f"activate at least 2 (text={text!r})"
        )

    return documents, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--out", default="api/text_classifier/model/classifier.json")
    parser.add_argument(
        "--emit-parity",
        action="store_true",
        help="Also generate and write parity fixtures. Off by default so a "
        "normal retrain never touches the committed parity artifact/"
        "fixtures -- this is a separate, explicit, maintainer-only step.",
    )
    parser.add_argument(
        "--fixtures",
        default=None,
        help="Path for parity fixtures; only used with --emit-parity. "
        "Defaults to --out with '.json' replaced by '.parity_fixtures.json'.",
    )
    parser.add_argument("--per-label-cap", type=int, default=5000)
    parser.add_argument("--per-feed-per-label-cap", type=int, default=200)
    parser.add_argument(
        "--max-features",
        type=int,
        default=MAX_FEATURES,
        help="Cap on vocabulary size. Kept small for the synthetic/parity "
        "model so classifier.json + parity_fixtures.json stay small.",
    )
    args = parser.parse_args()

    rows = build_dataset(args.corpus, args.per_label_cap, args.per_feed_per_label_cap)
    train_rows, dev_rows = feed_wise_split(rows)
    print(f"train={len(train_rows)} dev={len(dev_rows)}", file=sys.stderr)

    labels = list(LABEL_NAMES)
    train_texts, train_y = to_matrix(train_rows, labels)
    dev_texts, dev_y = to_matrix(dev_rows, labels)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        token_pattern=TOKEN_PATTERN,
        ngram_range=NGRAM_RANGE,
        max_features=args.max_features,
        sublinear_tf=True,
        norm="l2",
        stop_words="english",
        binary=BINARY,
        strip_accents=STRIP_ACCENTS,
        analyzer=ANALYZER,
    )
    x_train = vectorizer.fit_transform(train_texts)
    x_dev = vectorizer.transform(dev_texts)

    n_features = len(vectorizer.vocabulary_)
    coef = np.zeros((len(labels), n_features), dtype=np.float64)
    intercept = np.zeros(len(labels), dtype=np.float64)
    thresholds = np.zeros(len(labels), dtype=np.float64)

    for j, label in enumerate(labels):
        if train_y[:, j].sum() == 0:
            print(
                f"WARNING: no positives for {label!r}; label will never fire",
                file=sys.stderr,
            )
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
        binary=BINARY,
        strip_accents=STRIP_ACCENTS,
        analyzer=ANALYZER,
    )

    # `coef` must be flattened in C-order / row-major / label-major layout --
    # numpy's default `.ravel()` -- so that
    # coef[label_index * n_features + feature_index] is what
    # classifier.decision_scores expects. `coef` was allocated with
    # `np.zeros((len(labels), n_features))`, which is C-contiguous by
    # default, and `.ravel(order="C")` is spelled out explicitly here (not
    # left to whatever the array's current memory layout happens to be) so
    # this can never silently regress to a Fortran-order ravel if the
    # allocation above ever changes. See the long comment on `Artifact.coef`
    # in api/text_classifier/artifact.py for why this matters and why no
    # length check can catch getting it wrong.
    flat_coef = coef.ravel(order="C")

    fingerprint = dump_artifact(
        args.out,
        labels=labels,
        vocabulary_terms=terms,
        idf=[float(v) for v in idf],
        coef=[float(v) for v in flat_coef],
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

    if not args.emit_parity:
        return

    fixtures_path = args.fixtures or (
        args.out[: -len(".json")] + ".parity_fixtures.json"
        if args.out.endswith(".json")
        else args.out + ".parity_fixtures.json"
    )

    parity_documents, report = build_parity_documents(vectorizer, train_texts, idf)
    print("parity fixture categories:", file=sys.stderr)
    for category, text in sorted(report.items()):
        print(f"  {category}: {text[:70]!r}", file=sys.stderr)

    # Parity fixtures: sklearn's own decision scores for a set of
    # vocabulary-validated documents (see build_parity_documents). The
    # pure-Python inference path must reproduce these exactly, which is
    # what stops a tokenizer divergence degrading the model silently.
    fixture_x = vectorizer.transform(parity_documents)
    fixture_scores = (fixture_x @ coef.T) + intercept

    with open(fixtures_path, "w") as f:
        json.dump(
            [
                {"text": text, "scores": [float(v) for v in fixture_scores[i]]}
                for i, text in enumerate(parity_documents)
            ],
            f,
            indent=2,
        )
    print(f"wrote {fixtures_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
