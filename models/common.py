

from pydantic_xml import BaseXmlModel, attr


class RefElement(BaseXmlModel):
    ref: str = attr("ref")
    name: str = ""
