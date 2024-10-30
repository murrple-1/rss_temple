from query_utils.sort import DefaultDescriptor, SortConfig, standard_sort

sort_configs: dict[str, dict[str, SortConfig]] = {
    "usercategory": {
        "uuid": SortConfig([standard_sort("uuid")], DefaultDescriptor(0, "ASC")),
        "text": SortConfig([standard_sort("text")], None),
    },
    "feed": {
        "uuid": SortConfig([standard_sort("uuid")], DefaultDescriptor(0, "ASC")),
        "title": SortConfig([standard_sort("title")], None),
        "feedUrl": SortConfig([standard_sort("feed_url")], None),
        "homeUrl": SortConfig([standard_sort("home_url")], None),
        "publishedAt": SortConfig([standard_sort("published_at")], None),
        "updatedAt": SortConfig([standard_sort("updated_at")], None),
        "isSubscribed": SortConfig([standard_sort("is_subscribed")], None),
        "customTitle": SortConfig([standard_sort("custom_title")], None),
        "calculatedTitle": SortConfig(
            [standard_sort("custom_title"), standard_sort("title")], None
        ),
    },
    "feedentry": {
        "uuid": SortConfig([standard_sort("uuid")], None),
        "createdAt": SortConfig([standard_sort("created_at")], None),
        "publishedAt": SortConfig(
            [standard_sort("published_at")], DefaultDescriptor(0, "DESC")
        ),
        "updatedAt": SortConfig([standard_sort("updated_at")], None),
        "title": SortConfig([standard_sort("title")], None),
        "isArchived": SortConfig([standard_sort("is_archived")], None),
        "languageIso639_3": SortConfig([standard_sort("language_id")], None),
        "languageIso639_1": SortConfig([standard_sort("language__iso639_1")], None),
        "language_name": SortConfig([standard_sort("language__name")], None),
        "hasTopImageBeenProcessed": SortConfig(
            [standard_sort("has_top_image_been_processed")], None
        ),
    },
}
