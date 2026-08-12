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
            "anime",
            "manga",
            "shonen",
            "shounen",
            "seinen",
            "shoujo",
            "isekai",
            "otaku",
            "crunchyroll",
            "studio ghibli",
            "light novel",
            "mangaka",
            "myanimelist",
            "waifu",
        ],
        weak=["subtitled", "dubbed", "adaptation", "cosplay"],
    ),
    "Arts & Craft": _terms(
        strong=[
            "knitting",
            "crochet",
            "quilting",
            "embroidery",
            "woodworking",
            "pottery",
            "ceramics",
            "calligraphy",
            "scrapbooking",
            "origami",
            "cross stitch",
            "macrame",
            "needlework",
            "printmaking",
            "sculpture",
        ],
        weak=["handmade", "pattern", "craft", "watercolour", "watercolor"],
    ),
    "Automobile & Vehicles": _terms(
        strong=[
            "horsepower",
            "drivetrain",
            "camshaft",
            "odometer",
            "test drive",
            "dealership",
            "sedan",
            "suv",
            "motorcycle",
            "chassis",
            "transmission",
            "ev charging",
            "car review",
            "torque",
        ],
        weak=["vehicle", "mileage", "driver", "engine"],
        # "engine" is weak and heavily overloaded; veto the common non-automotive senses
        exclude=[
            "search engine",
            "game engine",
            "engine of growth",
            "rendering engine",
        ],
    ),
    "Books": _terms(
        strong=[
            "novelist",
            "paperback",
            "hardcover",
            "book review",
            "bestseller",
            "literary fiction",
            "poetry collection",
            "isbn",
            "goodreads",
            "booker prize",
            "audiobook",
            "bookstore",
            "memoir",
        ],
        weak=["novel", "publisher", "chapter", "reading"],
    ),
    "Business, Finance & Banking": _terms(
        strong=[
            "earnings",
            "ipo",
            "nasdaq",
            "hedge fund",
            "interest rate",
            "federal reserve",
            "mortgage",
            "dividend",
            "shareholder",
            "acquisition",
            "venture capital",
            "balance sheet",
            "inflation",
            "central bank",
            "valuation",
        ],
        weak=["market", "investor", "profit", "funding", "stock", "revenue"],
    ),
    "Celebrities & Culture": _terms(
        strong=[
            "red carpet",
            "paparazzi",
            "tabloid",
            "celebrity",
            "met gala",
            "socialite",
            "a-list",
            "kardashian",
            "gossip column",
            "tmz",
            "engagement ring",
            "publicist",
        ],
        weak=["rumour", "rumor", "spotted", "gossip"],
    ),
    "Computer Hardware & Software": _terms(
        strong=[
            "gpu",
            "cpu",
            "motherboard",
            "ssd",
            "benchmark",
            "nvidia",
            "ryzen",
            "overclock",
            "firmware",
            "thermal paste",
            "chipset",
            "raid array",
            "laptop review",
            "graphics card",
        ],
        weak=["hardware", "upgrade", "install", "peripheral"],
        exclude=["driver's licence", "driver's license"],
    ),
    "Education": _terms(
        strong=[
            "curriculum",
            "classroom",
            "school district",
            "undergraduate",
            "standardized test",
            "scholarship",
            "syllabus",
            "k-12",
            "tuition",
            "faculty",
            "professor",
            "phd programme",
            "phd program",
        ],
        weak=["student", "teacher", "learning", "course", "degree"],
    ),
    "Fashion & Beauty": _terms(
        strong=[
            "runway",
            "couture",
            "skincare",
            "mascara",
            "lipstick",
            "streetwear",
            "fashion week",
            "haircare",
            "manicure",
            "wardrobe",
            "moisturiser",
            "moisturizer",
            "sneakerhead",
        ],
        weak=["outfit", "boutique", "cosmetics", "styling"],
    ),
    "Food & Drink": _terms(
        strong=[
            "recipe",
            "preheat",
            "tablespoon",
            "teaspoon",
            "sourdough",
            "michelin star",
            "sommelier",
            "cocktail",
            "barista",
            "espresso",
            "marinade",
            "brewery",
            "restaurant review",
            "ingredients",
        ],
        weak=["kitchen", "cooking", "flavour", "flavor", "dish", "menu"],
    ),
    "Gaming": _terms(
        strong=[
            "video game",
            "video games",
            "playstation",
            "xbox",
            "nintendo",
            "esports",
            "speedrun",
            "roguelike",
            "steam deck",
            "mmorpg",
            "indie game",
            "game studio",
            "dlc",
        ],
        weak=["gameplay", "console", "multiplayer", "patch notes"],
        exclude=["board game", "the gaming commission"],
    ),
    "Health": _terms(
        strong=[
            "clinical trial",
            "vaccine",
            "cardiology",
            "mental health",
            "physician",
            "prescription",
            "diabetes",
            "cancer screening",
            "public health",
            "diagnosis",
            "symptoms",
            "epidemiology",
            "nutrition",
        ],
        weak=["patient", "treatment", "doctor", "disease", "wellness"],
    ),
    "Movies & TV": _terms(
        strong=[
            "box office",
            "screenplay",
            "netflix",
            "season finale",
            "showrunner",
            "film festival",
            "sundance",
            "blockbuster",
            "sitcom",
            "cinematography",
            "streaming series",
            "oscar",
        ],
        weak=["episode", "cast", "trailer", "director", "film"],
    ),
    "Music": _terms(
        strong=[
            "tracklist",
            "guitarist",
            "spotify",
            "concert tour",
            "billboard chart",
            "drummer",
            "vinyl",
            "songwriter",
            "grammy",
            "setlist",
            "bassline",
            "record label",
            "discography",
        ],
        weak=["album", "band", "song", "single"],
    ),
    "News & Weather": _terms(
        # Deliberately narrow. This label dominated the historical vote data;
        # generic newsroom vocabulary is intentionally absent.
        strong=[
            "hurricane",
            "tornado",
            "blizzard",
            "wildfire",
            "earthquake",
            "flood warning",
            "meteorologist",
            "evacuation order",
            "storm surge",
            "heatwave",
            "weather forecast",
            "tropical storm",
        ],
        weak=["forecast", "temperature", "officials said", "emergency services"],
    ),
    "Pets & Animals": _terms(
        strong=[
            "veterinarian",
            "puppy",
            "kitten",
            "animal shelter",
            "dog breed",
            "cat litter",
            "aquarium",
            "wildlife rescue",
            "pet food",
            "grooming",
            "leash",
            "adoption centre",
        ],
        weak=["pet", "breed", "owner", "paws"],
    ),
    "Photography": _terms(
        strong=[
            "aperture",
            "shutter speed",
            "mirrorless",
            "dslr",
            "lightroom",
            "bokeh",
            "focal length",
            "darkroom",
            "photographer",
            "tripod",
            "raw file",
            "telephoto",
        ],
        weak=["lens", "exposure", "camera", "photo"],
        exclude=["iso 27001", "iso standard", "iso 8601", "iso 9001"],
    ),
    "Politics": _terms(
        strong=[
            "parliament",
            "senator",
            "ballot",
            "legislation",
            "prime minister",
            "referendum",
            "filibuster",
            "coalition government",
            "impeach",
            "constituency",
            "electorate",
            "campaign trail",
            "congress",
        ],
        weak=["policy", "election", "government", "vote"],
    ),
    "Programming": _terms(
        strong=[
            "javascript",
            "typescript",
            "compiler",
            "refactor",
            "api endpoint",
            "git commit",
            "kubernetes",
            "pull request",
            "stack trace",
            "runtime error",
            "sql query",
            "open source",
            "docker",
        ],
        weak=["code", "function", "library", "developer", "repository"],
    ),
    "Religion": _terms(
        strong=[
            "theology",
            "scripture",
            "congregation",
            "sermon",
            "vatican",
            "rabbi",
            "imam",
            "buddhist",
            "liturgy",
            "pilgrimage",
            "parish",
            "quran",
            "torah",
            "monastery",
        ],
        weak=["faith", "church", "prayer", "spiritual"],
    ),
    "Science & Technology": _terms(
        strong=[
            "astrophysics",
            "quantum",
            "genome",
            "particle accelerator",
            "nasa",
            "peer-reviewed",
            "telescope",
            "neuroscience",
            "climate model",
            "biotech",
            "satellite",
            "arxiv",
            "hypothesis",
        ],
        weak=["research", "scientists", "discovery", "experiment", "laboratory"],
    ),
    "Sport": _terms(
        strong=[
            "goalkeeper",
            "touchdown",
            "premier league",
            "nba",
            "playoff",
            "marathon",
            "quarterback",
            "olympics",
            "formula 1",
            "midfielder",
            "fifa",
            "wicket",
            "striker",
        ],
        weak=["team", "match", "tournament", "coach", "season"],
    ),
    "Travel": _terms(
        strong=[
            "itinerary",
            "hostel",
            "airfare",
            "layover",
            "backpacking",
            "visa requirement",
            "tripadvisor",
            "boarding pass",
            "sightseeing",
            "national park",
            "airbnb",
            "all-inclusive resort",
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
