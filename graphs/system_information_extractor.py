import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from config import openai_api_key, openai_api_base

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)


class ComponentExtractionDetails(BaseModel):
    description: str = Field(..., description="The description of the component")
    reason: str = Field(..., description="The reason for the extraction")
    component: str = Field(..., description="The component")
    has_description: str = Field(
        ..., description="yes or no, Whether the component has a description"
    )


class ComponentExtractionVerification(BaseModel):
    verified: str = Field(
        ..., description="yes or no, Whether the component details are correct"
    )
    reason: str = Field(..., description="The reason for the verification")


class State(TypedDict):
    component_extraction_details: ComponentExtractionDetails
    component_extraction_verification: ComponentExtractionVerification
    component: str
    page_text: str


def extract_component_details(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """
                You are an expert in electrical device details. Very carefully and slowly check the page content and component name. If the component does not exist in the text, just say no information found. If the component exists in the text, only respond with the any information and the reason for the extraction.

                Keep the information as short as possible and only include the relevant information found as close to the component as possible thus enusuring the information is relevant to the component.

                The document is very unstructured and the information is not always in the same format. Sometimes the information is above or below the mentioned component.

                Example given component: E160
                Example Page Text: The E160 component is a type of electrical device that is used to control the flow of electricity in a circuit. It is commonly used in power supplies and other electronic devices.

                Example output:
                component= E160
                description= Control the flow of electricity in a circuit
                has_description= yes

                Example given component: C74
                Example Page Text: The B74 component is a type of electrical device that is used to control the flow of electricity in a circuit. It is commonly used in power supplies and other electronic devices.

                Example output:
                component= C74
                description= no information found
                has_description= no
                reason= The component does not exist in the text there is another component B74 but we are looking for C74

                output format: A valid JSON object
                {
                    "component": "",
                    "description": "",
                    "has_description": "yes/no",
                    "reason": ""
                }
                """,
            },
            {
                "role": "user",
                "content": f"""
            given component: "{state["component"]}"
            here is the actual page text
            Page Text: {state["page_text"]}
            """,
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.45,
        extra_body={
            "guided_json": ComponentExtractionDetails.model_json_schema(),
            "top_p": 0.95,
        },
    )
    component_extraction_details = ComponentExtractionDetails.model_validate_json(
        response.choices[0].message.content or "{}"
    )
    return {"component_extraction_details": component_extraction_details}


def verify_component_details(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """
                You are an expert in electrical device details. Very carefully and slowly check the page content and component details.

                Your job is to verify that all the component details are correct and present in the page text.

                Respond with yes/no and provide a reason for your decision.

                Example given component: E160
                Example given details: Control the flow of electricity in a circuit
                Example Page Text: The E155 component is a type of electrical device that is used to control the flow of electricity in a circuit. It is commonly used in power supplies and other electronic devices.

                Example output:
                verified= no
                reason= the information is not accurate as per the page text

                If in doubt, always say no.

                Output format: A valid JSON object
                {
                    "verified": "yes/no",
                    "reason": ""
                }
                """,
            },
            {
                "role": "user",
                "content": f"""
            given component: "{state["component"]}"
            given description: "{state["component_extraction_details"].description}"
            here is the actual page text
            Page Text: {state["page_text"]}
            """,
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.45,
        extra_body={
            "guided_json": ComponentExtractionVerification.model_json_schema(),
            "top_p": 0.95,
        },
    )
    component_extraction_verification = (
        ComponentExtractionVerification.model_validate_json(
            response.choices[0].message.content or "{}"
        )
    )
    return {"component_extraction_verification": component_extraction_verification}


def route_component_verification(state: State):
    if state["component_extraction_details"].has_description == "yes":
        return "Has Extraction"
    else:
        return "No Extraction"


components_builder = StateGraph(State)

# Add the nodes
components_builder.add_node("extract_component_details", extract_component_details)
components_builder.add_node("verify_component_details", verify_component_details)

components_builder.add_edge(START, "extract_component_details")
components_builder.add_conditional_edges(
    "extract_component_details",
    route_component_verification,
    {"Has Extraction": "verify_component_details", "No Extraction": END},
)
components_builder.add_edge("verify_component_details", END)

# compile the workflow
graph = components_builder.compile()
