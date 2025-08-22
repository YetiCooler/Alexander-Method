from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os

from pypdf import PdfReader
from state import State

from logger import (
    audit_logger as logger,
)
from graphs.system_information_extractor import graph as system_information_extractor
from graphs.system_information_extractor import graph as system_information_extractor

from config import (
    input_root_folder,
    max_parallel_workers,
    system_descriptions_folder,
)
from graphs.component_details_processor import graph as component_details_processor

from database.database import (
    add_component_fields,
    create_component_meta,
    driver,
    find_unlinked_components,
    get_all_components,
    get_component_meta,
    link_component_to_system,
    save_app_state,
)
from utils import (
    get_system_config_by_filename,
    get_system_config_using_system_description,
)


def process_system_information_page(
    state: State, pdf_file, page, filename, component_names, index
):
    """Function to process a single page independently"""
    logger.info(f"Processing page {index} of {len(pdf_file.pages)} in {filename}")
    state.update_queue.put(
        f"Processing page {index} of {len(pdf_file.pages)} in {filename}"
    )

    text = page.extract_text()

    # Extract components
    for component in component_names:
        # logger.info(
        #     f"Processing component {component} on page {index} of {len(pdf_file.pages)}"
        # )
        unverified_extraction = None

        for event in system_information_extractor.stream(
            {"component": component, "page_text": text},
            stream_mode="updates",
        ):
            if (
                "extract_component_details" in event
                and event["extract_component_details"][
                    "component_extraction_details"
                ].has_description
                == "yes"
            ):
                unverified_extraction = event["extract_component_details"][
                    "component_extraction_details"
                ]

            if "verify_component_details" in event:
                if (
                    event["verify_component_details"][
                        "component_extraction_verification"
                    ].verified
                    == "yes"
                ):

                    if unverified_extraction is None:
                        logger.info(
                            f"Could not find details on component {component} on page {index} of {len(pdf_file.pages)}"
                        )
                        continue

                    logger.info(
                        f"Found details on component {component} on page {index} of {len(pdf_file.pages)} with description: {unverified_extraction.description}"
                    )
                    with state.lock:  # Ensure thread-safe DB access
                        with driver.session() as session:
                            session.execute_write(
                                create_component_meta,
                                component,
                                unverified_extraction.description,
                                hash(pdf_file),
                                state.ecu_system_execution,
                            )
                    state.updated_components.append(component)
                    unverified_extraction = None


