import os
from models.input.function_view import FunctionView, Group, NamePresentation
from models.input.function_property_group import FunctionPropertyGroup
from processors.function_parameters.function_group_processor import content_to_int_hash
from state import State
from config import (
    input_root_folder,
    output_root_folder,
    function_parameters_output_folder,
)
from database.models import FunctionViewNode
from database.database import get_dense_vector, qclient, FG_COLLECTION_NAME
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, models

from utils import get_tokens


def export_function_tree(state: State):
    """
    Exports function tree data from the state.
    """
    # load the function tree data from the input folder
    function_tree_data_path = os.path.join(
        state.inference_base_folder,
        input_root_folder,
        "FunctionView_FunctionAdjustTree.xml",
    )

    state.update_queue.put(f"Processing FunctionView_FunctionAdjustTree.xml file")

    ft_node = None

    if os.path.exists(function_tree_data_path):
        # exit silently if the file does not exist
        with open(function_tree_data_path, "rb") as f:
            xml_data = f.read()
            function_tree = FunctionView.from_xml(xml_data)

            # check if we already have the function tree in the database
            ft_node = FunctionViewNode.nodes.first_or_none(name=function_tree.name)
            if ft_node is not None:
                ft_node.payload = function_tree.model_dump_json(indent=2)
            else:
                # save the function tree to the database
                ft_node = FunctionViewNode(
                    name=function_tree.name,
                    payload=function_tree.model_dump_json(indent=2),
                )

            # save the function tree to the database
            ft_node.save()

            # add the function tree to the inference
            state.inference.function_views.connect(ft_node)
    else:
        # load the function tree from the database
        ft_node = FunctionViewNode.nodes.first_or_none(name="FunctionAdjustTree")
        if ft_node is None:
            state.update_queue.put(
                f"FunctionView_FunctionAdjustTree.xml file not found and no data in the database"
            )
            return
        function_tree = FunctionView.model_validate_json(ft_node.payload)

    # TODO: check if extra processing is needed
    # we need to get the pending function group from qdrant
    # get the function group from the database

    _filter = Filter(
        must=[
            FieldCondition(
                key="pending",
                match=MatchValue(
                    value=True,
                ),
            )
        ]
    )
    all_results = []
    next_offset = None
    while True:
        # get the function group from the database
        points, next_offset = qclient.scroll(
            collection_name=FG_COLLECTION_NAME,
            scroll_filter=_filter,
            limit=100,
            offset=next_offset,
        )
        all_results.extend(points)
        if not next_offset:
            break

    if not all_results:
        state.update_queue.put(f"No pending function groups found in the database")
        return

    fv_node = FunctionViewNode.nodes.first_or_none(name="FunctionAdjustTree")
    if fv_node is None:
        state.update_queue.put(
            f"Function group FunctionAdjustTree not found in the database"
        )

    # save the function group to the database
    fv_node.save()

    for result in all_results:
        # get the function group from the database

        # review the function group
        function_group = FunctionPropertyGroup.model_validate_json(
            result.payload["json"]
        )

        # save the function groups to the tree
        function_tree.group.append(
            Group(
                name=function_group.name,
                namePresentation=NamePresentation(
                    edt=function_group.namePresentation.edt,
                    value=function_group.namePresentation.value,
                ),
            )
        )

        # update the function group in the vector store
        qclient.upsert(
            collection_name=FG_COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=content_to_int_hash(function_group.model_dump_json().encode()),
                    payload={
                        "json": function_group.model_dump_json(),
                        "document": result.payload["document"],
                        "tokens": result.payload["tokens"],
                        "type": "FunctionPropertyGroup",
                        "ufNumber": function_group.ufNumber,
                    },
                    vector=get_dense_vector(function_group.name),
                )
            ],
        )

    # update the function group in the database
    fv_node.payload = function_tree.model_dump_json(indent=2)
    fv_node.save()

    # export the same file to the output folder
    output_path = os.path.join(
        state.inference_base_folder,
        output_root_folder,
        function_parameters_output_folder,
        "FunctionView_FunctionAdjustTree.xml",
    )

    with open(output_path, "wb") as f:
        f.write(
            function_tree.to_xml(
                pretty_print=True, encoding="UTF-8", xml_declaration=True
            )  # type: ignore
        )
