class AppState:
    def __init__(self, circuit_diagrams=None, system_descriptions=None, dtc_specifications=None, io_list_files=None):
        """
        Each field contains a list of dictionaries:
        - { "hash": "computed_hash", "file_name": "original_file_name" }
        """
        self.circuit_diagrams = circuit_diagrams or []
        self.system_descriptions = system_descriptions or []
        self.dtc_specifications = dtc_specifications or []
        self.io_list_files = io_list_files or []

    def __repr__(self):
        return (f"AppState(circuit_diagrams={self.circuit_diagrams}, "
                f"system_descriptions={self.system_descriptions}, "
                f"dtc_specifications={self.dtc_specifications}, "
                f"io_list_files={self.io_list_files})")