import os
import uuid
from typing import Any

from dramatiq import Broker, Message, get_logger
from dramatiq.middleware import Middleware


class BeforeAfterLog(Middleware):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.logger = get_logger(__name__, type(self))
        # TODO remove, this is a temp hack to find a hard-to-trace bug
        self.lock_filepath = os.path.join("mount/", f"{uuid.uuid4()}.lock")

    def before_process_message(self, broker: Broker, message: Message):
        message_str = str(message)
        with open(self.lock_filepath, "w") as f:
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
        os.unlink(self.lock_filepath)
        self.logger.info("after message: %s", message)
