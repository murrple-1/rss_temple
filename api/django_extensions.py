import itertools
from typing import Iterable, TypeVar

from django.db.models import Model

_Model = TypeVar("_Model", bound=Model)


def bulk_create_iter(
    iterable: Iterable[_Model], model_type: type[_Model], batch_size=2000
):
    created = 0
    while True:
        objects = model_type.objects.bulk_create(itertools.islice(iterable, batch_size))  # type: ignore
        created += len(objects)
        if not objects:
            break

    return created
