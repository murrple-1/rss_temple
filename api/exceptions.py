from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = 409
    default_detail = "This response is sent when a request conflicts with the current state of the server."
    default_code = "conflict"


class UnprocessableContent(APIException):
    status_code = 422
    default_detail = "The request was well-formed but was unable to be followed due to semantic errors."
    default_code = "unprocessable_content"


class InsufficientStorage(APIException):
    status_code = 507
    default_detail = "The method could not be performed on the resource because the server is unable to store the representation needed to successfully complete the request."
    default_code = "insufficient_storage"
