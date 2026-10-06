#!/usr/bin/env python
"""Generate the synthetic corpus behind the committed parity fixtures.

Why this exists: no real production corpus is available yet (the dev DB
has the 23 classifier labels but zero feeds/entries, and production data
isn't accessible from here). `api/text_classifier/model/parity_artifact.json`
and `parity_fixtures.json` are trained/generated from a synthetic corpus
instead, purely so `ParityTestCase` in `api/tests/test_text_classifier.py`
always has a real trained model and real scikit-learn-computed scores to
check the pure-Python inference path against. This script is what produces
that corpus -- it is committed, deterministic, and gitignored-output-only,
so the parity pair is reproducible from a clean checkout instead of having
been generated once from data that only ever existed on one machine.

This is a stand-in, not a step toward a real model: `scripts/
train_classifier.py`'s normal (non `--emit-parity`) mode is what trains the
real, production `classifier.json`, and that always runs against a real
corpus exported by `manage.py exportcorpus`. Nothing here feeds that path.

Seeded from `api/text_classifier/taxonomy.py`'s terms, but wrapped in full
templated sentences (not bare term lists) so TF-IDF has real surrounding
vocabulary to weight, the way actual article text would.

One filler sentence below (the "café" one) is not incidental: it is what
gives the fitted vocabulary an accented term at all. Without it, nothing in
the corpus contains a non-ASCII character, `train_classifier.py`'s
accent-preservation fixture search finds nothing, and generation aborts (by
design -- see `build_parity_documents` in `train_classifier.py`). If you
ever need a *different* accented term instead, keep at least one shared
filler sentence containing one; it needs to appear across many documents
of many labels to survive `--max-features` truncation reliably, which a
label-specific sentence would not.

Deterministic: everything below flows from the single `SEED` constant via
`random.Random(SEED)`; there is no wall-clock or other outside input, so
re-running this against an unchanged `taxonomy.py` reproduces byte-identical
output every time (verified: this repo's committed parity pair was in fact
regenerated this way and diffed byte-for-byte against the prior run before
being committed).

Usage (regenerating the committed parity pair from scratch):

    python scripts/make_synthetic_corpus.py corpus.jsonl.gz
    python scripts/train_classifier.py corpus.jsonl.gz \\
      --out api/text_classifier/model/parity_artifact.json \\
      --fixtures api/text_classifier/model/parity_fixtures.json \\
      --emit-parity \\
      --per-label-cap 15 --per-feed-per-label-cap 5 --max-features 2000

Do not commit the generated `corpus.jsonl.gz` -- it's throwaway output, not
a fixture. The generator plus the fixed seed is what's committed instead.
"""

import argparse
import gzip
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.text_classifier.taxonomy import TAXONOMY  # noqa: E402

SEED = 20260730
FEEDS_PER_LABEL = 4
ENTRIES_PER_FEED = 22
CROSSOVER_CHANCE = 0.35
NOISE_DOCS = 60

TEMPLATES = [
    "Here's what to know about {term} this week, according to several sources close to the story.",
    "The latest report focused heavily on {term} and its impact on longtime readers and newcomers alike.",
    "Local coverage highlighted {term} as one of the bigger stories of the day, drawing plenty of reaction online.",
    "Experts weighed in on {term} during a lengthy panel, offering a range of perspectives on where things go next.",
    "Our roundup breaks down {term} in plain language so casual readers can follow along without prior context.",
    "This piece explores {term} from a few different angles, drawing on interviews conducted over the past month.",
    "Readers reacted strongly to the news about {term}, flooding comment sections with questions and opinions.",
    "A closer look at {term} reveals a few surprises that even longtime followers may not have expected.",
    "The panel spent nearly an hour discussing {term} before opening the floor to audience questions.",
    "Industry insiders say {term} will keep making headlines well into next quarter, for better or worse.",
    "In today's roundup, we take a deeper look at {term} and what it might mean going forward.",
    "Coverage of {term} dominated the morning newsletter, with follow-up pieces expected later this week.",
    "Several commentators pointed to {term} as the defining moment of an otherwise quiet stretch.",
    "The community has been buzzing about {term} since the story first broke earlier this week.",
    "According to people familiar with the matter, {term} is likely to remain a talking point for some time.",
    "A new feature dives into {term}, tracing how the story developed over the last several months.",
    "Analysts spent the afternoon debating {term}, with opinions split roughly down the middle.",
    "The editorial team put together a short explainer on {term} for readers who missed the earlier coverage.",
]

