from typing import Optional, List
from pydantic_xml import BaseXmlModel, attr, element


class ConditionalDefaultText(BaseXmlModel):
    edt: Optional[str] = attr("edt")
    value: str = ""


class NamePresentation(BaseXmlModel):
    edt: Optional[str] = attr("edt")
    value: str = ""


class DefaultImage(BaseXmlModel):
    name: str = element("Name")
    image: NamePresentation = element(
        "Image"
    )  # Using NamePresentation because <Image> also has edt attribute


class ComponentLocation(BaseXmlModel):
    defaultImage: DefaultImage = element("DefaultImage")


class Overview(BaseXmlModel):
    defaultImage: DefaultImage = element("DefaultImage")


class Symbol(BaseXmlModel):
    defaultImage: DefaultImage = element("DefaultImage")


class PtComponent(BaseXmlModel, tag="PtComponent"):
    name: str = element("Name")
    namePresentation: NamePresentation = element("NamePresentation")
    description: Optional[ConditionalDefaultText] = element("Description", default=None)
    pinListInformation: Optional[ConditionalDefaultText] = element(
        "PinListInformation", default=None
    )
    componentLocation: ComponentLocation = element(
        "ComponentLocation",
        default_factory=lambda: ComponentLocation(
            defaultImage=DefaultImage(
                name="Truck_NGS",
                image=NamePresentation(
                    edt="media",
                    value="${BasAppDataSource.Ecu.media}\\LBTestPicture.png",
                ),
            )
        ),
    )
    overview: Overview = element(
        "Overview",
        default_factory=lambda: Overview(
            defaultImage=DefaultImage(
                name="Truck_NGS",
                image=NamePresentation(
                    edt="media",
                    value="${BasAppDataSource.Ecu.media}\\LBTestPicture.png",
                ),
            )
        ),
    )
    symbol: Symbol = element(
        "Symbol",
        default_factory=lambda: Symbol(
            defaultImage=DefaultImage(
                name="Truck_NGS",
                image=NamePresentation(
                    edt="media",
                    value="${BasAppDataSource.Ecu.media}\\LBTestPicture.png",
                ),
            )
        ),
    )
    type: Optional[str] = element("Type", default=None)

    class Config:
        xml_ns = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
