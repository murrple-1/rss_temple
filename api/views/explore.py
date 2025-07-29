from typing import Any, TypedDict, cast

from django.core.cache import BaseCache, caches
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from url_normalize import url_normalize

from api.lock_context import lock_context
from api.models import (
    AlternateFeedURL,
    Feed,
    FeedEntry,
    SubscribedFeedUserMapping,
    User,
)
from api.serializers import ExploreSerializer


class _FeedDesc(TypedDict):
    feed_url: str
    image_src: str | None


class _Section(TypedDict):
    tag: str
    feeds: list[_FeedDesc]


_section_lookups: list[_Section] = [
    {
        "tag": "Gaming",
        "feeds": [
            {
                "feed_url": "http://feeds.ign.com/ign/all",
                "image_src": "/assets/images/explore_banner.png",
            },
            {
                "feed_url": "https://www.eurogamer.net/?format=rss",
                "image_src": "/assets/images/explore_banner.png",
            },
        ],
    },
    {
        "tag": "Technology",
        "feeds": [
            {
                "feed_url": "http://rss.slashdot.org/Slashdot/slashdot",
                "image_src": None,
            },
            {
                "feed_url": "http://feeds.arstechnica.com/arstechnica/index",
                "image_src": None,
            },
        ],
    },
    {
        "tag": "World News",
        "feeds": [
            {
                "feed_url": "https://www.ctvnews.ca/rss/ctvnews-ca-top-stories-public-rss-1.822009",
                "image_src": None,
            },
        ],
    },
    {
        "tag": "Programming",
        "feeds": [
            {
                "feed_url": "https://proandroiddev.com/feed",
                "image_src": None,
            },
            {
                "feed_url": "https://www.xda-developers.com/feed/",
                "image_src": None,
            },
            {
                "feed_url": "http://syndication.thedailywtf.com/TheDailyWtf",
                "image_src": None,
            },
        ],
    },
    {
        "tag": "Music",
        "feeds": [
            {
                "feed_url": "http://battlehelm.com/feed/",
                "image_src": "/assets/images/explore_banner.png",
            },
            {
                "feed_url": "http://www.theblackplanet.org/feed/",
                "image_src": "/assets/images/explore_banner.png",
            },
            {
                "feed_url": "http://www.angrymetalguy.com/feed/",
                "image_src": "/assets/images/explore_banner.png",
            },
            {
                "feed_url": "http://consequenceofsound.net/feed",
                "image_src": "/assets/images/explore_banner.png",
            },
            {
                "feed_url": "http://deadrhetoric.com/feed/",
                "image_src": "/assets/images/explore_banner.png",
            },
        ],
    },
]


class ExploreView(APIView):
    @extend_schema(
        responses=ExploreSerializer(many=True),
        summary="Return a list of feeds, with example headlines, which are tailored to you",
        description="""Return a list of feeds, with example headlines, which are tailored to you.

TODO: for the time being, this will just be static data (based on my personal OPML for now), because a recommendation engine is quite an endeavour
""",
    )
    def get(self, request: Request):
        cache: BaseCache = caches["default"]

        ret_obj: list[dict[str, Any]] | None
        cache_hit = True
        with lock_context(cache, "explore_lock"):
            cache_key = "explore__ret_obj"
            ret_obj = cache.get(cache_key)
            if ret_obj is None:
                ret_obj = []

                feed_urls = frozenset(
                    cast(str, url_normalize(sf["feed_url"]))
                    for s in _section_lookups
                    for sf in s["feeds"]
                )

                feeds: dict[str, Feed] = {}

                most_recent_entries_qs = FeedEntry.objects.filter(
                    is_archived=False
                ).order_by("-published_at")[:5]
                for afu in (
                    AlternateFeedURL.objects.select_related("feed")
                    .prefetch_related(
                        Prefetch(
                            "feed__feed_entries",
                            most_recent_entries_qs,
                            to_attr="feed__most_recent_entries",
                        )
                    )
                    .filter(feed_url__in=feed_urls)
                ):
                    feeds[afu.feed_url] = afu.feed

                for f in Feed.objects.prefetch_related(
                    Prefetch(
                        "feed_entries",
                        most_recent_entries_qs,
                        to_attr="most_recent_entries",
                    )
                ).filter(feed_url__in=feed_urls):
                    feeds[f.feed_url] = f

                for section_lookup in _section_lookups:
                    feed_objs: list[dict[str, Any]] = []
                    for feed_lookup in section_lookup["feeds"]:
                        feed = feeds.get(
                            cast(str, url_normalize(feed_lookup["feed_url"]))
                        )
                        if not feed:
                            continue

                        some_feed_entry_titles = list(
                            e.title for e in feed.most_recent_entries
                        )

                        if not some_feed_entry_titles:
                            continue

                        feed_objs.append(
                            {
                                "_uuid": feed.uuid,
                                "name": feed.title,
                                "feedUrl": feed.feed_url,
                                "homeUrl": feed.home_url,
                                "imageSrc": feed_lookup["image_src"],
                                "entryTitles": some_feed_entry_titles,
                            }
                        )

                    if feed_objs:
                        ret_obj.append(
                            {
                                "tagName": section_lookup["tag"],
                                "feeds": feed_objs,
                            }
                        )

                cache_hit = False
                cache.set(cache_key, ret_obj, 60.0 * 60.0 * 3.0)

        subscribed_feed_uuids = frozenset(
            SubscribedFeedUserMapping.objects.filter(
                user=cast(User, request.user)
            ).values_list("feed_id", flat=True)
        )

        for json_ in ret_obj:
            for feed_json in json_["feeds"]:
                uuid_ = feed_json.pop("_uuid")
                feed_json["isSubscribed"] = uuid_ in subscribed_feed_uuids

        response = Response(ExploreSerializer(ret_obj, many=True).data)
        response["X-Cache-Hit"] = "YES" if cache_hit else "NO"
        return response
