import os
from models.input.function_property_group import (
    FunctionPropertyGroup,
    Property,
    Server,
    NamePresentation,
)
from models.input.pt_imported_range import PtImportedRange
from models.input.pt_imported_simple_parameter import PtImportedSimpleParameter
from models.output.pt_sdp3_range import PtSDP3Range
from processors.function_parameters.function_group_processor import content_to_int_hash
from processors.function_parameters.llm.function_group_update import (
    FunctionGroupUpdate,
    update_function_group,
)
from processors.function_parameters.llm.function_group_create import (
    FunctionGroupCreate,
    create_function_group,
)
from processors.function_parameters.llm.generate_output_parameter import (
    FunctionParameterDetails,
    generate_output_parameter,
)
from state import State
from database.database import (
    FG_COLLECTION_NAME,
    qclient,
    oclient,
)

from database.models import (
    PhysicalQuantityNode,
)


from models.common import RefElement
from models.output.pt_sdp3_parameter import PresentationText, PtSDP3Parameter
from utils import get_tokens
from config import (
    input_root_folder,
    output_root_folder,
    max_parallel_workers,
    function_parameters_output_folder,
)
from models.input.physical_quantity import PhysicalQuantity
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from concurrent.futures import ThreadPoolExecutor


# load all the physical quantities from the ./data/Function-Parameters/PhysicalQuantity/ folder
from pathlib import Path
from openai import OpenAI
from pydantic import BaseModel

physical_quantities_details = ""
imported_ranges: list[PtImportedRange] = []

imported_parameters: list[PtImportedSimpleParameter] = []
from qdrant_client import models

new_function_group = []


def get_dense_vector(document):
    """
    Convert sparse vector to dense format.
    """
    response = oclient.embeddings(
        model="nomic-embed-text", prompt=" ".join(get_tokens(document))
    )
    embeddings = response["embedding"]

    return embeddings


