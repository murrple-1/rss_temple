def http_server_target(port):
    import os
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    os.chdir('api/tests/test_files/')

    class SimpleNoLogHTTPRequestHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            return

    with HTTPServer(('', port), SimpleNoLogHTTPRequestHandler) as httpd:
        httpd.serve_forever()