FILLER_SENTENCES = [
    "The newsletter goes out every Thursday morning to subscribers around the world.",
    "Thanks for reading; we'll be back with another update soon.",
    "Feel free to leave a comment below with your own take on the story.",
    "A full transcript of the discussion is available for members further down the page.",
    "We've updated our style a little this month, so let us know what you think.",
    "As always, corrections and clarifications are welcome and will be added promptly.",
    "This is part of an ongoing series covering stories our readers keep asking about.",
    "Subscribe to get similar roundups delivered directly to your inbox each week.",
    "Photos accompanying the original piece can be found in the linked gallery.",
    "We spoke to several people for this story who asked not to be named.",
    "It has been a busy stretch for the team behind the scenes putting this together.",
    "More coverage on related topics is linked at the bottom of this page.",
    "The team behind this publication has covered similar ground before, with mixed results.",
    "A previous version of this article has been updated to correct a minor detail.",
    # Deliberately the corpus's only source of a non-ASCII/accented term --
    # see the module docstring. Shared across every label (not put in a
    # single label's templates) so "café" gets enough document frequency to
    # survive --max-features truncation regardless of which label happens
    # to be under-represented on a given run.
    "Parts of this piece were drafted at a favourite neighbourhood café before the deadline crunch began.",
    "Our next issue will follow up on a few threads left open here.",
]

NOISE_SENTENCES = [
    "The weather stayed mild for most of the afternoon before clouds rolled in.",
    "Traffic on the main road was lighter than usual for a weekday.",
    "The committee agreed to meet again next month to revisit the agenda.",
    "Several attendees left early, citing a scheduling conflict with another event.",
    "The building's lobby was recently repainted a soft shade of grey.",
    "Nobody could quite agree on where to hold the annual gathering this year.",
    "The printer on the third floor has been out of toner since Monday.",
    "A light drizzle did little to dampen turnout for the afternoon walk.",
]


def term_bank(label):
    terms = TAXONOMY[label]
    return sorted(terms.strong) + sorted(terms.weak)


def make_sentences(rng, terms, count):
    sentences = []
    for _ in range(count):
        term = rng.choice(terms)
        template = rng.choice(TEMPLATES)
        sentences.append(template.format(term=term))
    return sentences


def make_document(rng, label, secondary_label=None):
    terms = term_bank(label)
    body_sentences = make_sentences(rng, terms, rng.randint(2, 3))
    filler = rng.sample(FILLER_SENTENCES, rng.randint(1, 2))

    if secondary_label:
        secondary_terms = term_bank(secondary_label)
        body_sentences += make_sentences(rng, secondary_terms, rng.randint(1, 2))

    sentences = body_sentences + filler
    rng.shuffle(sentences)

    title_term = rng.choice(terms)
    title = rng.choice(TEMPLATES).format(term=title_term).rstrip(".")
    content = " ".join(sentences)
    return title, content


def make_noise_document(rng):
    sentences = rng.sample(NOISE_SENTENCES, rng.randint(2, 4)) + rng.sample(
        FILLER_SENTENCES, 1
    )
    rng.shuffle(sentences)
    title = rng.choice(NOISE_SENTENCES).rstrip(".")
    return title, " ".join(sentences)


def build_rows():
    rng = random.Random(SEED)

    labels = sorted(TAXONOMY)
    feed_specs = []  # (feed_id, primary_label)
    feed_index = 0
    for label in labels:
        for _ in range(FEEDS_PER_LABEL):
            feed_specs.append((f"feed-{feed_index:04d}", label))
            feed_index += 1
    rng.shuffle(feed_specs)  # so feed_wise_split's shuffle isn't the only shuffle

    rows = []
    for feed_id, primary_label in feed_specs:
        other_labels = [label for label in labels if label != primary_label]
        for _ in range(ENTRIES_PER_FEED):
            secondary = (
                rng.choice(other_labels) if rng.random() < CROSSOVER_CHANCE else None
            )
            title, content = make_document(rng, primary_label, secondary)
            rows.append({"feed_id": feed_id, "title": title, "content": content})

    noise_feed_ids = [f"feed-noise-{i:03d}" for i in range(6)]
    for _ in range(NOISE_DOCS):
        feed_id = rng.choice(noise_feed_ids)
        title, content = make_noise_document(rng)
        rows.append({"feed_id": feed_id, "title": title, "content": content})

    rng.shuffle(rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "out",
        help="Output path for the gzipped JSONL corpus (NOT committed -- "
        "throwaway output; re-run this script instead of checking it in).",
    )
    args = parser.parse_args()

    rows = build_rows()

    with gzip.open(args.out, "wt") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    feed_ids = sorted({r["feed_id"] for r in rows})
    print(
        f"wrote {len(rows)} rows across {len(feed_ids)} feeds to {args.out}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
