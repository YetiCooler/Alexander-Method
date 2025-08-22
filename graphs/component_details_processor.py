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

class ComponentExtraDetails(BaseModel):
    description: str = Field(..., description="The description of the component")
    purpose: str = Field(..., description="The purpose of the component")
    has_description: str = Field(
        ..., description="yes or no, Whether the component has a description"
    )
    has_purpose: str = Field(
        ..., description="yes or no, Whether the component has a purpose"
    )
    reason: str = Field(..., description="The reason for the extraction")


class ComponentExtractionVerification(BaseModel):
    reason: str = Field(..., description="The reason for the verification")
    verified_description: str = Field(
        ..., description="yes or no, Whether the component has a description"
    )
    verified_purpose: str = Field(
        ..., description="yes or no, Whether the component has a purpose"
    )


class State(TypedDict):
    component_extraction_details: ComponentExtraDetails
    component_extraction_verification: ComponentExtractionVerification
    component: str
    short_description: str
    extra_information: str


def extract_component_details(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """
                You are an expert in electrical device details. Very carefully and slowly check the extra information extracted about a component. Based on the extra information, extract the purpose and description of the component. Also provide a reason for the extraction. The accuracy of the extraction is very important.

                EXAMPLE INPUT:
                component: T47
                basic_description: Connector, 1-pole
                extra_information: Front side left head lamp, Lamp connector
                
                EXAMPLE OUTPUT: 
                description: This is a front side left head lamp connector
                purpose: This connector is used to connect the front side left head lamp
                has_description: yes
                has_purpose: yes
                reason: The information is accurate as per the given extra information


                EXAMPLE INPUT:
                component: T72
                basic_description: Connector, 2-pole
                extra_information: Prep/Not connected

                EXAMPLE OUTPUT:
                description: 
                purpose:
                has_description: no
                has_purpose: no
                reason: There is not enough information to extract the description and purpose

                """,
            },
            {
                "role": "user",
                "content": f"""
            component: "{state["component"]}"
            basic_description: "{state["short_description"]}"
            extra information: "{state["extra_information"]}"
            """,
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.5,
        extra_body={
            "guided_json":ComponentExtraDetails.model_json_schema(),
            "top_p": 0.95
        }
    )
    component_extraction_details = ComponentExtraDetails.model_validate_json(
        response.choices[0].message.content
    )
    # print json response
    return {"component_extraction_details": component_extraction_details}


def verify_component_details(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """
                You are an expert in electrical device details. Very carefully and slowly analyze the extracted information about a component. Based on the extracted information, verify if the extracted description and purpose of the component are correct. Also provide a reason for your decision.

                Your job is to verify that all the component description and purpose details are correct are correct and provide more information about the component. Provide a reason for your decision.

                Respond with verified_description and verified_purpose as yes or no and provide a reason for your decision.

                EXAMPLE INPUT
                component: T72
                short_description: Connector, 2-pole
                extra_information: Prep/Not connected
                description: Prep/Not connected
                purpose: Prep/Not connected

                Example output:
                verified_description: no
                verified_purpose: no
                reason= the information is not helpful and does not provide any additional information about the component
                """,
            },
            {
                "role": "user",
                "content": f"""
            component: "{state["component"]}"
            short_description: "{state["short_description"]}"
            extra_information: "{state["extra_information"]}"
            description: "{state["component_extraction_details"].description}"
            purpose: "{state["component_extraction_details"].purpose}"
            
            """,
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.5,
        extra_body={
            "guided_json":ComponentExtractionVerification.model_json_schema(),
            "top_p": 0.95
        }
    )
    component_extraction_verification = (
        ComponentExtractionVerification.model_validate_json(
            response.choices[0].message.content
        )
    )
    # print json response
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


# Compile the workflow
graph = components_builder.compile()
