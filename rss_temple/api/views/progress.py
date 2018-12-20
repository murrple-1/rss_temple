import uuid

from django.http import HttpResponse, HttpResponseNotFound, HttpResponseNotAllowed

from api import models, searchqueries


def feed_subscription_progress(request, _uuid):
    permitted_methods = {'GET'}

    if request.method not in permitted_methods:
        return HttpResponseNotAllowed(permitted_methods) # pragma: no cover

    if request.method == 'GET':
        return _feed_subscription_progress_get(request, _uuid)


def _feed_subscription_progress_get(request, _uuid):
    _uuid = uuid.UUID(_uuid)

    feed_subscription_progress_entry = None
    try:
        feed_subscription_progress_entry = models.FeedSubscriptionProgressEntry.objects.get(uuid=_uuid, user=request.user)
    except models.FeedSubscriptionProgressEntry.DoesNotExist:
        return HttpResponseNotFound('progress not found')

    ret_obj = None
    if feed_subscription_progress_entry.status == models.FeedSubscriptionProgressEntry.NOT_STARTED:
        ret_obj = {
            'state': 'notstarted',
        }
    elif feed_subscription_progress_entry.status == models.FeedSubscriptionProgressEntry.STARTED:
        progress_statuses = list(models.FeedSubscriptionProgressEntryDescriptor.objects.filter(feed_subscription_progress_entry=feed_subscription_progress_entry).values_list('is_finished', flat=True))

        total_count = len(progress_statuses)

        finished_count = sum(1 for is_finished in progress_statuses if is_finished)

        ret_obj = {
            'state': 'started',
            'totalCount': total_count,
            'finishedCount': finished_count,
        }
    else:
        ret_obj = {
            'state': 'finished',
        }

    content, content_type = searchqueries.serialize_content(ret_obj)

    return HttpResponse(content, content_type)
