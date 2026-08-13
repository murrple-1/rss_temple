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

PARITY_DOCUMENTS = [
    "",
    "cat",
    "The quick brown fox jumps over the lazy dog.",
    # A single repeated word (e.g. "nintendo nintendo nintendo nintendo", the
    # brief's original example) only exercises sublinear_tf if the *bigram*
    # of that word with itself also survived into the fitted vocabulary --
    # otherwise there is exactly one active feature, and after L2
    # normalisation a vector with one nonzero component always collapses to
    # unit magnitude regardless of what the raw tf value was, so `1 +
    # ln(count)` and `1 + log10(count)` become indistinguishable (the same
    # reason `test_l2_normalisation_makes_length_irrelevant` in
    # test_text_classifier.py needs a *different* fixture from
    # `test_sublinear_tf_uses_natural_log_not_log10`). A same-word repeat is
    # very unlikely to land in any real fitted vocabulary, synthetic or
    # production. These two use two DIFFERENT taxonomy terms at different
    # repeat counts instead, which puts two features with unequal counts on
    # the vector at once regardless of vocabulary luck, so the ratio between
    # them -- and therefore the L2-normalised direction -- genuinely depends
    # on the log base. Verified empirically against the trained parity
    # artifact to actually diverge between `math.log` and `math.log10`
    # before being committed here.
    "recipe recipe recipe sourdough sourdough",
    "nintendo nintendo nintendo gaming gaming",
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--out", default="api/text_classifier/model/classifier.json")
    parser.add_argument(
        "--fixtures", default="api/text_classifier/model/parity_fixtures.json"
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
