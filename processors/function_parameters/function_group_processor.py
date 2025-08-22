from models.input.function_property_group import FunctionPropertyGroup
from state import State
import os
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from database.database import get_dense_vector, qclient, FG_COLLECTION_NAME
from qdrant_client import models
from config import input_root_folder
import hashlib
from utils import get_tokens
from database.models import FunctionPropertyGroupNode


def content_to_int_hash(content: bytes, algorithm: str = "sha256") -> int:
    hash_func = hashlib.new(algorithm)
    hash_func.update(content)
    # Convert the hash digest to an integer
    hash = int.from_bytes(hash_func.digest(), byteorder="big")

    hash = hash % (10**8)  # Limit to 8 digits
    return hash


def ingest_function_groups(state: State):
    """
    Ingests function groups from the state.
    """

    function_group_data_path = os.path.join(
        state.inference_base_folder, input_root_folder, "FunctionViewAdjust"
    )

    all_files = list(Path(function_group_data_path).glob("*.xml"))

    state.update_queue.put(f"Processing {len(all_files)} FunctionPropertyGroup files")

    # make sure their names start with FunctionPropertyGroup
    function_property_group_files = [
        file for file in all_files if file.name.startswith("FunctionPropertyGroup")
    ]

    function_group_objects: list[FunctionPropertyGroup] = []

    for file in function_property_group_files:
        with file.open("rb") as f:
            xml_data = f.read()
            obj = FunctionPropertyGroup.from_xml(xml_data)
            model_json = obj.model_dump_json(indent=2)
            function_group_objects.append(obj)

    # Save the function group objects to the vector store

    if len(function_group_objects) == 0:
        state.update_queue.put(
            f"No FunctionPropertyGroup files found in the specified path, looked for .xml files in FunctionViewAdjust folder"
        )
        return

    ## prep the data for vectorization
    documents = []
    for function_property_group in function_group_objects:
        document = ""
        if function_property_group.property:
            for prop in function_property_group.property:
                document += prop.server.propertyName + "\n"
        if function_property_group.propertyGroup:
            for prop_group in function_property_group.propertyGroup:
                document += prop_group.name + "\n"
                for prop in prop_group.property:
                    document += prop.server.propertyName + "\n"

        # save the function property group to the neo4j database
        fg_node = FunctionPropertyGroupNode(
            name=function_property_group.name,
            payload=function_property_group.model_dump_json(),
        )

        fg_node.save()

        # add the function property group to the inference
        state.inference.function_property_groups.connect(fg_node)

        # save the function property group to the vector store
        qclient.upsert(
            collection_name=FG_COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=content_to_int_hash(
                        function_property_group.model_dump_json().encode()
                    ),
                    payload={
                        "json": function_property_group.model_dump_json(),
                        "document": document,
                        "tokens": get_tokens(document),
                        "type": "FunctionPropertyGroup",
                        "ufNumber": function_property_group.ufNumber,
                    },
                    vector=get_dense_vector(document),
                )
            ],
        )
        documents.append(document)
