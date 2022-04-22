from lxml import etree as lxml_etree
from rest_framework.response import Response


class XMLResponse(Response):
    @property
    def rendered_content(self):
        self["Content-Type"] = "text/xml"
        return lxml_etree.tostring(self.data)
