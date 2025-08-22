import os
from queue import Queue
import threading
import time
from typing import Literal, cast

from database.models import Inference
from exporters.export_circuit_data import export_circuit_data
from exporters.export_dtc_data import export_dtc_data
from outflow.exporter import DataExporter
import shutil


from inflow.base_config import BaseConfig  # imports the pymupdf library
from database.database import (
    driver,
    get_all_components,
    get_app_state,
    get_dtc_with_components,
)  # imports the driver from the database module

# loop through the files in ./dtc_specifications
import os
from logger import (
    system_logger,
    audit_logger as logger,
    get_audit_log_messages as get_log_messages,
    remove_audit_log_handlers as remove_log_handlers,
    setup_loggers,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from processors.circuit_diagram_processor import process_circuit_diagrams
from processors.diagnostic_processor import process_diagnostic_files
from processors.dtc_specifications_processor import process_dtc_specifications
from processors.function_parameters.function_group_processor import (
    ingest_function_groups,
)
from processors.function_parameters.function_parameter_processor import (
    process_function_parameters,
)
from processors.function_parameters.function_tree_processor import export_function_tree
from processors.io_mapping_processor import process_io_mapping
from processors.system_information_processor import process_system_information
from state import State

from utils import (
    get_system_config_using_server_can,
)
from config import (
    data_root_folder,
    input_root_folder,
    base_configs_folder,
    circuit_diagrams_folder,
    output_root_folder,
    logs_output_folder,
    root_archive_folder,
    input_archive_name,
    output_archive_name,
    system_config,
)
from state import State


class Processor:

    # Lock for thread-safe database writes
    all_base_config_circuits: list[str] = []
    inference: Inference

    state: State
    graph: CompiledStateGraph
    server_can: str | None = None

    def __init__(
        self,
        ecu_system_family: str,
        ecu_system_execution: str,
        server_can: str | None,
        update_queue: Queue,
        inference: Inference,
    ):
        setup_loggers(
            os.path.join(
                "/var/log/vme",
                f"{inference.ecu}_{inference.version}-{time.time()}.log",  # with timestamp
            )
        )
        system_logger.info("Something private to system log")

        self.inference = inference
        self.compile_graph()

        with driver.session() as session:
            app_state = session.execute_read(get_app_state)
            self.state = State(
                inference_type=cast(Literal["IO", "FP"], str(inference.type)),
                inference=inference,
                ecu_system_execution=ecu_system_execution,
                ecu_system_family=ecu_system_family,
                inference_base_folder=os.path.join(
                    data_root_folder,
                    str(inference.ecu),
                    str(inference.version),
                ),
                update_queue=update_queue,
                app_state=app_state,
                all_base_config_circuits=[],
                all_self_server_circuits=[],
                all_other_server_circuits=[],
            )

        self.server_can = server_can

        self.load_base_configs()

        if self.server_can is None:
            logger.info(
                "Could not find the server can for the specified ECU system execution we cannot process the data further"
            )
            raise ValueError(
                "Could not find the server can for the specified ECU system execution we cannot process the data further"
            )
            return

        self.state.server_can = self.server_can

    def load_base_configs(self):
        self.state.base_configs = []
        base_config_path = os.path.join(
            self.state.inference_base_folder,
            input_root_folder,
            base_configs_folder,
        )
        if not os.path.exists(base_config_path):
            logger.info(
                f"Could not find the specified path for base configurations: {base_config_path}"
            )
            return
        for filename in os.listdir(base_config_path):
            with open(f"{base_config_path}/{filename}", "r") as file:
                base_config = BaseConfig(f"{base_config_path}/{filename}")
                current_server_config = get_system_config_using_server_can(
                    base_config.server_can
                )

                if current_server_config is not None:
                    if current_server_config.family != self.state.ecu_system_family:
                        logger.info(
                            f"Skipping {filename} as it does not belong to the {self.state.ecu_system_family} family"
                        )
                        continue

                    if (
                        current_server_config.execution
                        != self.state.ecu_system_execution
                    ):
                        logger.info(
                            f"Skipping {filename} as it does not belong to the {self.state.ecu_system_execution} system"
                        )
                        continue

                self.state.base_configs.append(base_config)

        self.all_base_config_circuits = [
            circuit
            for base_config in self.state.base_configs
            for circuit in base_config.base_config_circuits
        ]

        self.state.all_base_config_circuits = self.all_base_config_circuits

        self.state.all_self_server_circuits = [
            circuit
            for base_config in self.state.base_configs
            for circuit in base_config.hero_circuits
        ]

        self.state.all_other_server_circuits = [
            circuit
            for base_config in self.state.base_configs
            for circuit in base_config.other_server_circuits
            if circuit not in self.state.all_self_server_circuits
        ]

        # we try to get the server can from the base configurations
        # this is temprorary until we get all the server cans for all systems
        if len(self.state.base_configs) > 0:
            self.server_can = str(self.state.base_configs[0].server_can)
        else:
            ecu_config = next(
                (
                    item
                    for item in system_config
                    if item.execution == self.state.ecu_system_execution
                ),
                None,
            )

            if ecu_config is None:
                logger.info(
                    f"Could not find the specified ECU system execution: {self.state.ecu_system_execution}"
                )
                return
            if ecu_config.server_can is not None:
                self.server_can = ecu_config.server_can
            else:
                logger.info(
                    f"Could not find the server can for {self.state.ecu_system_execution}"
                )

        logger.info(f"Loaded {len(self.state.base_configs)} base configurations")

    def validate_system_details(self, current_system_config):
        if current_system_config is None:
            logger.info(
                f"Could not determine system details for the specified file, skipping processing"
            )
            return False

        if current_system_config.family != self.state.ecu_system_family:
            logger.info(
                f"Skipping {current_system_config.family } as it does not belong to the {self.state.ecu_system_family} family"
            )
            return False

        return True

    def compile_graph(self):
        def route_inference_process(state: State):
            if state.inference_type == "IO":
                return "io_processing"
            elif state.inference_type == "FP":
                return "function_parameter_processing"

        def export_artifacts(state: State):
            logger.info("Processing complete")

            logs = get_log_messages()
            remove_log_handlers()

            logs_output_path = os.path.join(
                self.state.inference_base_folder, output_root_folder, logs_output_folder
            )

            # create the logs output folder
            if not os.path.exists(logs_output_path):
                os.makedirs(logs_output_path)
            # overwrite the logs to the specified path
            with open(f"{logs_output_path}/process.log", "w") as file:
                file.write(logs)

            # zip the output and input folders
            shutil.make_archive(
                os.path.join(
                    self.state.inference_base_folder,
                    root_archive_folder,
                    input_archive_name,
                ),
                "zip",
                os.path.join(self.state.inference_base_folder, input_root_folder),
            )

            shutil.make_archive(
                os.path.join(
                    self.state.inference_base_folder,
                    root_archive_folder,
                    output_archive_name,
                ),
                "zip",
                os.path.join(self.state.inference_base_folder, output_root_folder),
            )

        # Build the graph
        builder = StateGraph(State)

    # nodes of the io_processing
        builder.add_node("process_circuit_diagrams", process_circuit_diagrams)
        builder.add_node("process_io_mapping", process_io_mapping)
        builder.add_node("process_dtc_specifications", process_dtc_specifications)
        builder.add_node("process_system_information", process_system_information)
        builder.add_node("export_circuit_data", export_circuit_data)
        builder.add_node("export_dtc_data", export_dtc_data)
        builder.add_node("process_diagnostic_files", process_diagnostic_files)
        builder.add_node("export_artifacts", export_artifacts)

        # nodes of the function_parameter_processing
        builder.add_node("ingest_function_groups", ingest_function_groups)
        builder.add_node("process_function_parameters", process_function_parameters)
        builder.add_node("export_function_tree", export_function_tree)
        
        builder.add_conditional_edges(
            START,
            route_inference_process,
            {
                "io_processing": "process_circuit_diagrams",
                "function_parameter_processing": "ingest_function_groups",
            },
        )
        
        # IO processing path
        builder.add_edge("process_circuit_diagrams", "process_system_information")
        builder.add_edge("process_system_information", "process_io_mapping")
        builder.add_edge("process_io_mapping", "process_diagnostic_files")  # Diagnostic processing added here
        builder.add_edge("process_diagnostic_files", "export_circuit_data")
        builder.add_edge("export_circuit_data", "process_dtc_specifications")
        builder.add_edge("process_dtc_specifications", "export_dtc_data")
        builder.add_edge("export_dtc_data", "export_artifacts")

        # Function parameter processing path
        builder.add_edge("ingest_function_groups", "process_function_parameters")
        builder.add_edge("process_function_parameters", "export_function_tree")
        builder.add_edge("export_function_tree", "export_artifacts")

        # Final export artifacts
        builder.add_edge("export_artifacts", END)
        self.graph = builder.compile()

    def process(self):
        logger.info("Starting processing")
        self.graph.invoke(self.state)
