from openai import OpenAI
from models.input.pt_imported_range import PtImportedRange
from models.input.pt_imported_simple_parameter import PtImportedSimpleParameter

# load all the physical quantities from the ./data/Function-Parameters/PhysicalQuantity/ folder
from pydantic import BaseModel, Field

from config import openai_api_key, openai_api_base

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)


class FunctionGroupUpdate(BaseModel):
    function_group_name: str = Field(
        ...,
        description="The name of the function group to which this function parameter belongs, none if it is not related to any function group",
    )
    function_group_type: str = Field(
        ...,
        description="new / existing - new: if the function group is new and does not exist in the database. existing: if the function group already exists in the database.",
    )
    reason: str = Field(..., description="The reason for the decision")


def update_function_group(
    function_parameter: PtImportedSimpleParameter,
    function_group_details: str,
):
    chat_response = client.chat.completions.create(
        model="NovaSky-AI/Sky-T1-32B-Flash",
        messages=[
            {
                "role": "system",
                "content": f"""
            You are a technical writer for an automotive company. You are familiar with various terms used in automotive documentation.
            Given a function parameter details, and a funciton group details, you need to decide if we can add this function parameter to one of the function groups or create a new function group.
            Return the name of the function group to which this function parameter belongs or return none if it is not related to any function group.
            You also need to provide the type of the function group, either existing or none.
            Provide a small reason for your decision.

            ========================================
            funciton group details
            {function_group_details}
            ========================================

            RULES:

            1. Return the name of the function group to which this function parameter belongs, or you can return a new function group name.
            2. If the function parameter is not related to any function group, return a new function group name.

            OUTPUT:
            Only return following items in JSON format:
            1. function_group_name: The name of the function group to which this function parameter belongs, it can be a new function group name or an existing function group name.
            2. function_group_type: new / existing - 
                new: if the function group is new and does not exist in the database.
                existing: if the function group already exists in the database.
            3. reason: The reason for the decision.

            OUTPUT FORMAT:
            The output should be in JSON format with the following keys:
            1. function_group_name: The name of the function group to which this function parameter belongs, it can be a new function group name or an existing function group name.
            2. function_group_type: new / existing - 
                new: if the function group is new and does not exist in the database.
                existing: if the function group already exists in the database.
            3. reason: The reason for the decision.

            """,
            },
            {
                "role": "user",
                "content": f"""
                function_parameter: { function_parameter.model_dump_json(indent=2)}
                    """,
            },
        ],
        temperature=0.5,
        extra_body={
            "guided_json": FunctionGroupUpdate.model_json_schema(),
            "top_p": 0.95,
        },
    )

    return FunctionGroupUpdate.model_validate_json(
        chat_response.choices[0].message.content  # type: ignore
    )
