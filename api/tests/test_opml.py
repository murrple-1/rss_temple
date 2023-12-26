from xml.etree.cElementTree import fromstring

import xmlschema
from django.test import TestCase

from api import opml


class OPMLTestCase(TestCase):
    def test_get_schema(self):
        self.assertIsNotNone(opml.schema())

    def test_schema_success(self):
        for filepath in [
            "api/tests/test_files/opml/opml-mix.xml",
            "api/tests/test_files/opml/opml-no-groups.xml",
        ]:
            with self.subTest(filepath=filepath):
                text: str
                with open("api/tests/test_files/opml/opml-mix.xml") as f:
                    text = f.read()

                element = fromstring(text)

                opml.schema().validate(element)

    def test_schema_failed(self):
        text: str
        with open("api/tests/test_files/opml/invalid_opml.xml") as f:
            text = f.read()

        element = fromstring(text)

        with self.assertRaises(xmlschema.XMLSchemaException):
            opml.schema().validate(element)

    def test_get_grouped_entries(self):
        for filepath, group_count in [
            ("api/tests/test_files/opml/opml-mix.xml", 8),
            ("api/tests/test_files/opml/opml-no-groups.xml", 1),
        ]:
            with self.subTest(filepath=filepath):
                text: str
                with open(filepath) as f:
                    text = f.read()

                element = fromstring(text)

                grouped_entries = opml.get_grouped_entries(element)
                self.assertEqual(len(grouped_entries), group_count)