def process_system_information(state: State):
    logger.info("Processing System Information")

    # load the processable components
    load_processable_components(state)

    # check if there are components
    if len(state.processable_components) == 0:
        logger.info(
            "No components found in the database, skipping processing of system information"
        )
        return

    components = []
    with driver.session() as session:
        result = session.execute_read(get_all_components, state.ecu_system_execution)
        for record in result:
            components.append(dict(record))

    system_descriptions_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        system_descriptions_folder,
    )

    if not os.path.exists(system_descriptions_path):
        logger.info(
            f"Could not find the specified path for system descriptions: {system_descriptions_path}"
        )
        return

    files = [f for f in os.listdir(system_descriptions_path) if f.endswith(".pdf")]
    logger.info(f"Found {len(files)} system descriptions")

    if len(files) == 0:
        logger.info(
            f"No system descriptions found in the specified path, looked for .pdf files in {system_descriptions_path}"
        )

    # loop through the files in ./system_descriptions
    for filename in files:
        logger.info(f"Processing {filename}")
        state.update_queue.put(f"Processing {filename}")

        with open(f"{system_descriptions_path}/{filename}", "rb") as file:
            # create a hash of the file
            file_id = hashlib.md5(file.read()).hexdigest()

        # check if the file has already been processed
        has_been_processed = False

        unlinked_components = []

        with driver.session() as session:
            result = session.execute_read(
                find_unlinked_components, file_id, state.ecu_system_execution
            )
            for record in result:
                unlinked_components.append(record)

        if len(unlinked_components) == 0:
            logger.info(
                f"Skipping {filename} as all components have been linked to the base configuration"
            )
            continue

        # open the pdf file
        # pdf_file = pymupdf.open(f"{system_descriptions_path}/{filename}")
        pdf_file = PdfReader(f"{system_descriptions_path}/{filename}")

        current_system_config = None

        #  loop throght the pages to find the system informaiton
        for page in pdf_file.pages:
            # load the circuit diagram family name
            current_system_config = get_system_config_using_system_description(
                page.extract_text()
            )
            if current_system_config is not None:
                break

        if current_system_config is None:
            current_system_config = get_system_config_by_filename(filename)

        if current_system_config is None:
            logger.info(f"Could not find the family name for {filename}")

        if not validate_system_details(state, current_system_config):
            continue

        if len(pdf_file.pages) == 0:
            logger.info(f"Could not extract text from {filename}")
            continue
        # get the first page
        state.updated_components = []
        # Use ThreadPoolExecutor for parallel page processing
        with ThreadPoolExecutor(max_workers=max_parallel_workers) as executor:
            future_to_page = {
                executor.submit(
                    process_system_information_page,
                    state,
                    pdf_file,
                    page,
                    filename,
                    [name for name in unlinked_components],
                    index,
                ): page
                for index, page in enumerate(pdf_file.pages, start=1)
            }
            state.app_state.system_descriptions.append(
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

            for future in as_completed(future_to_page):
                result = future.result(timeout=30)

        # mark the components as linked to the system
        for component in unlinked_components:
            with driver.session() as session:
                session.execute_write(
                    link_component_to_system,
                    component,
                    file_id,
                    state.ecu_system_execution,
                )

        # process the updated components
        for component in state.updated_components:
            with driver.session() as session:
                result = session.execute_read(
                    get_component_meta, component, state.ecu_system_execution
                )
                for record in result:
                    logger.info(f"Component Name: {record['name']}")
                    unverified_extraction = None

                    target_component_details = None
                    for component_details in components:
                        if component_details["name"] == record["name"]:
                            target_component_details = component_details

                    if target_component_details is None:
                        logger.info(
                            f"Could not find details for component {record['name']}"
                        )
                        continue

                    # process the metadata
                    for event in component_details_processor.stream(
                        {
                            "component": record["name"],
                            "short_description": target_component_details[
                                "description"
                            ],
                            "extra_information": ",".join(record["meta_description"]),
                        },
                        stream_mode="updates",
                    ):
                        if "component_extraction_details" in event:
                            unverified_extraction = event
                        if "component_extraction_verification" in event:
                            if unverified_extraction is None:
                                logger.info(
                                    f"Could not find details on component {record['name']}"
                                )
                                continue
                            if (
                                event[
                                    "component_extraction_verification"
                                ].verified_description
                                == "yes"
                            ):
                                target_component_details["more_description"] = (
                                    unverified_extraction[
                                        "component_extraction_details"
                                    ].description
                                )

                            if (
                                event[
                                    "component_extraction_verification"
                                ].verified_purpose
                                == "yes"
                            ):
                                target_component_details["purpose"] = (
                                    unverified_extraction[
                                        "component_extraction_details"
                                    ].purpose
                                )

                            with driver.session() as session:
                                session.execute_write(
                                    add_component_fields,
                                    record["name"],
                                    target_component_details["more_description"],
                                    target_component_details["purpose"],
                                    state.ecu_system_execution,
                                )


def validate_system_details(state: State, current_system_config):
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


def load_processable_components(state: State):
    state.processable_components = {}  # Dictionary for uniqueness

    # Fetch components from the database
    with driver.session() as session:
        all_components = session.execute_read(
            get_all_components, state.ecu_system_execution
        )

    # Identify components not in base_config_circuits
    for component in all_components:
        if (
            component["name"] not in state.all_base_config_circuits
            and component["name"] not in state.all_other_server_circuits
        ):
            state.processable_components[component["name"]] = dict(component)
