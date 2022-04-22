from django.urls import path

from . import views

urlpatterns = [
    path("user/verify", views.UserVerifyView.as_view()),
    path("user/attributes", views.UserAttributesView.as_view()),
    path("user", views.UserRetrieveUpdateView.as_view()),
    path("passwordresettoken/request", views.PasswordResetRequestView.as_view()),
    path("passwordresettoken/reset", views.PasswordResetView.as_view()),
    path(
        "feeds/subscribe/progress/<uuid:uuid>",
        views.FeedSubscriptionProgressView.as_view(),
    ),
    path("feeds/subscribe/<str:url>", views.FeedSubscribeView.as_view()),
    path("feeds/<str:url>", views.FeedRetrieveView.as_view()),
    path("feeds", views.FeedListView.as_view()),
    path("feedentries/stable", views.FeedEntryStableListView.as_view()),
    path("feedentries/read", views.FeedEntryReadView.as_view()),
    path("feedentries/favorite", views.FeedEntryFavoriteView.as_view()),
    path("feedentries/<uuid:uuid>", views.FeedEntryRetrieveView.as_view()),
    path("feedentries", views.FeedEntryListView.as_view()),
    path("usercategories/apply", views.UserCategoryApplyView.as_view()),
    path(
        "usercategories/<uuid:uuid>",
        views.UserCategoryRetrieveUpdateDestroyView.as_view(),
    ),
    path("usercategories", views.UserCategoryListCreateView.as_view()),
    path("opml", views.OPMLView.as_view()),
    path("explore", views.ExploreView.as_view()),
]