def process_function_parameters(state: State):
    global physical_quantities_details, imported_ranges, imported_parameters
    # reset the global variables
    physical_quantities_details = ""
    imported_ranges = []
    imported_parameters = []

    physical_quantities_data_path = os.path.join(
        state.inference_base_folder, input_root_folder, "PhysicalQuantity"
    )
    physical_quantity_files = Path(physical_quantities_data_path).glob("*.xml")

    # make sure their names start with PhysicalQuantity
    physical_quantity_files = [
        file
        for file in physical_quantity_files
        if file.name.startswith("PhysicalQuantity")
    ]

    token_count = 0
    print("total files: ", len(physical_quantity_files))

    for file in physical_quantity_files:
        with file.open("rb") as f:
            xml_data = f.read()
            obj = PhysicalQuantity.from_xml(xml_data)

            json_data = obj.model_dump_json(indent=2)
            # add the name of the physical quantity to the details
            physical_quantity_details = "\n\nPHYSICAL QUANTITY " + obj.name + "\n"

            ## loop through the units and add them to the details
            for unit in obj.unit:
                physical_quantity_details += unit.name + "\n"

            # Create and save the Neo4j node
            pq_node = PhysicalQuantityNode.nodes.first_or_none(name=obj.name)
            if pq_node is not None:
                pq_node.payload = json_data
            else:
                pq_node = PhysicalQuantityNode(
                    name=obj.name,
                    payload=json_data,
                )

                # save the physical quantity to the output folder
                output_data_path = os.path.join(
                    state.inference_base_folder,
                    output_root_folder,
                    function_parameters_output_folder,
                    "PhysicalQuantity",
                )

                # make sure the directory exists
                os.makedirs(output_data_path, exist_ok=True)

                output_file_name = os.path.join(
                    output_data_path,
                    f"PhysicalQuantity_{obj.name}.xml",
                )
                with open(output_file_name, "wb") as f:
                    f.write(
                        obj.to_xml(
                            pretty_print=True,
                            encoding="UTF-8",
                            xml_declaration=True,
                        )  # type: ignore
                    )
                print(f"Physical quantity saved to {output_file_name}")
            # save the physical quantity to the database
            pq_node.save()

            # add the physical quantity to the inference
            state.inference.physical_quantities.connect(pq_node)

    # load all the physical quantities from the collection to include the previous ones
    # unconditional search
    # TODO: load the all the previous physical quantities from the neo4j database
    all_pqs = PhysicalQuantityNode.nodes.all()

    # loop through the physical quantities and add them to the details
    for pq in all_pqs:
        pq_obj = PhysicalQuantity.model_validate_json(pq.payload)
        physical_quantities_details += "\n\nPHYSICAL QUANTITY " + pq_obj.name + "\n"
        for unit in pq_obj.unit:
            physical_quantities_details += unit.name + "\n"

    range_data_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        f"{state.ecu_system_execution.upper()}/Imported/Ranges",
    )

    # load all range parameters
    all_files = Path(range_data_path).glob("*.xml")

    # make sure their names start with PtImportedRange
    imported_range_files = [
        file for file in all_files if file.name.startswith("PtImportedRange")
    ]

    for file in imported_range_files:
        with file.open("rb") as f:
            xml_data = f.read()
            print(f"Processing file: {file.name}")
            obj = PtImportedRange.from_xml(xml_data)
            imported_ranges.append(obj)

    # load all import parameters

    parameter_data_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        f"{state.ecu_system_execution.upper()}/Imported/Parameters",
    )

    all_files = Path(parameter_data_path).glob("*.xml")

    # make sure their names start with PtImportedSimpleParameter
    imported_parameter_files = [
        file for file in all_files if file.name.startswith("PtImportedSimpleParameter")
    ]
    for file in imported_parameter_files:
        with file.open("rb") as f:
            xml_data = f.read()
            obj = PtImportedSimpleParameter.from_xml(xml_data)
            model_json = obj.model_dump_json(indent=2)
            imported_parameters.append(obj)

    with ThreadPoolExecutor(
        max_workers=max_parallel_workers
    ) as executor:  # Or use config.max_parallel_workers
        futures = [
            executor.submit(
                process_imported_parameter,
                state,
                param,
                index,
                len(imported_parameters),
            )
            for index, param in enumerate(imported_parameters)
        ]
        for future in futures:
            try:
                future.result(timeout=120)
            except Exception as e:
                print(f"Error processing parameter: {e}")

    # print(physical_quantities)


