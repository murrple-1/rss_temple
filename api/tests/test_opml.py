from xml.etree.cElementTree import fromstring

import xmlschema
from django.test import TestCase

from api import opml


class OPMLTestCase(TestCase):
    def test_get_schema(self):
        self.assertIsNotNone(opml.schema())

    def test_schema_success(self):
        text = None
        with open("api/tests/test_files/opml/opml-mix.xml") as f:
            text = f.read()

        element = fromstring(text)

        opml.schema().validate(element)

    def test_schema_failed(self):
        text = None
        with open("api/tests/test_files/opml/invalid_opml.xml") as f:
            text = f.read()

        element = fromstring(text)

        with self.assertRaises(xmlschema.XMLSchemaException):
            opml.schema().validate(element)
