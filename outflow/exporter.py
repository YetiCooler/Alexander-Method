import hashlib
import os
from xmltodict import parse, unparse

from inflow.base_config import BaseConfig
from config import (
    export_template_path,
    base_configs_output_folder,
    circuit_configs_output_folder,
    dtc_relations_output_folder,
    logs_output_folder,
    pt_components_output_folder,
)
from logger import audit_logger as logger

from database.database import get_component, mark_component_as_exported, driver
from database.models import PtComponentNode, Inference
from models.output.pt_component import PtComponent, NamePresentation
from pydantic_xml import BaseXmlModel, attr, element


class DataExporter:
    """Class to export the data to the xml files."""

    def __init__(self, base_output_path):
        self.base_output_path = base_output_path
        self.circuit_config_output_path = os.path.join(
            base_output_path, circuit_configs_output_folder
        )
        self.dtc_relation_output_path = os.path.join(
            base_output_path, dtc_relations_output_folder
        )
        self.base_config_output_path = os.path.join(
            base_output_path, base_configs_output_folder
        )
        self.logs_output_path = os.path.join(base_output_path, logs_output_folder)
        self.create_all_output_folders()

    def create_all_output_folders(self):
        os.makedirs(self.base_output_path, exist_ok=True)
        os.makedirs(self.circuit_config_output_path, exist_ok=True)
        os.makedirs(self.dtc_relation_output_path, exist_ok=True)
        os.makedirs(self.base_config_output_path, exist_ok=True)
        os.makedirs(self.logs_output_path, exist_ok=True)

    def export_component_config(
        self, component: str, details: dict, meta_config: dict, inference: Inference
    ) -> None:
        """
        Export the component configuration to the xml file.
        """

        # check if this component needs to be exported
        with driver.session() as session:
            component_db = session.execute_read(
                get_component,
                component,
                meta_config["ecu_system_execution"],
            )
            if component_db is None:
                logger.error(f"Component {component} not found in the database")
                return

            if component_db["exported"]:
                logger.info(f"Component {component} already exported skipping")
                return

        # check if the component is a connector by checking if starts with "C"

        if component.startswith("C"):
            self.export_connector_component_config(component, details, meta_config)
        else:
            self.export_normal_component_config(component, details, meta_config)

        # mark the component as exported
        with driver.session() as session:
            session.execute_write(
                mark_component_as_exported,
                component,
                meta_config["ecu_system_execution"],
            )

        # check if the component has a pt_component exported before
        pt_component = PtComponentNode.nodes.first_or_none(name=component)
        if pt_component is None:
            # create a new pt_component node
            pt_component = PtComponentNode(
                name=component,
            )
            pt_component.save()

            # add the pt_component to the inference
            inference.pt_components.connect(pt_component)  # type: ignore

            pt_component_model = PtComponent(
                name=component,
                namePresentation=NamePresentation(
                    value=details["description"],
                    edt="nfTxt",
                ),
            )

            if component.startswith("C"):
                pt_component_model.type = "Connector"

            # export the pt_component_model to the xml file
            pt_component_path = os.path.join(
                self.base_output_path,
                pt_components_output_folder,
                (
                    f"PtConnector_{component}.xml"
                    if component.startswith("C")
                    else f"PtComponent_{component}.xml"
                ),
            )

            # create the pt_component folder if it does not exist
            os.makedirs(os.path.dirname(pt_component_path), exist_ok=True)

            with open(pt_component_path, "wb") as file:
                file.write(
                    pt_component_model.to_xml(
                        pretty_print=True, encoding="UTF-8", xml_declaration=True
                    )  # type: ignore
                )

    def export_connector_component_config(
        self, component: str, details: dict, meta_config: dict
    ) -> None:
        """
        Export the connector component configuration to the xml file.
        """

        template_path = f"{export_template_path}/circuit_config_connector.xml"

        # load the template file
        with open(template_path, "r") as file:
            base_config = parse(file.read())

        # update the template with the component details
        base_config["PtCircuit"]["Name"] = component
        base_config["PtCircuit"]["EcuSystemFamily"]["#text"] = meta_config[
            "ecu_system_family"
        ]
        base_config["PtCircuit"]["EcuSystemExecution"]["#text"] = meta_config[
            "ecu_system_execution"
        ]
        base_config["PtCircuit"]["ServerExecution"]["#text"] = meta_config["server_can"]

        if "more_description" in details and details["more_description"] != "":
            base_config["PtCircuit"]["ShortFunctionDescription"] = {
                "#text": details["more_description"],
                "@edt": "nfTxt",
            }

        if "purpose" in details and details["purpose"] != "":
            base_config["PtCircuit"]["Purpose"] = {
                "#text": details["purpose"],
                "@edt": "fTxt",
            }

        base_config["PtCircuit"]["NamePresentation"][
            "#text"
        ] = f"{component}, {details['description']}"

        base_config["PtCircuit"]["MainComponent"]["Connector"]["#text"] = component

        # Add the IO Mapping
        if "io" in details:
            if "IO" not in base_config["PtCircuit"]:
                base_config["PtCircuit"]["IO"] = []
            for io_mapping in details["io"]:
                base_config["PtCircuit"]["IO"].append(
                    {
                        "@ref": "IO",
                        "#text": io_mapping["Name"],
                    }
                )

        # check if the file already exist and has the same content

        if os.path.exists(
            f"{self.circuit_config_output_path}/PtCircuit_{component}.xml"
        ):
            with open(
                f"{self.circuit_config_output_path}/PtCircuit_{component}.xml", "r"
            ) as file:
                existing_config = parse(file.read())
                if existing_config == base_config:
                    logger.info(
                        f"The configuration for the connector component {component} already exists and is up to date"
                    )
                    return

                else:
                    logger.info(
                        f"The configuration for the connector component {component} already exists but is not up to date"
                    )
                    # only update the IO mapping
                    if "IO" in base_config["PtCircuit"]:
                        existing_config["PtCircuit"]["IO"] = base_config["PtCircuit"][
                            "IO"
                        ]
                    if "ShortFunctionDescription" in base_config["PtCircuit"]:
                        existing_config["PtCircuit"]["ShortFunctionDescription"] = (
                            base_config["PtCircuit"]["ShortFunctionDescription"]
                        )
                    if "Purpose" in base_config["PtCircuit"]:
                        existing_config["PtCircuit"]["Purpose"] = base_config[
                            "PtCircuit"
                        ]["Purpose"]
                    base_config = existing_config

        # write the updated template to the xml file
        with open(
            f"{self.circuit_config_output_path}/PtCircuit_{component}.xml", "w"
        ) as file:
            file.write(unparse(base_config, pretty=True))
            logger.info(
                f"Exported the configuration for the connector component {component}"
            )

    def export_normal_component_config(
        self, component: str, details: dict, meta_config: dict
    ) -> None:
        """
        Export the normal component configuration to the xml file.
        """

        template_path = f"{export_template_path}/circuit_config_component.xml"

        # load the template file
        with open(template_path, "r") as file:
            base_config = parse(file.read())

        # update the template with the component details
        base_config["PtCircuit"]["Name"] = component
        base_config["PtCircuit"]["NamePresentation"]["#text"] = details["description"]

        base_config["PtCircuit"]["EcuSystemFamily"]["#text"] = meta_config[
            "ecu_system_family"
        ]
        base_config["PtCircuit"]["EcuSystemExecution"]["#text"] = meta_config[
            "ecu_system_execution"
        ]
        base_config["PtCircuit"]["ServerExecution"]["#text"] = meta_config["server_can"]

        base_config["PtCircuit"]["MainComponent"]["Component"]["#text"] = component

        if "more_description" in details and details["more_description"] != "":
            base_config["PtCircuit"]["ShortFunctionDescription"] = {
                "#text": details["more_description"],
                "@edt": "nfTxt",
            }

        if "purpose" in details and details["purpose"] != "":
            base_config["PtCircuit"]["Purpose"] = {
                "#text": details["purpose"],
                "@edt": "fTxt",
            }
        # Add the IO Mapping
        if "io" in details:
            for io_mapping in details["io"]:
                if "IO" not in base_config["PtCircuit"]:
                    base_config["PtCircuit"]["IO"] = []

                base_config["PtCircuit"]["IO"].append(
                    {
                        "@ref": "IO",
                        "#text": io_mapping["Name"],
                    }
                )

        # check if the file already exist and has the same content
        if os.path.exists(
            f"{self.circuit_config_output_path}/PtCircuit_{component}.xml"
        ):
            with open(
                f"{self.circuit_config_output_path}/PtCircuit_{component}.xml", "r"
            ) as file:
                existing_config = parse(file.read())
                if existing_config == base_config:
                    logger.info(
                        f"The configuration for the connector component {component} already exists and is up to date"
                    )
                    return

                else:
                    logger.info(
                        f"The configuration for the connector component {component} already exists but is not up to date"
                    )
                    # only update the IO mapping
                    if "IO" in base_config["PtCircuit"]:
                        existing_config["PtCircuit"]["IO"] = base_config["PtCircuit"][
                            "IO"
                        ]
                    if "ShortFunctionDescription" in base_config["PtCircuit"]:
                        existing_config["PtCircuit"]["ShortFunctionDescription"] = (
                            base_config["PtCircuit"]["ShortFunctionDescription"]
                        )
                    if "Purpose" in base_config["PtCircuit"]:
                        existing_config["PtCircuit"]["Purpose"] = base_config[
                            "PtCircuit"
                        ]["Purpose"]
                    base_config = existing_config

        # write the updated template to the xml file
        with open(
            f"{self.circuit_config_output_path}/PtCircuit_{component}.xml", "w"
        ) as file:
            file.write(unparse(base_config, pretty=True))
            logger.info(
                f"Exported the configuration for the normal component {component}"
            )

    def export_dtc_relation(self, dtc: str, details: dict, meta_config: dict) -> None:
        # just to be sure, check if the output folder exists and create it if not
        if not os.path.exists(self.dtc_relation_output_path):
            os.makedirs(self.dtc_relation_output_path)

        template_path = f"{export_template_path}/pt_dtc_relation.xml"

        # load the template file
        with open(template_path, "r") as file:
            base_config = parse(file.read())

        # update the template with the component details
        base_config["PtDtcRelation"]["DtcNr"] = dtc
        base_config["PtDtcRelation"]["ReferenceList"]["ObjectRefList"][
            "CircuitRefContainer"
        ]["CircuitName"] = details["component_name"]
        base_config["PtDtcRelation"]["ReferenceList"]["ObjectRefList"][
            "CircuitRefContainer"
        ]["CanAddress"] = meta_config["server_can"]

        base_config["PtDtcRelation"]["ReferenceList"]["ObjectRefList"][
            "CircuitRefContainer"
        ]["ServerExecution"] = meta_config["ecu_system_execution"]

        base_config["PtDtcRelation"]["ReferenceList"]["ObjectRefList"][
            "CircuitRefContainer"
        ]["EcuSystemFamily"] = meta_config["ecu_system_family"]

        base_config["PtDtcRelation"]["EcuSystemFamily"]["#text"] = meta_config[
            "ecu_system_family"
        ]
        base_config["PtDtcRelation"]["EcuSystemExecution"]["#text"] = meta_config[
            "ecu_system_execution"
        ]
        base_config["PtDtcRelation"]["ServerExecution"]["#text"] = meta_config[
            "server_can"
        ]

        # write the updated template to the xml file
        with open(
            f"{self.dtc_relation_output_path}/PtDtcRelation_{dtc}.xml", "w"
        ) as file:
            file.write(unparse(base_config, pretty=True))
            logger.info(f"Exported the DTC relation for the DTC {dtc}")

    def export_base_config(self, base_config: BaseConfig, components: dict) -> None:
        """
        Export the base configuration to the xml file.
        """

        # update the template with the base configuration details
        new_component_keys = [
            key
            for key in components.keys()
            if key not in base_config.base_config_circuits
            and key not in base_config.hero_circuits
        ]

        if len(new_component_keys) == 0:
            logger.info("No new components to add to the base configuration")
            return

        base_config_new = base_config.base_config

        if (base_config.id is None) or (base_config_new is None):
            logger.error(
                f"Base configuration {base_config.filename} has no id or filename"
            )
            return

        server_configuration_template = {
            "DisplayName": base_config.id + "-Hero-Intro",
            "ProductVariantConditionRef": {
                "@ref": "ProductVariantCondition",
                "#text": "Hero_Intro1",
            },
            "CircuitRef": [
                {"@ref": "CircuitRef", "#text": component}
                for component in new_component_keys
            ],
        }
        if "ServerConfiguration" not in base_config_new["PtConfigSet"]:
            base_config_new["PtConfigSet"][
                "ServerConfiguration"
            ] = server_configuration_template
        elif type(base_config_new["PtConfigSet"]["ServerConfiguration"]) == list:
            # check if our server configuration is already in the list
            server_config_exists = False
            for server_config in base_config_new["PtConfigSet"]["ServerConfiguration"]:
                if "Hero" in server_config["DisplayName"]:
                    # lets add the new components to the existing server configuration
                    # check if the server configuration has multiple components
                    if "CircuitRef" in server_config:
                        if type(server_config["CircuitRef"]) == list:
                            server_config["CircuitRef"].extend(
                                server_configuration_template["CircuitRef"]
                            )
                        else:
                            server_config["CircuitRef"] = [
                                server_config["CircuitRef"],
                                server_configuration_template["CircuitRef"],
                            ]
                        server_config_exists = True
                        break
                    else:
                        server_config["CircuitRef"] = server_configuration_template[
                            "CircuitRef"
                        ]
                        server_config_exists = True
                        break

            if not server_config_exists:
                base_config_new["PtConfigSet"]["ServerConfiguration"].append(
                    server_configuration_template
                )
        else:
            if (
                "Hero"
                in base_config_new["PtConfigSet"]["ServerConfiguration"]["DisplayName"]
            ):
                # lets add the new components to the existing server configuration
                # check if the server configuration has multiple components
                if (
                    "CircuitRef"
                    in base_config_new["PtConfigSet"]["ServerConfiguration"]
                ):
                    if (
                        type(
                            base_config_new["PtConfigSet"]["ServerConfiguration"][
                                "CircuitRef"
                            ]
                        )
                        == list
                    ):
                        base_config_new["PtConfigSet"]["ServerConfiguration"][
                            "CircuitRef"
                        ].extend(server_configuration_template["CircuitRef"])
                    else:
                        base_config_new["PtConfigSet"]["ServerConfiguration"][
                            "CircuitRef"
                        ] = [
                            base_config_new["PtConfigSet"]["ServerConfiguration"][
                                "CircuitRef"
                            ],
                            server_configuration_template["CircuitRef"],
                        ]
                else:
                    base_config_new["PtConfigSet"]["ServerConfiguration"][
                        "CircuitRef"
                    ] = server_configuration_template["CircuitRef"]
            else:
                base_config_new["PtConfigSet"]["ServerConfiguration"] = [
                    base_config_new["PtConfigSet"]["ServerConfiguration"],
                    server_configuration_template,
                ]

        # check if the hash of the base configuration has changed
        base_config_new_hash = hashlib.md5(
            unparse(base_config_new).encode()
        ).hexdigest()
        if base_config_new_hash == base_config.file_hash:
            logger.info("No new components to add to the base configuration")
            return

        # just to be sure, check if the output folder exists and create it if not
        if not os.path.exists(self.base_config_output_path):
            os.makedirs(self.base_config_output_path)

        # write the updated template to the xml file
        with open(
            f"{self.base_config_output_path}/{base_config.filename}", "w"
        ) as file:
            file.write(unparse(base_config_new, pretty=True))
            logger.info("Exported the base configuration")
