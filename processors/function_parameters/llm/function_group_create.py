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


class FunctionGroupCreate(BaseModel):
    function_group_name: str = Field(
        ..., description="Suggested name of the new function group"
    )
    short_description: str = Field(
        ...,
        description="a very short description of the function group, 1-2 lines",
    )
    reason: str = Field(..., description="The reason for the decision")


def create_function_group(
    function_parameter: PtImportedSimpleParameter,
    all_function_group_names: str,
):
    chat_response = client.chat.completions.create(
        model="NovaSky-AI/Sky-T1-32B-Flash",
        messages=[
            {
                "role": "system",
                "content": f"""
            You are a technical writer for an automotive company. You are familiar with various terms used in automotive documentation.
            Given a function parameter details, we need to create a new function group for this function parameter.
            You will need to provide a suggested name for the new function group, a short description of the function group, and a reason for the decision.
            Names of other funciton groups are provided for your reference.

            ========================================
            All function group names
            {all_function_group_names}
            ========================================

            RULES:

            1. Return a new function group name.
            2. The name should be unique and not already exist in the database.
            3. The name should be descriptive and relevant to the function parameter.
            4. The name should be in camel case format.
            5. Provide a short description of the function group, 1-2 lines.

            OUTPUT:
            Only return following items in JSON format:
            1. function_group_name: The suggested name of the new function group.
            2. short_description: a very short description of the function group, 1-2 lines.
            3. reason: The reason for the decision.

            OUTPUT FORMAT:
            The output should be in JSON format with the following keys:
            1. function_group_name: The suggested name of the new function group.
            2. short_description: a very short description of the function group, 1-2 lines.
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
            "guided_json": FunctionGroupCreate.model_json_schema(),
            "top_p": 0.95,
        },
    )

    return FunctionGroupCreate.model_validate_json(
        chat_response.choices[0].message.content  # type: ignore
    )
