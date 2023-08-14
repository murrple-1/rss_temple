import cProfile
import io
import marshal
import pstats
from typing import Callable

from django.http import HttpRequest, HttpResponse


class ProfilerMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if "prof" in request.GET:
            profiler = cProfile.Profile()
            profiler.runcall(self.get_response, request)

            response: HttpResponse
            if "download" in request.GET:
                stats = pstats.Stats(profiler)
                output = marshal.dumps(getattr(stats, "stats"))
                response = HttpResponse(output, content_type="application/octet-stream")
                response["Content-Disposition"] = "attachment; filename=view.prof"
                response["Content-Length"] = len(output)
            else:
                with io.StringIO() as f:
                    stats = pstats.Stats(profiler, stream=f)
                    stats.strip_dirs().sort_stats(request.GET.get("sort", "time"))
                    stats.print_stats(int(request.GET.get("count", 100)))

                    response = HttpResponse(f"<pre>{f.getvalue()}</pre>")
            return response
        else:
            return self.get_response(request)
