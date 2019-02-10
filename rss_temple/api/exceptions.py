class QueryException(Exception):
    def __init__(self, message: str, httpcode: int):
        self.message = message
        self.httpcode = httpcode