def process_imported_parameter(
    state: State, imported_parameter: PtImportedSimpleParameter, index, total
):
    # load associated range

    print(f"Processing {index + 1}/{total}")

    # find the associated range
    range_name = imported_parameter.importedSimpleParameter.rangeRef.name

    # find the range object
    range_obj = next(
        (r for r in imported_ranges if r.name == range_name), None
    )  # type: ignore

    # create lookup document
    lookup_document = imported_parameter.name + "\n"
    lookup_document += imported_parameter.importedSimpleParameter.description + "\n"

    dense_embedding = get_dense_vector(lookup_document)

    result = qclient.query_points(
        collection_name=FG_COLLECTION_NAME,
        query=dense_embedding,
        limit=3,
    )

    results_string = ""

    for points in result.points:
        if points is None or points.payload is None:
            continue
        # get the document from the result
        result_doc = points.payload["json"]

        results_string += f"{result_doc} \n"

    if not range_obj:
        print(f"Range object not found for {range_name}")
        return

    function_params: FunctionParameterDetails = generate_output_parameter(
        imported_parameter, range_obj, results_string, physical_quantities_details
    )
    # output data parameter

    output_data = PtSDP3Parameter(
        name=imported_parameter.name,
        ecuSystemFamily=imported_parameter.ecuSystemFamily,
        ecuSystemExecution=imported_parameter.ecuSystemExecution,
        serverExecution=imported_parameter.serverExecution,
        categoryCondition=RefElement(
            ref="CategoryCondition",
            name="-",
        ),
        description=PresentationText(edt="nfTxt", value=function_params.description),
        physicalQuantity=RefElement(
            ref="PhysicalQuantity",
            name=function_params.physical_quantity,
        ),
        namePresentation=PresentationText(edt="nfTxt", value=imported_parameter.name),
        importedSimpleParameterRef=RefElement(
            ref="ImportedSimpleParameter",
            name=imported_parameter.name,
        ),
    )

    # save the output data in xml format
    output_data_xml = output_data.to_xml(
        pretty_print=True,
        encoding="UTF-8",
        xml_declaration=True,
    )

    # export the range in the xml format

    if range_obj is None:
        print(f"Range object not found for {range_name}")
        return

    range_data = PtSDP3Range(
        name=range_obj.name,
        ecuSystemFamily=imported_parameter.ecuSystemFamily,
        ecuSystemExecution=imported_parameter.ecuSystemExecution,
        serverExecution=imported_parameter.serverExecution,
        importedRangeRef=RefElement(
            ref="ImportedRange",
            name=range_obj.name,
        ),
        discreteValueRef=[],
    )

    if range_obj.importedDiscreteValue is not None:
        for value in range_obj.importedDiscreteValue:
            range_data.discreteValueRef.append(
                RefElement(
                    ref="DiscreteValue",
                    name=value.name,
                )
            )

    range_data_xml = range_data.to_xml(
        pretty_print=True,
        encoding="UTF-8",
        xml_declaration=True,
    )

    # save the output data in the output destination
    output_data_path = os.path.join(
        state.inference_base_folder,
        output_root_folder,
        function_parameters_output_folder,
        f"{state.ecu_system_execution.upper()}/SDP3/Parameters",
    )

    # make sure the directory exists
    os.makedirs(output_data_path, exist_ok=True)
    output_file_name = os.path.join(
        output_data_path,
        f"PtSDP3Parameter_{imported_parameter.name}.xml",
    )
    with open(output_file_name, "wb") as f:
        f.write(output_data_xml)  # type: ignore

    # save the range data in the output destination
    range_data_path = os.path.join(
        state.inference_base_folder,
        output_root_folder,
        function_parameters_output_folder,
        f"{state.ecu_system_execution.upper()}/SDP3/Ranges",
    )
    # make sure the directory exists
    os.makedirs(range_data_path, exist_ok=True)
    range_file_name = os.path.join(
        range_data_path,
        f"PtSDP3Range_{range_obj.name}.xml",
    )
    with open(range_file_name, "wb") as f:
        f.write(range_data_xml)  # type: ignore

    # load the function group from qdrant
    filter_ = Filter(
        must=[
            FieldCondition(
                key="ufNumber",
                match=MatchValue(
                    value=int(imported_parameter.importedSimpleParameter.UserFunction)
                ),
            )
        ]
    )

    all_results = []
    next_offset = None

    while True:
        points, next_offset = qclient.scroll(
            collection_name=FG_COLLECTION_NAME,
            scroll_filter=filter_,
            limit=100,  # Max batch size per request
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )
        all_results.extend(points)
        if next_offset is None:
            break

    # Done — now all_results contains all matching documents
    for point in all_results:
        with state.lock:
            # revive the object
            function_group_object = FunctionPropertyGroup.model_validate_json(
                point.payload["json"]
            )

            # save the function group object in the output destination
            output_data_path = os.path.join(
                state.inference_base_folder,
                output_root_folder,
                function_parameters_output_folder,
                "FunctionViewAdjust",
            )
            # make sure the directory exists
            os.makedirs(output_data_path, exist_ok=True)

            output_file_name = os.path.join(
                output_data_path,
                f"FunctionPropertyGroup_{function_group_object.name}.xml",
            )

            llm_data: FunctionGroupUpdate = update_function_group(
                imported_parameter, function_group_object.model_dump_json(indent=2)
            )

            new_property = Property(
                server=Server(
                    propertyName=imported_parameter.name,
                    canAddress=state.server_can or "",
                )
            )

            if llm_data.function_group_type == "new":
                if function_group_object.property is None:
                    function_group_object.property = []
                function_group_object.property.append(new_property)
            else:
                if function_group_object.propertyGroup is None:
                    function_group_object.propertyGroup = []
                # find the property in the function group object
                for property in function_group_object.propertyGroup:
                    if property.name == imported_parameter.name:
                        if property.property is None:
                            property.property = []
                        property.property.append(new_property)
                        break

            # update the function group object to the qdrant collection

            qclient.set_payload(
                collection_name=FG_COLLECTION_NAME,
                payload={
                    "json": function_group_object.model_dump_json(indent=2),
                },
                points=[point.id],
            )

            with open(output_file_name, "wb") as f:
                f.write(
                    function_group_object.to_xml(
                        pretty_print=True, encoding="UTF-8", xml_declaration=True
                    )  # type: ignore
                )
            print(f"Function group object saved to {output_file_name}")

    if len(all_results) == 0:
        # we need to create a new function group object
        # load all the function group names from the qdrant collection to get their names
        # no filter
        all_names = ""
        all_function_groups = []
        next_offset = None

        while True:
            # get all the function groups from the qdrant collection
            # no filter
            points, next_offset = qclient.scroll(
                collection_name=FG_COLLECTION_NAME,
                scroll_filter=None,
                limit=100,  # Max batch size per request
                with_payload=True,
                with_vectors=False,
                offset=next_offset,
            )
            all_function_groups.extend(points)
            if next_offset is None:
                break

        for point in all_function_groups:
            if point is None or point.payload is None:  # type: ignore
                continue
            # get the document from the result
            result_doc = point.payload["json"]  # type: ignore
            # revive the object
            function_group_object = FunctionPropertyGroup.model_validate_json(
                result_doc
            )
            # add the name of the function group to the details
            all_names += f"{function_group_object.name} \n"

        # call the llm to create a new function group
        new_function_group: FunctionGroupCreate = create_function_group(
            imported_parameter, all_names
        )

        # create a new function group object
        function_group_object = FunctionPropertyGroup(
            name=new_function_group.function_group_name,
            propertyGroup=[],
            property=[
                Property(
                    server=Server(
                        propertyName=imported_parameter.name,
                        canAddress=state.server_can or "",
                    )
                )
            ],
            ufNumber=[int(imported_parameter.importedSimpleParameter.UserFunction)],
            namePresentation=NamePresentation(
                edt="nfTxt", value=new_function_group.function_group_name
            ),
        )

        # save the function group object in the output destination
        output_data_path = os.path.join(
            state.inference_base_folder,
            output_root_folder,
            function_parameters_output_folder,
            "FunctionViewAdjust",
        )
        # make sure the directory exists
        os.makedirs(output_data_path, exist_ok=True)

        output_file_name = os.path.join(
            output_data_path,
            f"FunctionPropertyGroup_{function_group_object.name}.xml",
        )

        with open(output_file_name, "wb") as f:
            f.write(
                function_group_object.to_xml(
                    pretty_print=True, encoding="UTF-8", xml_declaration=True
                )  # type: ignore
            )
        print(f"Function group object saved to {output_file_name}")

        with state.lock:
            # save the function group object to the qdrant collection
            document = ""
            if function_group_object.property:
                for prop in function_group_object.property:
                    document += prop.server.propertyName + "\n"
            if function_group_object.propertyGroup:
                for prop_group in function_group_object.propertyGroup:
                    document += prop_group.name + "\n"
                    for prop in prop_group.property:
                        document += prop.server.propertyName + "\n"
            # save the function property group to the vector store
            qclient.upsert(
                collection_name=FG_COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=content_to_int_hash(
                            function_group_object.model_dump_json().encode()
                        ),
                        payload={
                            "json": function_group_object.model_dump_json(),
                            "document": document,
                            "tokens": get_tokens(document),
                            "type": "FunctionPropertyGroup",
                            "ufNumber": function_group_object.ufNumber,
                            "pending": True,
                        },
                        vector=get_dense_vector(document),
                    )
                ],
            )
