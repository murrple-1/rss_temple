import requests


def safe_response_content(
    response: requests.Response, max_size: int, chunk_size: int
) -> bytes:
    content = b""

    for chunk in response.iter_content(chunk_size=chunk_size):
        content += chunk

        if len(content) > max_size:
            raise requests.exceptions.RequestException(
                f"response too big (max size: {max_size} bytes)", response=response
            )

    return content


def safe_response_text(
    response: requests.Response,
    max_size: int,
    chunk_size: int,
    default_encoding="utf-8",
) -> str:
    return safe_response_content(response, max_size, chunk_size).decode(
        response.encoding or default_encoding
    )
