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


def load_artifact(path: str) -> Artifact:
    with open(path, "r") as f:
        body = json.load(f)

    version = body.get("format_version")
    if version != ARTIFACT_FORMAT_VERSION:
        raise ArtifactError(
            f"artifact format_version {version!r} is not supported "
            f"(this build reads format_version {ARTIFACT_FORMAT_VERSION})"
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
        taxonomy_fingerprint=body["taxonomy_fingerprint"],
        model_fingerprint=body["model_fingerprint"],
        training=body["training"],
    )
