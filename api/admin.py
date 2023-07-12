from django.contrib import admin

from api.models import Feed, FeedEntry, User, UserCategory

admin.site.register(User)
admin.site.register(UserCategory)
admin.site.register(Feed)
admin.site.register(FeedEntry)
