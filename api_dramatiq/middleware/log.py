from typing import Any

from dramatiq import Broker, Message, get_logger
from dramatiq.middleware import Middleware


class BeforeAfterLog(Middleware):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.logger = get_logger(__name__, type(self))

    def before_process_message(self, broker: Broker, message: Message):
        message_str = str(message)
        self.logger.info("before message: %s", message_str)

    def after_process_message(
        self,
        broker: Broker,
        message: Message,
        *,
        result: Any = None,
        exception: BaseException | None = None,
    ):
        self.logger.info("after message: %s", message)
