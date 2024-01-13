import os
from typing import Any

from dramatiq import Broker, Message, get_logger
from dramatiq.middleware import Middleware


def _message_str(message: Message) -> str:
    return f"{message.actor_name}|{message.message_id}|{message.message_timestamp}"


def _message_lock_filepath(message: Message) -> str:
    return os.path.join("mount/", f"{message.message_id}.lock")


class BeforeAfterLog(Middleware):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.logger = get_logger(__name__, type(self))

    def before_process_message(self, broker: Broker, message: Message):
        message_str = _message_str(message)

        # TODO remove, this is a temp hack to find a hard-to-trace bug
        with open(_message_lock_filepath(message), "w") as f:
            f.write(message_str)

        self.logger.info("before message: %s", message_str)

    def after_process_message(
        self,
        broker: Broker,
        message: Message,
        *,
        result: Any = None,
        exception: BaseException | None = None,
    ):
        # TODO remove, this is a temp hack to find a hard-to-trace bug
        os.unlink(_message_lock_filepath(message))

        self.logger.info("after message: %s", _message_str(message))
