import dramatiq

from api_dramatiq.broker import broker
from api_dramatiq.encoder import UJSONEncoder

dramatiq.set_broker(broker)
dramatiq.set_encoder(UJSONEncoder())

from api_dramatiq import tasks

assert tasks
