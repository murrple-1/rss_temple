from django.contrib import admin

from api import models

admin.site.register(models.User)
admin.site.register(models.VerificationToken)
admin.site.register(models.PasswordResetToken)
admin.site.register(models.UserCategory)
admin.site.register(models.Feed)
admin.site.register(models.FeedEntry)
admin.site.register(models.NotifyEmailQueueEntry)
