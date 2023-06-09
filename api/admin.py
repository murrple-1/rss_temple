from django.contrib import admin

from api.models import (
    Feed,
    FeedEntry,
    NotifyEmailQueueEntry,
    PasswordResetToken,
    User,
    UserCategory,
    VerificationToken,
)

admin.site.register(User)
admin.site.register(VerificationToken)
admin.site.register(PasswordResetToken)
admin.site.register(UserCategory)
admin.site.register(Feed)
admin.site.register(FeedEntry)
admin.site.register(NotifyEmailQueueEntry)
