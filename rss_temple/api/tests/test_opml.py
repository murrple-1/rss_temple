from xml.etree.cElementTree import fromstring

from django.test import TestCase

import xmlschema

from api import opml


class OPMLTestCase(TestCase):
    def test_get_schema(self):
        self.assertIsNotNone(opml.schema())

    def test_schema_success(self):
        text = None
        with open('api/tests/test_files/opml/murray.opml') as f:
            text = f.read()

        element = fromstring(text)

        opml.schema().validate(element)

    def test_schema_failed(self):
        text = None
        with open('api/tests/test_files/opml/murray.opml') as f:
            text = f.read()

        element = fromstring(text)
        head_element = element.find('./head')
        element.remove(head_element)

        with self.assertRaises(xmlschema.XMLSchemaException):
            opml.schema().validate(element)
