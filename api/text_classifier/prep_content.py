from bs4 import BeautifulSoup

# The single length cap classification text is ever truncated to. Applied
# HERE, to the OUTPUT of preparation (stripped, whitespace-joined text) --
# never by a caller slicing raw title/content beforehand.
#
# Truncating raw HTML/content instead (as `exportcorpus` used to) can cut
# input mid-tag or mid-entity, so the same underlying article produces
# different stripped text depending on exactly where the raw slice landed
# relative to markup -- and worse, a caller that slices at a different raw
# length than another caller (e.g. a training-time export cap that doesn't
# match whatever the inference path uses) makes training and inference feed
# scikit-learn/the pure-Python vectorizer genuinely different text for the
# "same" document, a divergence no parity fixture can ever catch because it
# happens upstream of both sides of that comparison.
#
# Contract: every caller of `prep_for_classification` -- `scripts/
# train_classifier.py` today, and any future production inference path --
# MUST pass the full, untruncated title/content and let this function do the
# only truncation that happens. Do not pre-slice raw content before calling
# this, and do not re-truncate its output to a different length afterward.
#
# One caller structurally cannot follow that contract today:
# `manage.py exportcorpus` (which produces the corpus this trainer reads)
# caps raw content at `--max-raw-content-chars` (default 50,000) before it
# ever reaches this function, as a JSONL-payload safety valve -- see that
# command's docstring. 50,000 raw chars is considered enough headroom
# because it is 12.5x this 4,000-char output cap: for markup-to-text
# overhead below that 12.5:1 ratio, stripping 50,000 raw chars still
# produces more than 4,000 characters of prepared text, so this function's
# own truncation is what actually bites and both sides agree. Above roughly
# a 12.5:1 raw-to-prepared ratio (e.g. entries link-heavy or otherwise very
# markup-dense), 50,000 raw chars can strip down to fewer than 4,000
# prepared characters, and training would then see less text than a
# production caller preparing the full row would -- the same class of
# training/inference divergence this truncation move was meant to close,
# just pushed to a much rarer case instead of eliminated. No parity fixture
# can catch this either, for the same reason as before: it happens upstream
# of both sides of that comparison.
MAX_CLASSIFICATION_CHARS = 4000


def prep_for_lang_detection(title: str, content: str) -> str:
    return " ".join(
        BeautifulSoup(f"<h1>{title}</h1>{content}", "lxml").stripped_strings
    )


def prep_for_classification(title: str, content: str) -> str:
    # TODO more here needs to be done (remove special characters, normalize whitespace, etc)
    prepped = prep_for_lang_detection(title, content)
    return prepped[:MAX_CLASSIFICATION_CHARS]
