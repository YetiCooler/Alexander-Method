import streamlit as st
import time
from streamlit_extras.stylable_container import stylable_container
from streamlit_extras.app_logo import add_logo
from PIL import Image
from config import (
    circuit_diagrams_path,
    dtc_specifications_path,
    system_descriptions_path,
    io_lists_path,
    base_config_path,
    base_config_output_path,
    dtc_relation_output_path,
    circuit_config_output_path,
    logs_output_path,
)
from logger import remove_log_handlers, setup_logger
from processor import Processor

im = Image.open("icon/icon.png")

st.set_page_config(
    page_title="",
    page_icon=im,
    layout="wide",
)
# Custom CSS for styling
st.markdown(
    """
<style>
    header {visibility: hidden;}
    .block-container {
        max-width: 1024px; /* Adjust this value as needed */
        padding-top: 2rem;
        padding-bottom: 2rem;
        margin: 0 auto;
    }
    :root {
        --primary-blue: #041E42;
        --primary-white: #FAFAFA;
        --primary-grey: #F8F8F8;
    }

    .stApp {
        background-color: var(--primary-white);
        color: var(--primary-blue);
    }
    .stFileUploader>section {
        background-color: var(--primary-grey);
        border-radius: 10px;
    }

    .stButton>button {
        background-color: var(--primary-blue);
        color: var(--primary-white);
        border-radius: 10px;
        padding: 10px;
        font-size: 20px;
    }

    .stButton>button:hover {
        color: var(--primary-white);
    }

    .stSelectbox label {
        color: var(--primary-blue);
        font-weight: bold;
    }

    h1, .stSubheader {
        color: var(--primary-blue);
        text-align: center;
    }

    .stTextArea textarea {
        background-color: var(--primary-grey);
        border-radius: 8px;
    }

    div.stSpinner, div.stMarkdown, div.stSuccess {
        text-align: center;
    }
    .stAlert {
        text-align: center;
    }

    .stSpinner>div{
        align-items: center;
        justify-content: center;
    }

    .stElementContainer>div{
        text-align: center;
    }
    .stElementContainer>div>div{
        width: 100%;
        }
</style>
""",
    unsafe_allow_html=True,
)

if "process_started" not in st.session_state:
    st.session_state.process_started = False

if "process_finished" not in st.session_state:
    st.session_state.process_finished = False

st.image("icon/icon.png", width=100)
st.title("Jarvis")

placeholder = st.empty()


codes = {
    "APS2": "APS",
    "EBS9": "BMS",
    "CMS1": "CMS",
    "DIS3": "DIS",
    "FLC3": "FLC",
    "TPM2": "TPM",
    "COO11": "COO",
    "PDS2": "DCS",
    "DCS2": "DCS",
    "DD": "DIM",
    "DDU": "DIM",
    "CID1": "DIM",
    "C400": "RTC",
    "CUV3": "VIS",
    "EPB1": "PBC",
    "ECU1": "ECU",
    "CCU1": "CCM",
}


def clear_previous_files():
    import os

    # input files
    for file in os.listdir(base_config_path):
        print(f"deleting {base_config_path}/{file}")
        os.remove(f"{base_config_path}/{file}")

    for file in os.listdir(dtc_relation_output_path):
        print(f"deleting {dtc_relation_output_path}/{file}")
        os.remove(f"{dtc_relation_output_path}/{file}")

    for file in os.listdir(circuit_config_output_path):
        print(f"deleting {circuit_config_output_path}/{file}")
        os.remove(f"{circuit_config_output_path}/{file}")

    for file in os.listdir(logs_output_path):
        print(f"deleting {logs_output_path}/{file}")
        os.remove(f"{logs_output_path}/{file}")

    # output files
    for file in os.listdir(circuit_diagrams_path):
        print(f"deleting {circuit_diagrams_path}/{file}")
        os.remove(f"{circuit_diagrams_path}/{file}")

    for file in os.listdir(dtc_specifications_path):
        print(f"deleting {dtc_specifications_path}/{file}")
        os.remove(f"{dtc_specifications_path}/{file}")

    for file in os.listdir(system_descriptions_path):
        print(f"deleting {system_descriptions_path}/{file}")
        os.remove(f"{system_descriptions_path}/{file}")

    for file in os.listdir(base_config_output_path):
        print(f"deleting {base_config_output_path}/{file}")
        os.remove(f"{base_config_output_path}/{file}")

    for file in os.listdir(io_lists_path):
        print(f"deleting {io_lists_path}/{file}")
        os.remove(f"{io_lists_path}/{file}")


if not st.session_state.process_started:

    with placeholder.container():

        file_categories = {
            "base_configs": {
                "label": "Base Config(s)",
                "type": "xml",
                "path": base_config_path,
            },
            "circuit_diagrams": {
                "label": "Circuit Diagram(s)",
                "type": "pdf",
                "path": circuit_diagrams_path,
            },
            "io_lists": {"label": "IO List(s)", "type": "xml", "path": io_lists_path},
            "system_descriptions": {
                "label": "System Description(s)",
                "type": "pdf",
                "path": system_descriptions_path,
            },
            "dtc_specifications": {
                "label": "DTC Specification(s)",
                "type": "pdf",
                "path": dtc_specifications_path,
            },
        }

        uploaded_files = {}

        with stylable_container(
            key="green_button",
            css_styles="""
                button {
                    background-color: var(--primary-blue);
                    color: white;
                }
                """,
        ):
            for category in file_categories.keys():
                files = st.file_uploader(
                    f"{file_categories[category]['label']}",
                    accept_multiple_files=True,
                    type=[file_categories[category]["type"]],
                    key=category,
                )
                uploaded_files[category] = files

        st.session_state.system_execution = st.selectbox(
            "Select System Execution",
            [
                "APS2",
                "EBS9",
                "CMS1",
                "DIS3",
                "FLC3",
                "TPM2",
                "COO11",
                "PDS2",
                "DCS2",
                "DD",
                "DDU",
                "CID1",
                "C400",
                "CUV3",
                "EPB1",
                "ECU1",
                "CCU1",
            ],
        )

        with stylable_container(
            key="green_button",
            css_styles="""
                button {
                    background-color: var(--primary-blue);
                    color: white;
                }
                """,
        ):
            if st.button("Start Process", use_container_width=True):
                print(uploaded_files)

                clear_previous_files()

                # loop through the uploaded files
                for key, value in uploaded_files.items():
                    if value:
                        for file in value:
                            # get the base path based on the key
                            base_path = file_categories[key]["path"]
                            # save the file to the base path
                            with open(f"{base_path}/{file.name}", "wb") as f:
                                f.write(file.getbuffer())

                st.session_state.process_started = True
                placeholder.empty()
                st.rerun()


else:
    if st.session_state.process_started and not st.session_state.process_finished:
        with st.spinner("Processing your files... Please wait."):
            setup_logger()
            processor = Processor(
                ecu_system_execution=st.session_state.system_execution,
                ecu_system_family=codes[st.session_state.system_execution],
            )
            processor.process()
            remove_log_handlers()
            # Simulate processing time
            st.session_state.process_finished = True
    if st.session_state.process_finished:
        st.success("Files processed successfully!")

        with stylable_container(
            key="green_button",
            css_styles="""
                    button {
                        background-color: var(--primary-blue);
                        color: white;
                    }
                    """,
        ):
            # Provide the download button
            with open("data/output.zip", "rb") as file:
                st.download_button(
                    label="Download Output",
                    data=file,
                    file_name="output.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
