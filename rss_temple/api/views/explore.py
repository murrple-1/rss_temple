from django.http import HttpResponse, HttpResponseNotAllowed

from api import models, query_utils


def explore(request):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods)  # pragma: no cover

    if request.method == 'GET':
        return _explore_get(request)


def _explore_get(request):
    # TODO for the time being, this will just be static data (based on my personal OPML for now), because a recommendation engine is quite an endeavour
    section_lookups = [
        {
            'tag': 'Gaming',
            'feeds': [
                {
                  'feed_url': 'http://feeds.gawker.com/kotaku/full',
                  'image_src': 'https://pbs.twimg.com/profile_banners/759251/1607983278/1080x360',
                },
                {
                  'feed_url': 'http://feeds.feedburner.com/GamasutraFeatureArticles',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://feeds.wolfire.com/WolfireGames',
                  'image_src': 'https://pbs.twimg.com/profile_banners/759251/1607983278/1080x360',
                },
            ],
        },
        {
            'tag': 'Technology',
            'feeds': [
                {
                  'feed_url': 'http://rss.slashdot.org/Slashdot/slashdot',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://feeds.arstechnica.com/arstechnica/index',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://feeds.gawker.com/gizmodo/full',
                  'image_src': None,
                },
            ],
        },
        {
            'tag': 'World News',
            'feeds': [
                {
                  'feed_url': 'http://www.ctv.ca/generic/generated/freeheadlines/rdf/allNewsRss.xml',
                  'image_src': None,
                },
            ],
        },
        {
            'tag': 'Programming',
            'feeds': [
                {
                  'feed_url': 'http://feeds.feedburner.com/codinghorror',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://blogs.msdn.com/oldnewthing/rss.xml',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://feeds.wolfire.com/WolfireGames',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://syndication.thedailywtf.com/TheDailyWtf',
                  'image_src': None,
                },
            ],
        },
        {
            'tag': 'Music',
            'feeds': [
                {
                  'feed_url': 'http://battlehelm.com/feed/',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://www.theblackplanet.org/feed/',
                  'image_src': 'https://pbs.twimg.com/profile_banners/759251/1607983278/1080x360',
                },
                {
                  'feed_url': 'http://www.angrymetalguy.com/feed/',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://www.terrorizer.com/feed/',
                  'image_src': None,
                },
                {
                  'feed_url': 'http://deadrhetoric.com/feed/',
                  'image_src': None,
                },
            ],
        },
    ]

    ret_obj = []
    for section_lookup in section_lookups:
        feed_objs = []
        for feed_lookup in section_lookup['feeds']:
            feed = None
            try:
                feed = models.Feed.objects.with_subscription_data(request.user).get(feed_url=feed_lookup['feed_url'])
            except models.Feed.DoesNotExist:
                continue

            some_feed_entries = list(models.FeedEntry.objects.filter(feed=feed, title__isnull=False).order_by('published_at').values_list('title', flat=True)[:5])
            if len(some_feed_entries) < 1:
                continue

            feed_objs.append({
                'name': feed.title,
                'feedUrl': feed.feed_url,
                'homeUrl': feed.home_url,
                'imageSrc': feed_lookup['image_src'],
                'entryTitles': some_feed_entries,
                'isSubscribed': feed.is_subscribed,
            })

        if len(feed_objs) > 0:
            ret_obj.append({
                'tagName': section_lookup['tag'],
                'feeds': feed_objs,
            })

    content, content_type = query_utils.serialize_content(ret_obj)

    return HttpResponse(content, content_type)
