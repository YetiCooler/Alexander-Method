import os
from outflow.exporter import DataExporter
from state import State

from database.database import (
    driver,
    get_all_components,
)

from config import (
    output_root_folder,
)


def export_circuit_data(state: State):

    data_exporter = DataExporter(
        os.path.join(
            state.inference_base_folder,
            output_root_folder,
        )
    )
    meta_conf = {
        "ecu_system_family": state.ecu_system_family,
        "ecu_system_execution": state.ecu_system_execution,
        "server_can": state.server_can,  # TODO: clarify this one
    }

    # load processable components
    load_processable_components(state)

    for component in state.processable_components:
        data_exporter.export_component_config(
            component,
            state.processable_components[component],
            meta_conf,
            inference=state.inference,
        )

    for base_config in state.base_configs:
        data_exporter.export_base_config(base_config, state.processable_components)


def load_processable_components(state: State):
    state.processable_components = {}  # Dictionary for uniqueness

    # Fetch components from the database
    with driver.session() as session:
        all_components = session.execute_read(
            get_all_components, state.ecu_system_execution
        )

    # Identify components not in base_config_circuits
    for component in all_components:
        if component["name"] not in state.all_base_config_circuits:
            state.processable_components[component["name"]] = dict(component)
