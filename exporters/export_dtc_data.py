import os
from outflow.exporter import DataExporter
from state import State

from config import (
    output_root_folder,
)
from database.database import (
    driver,
    get_dtc_with_components,
)


def export_dtc_data(state: State):

    data_exporter = DataExporter(
        os.path.join(
            state.inference_base_folder,
            output_root_folder,
        )
    )

    meta_conf = {
        "ecu_system_family": state.ecu_system_family,
        "ecu_system_execution": state.ecu_system_execution,
        "server_can": state.base_configs[0].server_can,
    }

    with driver.session() as session:
        dtc_with_components = session.execute_read(
            get_dtc_with_components,
            state.ecu_system_execution,
            state.all_base_config_circuits + state.all_other_server_circuits,
        )
        for record in dtc_with_components:
            data_exporter.export_dtc_relation(
                record["dtc_code"], dict(record), meta_conf
            )
