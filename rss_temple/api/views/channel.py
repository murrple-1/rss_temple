import pprint

from django.http import HttpResponse

import requests

import feedparser

from argon2 import PasswordHasher

from api import models

def test(request):
    # r = requests.get('https://community.chrono.gg/c/daily-deals.rss')

    # d = feedparser.parse(r.text)

    # return HttpResponse(pprint.pformat(d), 'text/plain')

    # user = models.User()
    # user.email = 'test@test.com'

    # ph = PasswordHasher()

    # user.pw_hash = ph.hash('password')

    # user.save()

    # return HttpResponse(user.pw_hash, 'text/plain')

    user = models.User.objects.first()

    return HttpResponse(str(user.uuid), 'text/plain')
