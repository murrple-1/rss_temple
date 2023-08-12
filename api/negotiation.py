from typing import Iterable

from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.parsers import BaseParser
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    def select_parser(
        self, request: Request, parsers: Iterable[BaseParser]
    ) -> BaseParser | None:  # pragma: no cover
        """
        Select the first parser in the `.parser_classes` list.
        """
        return list(parsers)[0]

    def select_renderer(
        self,
        request: Request,
        renderers: Iterable[BaseRenderer],
        format_suffix: str | None = None,
    ):  # pragma: no cover
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        renderers = list(renderers)
        return (renderers[0], renderers[0].media_type)
