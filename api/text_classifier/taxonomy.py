"""Classifier label taxonomy and the seed terms used for weak supervision.

Deliberately free of any Django import: `scripts/train_classifier.py` imports
this module on a machine with no Django settings configured.

This module is the single source of truth for the label set.
`api/management/commands/checkclassifierlabels.py` imports LABEL_NAMES from
here and warns when the database drifts from it.

Seed term rule of thumb: a *weak* term must look out of place in an article
about a different topic. If you can write a natural sentence in another
domain that contains it, it is not a weak term -- it is noise. Two weak
matches are enough to fire a label, so two generic words that happen to
co-occur in an unrelated article are enough to mislabel it. Prefer a longer,
more specific phrase (e.g. "film director" instead of bare "director") over
a bare common word, and prefer removing/replacing an offending term over
bolting on an `exclude` entry for every phrasing you can think of --
excludes only catch phrasings you predicted.
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
        # "dubbed" ("the plan, dubbed Project X") and "adaptation" (any book
        # or film adaptation) are generic English, not anime-specific.
        weak=["cosplay", "fansub", "anime convention"],
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
        # "handmade" and "craft" alone are generic (craft beer, statecraft,
        # handmade jewellery/furniture/soap) and co-occur in unrelated
        # articles, e.g. "a small-batch brewery, true to the craft of
        # brewing, makes everything handmade." "pattern" alone is likewise
        # generic (design pattern, weather pattern, sleep pattern).
        weak=[
            "watercolour",
            "watercolor",
            "craft project",
            "diy tutorial",
            "sewing pattern",
            "papercraft",
        ],
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
        # "driver" and "engine" co-occur naturally in tech/gaming writing
        # ("the updated graphics driver boosts frame rates in Unreal Engine
        # titles"). "vehicle" and "mileage" are also generic metaphors
        # ("vehicle for change", "got a lot of mileage out of the story").
        # Dropped all four rather than trying to enumerate every non-
        # automotive sense; the strong list is already specific enough to
        # carry the label on its own. "driver" (device driver) now lives on
        # Computer Hardware & Software instead, where it belongs.
        weak=["roadworthy", "fuel economy", "vehicle recall", "used car"],
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
        # "novel" is routinely an adjective ("a novel approach", "novel
        # coronavirus"); "chapter" means a local branch of an organization
        # or a bankruptcy filing as often as a book section; "reading" is a
        # generic verb in every domain; "publisher" also means a video game
        # publisher.
        weak=["book club", "debut novel", "self-published", "protagonist"],
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
        # "market", "stock", and "funding" are extremely generic (job
        # market, art market, stock photo, stock car, chicken stock, school
        # funding, research funding); "profit" shows up as a plain verb in
        # unrelated writing ("the team profited from a strong start").
        weak=["investor", "revenue", "profit margin", "funding round", "stock buyback"],
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
        # Bare "rumour"/"rumor" collide with trade rumours (Sport), product
        # rumours (Gaming/Tech), and political rumours; bare "spotted" is a
        # generic verb ("spotted a pattern", "spotted owl").
        weak=["celebrity gossip", "dating rumour", "dating rumor", "spotted together"],
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
        # "upgrade" and "install" are generic verbs used for anything
        # mechanical ("upgrade your suspension yourself -- easy to install
        # in an afternoon"); bare "hardware" collides with hardware
        # stores, and bare "peripheral" is a common adjective meaning
        # "tangential". "driver" (device/graphics driver) belongs here --
        # moved from Automobile & Vehicles -- which is also why the
        # driver's-licence exclude below now has a term to guard.
        weak=["computer hardware", "software update", "driver", "usb peripheral"],
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
        # "course" matches "of course" ("it has, of course, been a learning
        # experience for the team this season" -- a sports blurb -- scores
        # both "course" and "learning"). "learning" alone is likewise
        # generic ("machine learning", "a learning experience", "learning
        # curve"). "degree" overwhelmingly means temperature or angle
        # ("the temperature dropped ten degrees overnight").
        weak=[
            "teacher",
            "online course",
            "lesson plan",
            "college student",
            "bachelor's degree",
        ],
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
        # Bare "boutique" is a common business idiom ("boutique investment
        # firm", "boutique law firm"); bare "outfit" also means a business
        # or organization ("a small trading outfit"); bare "styling" is
        # also CSS styling (Programming).
        weak=["cosmetics", "fashion boutique", "hair styling", "outfit inspiration"],
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
        # "cooking the books" is a finance-fraud idiom; "kitchen cabinet" is
        # a politics idiom; "flavour of the month" and "dish the dirt" are
        # general idioms; "menu" is now overwhelmingly software UI
        # vocabulary (settings menu, dropdown menu).
        weak=[
            "home cooking",
            "flavor profile",
            "flavour profile",
            "signature dish",
            "restaurant menu",
            "home kitchen",
        ],
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
        # Bare "console" is also the verb "to console" (comfort) and a
        # console table; the bigram is unambiguous.
        weak=["gameplay", "gaming console", "multiplayer", "patch notes"],
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
        # "wellness" and "treatment" collide in spa/retreat marketing copy
        # ("the retreat blends wellness with traditional spa treatment
        # rituals"); bare "patient" is also the common adjective ("she was
        # patient during the delay"); bare "doctor" is also a verb
        # ("accused of doctoring the documents").
        weak=["disease", "medical treatment", "hospital patient"],
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
        # "cast" is also a generic verb ("cast a vote", "cast doubt"), and
        # "director" is generic across every organization ("the board cast
        # the deciding vote to appoint a new director"); "trailer" also
        # means a vehicle/mobile home; bare "film" also means photographic
        # film.
        weak=[
            "film cast",
            "film director",
            "movie trailer",
            "tv episode",
            "feature film",
        ],
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
        # "single" and "band" collide directly in tech writing ("router
        # review: single-band 2.4GHz Wi-Fi..."); "band" is also a rubber
        # band, wedding band, or frequency band.
        weak=["studio album", "music band", "hit song", "chart single"],
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
        # "officials said" is generic wire-copy phrasing that appears in
        # sports, politics, and business reporting just as often as weather
        # reporting -- exactly the generic newsroom vocabulary this label is
        # supposed to avoid. Bare "forecast" is routinely a sales/earnings
        # forecast, and bare "temperature" is routinely a body temperature
        # (Health).
        weak=[
            "storm forecast",
            "temperature drop",
            "emergency officials",
            "emergency services",
        ],
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
        # Bare "pet" is a common idiom ("pet project", "pet peeve"); bare
        # "breed" is a common verb ("familiarity breeds contempt",
        # "competition breeds innovation"); bare "owner" is extremely
        # generic (business owner, homeowner, team owner).
        weak=["pet owner", "purebred", "paws", "family pet"],
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
        # "lens" is a generic metaphor ("viewed through the lens of recent
        # Fed moves"); "exposure" is routinely financial or sun exposure;
        # bare "camera" is also a security camera; bare "photo" is a photo
        # finish (Sport) or photo op (Politics). "iso" is added as a weak
        # term (the exposure-triangle setting) specifically so the
        # standards-body excludes below have something to guard.
        weak=["camera lens", "exposure settings", "camera gear", "photo essay", "iso"],
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
        # Bare "policy" is overwhelmingly an insurance/company policy;
        # bare "vote" is a generic idiom of confidence/approval used in
        # sport and business ("the coach got a vote of confidence") and in
        # reality-TV eliminations.
        weak=["public policy", "election", "government", "voter turnout"],
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
        # "code" collides with dress code/zip code/building code (verified:
        # "the property developer must follow the local building code");
        # "developer" also means a property developer; "function" is also
        # a social event ("a corporate function"); "library" is also a
        # public library.
        weak=[
            "source code",
            "software function",
            "code library",
            "software developer",
            "git repository",
        ],
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
        # Bare "faith" is a common business/legal idiom ("acted in good
        # faith"); bare "prayer" means a long-shot play in American
        # football ("a prayer", "Hail Mary"); bare "spiritual" is common in
        # "spiritual successor" (Gaming) and "spiritual home" (Sport).
        weak=["church", "religious faith", "prayer service", "spiritual guidance"],
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
        # Bare "research" is generic in every domain (market research,
        # "the team did their research before the match"); bare
        # "discovery" is also legal discovery (a lawsuit phase); bare
        # "experiment" is a culinary/fashion/social experiment.
        weak=[
            "scientists",
            "laboratory",
            "scientific research",
            "scientific discovery",
            "controlled experiment",
        ],
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
        # "team" and "season" collide directly (verified: "the hit sitcom
        # is returning with the same team for another season"); bare
        # "match" is also a matchstick or a perfect match; bare "coach" is
        # also a life/business coach or a bus/train carriage (Travel).
        weak=[
            "sports team",
            "match report",
            "tournament",
            "coaching staff",
            "regular season",
        ],
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
        # Bare "flight" is also "capital flight" (Business/Finance) or
        # "flight risk" (Legal); bare "destination" is a common business
        # metaphor ("a top destination for tech investment").
        weak=["hotel", "flight itinerary", "vacation destination", "tourist"],
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
