from typing import List, Optional
from pydantic import Field
from pydantic_xml import BaseXmlModel, attr, element


class EcuSystemFamily(BaseXmlModel):
    ref: str = attr("ref")
    name: str = ""

class EcuSystemExecution(BaseXmlModel):
    ref: str = attr("ref")
    name: str = ""

class ServerExecution(BaseXmlModel):
    ref: str = attr("ref")
    name: str = ""

class ImportedDiscreteValue(BaseXmlModel):
    name: str = element("Name")


class PtImportedRange(BaseXmlModel, tag="PtImportedRange"):
    name: str = element("Name")
    ecuSystemFamily: EcuSystemFamily = element("EcuSystemFamily")
    ecuSystemExecution: EcuSystemExecution = element("EcuSystemExecution")
    serverExecution: ServerExecution = element("ServerExecution")
    importedDiscreteValue: Optional[List[ImportedDiscreteValue]] = element(
        "ImportedDiscreteValue", default=None
    )

    class Config:
        xml_ns = {
            "xsi": "http://www.w3.org/2001/XMLSchema-instance"
        }
