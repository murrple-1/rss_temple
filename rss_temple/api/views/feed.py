import pprint

from django.http import HttpResponse

import requests

import feedparser

def test(request):
    r = requests.get('https://community.chrono.gg/c/daily-deals.rss')

    d = feedparser.parse(r.text)

    return HttpResponse(pprint.pformat(d), 'text/plain')
