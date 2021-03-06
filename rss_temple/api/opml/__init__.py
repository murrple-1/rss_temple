import os

import xmlschema

_schema = None


def schema():
    global _schema

    if _schema is None:
        with open(os.path.join(os.path.dirname(__file__), 'xsd/opml-2.0.xsd')) as f:
            _schema = xmlschema.XMLSchema(f)

    return _schema
