import hashlib
import os

import pymupdf
from graphs import circuit_extractor
from logger import (
    audit_logger as logger,
)
from database.database import (
    create_component,
    driver,
    link_component_to_circuit_diagram,
    save_app_state,
)
from config import (
    input_root_folder,
    circuit_diagrams_folder,
)

from state import State
from utils import get_system_config_by_filename, get_system_config_using_circuit_files
from graphs.circuit_extractor import graph as circuit_extractor


def process_circuit_diagrams(state: State):
    if not validate_circuit_files(state):
        logger.info(
            f"Skipping circuit diagram processing as the files are not valid or not found"
        )
        return
    if not validate_base_config(state):
        logger.info(
            f"Skipping circuit diagram processing as the base configuration is not valid"
        )
        return

    logger.info("Processing Circuit Diagrams")
    logger.info(f"Processing Circuit Diagrams for {state.ecu_system_execution}")
    logger.info(f"Processing Circuit Diagrams for {state.ecu_system_family}")
    # load all .pdf files in the specified path
    circuit_diagrams_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        circuit_diagrams_folder,
    )
    if not os.path.exists(circuit_diagrams_path):
        logger.info(
            f"Could not find the specified path for circuit diagrams: {circuit_diagrams_path}"
        )
        return
    files = [f for f in os.listdir(circuit_diagrams_path) if f.endswith(".pdf")]
    logger.info(f"Found {len(files)} circuit diagrams")
    if len(files) == 0:
        logger.info(
            f"No circuit diagrams found in the specified path, looked for .pdf files in {circuit_diagrams_path}"
        )
    # loop through the files in ./circuit_diagrams
    for filename in files:
        state.update_queue.put(f"Processing {filename}")
        logger.info(f"Processing{ filename}")
        with open(f"{circuit_diagrams_path}/{filename}", "rb") as file:
            # create a hash of the file
            file_id = hashlib.md5(file.read()).hexdigest()
        # open the pdf file
        pdf_file = pymupdf.open(f"{circuit_diagrams_path}/{filename}")

        has_been_processed = False
        for app_state_file in state.app_state.circuit_diagrams:
            if (
                file_id == app_state_file["hash"]
                and app_state_file["ecu_system"] == state.ecu_system_execution
            ):
                logger.info(f"Skipping {filename} as it has already been processed")
                has_been_processed = True
                break

        if has_been_processed:
            continue

        else:
            # we need to remove the system information from the app state
            # becasue we are going to reprocess the system information
            state.app_state.system_descriptions = []
            with driver.session() as session:
                session.execute_write(
                    save_app_state,
                    state.app_state,
                )

        # get the first page
        page = pdf_file[0]
        # extract the text from the page
        text = page.get_text()  # type: ignore

        if text is None:
            logger.info(f"The circuit diagram {filename} is in incorrect format")
            continue

        # load the circuit diagram family name
        current_system_config = None

        current_system_config = get_system_config_using_circuit_files(text)
        if current_system_config is None:
            current_system_config = get_system_config_by_filename(filename)

        if current_system_config is None:
            logger.info(f"Could not find the family name for {filename}")

        if not validate_system_details(state, current_system_config):
            continue

        # Run the graph until the first interruption
        for event in circuit_extractor.stream(
            {
                "diagram_content": text,
            },
            stream_mode="updates",
        ):
            if "components" in event:
                for component in event["components"]:
                    logger.info(f"Component Name:{component.name}")
                    logger.info(f"Component Description:{component.description}")

                    control_system_names_without_numbers = [
                        "".join(c for c in state.ecu_system_family if not c.isdigit()),
                        "".join(
                            c for c in state.ecu_system_execution if not c.isdigit()
                        ),
                    ]

                    # check if control unit and name options present in in the description
                    if "control unit" in component.description.lower() and any(
                        code in component.description
                        for code in control_system_names_without_numbers
                    ):
                        logger.info(
                            f"Skipping component {component.name} as it is a control unit for current system as the description is {component.description}"
                        )
                        continue

                    if (
                        component.description.lower()
                        == f"control unit, {state.ecu_system_family}".lower()
                    ):
                        logger.info(
                            f"Skipping component {component.name} as it is a control unit for {state.ecu_system_family}"
                        )
                        continue
                    # expand the components if they have a slash in the name
                    if "/" in component.name:
                        expanded_components = component.name.split("/")
                        for expanded_component in expanded_components:
                            add_component(
                                state,
                                expanded_component,
                                component.description,
                                file_id,
                            )
                    else:
                        add_component(
                            state, component.name, component.description, file_id
                        )

        # add the file to the app state
        state.app_state.circuit_diagrams.append(
            {
                "hash": file_id,
                "file_name": filename,
                "ecu_system": state.ecu_system_execution,
            }
        )
        with driver.session() as session:
            session.execute_write(
                save_app_state,
                state.app_state,
            )


def add_component(state, name, description, file_id):
    if name in state.all_base_config_circuits:
        logger.info(
            f"Component {name} exists in the base configuration, skipping processing"
        )
        return

    with driver.session() as session:
        session.execute_write(
            create_component,
            name,
            description,
            state.ecu_system_execution,
        )

        session.execute_write(
            link_component_to_circuit_diagram,
            name,
            file_id,
            state.ecu_system_execution,
        )


def validate_system_details(state, current_system_config):
    if current_system_config is None:
        logger.info(
            f"Could not determine system details for the specified file, skipping processing"
        )
        return False

    if current_system_config.family != state.ecu_system_family:
        logger.info(
            f"Skipping {current_system_config.family } as it does not belong to the {state.ecu_system_family} family"
        )
        return False

    return True


def validate_circuit_files(state: State):
    circuit_diagrams_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        circuit_diagrams_folder,
    )
    # validate the files in the specified paths
    # check if the circuit diagrams path exists and it's not empty
    if not os.path.exists(circuit_diagrams_path) or not os.listdir(
        circuit_diagrams_path
    ):
        logger.info(
            f"No circuit diagrams found in the specified path, looked for .pdf files in {circuit_diagrams_path}"
        )
        return False
    return True


def validate_base_config(state: State):
    if len(state.base_configs) == 0:
        logger.info(f"No base configuration files were loaded in this session.")
        return False
    return True
