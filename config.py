import os
import dotenv
from dataclasses import dataclass

dotenv.load_dotenv()

export_template_path = os.environ.get("EXPORT_TEMPLATE_PATH", "./outflow/templates")

qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
qdrant_port = os.environ.get("QDRANT_PORT", "6333")

neo4j_connection = os.environ.get("NEO4J_CONNECTION", "bolt://localhost:7687")
neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
neo4j_password = os.environ.get("NEO4J_PASSWORD", "password")
webhook_secret = os.environ.get("WEBHOOK_SECRET", "secret")

data_root_folder = os.environ.get("DATA_ROOT_FOLDER", "\\var\\tmp\\vme")
# new environment variables
input_root_folder = os.environ.get("INPUT_ROOT_FOLDER", "input")
circuit_diagrams_folder = os.environ.get("CIRCUIT_DIAGRAMS_FOLDER", "circuit_diagrams")
system_descriptions_folder = os.environ.get(
    "SYSTEM_DESCRIPTIONS_FOLDER", "system_descriptions"
)
io_lists_folder = os.environ.get("IO_LISTS_FOLDER", "io_lists")
dtc_specifications_folder = os.environ.get(
    "DTC_SPECIFICATIONS_FOLDER", "dtc_specifications"
)
diagnostic_files_folder = os.environ.get(
    "PROCESSED_IO_FOLDER", "diagnostic_files"
)
base_configs_folder = os.environ.get("BASE_CONFIGS_FOLDER", "base_configs")


output_root_folder = os.environ.get("OUTPUT_ROOT_FOLDER", "output")
base_configs_output_folder = os.environ.get(
    "BASE_CONFIGS_OUTPUT_FOLDER", "base_configs"
)
circuit_configs_output_folder = os.environ.get(
    "CIRCUIT_CONFIGS_OUTPUT_FOLDER", "circuit_configs"
)
dtc_relations_output_folder = os.environ.get(
    "DTC_RELATIONS_OUTPUT_FOLDER", "dtc_relations"
)
pt_components_output_folder = os.environ.get(
    "PT_COMPONENTS_OUTPUT_FOLDER", "pt_components"
)
function_parameters_output_folder = os.environ.get(
    "FUNCTION_PARAMETER_OUTPUT_FOLDER", "function_parameters"
)
diagnostics_output_folder = os.environ.get(
    "PROCESSED_IO_OUTPUT_FOLDER", "processed_ios"
)
logs_output_folder = os.environ.get("LOGS_OUTPUT_FOLDER", "logs")

root_archive_folder = os.environ.get("ROOT_ARCHIVE_FOLDER", "archive")
output_archive_name = os.environ.get("OUTPUT_ARCHIVE_NAME", "output")
input_archive_name = os.environ.get("INPUT_ARCHIVE_NAME", "input")

# llm specific environment variables
openai_api_key = os.environ.get("OPENAI_API_KEY", "EMPTY")
openai_api_base = os.environ.get("OPENAI_API_BASE", "http://localhost:9000/v1")
print(f"openai_api_key: {openai_api_key}")
print(f"openai_api_base: {openai_api_base}")
max_parallel_workers = int(os.environ.get("MAX_PARALLEL_WORKERS", 8))

# print all the environment variables in the config file for reference
print(f"export_template_path: {export_template_path}")
print(f"qdrant_host: {qdrant_host}")
print(f"qdrant_port: {qdrant_port}")
print(f"neo4j_connection: {neo4j_connection}")
print(f"neo4j_user: {neo4j_user}")
print(f"neo4j_password: ********")


# system specific configuration


# Define the data class
@dataclass
class SystemConfig:
    execution: str
    family: str
    server_can: str | None


system_config = [
    SystemConfig(
        "APS2",
        "APS",
        "30",
    ),
    SystemConfig(
        "EBS9",
        "BMS",
        "0B",
    ),
    SystemConfig(
        "CMS1",
        "CMS",
        "47",
    ),
    SystemConfig(
        "DIS3",
        "DIS",
        "4A",
    ),
    SystemConfig(
        "FLC3",
        "FLC",
        "EB",
    ),
    SystemConfig(
        "TPM2",
        "TPM",
        "33",
    ),
    SystemConfig(
        "COO11",
        "COO",
        "27",
    ),
    SystemConfig("PDS2", "DCSXA", "ED"),
    SystemConfig("DCS2", "DCS", "EC"),
    SystemConfig("DD", "DIM", None),
    SystemConfig("DDU", "DIM", None),
    SystemConfig("CID1", "DIM", None),
    SystemConfig("C400", "RTC", "4A"),
    SystemConfig(
        "CUV3",
        "VIS",
        "1E",
    ),
    SystemConfig("EPB1", "PBC", "50"),
    SystemConfig("ECU1", "ECU", None),
    SystemConfig(
        "CCU1",
        "CCM",
        "19",
    ),
    SystemConfig("C008", "COO", None),
    SystemConfig("DDU1", "DDU", "17"),
    SystemConfig("DD1", "DD", "3B"),
    SystemConfig("EMS10", "EMC", "00"),
    SystemConfig("EBS9", "BMS", "0B"),
    SystemConfig("CID2", "CID", "54"),
    SystemConfig("ECAKB4", "ECA", "FD"),
    SystemConfig("DIS3", "DIS", "2A"),
    SystemConfig("TMS3", "TMS", "DC"),
]
