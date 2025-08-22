from typing import List
from pydantic_xml import BaseXmlModel, attr, element

from models.common import RefElement


class PtSDP3Range(
    BaseXmlModel,
    tag="PtSDP3Range",
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
    importedRangeRef: RefElement = element("ImportedRangeRef")
    discreteValueRef: List[RefElement] = element("DiscreteValueRef")

    class Config:
        xml_ns = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
