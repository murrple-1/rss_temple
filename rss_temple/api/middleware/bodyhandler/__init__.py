# If the HTTP request body is large (seemingly 4096 bytes or larger),
# Nginx keeps the connection open until the body is read

# In certain cases (like authentication failing), the response will return
# early, and the body will not be read. This causes Nginx to hold the response
# and fail/timeout instead of returning the response. As such, this middleware
# ensures the body is read, regardless if it's used or not

# See: https://stackoverflow.com/a/28992297/240386
# http://uwsgi-docs.readthedocs.io/en/latest/ThingsToKnow.html (ctrl-F 'post-buffering')


class BodyHandlerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):
        request.body
        return self.get_response(request)
