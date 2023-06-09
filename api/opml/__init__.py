import os

import xmlschema

_schema: xmlschema.XMLSchema | None = None


def schema() -> xmlschema.XMLSchema:
    global _schema

    if _schema is None:
        with open(os.path.join(os.path.dirname(__file__), "xsd/opml-2.0.xsd")) as f:
            _schema = xmlschema.XMLSchema(f)

    return _schema
