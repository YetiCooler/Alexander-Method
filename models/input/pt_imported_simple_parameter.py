from typing import Dict
from pydantic import Field
from pydantic_xml import BaseXmlModel, attr, element

from models.common import RefElement


class ImportedSimpleParameter(BaseXmlModel):
    name: str = element("Name")
    description: str = element("Description")
    Unit: str = element("Unit")
    rangeRef: RefElement = element("ImportedRangeRef")
    UserFunction: str = element("UserFunction")


class PtImportedSimpleParameter(BaseXmlModel, tag="PtImportedSimpleParameter"):
    name: str = element("Name")
    ecuSystemFamily: RefElement = element("EcuSystemFamily")
    ecuSystemExecution: RefElement = element("EcuSystemExecution")
    serverExecution: RefElement = element("ServerExecution")
    importedSimpleParameter: ImportedSimpleParameter = element("ImportedSimpleParameter")

    class Config:
        xml_ns = {
            "xsi": "http://www.w3.org/2001/XMLSchema-instance"
        }
