import logging

_logger = logging.getLogger(__name__)


def monkey_patch():
    from django.db.models.query_utils import DeferredAttribute

    def _deferredattribute_get(self, instance, cls=None):
        if instance is None:
            return self
        data = instance.__dict__
        field_name = self.field.attname
        if field_name not in data:
            # Let's see if the field is part of the parent chain. If so we
            # might be able to reuse the already loaded value. Refs #18343.
            val = self._check_parent_chain(instance)
            if val is None:
                if instance.pk is None and self.field.generated:
                    raise AttributeError(
                        "Cannot read a generated field from an unsaved model."
                    )

                import traceback

                stack = "\n".join(str(t) for t in traceback.format_stack())
                _logger.warning(
                    "loading deferred %s from %s, PK %s\n%s",
                    field_name,
                    instance.__class__,
                    instance.pk,
                    stack,
                )
                instance.refresh_from_db(fields=[field_name])
            else:
                data[field_name] = val
        return data[field_name]

    DeferredAttribute.__get__ = _deferredattribute_get
