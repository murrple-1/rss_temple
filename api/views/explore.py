from typing import Any, TypedDict, cast

from django.core.cache import BaseCache, caches
from drf_yasg.utils import swagger_auto_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Feed, FeedEntry, User
from api.serializers import ExploreSerializer


class _FeedDesc(TypedDict):
    feed_url: str
    image_src: str | None


class _Section(TypedDict):
    tag: str
    feeds: list[_FeedDesc]


class ExploreView(APIView):
    @swagger_auto_schema(
        responses={200: ExploreSerializer(many=True)},
        operation_summary="Return a list of feeds, with example headlines, which are tailored to you",
        operation_description="""Return a list of feeds, with example headlines, which are tailored to you.

TODO: for the time being, this will just be static data (based on my personal OPML for now), because a recommendation engine is quite an endeavour
""",
    )
    def get(self, request: Request):
        cache: BaseCache = caches["default"]

        section_lookups: list[_Section] = [
            {
                "tag": "Gaming",
                "feeds": [
                    {
                        "feed_url": "http://feeds.feedburner.com/GamasutraFeatureArticles",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                    {
                        "feed_url": "http://feeds.wolfire.com/WolfireGames",
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
                        "feed_url": "http://feeds.feedburner.com/codinghorror",
                        "image_src": None,
                    },
                    {
                        "feed_url": "http://feeds.wolfire.com/WolfireGames",
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
                        "feed_url": "http://www.terrorizer.com/feed/",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                    {
                        "feed_url": "http://deadrhetoric.com/feed/",
                        "image_src": "/assets/images/explore_banner.png",
                    },
                ],
            },
        ]

        ret_obj: list[dict[str, Any]] = []

        feeds = {
            f.feed_url: f
            for f in Feed.annotate_subscription_data(
                Feed.objects.filter(
                    feed_url__in=(
                        sf["feed_url"] for s in section_lookups for sf in s["feeds"]
                    )
                ),
                cast(User, request.user),
            )
        }

        for section_lookup in section_lookups:
            feed_objs: list[dict[str, Any]] = []
            for feed_lookup in section_lookup["feeds"]:
                feed = feeds.get(feed_lookup["feed_url"])
                if not feed:
                    continue

                cache_key = f"explore__some_feed_entry_titles__{feed.uuid}"
                some_feed_entry_titles: list[str] | None = cache.get(cache_key)
                if some_feed_entry_titles is None:
                    some_feed_entry_titles = list(
                        feed.feed_entries.order_by("published_at").values_list(
                            "title", flat=True
                        )[:5]
                    )
                    cache.set(cache_key, some_feed_entry_titles, 60.0 * 60.0 * 24.0)

                if len(some_feed_entry_titles) < 1:
                    continue

                feed_objs.append(
                    {
                        "name": feed.title,
                        "feedUrl": feed.feed_url,
                        "homeUrl": feed.home_url,
                        "imageSrc": feed_lookup["image_src"],
                        "entryTitles": some_feed_entry_titles,
                        "isSubscribed": feed.is_subscribed,
                    }
                )

            if len(feed_objs) > 0:
                ret_obj.append(
                    {
                        "tagName": section_lookup["tag"],
                        "feeds": feed_objs,
                    }
                )

        return Response(ExploreSerializer(ret_obj, many=True).data)
