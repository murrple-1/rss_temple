import os
from collections import defaultdict
from typing import NamedTuple, cast
from xml.etree.ElementTree import Element

import xmlschema
from url_normalize import url_normalize

_schema: xmlschema.XMLSchema | None = None


def schema() -> xmlschema.XMLSchema:
    global _schema

    if _schema is None:
        with open(os.path.join(os.path.dirname(__file__), "xsd/opml-2.0.xsd")) as f:
            _schema = xmlschema.XMLSchema(f)

    return _schema


class Entry(NamedTuple):
    title: str
    url: str


def get_grouped_entries(opml_element: Element) -> dict[str | None, frozenset[Entry]]:
    grouped_entries: dict[str | None, set[Entry]] = defaultdict(set)

    for outer_outline_element in opml_element.findall("./body/outline"):
        outer_outline_name = outer_outline_element.attrib["title"]

        if (outline_xml_url := outer_outline_element.attrib.get("xmlUrl")) is not None:
            outline_xml_url = cast(str, url_normalize(outline_xml_url))
            grouped_entries[None].add(Entry(outer_outline_name, outline_xml_url))
        else:
            for outline_element in outer_outline_element.findall("./outline"):
                outline_name = outline_element.attrib["title"]
                outline_xml_url = cast(
                    str, url_normalize(outline_element.attrib["xmlUrl"])
                )

                grouped_entries[outer_outline_name].add(
                    Entry(outline_name, outline_xml_url)
                )

    return cast(dict[str | None, frozenset[Entry]], grouped_entries)
