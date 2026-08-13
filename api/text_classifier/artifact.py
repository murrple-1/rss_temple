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
_SUPPORTED_BINARY = False
_SUPPORTED_STRIP_ACCENTS = None
_SUPPORTED_ANALYZER = "word"


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
    # These three are recorded (and validated at load time below) purely as
    # a tripwire. classifier.py's analyzer only ever implements
    # binary=False, strip_accents=None, analyzer="word" -- if the training
    # box fits a vectorizer with any other value for these, the produced
    # feature vectors would silently disagree with what classifier.py
    # computes, with no error at either fit time or load time, unless this
    # dataclass records the value and load_artifact rejects a mismatch.
    binary: bool
    strip_accents: str | None
    analyzer: str


@dataclass(frozen=True)
class Artifact:
    labels: tuple[str, ...]
    vocabulary: dict[str, int]
    idf: array
    # Flattened one-vs-rest coefficient matrix in C-order / row-major /
    # label-major layout: coef[label_index * n_features + feature_index].
    # This is scikit-learn's default `LogisticRegression.coef_.ravel()`
    # order, but nothing about the array's length distinguishes it from a
    # Fortran-order (feature-major) ravel of the same shape -- both produce
    # exactly n_labels * n_features entries, so `dump_artifact`'s and
    # `load_artifact`'s length checks cannot catch a wrong ravel order.
    # Getting this wrong silently mixes up which coefficients score which
    # label; every downstream length check still passes. See
    # `classifier.decision_scores`, which indexes with this exact formula.
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
    """Write the artifact and return its model fingerprint.

    `coef` must already be flattened in C-order / row-major / label-major
    layout, i.e. `coef[label_index * n_features + feature_index]` -- the
    default `.ravel()` order of a `(n_labels, n_features)` NumPy array.
    A Fortran-order (feature-major) ravel has the same length and passes
    every check in this function and in `load_artifact`, but silently
    scores every label with the wrong coefficients. See the `coef` field
    docstring on `Artifact` and `classifier.decision_scores` for the
    indexing formula this must match.
    """
    n_labels = len(labels)
    n_features = len(vocabulary_terms)

    if len(idf) != n_features:
        raise ArtifactError(
            f"idf has {len(idf)} entries, expected {n_features} "
            f"(one per vocabulary term)"
        )
    if len(coef) != n_labels * n_features:
        raise ArtifactError(
            f"coef has {len(coef)} entries, expected {n_labels * n_features} "
            f"({n_labels} labels x {n_features} vocabulary terms)"
        )
    if len(intercept) != n_labels:
        raise ArtifactError(
            f"intercept has {len(intercept)} entries, expected {n_labels} "
            f"(one per label)"
        )
    if len(thresholds) != n_labels:
        raise ArtifactError(
            f"thresholds has {len(thresholds)} entries, expected {n_labels} "
            f"(one per label)"
        )
    for term in vocabulary_terms:
        if "\n" in term:
            raise ArtifactError(
                f"vocabulary term {term!r} contains a newline, which is not "
                "allowed because the vocabulary is stored newline-joined; "
                "an embedded newline would silently shift every later index"
            )

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

    # Fingerprint is computed over the body *without* the fingerprint field,
    # then inserted afterward. Computing it over a body that already
    # contains a (previous, or placeholder) fingerprint would make the
    # result depend on write history rather than purely on content, and
    # would make the round-trip test's equality check meaningless.
    fingerprint = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    body["model_fingerprint"] = fingerprint

    with open(path, "w") as f:
        json.dump(body, f, sort_keys=True)

    return fingerprint


def _require(mapping: Any, key: str, where: str, path: str) -> Any:
    """Fetch `key` from `mapping`, raising `ArtifactError` (naming the path,
    the location, and the missing key) instead of letting a raw `KeyError`
    (missing key) or `TypeError` (e.g. `where` isn't even a dict -- a
    truncated write can leave `"vectorizer"` as `null` or a partial string)
    escape to the caller.

    `load_artifact`'s whole stated purpose is to fail loudly and
    informatively on malformed input; a bare dict-indexing KeyError/TypeError
    does neither -- it isn't even the right exception type for callers that
    (correctly) only catch `ArtifactError`.
    """
    try:
        return mapping[key]
    except (KeyError, TypeError) as e:
        raise ArtifactError(
            f"artifact at {path!r} is missing required key {key!r} in {where}"
        ) from e


