from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from state import State

from logger import (
    system_logger,
    audit_logger as logger,
)

from database.database import (
    create_io,
    create_io_mapping_with_component,
    driver,
    mark_component_as_not_exported,
    save_app_state,
    update_io_file_io_mapping,
)


from config import (
    input_root_folder,
    max_parallel_workers,
    io_lists_folder,
)
from xmltodict import parse

from graphs.io_processor import graph as io_processor


def process_io(state: State, index, io, total_io_count):
    """Process a single IO item independently"""
    print(f"Processing IO {index} of {total_io_count}")
    system_logger.info(f"Processing IO {index} of {total_io_count}")
    state.update_queue.put(f"Processing IO {index} of {total_io_count}")

    io_description = ""

    io_name_presentation = ""
    io_name = io["Name"]
    if "NamePresentation" in io and "#text" in io["NamePresentation"]:
        io_name_presentation = io["NamePresentation"]["#text"]

    if "Description" in io["IOService"] and "#text" in io["IOService"]["Description"]:
        io_description = io["IOService"]["Description"]["#text"]

    # add the io in the database
    with driver.session() as session:
        session.execute_write(
            create_io,
            io_name,
            io_description,
            io_name_presentation,
            state.ecu_system_execution,
        )
    # Run IO processing workflow
    for event in io_processor.stream(
        {
            "io_item": io,
            "ecu_system": state.ecu_system_execution,
            "excluded_components": state.all_base_config_circuits
            + state.all_other_server_circuits,
        },
        stream_mode="updates",
    ):
        if "process_io_item" in event and event["process_io_item"]["matched"] == "yes":
            component_name = event["process_io_item"]["component"]
            logger.info(
                "IO {} matched with component {}".format(io["Name"], component_name)
            )
            system_logger.info(
                "IO {} matched with component {}".format(io["Name"], component_name)
            )

            # Ensure thread-safe updates
            with state.lock:  # Ensure thread-safe updates
                if component_name in state.processable_components:
                    state.processable_components[component_name].update(
                        {
                            "io": state.processable_components[component_name].get(
                                "io", []
                            )
                            + [io]
                        }
                    )

            with driver.session() as session:
                # Create a relationship between the IO and the component
                session.execute_write(
                    create_io_mapping_with_component,
                    io["Name"],
                    component_name,
                    state.ecu_system_execution,
                )
                session.execute_write(
                    mark_component_as_not_exported,
                    component_name,
                    state.ecu_system_execution,
                )  # Mark component as not exported so we can re-export


def process_io_mapping(state: State):
    """Parallelized IO mapping processing"""

    io_mapping_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        io_lists_folder,
    )

    if not os.path.exists(io_mapping_path):
        logger.info(
            f"Could not find the specified path for IO mapping: {io_mapping_path}"
        )
        return

    # loop through the io mapping files and check if we have processed them before
    files = [f for f in os.listdir(io_mapping_path) if f.endswith(".xml")]
    logger.info(f"Found {len(files)} IO mapping files")

    if len(files) == 0:
        logger.info(
            f"No IO mapping files found in the specified path, looked for .xml files in {io_mapping_path}"
        )
        return

    # load the io mapping files
    for filename in files:
        file_id = None
        file_content = None
        # calculate the hash of the file
        with open(f"{io_mapping_path}/{filename}", "rb") as file:
            file_content = file.read()
            file_id = hashlib.md5(file_content).hexdigest()

        # check if the file has already been processed
        has_been_processed = False

        for app_state_file in state.app_state.io_list_files:
            if (
                file_id == app_state_file["hash"]
                and app_state_file["ecu_system"] == state.ecu_system_execution
            ):
                has_been_processed = True
                break

        if has_been_processed:
            logger.info(f"Skipping {filename} as it has already been processed")
            continue

        state.update_queue.put(f"Processing {filename}")
        logger.info(f"Processing {filename}")

        # parse the xml file content to a dictionary
        pt_io_list = parse(file_content)
        io_list = []

        # validate the family name
        if ("EcuSystemFamily" in pt_io_list) and (
            pt_io_list["EcuSystemFamily"]["#text"] != state.ecu_system_family
        ):
            logger.info(
                f"Skipping {filename} as it does not belong to the {state.ecu_system_family} family"
            )
            continue

        # validate the ecu system
        if ("EcuSystemExecution" in pt_io_list) and (
            pt_io_list["EcuSystemExecution"]["#text"] != state.ecu_system_execution
        ):
            logger.info(
                f"Skipping {filename} as it does not belong to the {state.ecu_system_execution} system"
            )
            continue

        if (
            "IO" in pt_io_list["PtIOList"]
            and type(pt_io_list["PtIOList"]["IO"]) == list
        ):
            for io in pt_io_list["PtIOList"]["IO"]:
                io_list.append(io)

        elif "IO" in pt_io_list["PtIOList"]:
            io_list.append(pt_io_list["PtIOList"]["IO"])

        logger.info(f"Processing IO Mapping - total IOs: {len(io_list)}")
        state.update_queue.put(f"Processing IO Mapping - total IOs: {len(io_list)}")
        # **Parallel Execution** of semantic IO matching
        with ThreadPoolExecutor(max_workers=max_parallel_workers) as executor:
            for batch_start in range(0, len(io_list), 50):
                batch = io_list[batch_start : batch_start + 50]
                futures = [
                    executor.submit(process_io, state, idx + 1, io, len(io_list))
                    for idx, io in enumerate(batch, start=batch_start)
                ]
                for future in futures:
                    future.result(timeout=30)  # Force sequential processing per batch

        # add the file to the app state
        state.app_state.io_list_files.append(
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

            # add all io relation to the new file
            for io in io_list:
                session.execute_write(
                    update_io_file_io_mapping,
                    io["Name"],
                    file_id,
                    state.ecu_system_execution,
                )

        logger.info("Completed IO Mapping.")
