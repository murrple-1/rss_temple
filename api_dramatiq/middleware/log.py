import tracemalloc
from typing import Any

from dramatiq import Broker, Message, get_logger
from dramatiq.middleware import Middleware


class BeforeAfterLog(Middleware):
    snapshots: dict[str, tracemalloc.Snapshot]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.logger = get_logger(__name__, type(self))
        self.snapshots = {}
        tracemalloc.start()

    def before_process_message(self, broker: Broker, message: Message):
        self.snapshots[message.message_id] = tracemalloc.take_snapshot()

    def after_process_message(
        self,
        broker: Broker,
        message: Message,
        *,
        result: Any = None,
        exception: BaseException | None = None,
    ):
        old_snapshot = self.snapshots.pop(message.message_id)
        final_snapshot = tracemalloc.take_snapshot()

        top_stats = final_snapshot.compare_to(old_snapshot, "lineno")

        for stat in top_stats[:10]:
            self.logger.info(str(stat))
