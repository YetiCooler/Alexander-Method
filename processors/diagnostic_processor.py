"""
Generate a consolidated PtIOList XML file from raw diagnostic XMLs
and drop it into the inference’s output folder.

This is a self-contained refactor of the notebook “Conversion of PtIOlist (2).py”.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict

from lxml import etree
from neo4j import GraphDatabase
from pydantic_xml import BaseXmlModel, attr, element

from database.database import (
    neo4j_connection,
    neo4j_user,
    neo4j_password,
)
from processors.function_parameters.llm.iolist_conversion import (
   select_physical_quantity_description_for_io
)
from logger import (
    audit_logger as logger,
)
# ---------------------------------------------------------------------- XML MODELS
class RefElement(BaseXmlModel):
    ref: str = attr()
    text: str
    model_config = {"text_content_field": "text"}


class NamePresentation(BaseXmlModel):
    edt: Optional[str] = attr(default="nfTxt")
    text: str
    model_config = {"text_content_field": "text"}


class PhysicalQuantityElement(BaseXmlModel):
    ref: str = attr(default="PhysicalQuantity")
    text: str
    model_config = {"text_content_field": "text"}


class DescriptionElement(BaseXmlModel):
    edt: str = attr(default="fTxt")
    text: str
    model_config = {"text_content_field": "text"}


class DiscreteValueRef(BaseXmlModel):
    ref: Optional[str] = attr(default="DiscreteValue")
    text: str


class DiscreteVariable(BaseXmlModel):
    ref: str = attr(default="DiscreteVariable")
    text: str
    model_config = {"text_content_field": "text"}


class IOService(BaseXmlModel):
    name: str = element("Name")
    command_type: str = element("CommandType")
    description: Optional[DescriptionElement] = element("Description", default=None)
    resolution: Optional[str] = element("Resolution", default=None)
    min_value: Optional[str] = element("MinValue", default=None)
    max_value: Optional[str] = element("MaxValue", default=None)
    discrete_values: List[DiscreteValueRef] = element("DiscreteValueRef", default_factory=list)
    discrete_variable: Optional[DiscreteVariable] = element("DiscreteVariable", default=None)


class IO(BaseXmlModel):
    name: str = element("Name")
    name_presentation: NamePresentation = element("NamePresentation")
    physical_quantity: PhysicalQuantityElement = element("PhysicalQuantity")
    io_services: List[IOService] = element("IOService")


class PtIOList(BaseXmlModel, tag="PtIOList"):
    name: str = element("Name")
    ecu_system_family: RefElement = element("EcuSystemFamily")
    ecu_system_execution: RefElement = element("EcuSystemExecution")
    server_execution: RefElement = element("ServerExecution")
    io: List[IO] = element("IO")

    class Config:
        xml_ns = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        xml_attrs = {
            "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation":
            "../../../../../../Dev/schema/sds/ecuSystem/sdp/ioList/PtIOList.xsd"
        }

# ---------------------------------------------------------------------- helpers
_DRIVER = GraphDatabase.driver(
    neo4j_connection, auth=(neo4j_user, neo4j_password)
)


def get_ecu_info(system_name: str) -> Dict[str, str]:
    with _DRIVER.session() as s:
        rec = s.run(
            """
            MATCH (f:ECUFamily)-[:HAS_SYSTEM]->(s:ECUSystem {name: $system})
            MATCH (s)-[:USES_SERVER]->(srv:Server)
            RETURN f.name AS family, s.name AS system, srv.code AS server
            """,
            system=system_name,
        ).single()
    if rec:
        return {"family": rec["family"], "system": rec["system"], "server": rec["server"]}
    raise ValueError(f"ECU system {system_name} not found in Neo4j.")


def get_physical_quantity_by_unit(unit_name: str) -> List[str]:
    with _DRIVER.session() as s:
        result = s.run(
            """
            MATCH (u:Unit {name: $unit})<-[:HAS_UNIT]-(pq:PhysicalQuantity)
            RETURN pq.name AS name
            """,
            unit=unit_name,
        )
        return [r["name"] for r in result]


def extract_common(elem) -> Tuple[str, str, str, str, bool, bool, Optional[str]]:
    """
    Return (name, description, unit, scania_state, read_step?, control_step?, enumeration_element)
    """
    name = elem.findtext("Name") or ""
    desc = elem.findtext("Description") or ""
    unit = elem.findtext("Unit") or ""
    sc_state = elem.findtext("ScaniaState") or ""
    read_ts = elem.find("ReadTestStep") is not None
    ctrl_ts = elem.find("ControlTestStep") is not None
    enum = elem.find("Enumeration")
    return name.strip(), desc.strip(), unit.strip(), sc_state.strip(), read_ts, ctrl_ts, enum


def resolution_min_max(unit: str) -> Tuple[str, str, str]:
    if unit == "degC":
        return "0.1", "-40", "100"
    if unit == "%":
        return "1", "0", "100"
    if unit == "Pa":
        return "1", "0", "14"
    if unit == "V":
        return "0.1", "0", "24"
    return "1", "0", "100"


def create_io_service(
    io_name: str,
    io_desc: str,
    cmd_type: str,
    unit: str,
    scania_state: str,
    enum,
) -> IOService:
    svc = IOService(
        name=f"{io_name}-{cmd_type}",
        command_type=cmd_type,
        description=DescriptionElement(text=io_desc),
    )

    if enum is not None:
        for v in enum.findall("Value"):
            parts = (v.text or "").split(",")
            if len(parts) == 3:
                svc.discrete_values.append(DiscreteValueRef(text=parts[2].strip()))
    elif scania_state:
        svc.discrete_variable = DiscreteVariable(text=scania_state)
    else:
        r, mn, mx = resolution_min_max(unit)
        svc.resolution, svc.min_value, svc.max_value = r, mn, mx

    return svc


# ---------------------------------------------------------------------- main entry
def build_ptiolist_from_files(
    diagnostics_dir: str,
    output_dir: str,
) -> str:
    """
    Parse every XML in *diagnostics_dir*, create a de-duplicated PtIOList
    and return the path to the written file.
    """
    xmls = [f for f in os.listdir(diagnostics_dir) if f.lower().endswith(".xml")]
    if not xmls:
        raise FileNotFoundError("No diagnostic XML files found")

    # Determine ECU execution from first file name (prefix before underscore/extension)
    system_name = Path(xmls[0]).stem.split("_")[0]
    ecu_info = get_ecu_info(system_name)

    seen: set[str] = set()
    io_items: List[IO] = []

    for xml_name in xmls:
        logger.info(f"Processing {xml_name} Diagnostic file")
        tree = etree.parse(os.path.join(diagnostics_dir, xml_name))
        for path in (".//Values/Value", ".//IOs/IO", ".//FreezeFrameData"):
            for elem in tree.xpath(path):
                (
                    io_name,
                    desc,
                    unit,
                    sc_state,
                    read_step,
                    ctrl_step,
                    enum,
                ) = extract_common(elem)
                if not io_name or io_name in seen:
                    continue
                seen.add(io_name)

                # ---------------- LLM selection -----------------
                pq_choice = select_physical_quantity_description_for_io(
                    io_name=io_name,
                    unit=unit,
                    ecu_family=ecu_info["family"],
                    ecu_system=ecu_info["system"],
                    physical_quantities=", ".join(get_physical_quantity_by_unit(unit)),
                )
                physical_quantity = pq_choice.PhysicalQuantity
                io_desc = pq_choice.IODescription
                # ------------------------------------------------

                services: List[IOService] = []
                if read_step:
                    services.append(
                        create_io_service(
                            io_name, io_desc, "readIO", unit, sc_state, enum
                        )
                    )
                if ctrl_step:
                    services.append(
                        create_io_service(
                            io_name, io_desc, "controlIO", unit, sc_state, enum
                        )
                    )

                io_items.append(
                    IO(
                        name=io_name,
                        name_presentation=NamePresentation(text=desc),
                        physical_quantity=PhysicalQuantityElement(text=physical_quantity),
                        io_services=services,
                    )
                )

    ptio = PtIOList(
        name=ecu_info["system"],
        ecu_system_family=RefElement(ref="PtEcuSystemFamily", text=ecu_info["family"]),
        ecu_system_execution=RefElement(ref="PtEcuSystemExecution", text=ecu_info["system"]),
        server_execution=RefElement(ref="PtServerExecution", text=ecu_info["system"]),
        io=io_items,
    )

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"PtIOList_{ecu_info['system']}.xml")
    with open(out_path, "wb") as fh:
        fh.write(ptio.to_xml(encoding="utf-8", pretty_print=True, exclude_none=True))

    return out_path


# ---------------------------------------------------------------------- LangGraph integration node
def process_diagnostic_files(state):
    """
    LangGraph node wrapper – expects `diagnostic_files_folder` inside the
    inference input folder and puts the generated XML under
    <output_root_folder>/diagnostics/.
    """
    from config import (
        input_root_folder,
        output_root_folder,
        diagnostic_files_folder,
    )

    diag_dir = os.path.join(
        state.inference_base_folder, input_root_folder, diagnostic_files_folder
    )
    out_dir = os.path.join(
        state.inference_base_folder, output_root_folder, "diagnostics"
    )

    xml_path = build_ptiolist_from_files(diag_dir, out_dir)
    logger.info(f"PtIOList generated: {Path(xml_path).name}")
    state.update_queue.put(f"PtIOList generated: {Path(xml_path).name}")
