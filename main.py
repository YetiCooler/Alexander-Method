import hashlib
import hmac
import json
import os
import queue
import shutil
import threading
import time
from typing import List, Optional, Tuple, Union
import traceback

from fastapi import BackgroundTasks, FastAPI, HTTPException, Path, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests
from database.models import Inference
from models.input.physical_quantity import PhysicalQuantity
from processor import Processor
from config import (
    webhook_secret,
    data_root_folder,
    input_root_folder,
    circuit_diagrams_folder,
    system_descriptions_folder,
    io_lists_folder,
    dtc_specifications_folder,
    diagnostic_files_folder,
    base_configs_folder,
    root_archive_folder,
    system_config,
)
from database.database import (
    driver,
    save_ecu_family,
    store_physical_quantity
)
from processors.physical_quantity_writer import load_physical_quantities_from_folder
# from processors.diagnostic_processor import build_ptiolist_from_files
app = FastAPI()


class Payload(BaseModel):
    ecu: str


class InferenceCreate(BaseModel):
    """Input data for creating a new inference."""

    webhook_url: str


class InferenceModel(BaseModel):
    """data for an inference."""

    ecu: str
    version: int
    status: str
    messages: List[str] = []


def send_signed_webhook(
    url: str,
    data: dict,
    files: Optional[List[Tuple[str, Tuple[str, bytes, str]]]] = None,
):
    payload_bytes = json.dumps(data).encode()
    signature = hmac.new(
        webhook_secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()

    if files:
        multipart_data = []

        # Add JSON fields as form fields
        for key, value in data.items():
            multipart_data.append((key, (None, str(value), "text/plain")))

        # Add files - all under "files"
        for field_name, file_tuple in files:
            multipart_data.append(
                ("files", file_tuple)
            )  # Key must match FastAPI expectation

        headers = {
            "X-Signature": signature,
        }

        print(
            f"Sending webhook (multipart) to {url} with data {data} and signature {signature}"
        )
        return requests.post(url, headers=headers, files=multipart_data)

    else:
        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
        }
        return requests.post(url, headers=headers, data=payload_bytes)


def event_generator(queue: queue.Queue, inference: Inference):
    """Generator that yields events from the queue in SSE format."""
    while True:
        data = queue.get()  # Wait for an update from the queue
        if data is not None:
            inference.messages.append(data)  # type: ignore
            inference.save()  # Call directly, no need for await
        if data is None:
            break


def producer(processor: Processor, queue: queue.Queue):
    """Background producer that sends updates to the queue."""
    try:
        processor.inference.status = "R"
        processor.inference.save()
        processor.process()
        processor.inference.status = "C"
        processor.inference.save()
    except Exception as e:
        processor.inference.status = "F"
        processor.inference.save()
        queue.put(f"Error: There was an error processing the inference")
        print(traceback.format_exc())
        print(e)
    finally:
        queue.put(None)  # Signal the end of the stream


def perform_inference(inference: Inference):
    """Perform inference and update the status."""
    update_queue = queue.Queue()

    # Get the system configuration for the ECU
    # return [item for item in system_config if item.id == value]
    ecu_config = next(
        (item for item in system_config if item.execution == inference.ecu), None
    )
    if not ecu_config:
        raise HTTPException(status_code=400, detail="ECU not found")

    processor = Processor(
        ecu_system_execution=str(inference.ecu),
        ecu_system_family=ecu_config.family,
        server_can=ecu_config.server_can,
        update_queue=update_queue,
        inference=inference,
    )

    # Start producer in background thread
    producer_thread = threading.Thread(target=producer, args=(processor, update_queue))
    producer_thread.start()

    # Process events in the main thread
    event_generator(update_queue, inference)

    # read the input and output zip files and send them to the webhook
    files = []
    for root, _, filenames in os.walk(
        os.path.join(
            data_root_folder,
            str(inference.ecu),
            str(inference.version),
            root_archive_folder,
        )
    ):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            files.append(
                (
                    # use output form output.zip and input from input.zip
                    filename,
                    (filename, open(file_path, "rb"), "application/octet-stream"),
                )
            )

    response = send_signed_webhook(
        str(inference.webhook_url),
        data={
            "ecu": inference.ecu,
            "version": inference.version,
            "status": inference.STATUSES[str(inference.status)],
        },
        files=files,
    )

    print(response.status_code, response.text)
    # Ensure producer thread has finished
    producer_thread.join()


@app.post("/{ecu}/inferences/", response_model=InferenceModel)
def create_inference(
    ecu: str, inference_data: InferenceCreate, background_tasks: BackgroundTasks
):
    """Create a new inference and start processing."""
    # get all the inferences for the given ECU so we can assign a numerical version
    all_inferences = Inference.nodes.filter(ecu=ecu)

    # get the latest version number
    version = 1
    if all_inferences:
        version = max([inference.version for inference in all_inferences]) + 1

    inference = Inference(
        ecu=ecu,
        version=version,
        status="P",
        webhook_url=inference_data.webhook_url,
        messages=[],
    ).save()

    # # start the inference in the background
    # background_tasks.add_task(perform_inference, inference)

    # return the inference object
    return {
        "ecu": inference.ecu,
        "version": inference.version,
        "status": inference.STATUSES[inference.status],
    }


