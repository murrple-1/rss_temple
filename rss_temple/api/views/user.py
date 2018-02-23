import uuid

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseNotModified

from .. import models, searchqueries

def user(request, _uuid):
	permitted_methods = ['GET']

	if request.method not in permitted_methods:
		return HttpResponseNotAllowed(permitted_methods)

	if request.method == 'GET':
		return _user_get(request, _uuid)

def _user_get(request, _uuid):
	user = None
	try:
		user = models.User.objects.get(uuid=_uuid)
	except models.User.DoesNotExist:
		return HttpResponseNotFound('user not found')

	return HttpResponse(str(user.uuid), 'text/plain')