def load_artifact(path: str) -> Artifact:
    with open(path, "r") as f:
        try:
            body = json.load(f)
        except json.JSONDecodeError as e:
            raise ArtifactError(f"artifact at {path!r} is not valid JSON: {e}") from e

    if not isinstance(body, dict):
        raise ArtifactError(
            f"artifact at {path!r} does not contain a JSON object at the "
            f"top level (got {type(body).__name__})"
        )

    version = body.get("format_version")
    if version != ARTIFACT_FORMAT_VERSION:
        raise ArtifactError(
            f"artifact format_version {version!r} is not supported "
            f"(this build reads format_version {ARTIFACT_FORMAT_VERSION})"
        )

    raw_vectorizer = _require(body, "vectorizer", "top-level body", path)
    vectorizer = VectorizerConfig(
        token_pattern=_require(raw_vectorizer, "token_pattern", "vectorizer", path),
        ngram_range=tuple(  # type: ignore[arg-type]
            _require(raw_vectorizer, "ngram_range", "vectorizer", path)
        ),
        lowercase=_require(raw_vectorizer, "lowercase", "vectorizer", path),
        sublinear_tf=_require(raw_vectorizer, "sublinear_tf", "vectorizer", path),
        norm=_require(raw_vectorizer, "norm", "vectorizer", path),
        stop_words=tuple(_require(raw_vectorizer, "stop_words", "vectorizer", path)),
        binary=_require(raw_vectorizer, "binary", "vectorizer", path),
        strip_accents=_require(raw_vectorizer, "strip_accents", "vectorizer", path),
        analyzer=_require(raw_vectorizer, "analyzer", "vectorizer", path),
    )

    if vectorizer.token_pattern != _SUPPORTED_TOKEN_PATTERN:
        raise ArtifactError(
            f"unsupported token_pattern {vectorizer.token_pattern!r}, "
            f"expected {_SUPPORTED_TOKEN_PATTERN!r}"
        )
    if vectorizer.ngram_range != _SUPPORTED_NGRAM_RANGE:
        raise ArtifactError(
            f"unsupported ngram_range {vectorizer.ngram_range!r}, "
            f"expected {_SUPPORTED_NGRAM_RANGE!r}"
        )
    if vectorizer.norm != _SUPPORTED_NORM:
        raise ArtifactError(
            f"unsupported norm {vectorizer.norm!r}, expected {_SUPPORTED_NORM!r}"
        )
    if not vectorizer.lowercase or not vectorizer.sublinear_tf:
        raise ArtifactError(
            "unsupported vectorizer config: lowercase and sublinear_tf must "
            f"both be enabled (got lowercase={vectorizer.lowercase!r}, "
            f"sublinear_tf={vectorizer.sublinear_tf!r})"
        )
    if vectorizer.binary != _SUPPORTED_BINARY:
        raise ArtifactError(
            f"unsupported binary {vectorizer.binary!r}, "
            f"expected {_SUPPORTED_BINARY!r}"
        )
    if vectorizer.strip_accents != _SUPPORTED_STRIP_ACCENTS:
        raise ArtifactError(
            f"unsupported strip_accents {vectorizer.strip_accents!r}, "
            f"expected {_SUPPORTED_STRIP_ACCENTS!r}"
        )
    if vectorizer.analyzer != _SUPPORTED_ANALYZER:
        raise ArtifactError(
            f"unsupported analyzer {vectorizer.analyzer!r}, "
            f"expected {_SUPPORTED_ANALYZER!r}"
        )

    labels = tuple(_require(body, "labels", "top-level body", path))
    raw_vocabulary = _require(body, "vocabulary", "top-level body", path)
    terms = raw_vocabulary.split("\n") if raw_vocabulary else []
    vocabulary = {term: index for index, term in enumerate(terms)}

    idf = _decode(_require(body, "idf_b64", "top-level body", path))
    coef = _decode(_require(body, "coef_b64", "top-level body", path))
    intercept = _decode(_require(body, "intercept_b64", "top-level body", path))
    thresholds = _decode(_require(body, "thresholds_b64", "top-level body", path))

    n_labels = len(labels)
    n_features = len(vocabulary)
    if len(idf) != n_features:
        raise ArtifactError(
            f"idf has {len(idf)} entries, expected {n_features} "
            f"to match the vocabulary size"
        )
    if len(coef) != n_labels * n_features:
        raise ArtifactError(
            f"coef has {len(coef)} entries, expected {n_labels * n_features} "
            f"({n_labels} labels x {n_features} vocabulary terms)"
        )
    if len(intercept) != n_labels:
        raise ArtifactError(
            f"intercept has {len(intercept)} entries, expected {n_labels} "
            f"to match the label count"
        )
    if len(thresholds) != n_labels:
        raise ArtifactError(
            f"thresholds has {len(thresholds)} entries, expected {n_labels} "
            f"to match the label count"
        )

    return Artifact(
        labels=labels,
        vocabulary=vocabulary,
        idf=idf,
        coef=coef,
        intercept=intercept,
        thresholds=thresholds,
        vectorizer=vectorizer,
        taxonomy_fingerprint=_require(
            body, "taxonomy_fingerprint", "top-level body", path
        ),
        model_fingerprint=_require(body, "model_fingerprint", "top-level body", path),
        training=_require(body, "training", "top-level body", path),
    )
