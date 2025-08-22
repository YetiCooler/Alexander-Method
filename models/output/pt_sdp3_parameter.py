from pydantic_xml import BaseXmlModel, attr, element
from typing import Optional

from models.common import RefElement


class PresentationText(BaseXmlModel):
    edt: Optional[str] = attr("edt")
    value: str = ""


class PtSDP3Parameter(
    BaseXmlModel,
    tag="PtSDP3Parameter",
    nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"},
):
    name: str = element("Name")
    no_namespace_schema_location: str = attr(
        name="noNamespaceSchemaLocation",
        ns="xsi",
        default="../../../Dev/schema/sds/FunctionView/FunctionPropertyGroup/FunctionPropertyGroup.xsd",
    )
    ecuSystemFamily: RefElement = element("EcuSystemFamily")
    ecuSystemExecution: RefElement = element("EcuSystemExecution")
    serverExecution: RefElement = element("ServerExecution")
    categoryCondition: RefElement = element("CategoryCondition")
    namePresentation: PresentationText = element("NamePresentation")
    description: PresentationText = element("Description")
    physicalQuantity: RefElement = element("PhysicalQuantity")
    importedSimpleParameterRef: RefElement = element("ImportedSimpleParameterRef")

    class Config:
        xml_ns = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
