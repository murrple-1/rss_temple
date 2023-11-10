import uuid

import ujson
from dramatiq.encoder import Encoder, MessageData
from dramatiq.errors import DecodeError


def _default(obj):
    if isinstance(obj, uuid.UUID) and type(obj) is not uuid.UUID:
        return uuid.UUID(bytes=obj.bytes)
    raise TypeError


class UJSONEncoder(Encoder):
    def encode(self, data: MessageData) -> bytes:
        return ujson.dumps(data, default=_default).encode("utf-8")

    def decode(self, data: bytes) -> MessageData:
        try:
            return ujson.loads(data)
        except ujson.JSONDecodeError as e:
            raise DecodeError(f"failed to decode message: {data!r}", data, e) from None
