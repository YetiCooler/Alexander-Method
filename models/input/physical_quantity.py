from typing import List, Optional
from pydantic_xml import BaseXmlModel, attr, element


class NamePresentation(BaseXmlModel):
    edt: Optional[str] = attr("edt")
    value: str = ""


class Unit(BaseXmlModel):
    name: str = element("Name")
    namePresentation: NamePresentation = element("NamePresentation")
    factor: Optional[float] = element("Factor", default=None)


class StandardUnit(BaseXmlModel):
    ref: str = attr("ref")
    value: str = ""


class PhysicalQuantity(BaseXmlModel, tag="PhysicalQuantity"):
    name: str = element("Name")
    namePresentation: NamePresentation = element("NamePresentation")
    standardUnit: StandardUnit = element("StandardUnit")
    unit: List[Unit] = element("Unit")

    class Config:
        xml_ns = {
            "xsi": "http://www.w3.org/2001/XMLSchema-instance"
        }