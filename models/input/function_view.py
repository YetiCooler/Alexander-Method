from typing import List, Optional
from pydantic_xml import BaseXmlModel, attr, element


class NamePresentation(BaseXmlModel):
    edt: Optional[str] = attr("edt")
    value: str = ""


class FunctionReference(BaseXmlModel):
    ref: str = attr("ref")
    value: str = ""


class Content(BaseXmlModel):
    functionPropertyGroup: Optional[List[FunctionReference]] = element(
        "FunctionPropertyGroup", default=None
    )
    functionGuidedMethodControlGroup: Optional[List[FunctionReference]] = element(
        "FunctionGuidedMethodControlGroup", default=None
    )
    functionGuidedMethodCalibrateGroup: Optional[List[FunctionReference]] = element(
        "FunctionGuidedMethodCalibrateGroup", default=None
    )


class Group(BaseXmlModel):
    name: str = element("Name")
    namePresentation: NamePresentation = element("NamePresentation")
    group: Optional[List["Group"]] = element("Group", default=None)  # recursive
    content: Optional[Content] = element("Content", default=None)


class FunctionView(
    BaseXmlModel,
    tag="FunctionView",
    nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"},
):
    name: str = element("Name")
    namePresentation: NamePresentation = element("NamePresentation")
    group: List[Group] = element("Group")
    no_namespace_schema_location: str = attr(
        name="noNamespaceSchemaLocation",
        ns="xsi",
        default="../../../Dev/schema/sds/FunctionView/FunctionPropertyGroup/FunctionPropertyGroup.xsd",
    )