@app.post("/{ecu}/inferences/{version}/files")
def upload_inference_files(
    ecu: str,
    version: int,
    system_descriptions: Optional[List[UploadFile]] = File(
        None, description="System description files"
    ),
    configuration_files: Optional[List[UploadFile]] = File(
        None, description="Configuration files"
    ),
    dtc_specifications: Optional[List[UploadFile]] = File(
        None, description="DTC specification files"
    ),
    circuit_diagrams: Optional[List[UploadFile]] = File(
        None, description="Circuit diagram files"
    ),
    function_parameters: Optional[List[UploadFile]] = File(
        None, description="Function parameter files"
    ),
    ios: Optional[List[UploadFile]] = File(None, description="IOS files"),
    diagnostic_files: Optional[List[UploadFile]] = File(
        None, description="Diagnostic files"
    ),
):
    """Upload inference files."""
    inference = Inference.nodes.get_or_none(ecu=ecu, version=version)
    if not inference:
        return {"message": "Inference not found"}

    try:
        # save the files to the data folder with the ecu and version
        data_folder = os.path.join(
            data_root_folder, ecu, str(version), input_root_folder
        )
        # delete the folder if it exists
        base_inference_folder = os.path.join(data_root_folder, ecu, str(version))
        if os.path.exists(base_inference_folder):
            shutil.rmtree(base_inference_folder)

        os.makedirs(data_folder, exist_ok=True)

        def save_uploaded(files: Optional[List[UploadFile]], subdir: str):
            if not files:
                return
            for f in files:
                if f.filename:
                    dst = os.path.join(data_folder, subdir, f.filename)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(dst, "wb") as fh:
                        fh.write(f.file.read())
        save_uploaded(system_descriptions, system_descriptions_folder)
        save_uploaded(configuration_files, base_configs_folder)
        save_uploaded(dtc_specifications, dtc_specifications_folder)
        save_uploaded(circuit_diagrams, circuit_diagrams_folder)
        save_uploaded(ios, io_lists_folder)
        save_uploaded(diagnostic_files, diagnostic_files_folder)                   
     
        if function_parameters:
            for file in function_parameters:
                if file.filename is not None:
                    file_path = os.path.join(data_folder, file.filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "wb") as f:
                        f.write(file.file.read())

                        # uncompress the file if it is a zip file
                    if file.filename.endswith(".zip"):
                        shutil.unpack_archive(file_path, data_folder)
                        os.remove(file_path)
                    else:
                        # remove the file if it is not a zip file
                        os.remove(file_path)

            inference.type = "FP"
            inference.save()

        else:
            inference.type = "IO"
            inference.save()
    except Exception as e:
        # return error message in json and 500 status code
        raise HTTPException(status_code=500, detail="Error uploading files")

    return {
        "ecu": inference.ecu,
        "version": inference.version,
        "status": inference.STATUSES[inference.status],
    }


@app.post("/{ecu}/inferences/{version}/run")
def run_inference(ecu: str, version: int, background_tasks: BackgroundTasks):
    """Run inference."""
    # check if any other inference is running
    running_inference = Inference.nodes.filter(status="R")
    if running_inference:
        raise HTTPException(
            status_code=400, detail="Another Inference already running, try again later"
        )

    inference = Inference.nodes.get_or_none(ecu=ecu, version=version)
    if not inference:
        return {"message": "Inference not found"}

    # start the inference in the background
    background_tasks.add_task(perform_inference, inference)

    return {
        "message": "Inference started",
    }


@app.get("/{ecu}/inferences/", response_model=List[InferenceModel])
def list_inferences(ecu: str):
    """List all inferences."""
    inferences: Inference = Inference.nodes.filter(ecu=ecu)
    inferences_response = [
        {
            "ecu": inference.ecu,
            "version": inference.version,
            "status": inference.STATUSES[inference.status],
        }
        for inference in inferences
    ]
    return inferences_response


@app.get("/{ecu}/inferences/{version}", response_model=Union[InferenceModel, dict])
def get_inference(ecu: str, version: int):
    """Get a specific inference by ID."""

    inference = Inference.nodes.get_or_none(ecu=ecu, version=version)
    if not inference:
        return {"message": "Inference not found"}
    return {
        "ecu": inference.ecu,
        "version": inference.version,
        "status": inference.STATUSES[inference.status],
        "messages": inference.messages,
    }

@app.post("/upload-physical-quantities-knowledgebase/")
def bulk_upload():
    quantities = load_physical_quantities_from_folder()
    with driver.session() as session:
        for pq in quantities:
            session.execute_write(store_physical_quantity, pq)
    return {"message": f"Physical Quantities inserted successfully"}

@app.post("/upload-ecu_families-knowledgebase/")
def bulk_upload_ecu_family():
    data = [
    ("COO", "COO11", "27"),
    ("DDU", "DDU1", "17"),
    ("DD", "DD1", "3B"),
    ("VIS", "CUV3", "1E"),
    ("EMS", "EMS10", "00"),
    ("BMS", "EBS9", "0B"),
    ("CMS", "CMS1", "47"),
    ("TPM", "TPM2", "33"),
    ("APS", "APS2", "30"),
    ("CCU", "CCU1", "19"),
    ("CID", "CID2", "54"),
    ("DCS", "DCS2", "EC"),
    ("DCSXA", "PDS2", "ED"),
    ("TMS", "TMS3", "DC"),
    ("ECA", "ECAKB4", "FD"),
    ("PBC", "EPB1", "50"),
    ("DIS", "DIS3", "2A"),
    ("FLC", "FLC3", "EB"),
    ("RTC", "C400", "4A"),
]
    with driver.session() as session:
        for family, system, server in data:
            session.execute_write(save_ecu_family, family, system, server)
    return {"message": f"ECU Families inserted successfully"}

@app.get("/{ecu}/inferences/{version}/download")
async def download_inference_result(ecu: str, version: str):
    """Download the inference result file from local folder."""
    try:
        file_path = os.path.join(
            data_root_folder,
            ecu,
            str(version),
            root_archive_folder,
            "output.zip"
        )

        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="Output file not found")
        print(file_path)
        return FileResponse(
            path=file_path,
            filename="output.zip",
            media_type="application/zip",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
