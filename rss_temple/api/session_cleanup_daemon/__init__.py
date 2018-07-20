import logging
import sys

from django.db.models.functions import Now

from api import models

_logger = None
def logger():
    global _logger

    if _logger is None:
        _logger = logging.getLogger(__name__)
        _logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(stream_handler)

        file_handler = logging.handlers.RotatingFileHandler(
            filename='session_cleanup_daemon.log', maxBytes=(
                50 * 100000), backupCount=3)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter(
                fmt='%(asctime)s (%(levelname)s): %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(file_handler)

    return _logger


def cleanup():
    count, _ = models.Session.objects.filter(expires_at__lt=Now()).delete()

    if count > 0:
        logger().debug('deleting %s sessions', count)
    else:
        logger().debug('no sessions deleted')
