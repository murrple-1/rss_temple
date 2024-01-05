from typing import Any

import requests
from requests.models import CONTENT_CHUNK_SIZE


class ResponseTooBig(BufferError):
    def __init__(self, *args: Any, **kwargs: Any):
        response = kwargs.pop("response", None)
        self.response = response
        super().__init__(*args, **kwargs)


def safe_response_content(response: requests.Response, max_byte_count: int) -> bytes:
    if max_byte_count >= 0:
        byte_count = 0
        content_parts: list[bytes] = []

        for chunk in response.iter_content(chunk_size=CONTENT_CHUNK_SIZE):
            content_parts.append(chunk)
            byte_count += len(chunk)

            if byte_count > max_byte_count:
                raise ResponseTooBig(
                    f"response too big (max size: {max_byte_count} bytes)",
                    response=response,
                )

        content = b"".join(content_parts)
        response._content = content
        return content
    else:
        return response.content


def safe_response_text(
    response: requests.Response,
    max_byte_count: int,
) -> str:
    if max_byte_count >= 0:
        # based heavily on `requests.Response.text()`
        content = safe_response_content(response, max_byte_count)

        if not content:  # pragma: no cover
            return ""

        try:
            return str(
                content,
                (
                    r_encoding
                    if (r_encoding := response.encoding) is not None
                    else response.apparent_encoding
                ),
                errors="replace",
            )
        except (LookupError, TypeError):  # pragma: no cover
            return str(content, errors="replace")
    else:
        return response.text
