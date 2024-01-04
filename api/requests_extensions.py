import requests
from requests.models import CONTENT_CHUNK_SIZE


def safe_response_content(response: requests.Response, max_size: int) -> bytes:
    if max_size >= 0:
        byte_count = 0
        content_parts: list[bytes] = []

        for chunk in response.iter_content(chunk_size=CONTENT_CHUNK_SIZE):
            content_parts.append(chunk)
            byte_count += len(chunk)

            if byte_count > max_size:
                raise requests.exceptions.RequestException(
                    f"response too big (max size: {max_size} bytes)", response=response
                )

        content = b"".join(content_parts)
        response._content = content
        return content
    else:
        return response.content


def safe_response_text(
    response: requests.Response,
    max_size: int,
) -> str:
    if max_size >= 0:
        # based heavily on `requests.Response.text()`
        content = safe_response_content(response, max_size)

        if not content:
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
        except (LookupError, TypeError):
            return str(content, errors="replace")
    else:
        return response.text
