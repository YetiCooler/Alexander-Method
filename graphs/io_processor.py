from openai import OpenAI
from pydantic import BaseModel, Field
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from database.database import oclient, qclient, COLLECTION_NAME
from utils import get_tokens, get_clean_io_name
from qdrant_client import models
from logger import system_logger
from config import openai_api_key, openai_api_base

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)


class IOVerification(BaseModel):
    matched: str = Field(
        ..., description="yes or no, Whether the IO event belongs to the component"
    )
    component: str = Field(..., description="The component name")
    reason: str = Field(..., description="The reason for the verification")


class State(TypedDict):
    io_item: dict
    excluded_components: list[str]
    ecu_system: str
    matched: str
    component: str


def process_io_item(state: State):
    system_logger.info(f"Processing IO item {state['io_item']}")
    description = ""
    name_presentation = ""
    name = state["io_item"]["Name"]
    if (
        "NamePresentation" in state["io_item"]
        and "#text" in state["io_item"]["NamePresentation"]
    ):
        name_presentation = state["io_item"]["NamePresentation"]["#text"]

    if (
        "Description" in state["io_item"]["IOService"]
        and "#text" in state["io_item"]["IOService"]["Description"]
    ):
        description = state["io_item"]["IOService"]["Description"]["#text"]

    if name == name_presentation:
        name_presentation = ""  # if name and name_presentation are the same, we don't need to repeat the name_presentation

    data = get_clean_io_name(name) + "\n" + name_presentation + "\n" + description

    system_logger.info(f"Processing IO: {name} {name_presentation} {description}")
    system_logger.info(f"IO data: {data}")
    system_logger.info(f"Generated tokens: {get_tokens(data)}")

    tokens = get_tokens(data)

    # make tokens unique
    tokens = list(set(tokens))
    system_logger.info(f"Unique tokens: {tokens}")

    if len(tokens) == 0:
        system_logger.info(f"No tokens found for IO event {name}")
        return {"matched": "no", "component": "No component found"}

    points = []
    try:
        embeddings_response = oclient.embeddings(
            model="nomic-embed-text", prompt=" ".join(tokens)
        )
        embeddings = embeddings_response["embedding"]
        response = qclient.query_points(
            collection_name=COLLECTION_NAME,
            query=embeddings,
            score_threshold=0.55,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="ecu_system",
                        match=models.MatchValue(
                            value=state["ecu_system"],
                        ),
                    ),
                    models.FieldCondition(
                        key="name",
                        match=models.MatchExcept(
                            **{"except": state["excluded_components"]},
                        ),
                    ),
                ],
            ),
        )

        points = response.points

    except Exception as e:
        system_logger.error(f"Error querying Qdrant: {e}")
        return {"matched": "no", "component": "No component found"}

    if len(points) == 0:
        system_logger.info(f"No component found for IO event {name}")
        return {"matched": "no", "component": "No component found"}

    # take the first three points and run it via LLM
    selected_points = points[:3]

    system_logger.info(
        f"""Queried qdrant for embeddings for: {data} - proceeding to LLM confirmation \n
        The top 3 components are: {
             [(point.payload["name"], point.payload["description"], point.score) for point in selected_points]
        }
        """
    )
    component_descriptions = "\n".join(
        [
            f"Component Name: {point.payload['name']}\nComponent Description: {point.payload['description']}"
            for point in selected_points
        ]
    )
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """
                You are an expert in error diagnosis and detection for vehicle electrical components. Based on an IO event decide if the IO event blongs to a given component or not.
                Example 1:
                Example Input:
                IO EVENT: Cabin fan PWM duty cycle

                COMPONENTS:
                Component Name: L32/L33
                Component Description: Lamp, boarding step, driver/passenger

                Component Name: L34
                Component Description: Lamp, boarding step, driver/passenger

                Component Name: E107
                Component Description: Fuel level sensor

                Example Output:
                matched: no
                component: None
                reason: The IO event does not belong to any of the components because it's related to cabin fan and none of the components are related to cabin fan

                EXAMPLE 2:
                Example Input:
                IO EVENT: pin el position voltage clutch sensor
                
                Component Name: T20
                Component Description: Sensor, tachograph

                Component Name: R142
                Component Description: Relay, coolant level sensor

                COMPONENT:
                Component Name: D60
                Component Description: Sensor, clutch pedal

                Example Output:
                matched: yes
                component: D60
                reason: The IO event belongs to the component because it's related to clutch sensor and D60 is related to clutch sensor

                Be critical and provide a reason for your decision, match only when you are fully confident.
                """,
            },
            {
                "role": "user",
                "content": f"""
            IO EVENT: {" ".join(tokens)}
            
            COMPONENT:
            {component_descriptions}
            """,
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.45,
        extra_body={
            "guided_json": IOVerification.model_json_schema(),
            "top_p": 0.95,
        },
    )
    io_verification = IOVerification.model_validate_json(
        response.choices[0].message.content
    )

    system_logger.info(
        f"""Selected component: {io_verification.component} - matched: {io_verification.matched} - reason: {io_verification.reason}"""
    )

    return {
        "matched": io_verification.matched,
        "reason": io_verification.reason,
        "component": io_verification.component,
    }


components_builder = StateGraph(State)

# Add the nodes
components_builder.add_node("process_io_item", process_io_item)

components_builder.add_edge(START, "process_io_item")
components_builder.add_edge("process_io_item", END)

# compile the workflow
graph = components_builder.compile()
