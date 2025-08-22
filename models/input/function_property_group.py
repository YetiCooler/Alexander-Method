from typing import List, Optional
from pydantic_xml import BaseXmlModel, attr, element


class NamePresentation(BaseXmlModel):
    edt: Optional[str] = attr("edt")
    value: str = ""


class Description(BaseXmlModel):
    edt: Optional[str] = attr("edt")
    value: str = ""


class ProductVariantConditionRef(BaseXmlModel):
    ref: Optional[str] = attr("ref")
    value: str = ""


class Server(BaseXmlModel):
    canAddress: str = element("CanAddress")
    propertyName: str = element("PropertyName")


class Property(BaseXmlModel):
    server: Server = element("Server")


class PropertyGroup(BaseXmlModel):
    name: str = element("Name")
    namePresentation: NamePresentation = element("NamePresentation")
    description: Optional[Description] = element("Description", default=None)  # ✅ Added
    property: List[Property] = element("Property")


class FunctionPropertyGroup(
    BaseXmlModel,
    tag="FunctionPropertyGroup",
    nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"},
):
    name: str = element("Name")
    no_namespace_schema_location: str = attr(
        name="noNamespaceSchemaLocation",
        ns="xsi",
        default="../../../Dev/schema/sds/FunctionView/FunctionPropertyGroup/FunctionPropertyGroup.xsd",
    )

    namePresentation: NamePresentation = element("NamePresentation")
    description: Optional[Description] = element("Description", default=None)
    productVariantConditionRef: Optional[ProductVariantConditionRef] = element("ProductVariantConditionRef", default=None)
    ufNumber: List[int] = element("UFNumber")

    propertyGroup: Optional[List[PropertyGroup]] = element("PropertyGroup", default=None)
    property: Optional[List[Property]] = element("Property", default=None)
