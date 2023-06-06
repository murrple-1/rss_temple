class QueryException(Exception):
    def __init__(self, message, httpcode):
        self.message = message
        self.httpcode = httpcode
