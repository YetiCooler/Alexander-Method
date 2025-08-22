from openai import OpenAI
from models.input.pt_imported_range import PtImportedRange
from models.input.pt_imported_simple_parameter import PtImportedSimpleParameter

# load all the physical quantities from the ./data/Function-Parameters/PhysicalQuantity/ folder
from pydantic import BaseModel

from config import openai_api_key, openai_api_base

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

class FunctionParameterDetails(BaseModel):
    description: str
    physical_quantity: str
    reason: str


def generate_output_parameter(
    function_parameter: PtImportedSimpleParameter,
    function_range: PtImportedRange,
    search_results: str,
    physical_quantities_details: str,
):
    chat_response = client.chat.completions.create(
        model="NovaSky-AI/Sky-T1-32B-Flash",
        messages=[
            {
                "role": "system",
                "content": f"""
            You are a technical writer for an automotive company. You are familiar with various terms used in automotive documentation.
            Given the details about a function paramter, you need to return description and physical quantitiy of the parameter.

            ========================================
            physical quantities:
            {physical_quantities_details}
            ========================================
            ========================================
            A vector search result:
            {search_results}
            ========================================

            RULES:

            1. Return the accurate description of the function parameter.
            2. Return the physical quantity of the function parameter from the list of physical quantities.
            3. Don't mention any search results, they are just for your reference.


            OUTPUT:
            Only return following items in JSON format:
            1. description: Description of the function parameter.
            2. physical_quantity: Physical quantity of the function parameter.
            3. reason: Reason for the description and physical quantity.
            """,
            },
            {
                "role": "user",
                "content": f"""
                function_parameter: { function_parameter.model_dump_json(indent=2)}
                function_range: { function_range.model_dump_json(indent=2)}
                    """,
            },
        ],
        temperature=0.5,
        extra_body={
            "guided_json": FunctionParameterDetails.model_json_schema(),
            "top_p": 0.95,
        },
    )

    return FunctionParameterDetails.model_validate_json(
        chat_response.choices[0].message.content  # type: ignore
    )
