from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import pandas as pd
from pypdf import PdfReader
from graphs.dtc_extractor import graph as dtc_extractor
from state import State

from logger import (
    audit_logger as logger,
)


from config import (
    input_root_folder,
    dtc_specifications_folder,
    max_parallel_workers,
)
from utils import get_system_config_by_filename, get_system_config_using_dtc

from database.database import (
    create_dtc,
    create_relationship_if_component_exists,
    driver,
    save_app_state,
)


def process_dtc_page(state: State, index, page, filename, pdf_file):
    """Extracts text and runs optimizer workflow on a single page."""
    print(f"Processing {filename} - Page {index} of {len(pdf_file.pages)}")
    state.update_queue.put(
        f"Processing {filename} - Page {index} of {len(pdf_file.pages)}"
    )

    # Extract text
    text = page.extract_text()

    # Run the workflow on the text
    unverified_extraction = None
    verified_extraction = None
    for event in dtc_extractor.stream(
        {"page_text": text, "attempt": 0}, stream_mode="updates"
    ):
        if "extract_error_codes" in event:
            unverified_extraction = event["extract_error_codes"]["dtc_specification"]
        if (
            "verify_error_extraction" in event
            and "error_extraction_evaluation" in event["verify_error_extraction"]
        ):
            if (
                event["verify_error_extraction"]["error_extraction_evaluation"].approved
                == "yes"
                and unverified_extraction
            ):
                print("we have a verified extraction")
                verified_extraction = unverified_extraction

    if verified_extraction:
        logger.info(f"Extracted DTC from page{index}: {verified_extraction.dict()}")
        return verified_extraction.dict()

    return None  # Return None if extraction failed


def process_dtc_specifications(state: State):
    logger.info("Processing DTC Specifications")
    errors_df = pd.DataFrame(
        columns=[
            "error_code",
            "components",
            "heading",
            "detection",
            "cause",
            "system_reaction",
            "symptom",
        ]
    )

    dtc_specifications_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        dtc_specifications_folder,
    )

    if not os.path.exists(dtc_specifications_path):
        logger.info(
            f"Could not find the specified path for DTC specifications: {dtc_specifications_path}"
        )
        return

    files = [f for f in os.listdir(dtc_specifications_path) if f.endswith(".pdf")]
    logger.info(f"Found {len(files)} DTC specifications")

    if len(files) == 0:
        logger.info(
            f"No DTC specifications found in the specified path, looked for .pdf files in {dtc_specifications_path}"
        )
    for filename in files:
        state.update_queue.put(f"Processing {filename}")
        with open(f"{dtc_specifications_path}/{filename}", "rb") as file:
            # create a hash of the file
            file_id = hashlib.md5(file.read()).hexdigest()

        # check if the file has already been processed
        has_been_processed = False

        for app_state_file in state.app_state.dtc_specifications:
            if (
                file_id == app_state_file["hash"]
                and app_state_file["ecu_system"] == state.ecu_system_execution
            ):
                logger.info(f"Skipping {filename} as it has already been processed")
                has_been_processed = True
                break

        if has_been_processed:
            continue

        logger.info(f"Processing {filename}")
        # open the pdf file

        # pdf_file = pymupdf.open(f"{dtc_specifications_path}/{filename}")
        pdf_file = PdfReader(f"{dtc_specifications_path}/{filename}")

        current_system_config = None

        #  loop throght the pages to find the system informaiton
        for page in pdf_file.pages:
            # load the circuit diagram family name
            current_system_config = get_system_config_using_dtc(page.extract_text())
            if current_system_config is not None:
                break

        if current_system_config is None:
            current_system_config = get_system_config_by_filename(filename)

        if current_system_config is None:
            logger.info(f"Could not find the family name for {filename}")

        if not validate_system_details(state, current_system_config):
            continue

        # # Use ThreadPoolExecutor to process 4 pages in parallel
        with ThreadPoolExecutor(max_workers=max_parallel_workers) as executor:
            future_to_page = {
                executor.submit(
                    process_dtc_page,
                    state,
                    index,
                    page,
                    filename,
                    pdf_file,
                ): page
                for index, page in enumerate(
                    pdf_file.pages, start=1
                )  # @TODO: Remove the slicing here
            }

            for future in as_completed(future_to_page):
                result = future.result(timeout=30)
                if result:
                    errors_df.loc[len(errors_df)] = result

        # save the dataframe to the specified path
        with driver.session() as session:
            for index, row in errors_df.iterrows():
                print(f"Processing DTC {row['error_code']}")
                session.execute_write(
                    create_dtc,
                    row["error_code"],
                    row["heading"],
                    row["components"],
                    row["detection"],
                    row["cause"],
                    row["system_reaction"],
                    row["symptom"],
                    state.ecu_system_execution,
                )
                # create relationships between the DTC and the components
                components = row["components"].split(",")
                for component in components:
                    logger.info(
                        f"Creating relationship between {row['error_code']} and {component.strip()}"
                    )
                    session.execute_write(
                        create_relationship_if_component_exists,
                        row["error_code"],
                        component,
                        "AFFECTS",
                        state.ecu_system_execution,
                    )

        # add the file to the app state
        state.app_state.dtc_specifications.append(
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

        # clear the dataframe
        errors_df = errors_df.iloc[0:0]


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
