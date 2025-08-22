from pydantic import Field, BaseModel
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from openai import OpenAI
from rich import print
from config import openai_api_key, openai_api_base

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

class Component(BaseModel):
    name: str = Field("component name example, E07")
    description: str = Field("component description example, 1uF capacitor")


class CircuitComponents(BaseModel):
    components: list[Component]


class State(TypedDict):
    components: list
    diagram_content: str


# load markdown_table.md


def extract_all_components(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """
                        You are a highly skilled technician. You have been given a list of components that are used in the circuit board.
                        based on the given input, extract all component name and description,
                        
                        component has a name, position and a description
                        
                        component description is a string with electrical component description
                        
                        Example Input:
                        Des.
                        Pos.
                        Description
                        C9
                        E 3
                        Connector, 15-pole
                        C14
                        E 5
                        Connector, 18-pole
                        C26
                        E 6
                        Connector 16-pole
                        C8623
                        E 2
                        Connector, 1-pole
                        C8636
                        G 2
                        Connector, 1-pole

                        Example Output:
                        name: C9
                        description: Connector, 15-pole

                        name: C14
                        description: Connector, 18-pole

                        name: C26
                        description: Connector 16-pole

                        name: C8623
                        description: Connector, 1-pole

                        name: C8636
                        description: Connector, 1-pole
                        """,
            },
            {
                "role": "user",
                "content": state["diagram_content"],
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        extra_body={
            "guided_json": CircuitComponents.model_json_schema(),
            "top_p": 0.9,
        },
        temperature=0.5,
    )
    components_response = CircuitComponents.model_validate_json(
        response.choices[0].message.content or "{}"
    )
    return {
        "components": components_response.components,
    }


components_builder = StateGraph(State)

# Add the nodes
components_builder.add_node("extract_all_components", extract_all_components)

components_builder.add_edge(START, "extract_all_components")
components_builder.add_edge("extract_all_components", END)

# Compile the workflow
graph = components_builder.compile()
