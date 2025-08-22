example_errorcode_input = """4.37 A03D Permanent electrical fault reported by actuator for defrost 
(M59)
Implemented:
True
Enabled:
True
Order:
PRIMARY
Internal:
False
Classification:
FAULT
SAE J1939­73:
False
SPN:
 
FMI:
 
Heading
Permanent electrical fault reported by actuator for defrost (M59)
Detection
The cab comfort unit (E186) has detected the actuator reports an error.
Cause
The actuator has a permanent electrial fault.
System Reaction
The air dist/defrost flap will not function. It will not be possible to change the defrost air distribution from the current 
setting
Symptom
The air dist/defrost flap will not function. It will not be possible to change the defrost air distribution from the current 
setting
Action
Check the cable harness for the air dist/defrost motor, if no fault is found, replace the air dist/defrost motor.This unit 
is connected to the climate control system via a LIN­bus. If one of the units on the LIN­bus is faulty it can affect the 
other units further down the same communication line.
Calibration"""

example_errorcode_output = """
error_code - A03D
components - M59, E186
heading - Permanent electrical fault reported by actuator for defrost (M59)
detection - The cab comfort unit (E186) has detected the actuator reports an error.
cause - The actuator has a permanent electrical fault.
system_reaction - The air dist/defrost flap will not function. It will not be possible to change the defrost air distribution from the current setting
symptom - The air dist/defrost flap will not function. It will not be possible to change the defrost air distribution from the current setting
"""

negative_input = """
 
TECHNICAL 
PRODUCT DATA 
 
 
Issued by 
Generated from DIMATool v 7.6.0.11 by SERVICEJENKINSREV. 
Status 
P 
Date 
2024-01-29 
Page 
69 (203) 
 
N.B. The copyright and ownership of this document including associated computer data are and will remain ours. 
They must not be copied, used or brought to the knowledge of any third party without our prior permission. 
©  Scania CV AB, Sweden 
SV 1744   01-06 
 
Component: BM 
Electrical dual circuit steering: Overload 
Selfhealing 
CMS: No selfhealing 
Erasability 
CMS: 0 - Erasable (can be erased, unconditional) 
Redetected degradation 
CMS: No degradation 
Warning lamp 
CMS: No warning lamp 
Direct degradation 
CMS: No degradation 
Validation 
0 
Invalidation 
0 
 
 

"""

negative_output = """
has_error_details= No
reason = "the input does not contain any error details"
"""

positive_input = """
4.37 A03D Permanent electrical fault reported by actuator for defrost 
(M59)
Implemented:
True
Enabled:
True
Order:
PRIMARY
Internal:
False
Classification:
FAULT
SAE J1939­73:
False
SPN:
 
FMI:
 
Heading
Permanent electrical fault reported by actuator for defrost (M59)
Detection
The cab comfort unit (E186) has detected the actuator reports an error.
Cause
The actuator has a permanent electrial fault.
System Reaction
The air dist/defrost flap will not function. It will not be possible to change the defrost air distribution from the current 
setting
Symptom
The air dist/defrost flap will not function. It will not be possible to change the defrost air distribution from the current 
setting
Action
Check the cable harness for the air dist/defrost motor, if no fault is found, replace the air dist/defrost motor.This unit 
is connected to the climate control system via a LIN­bus. If one of the units on the LIN­bus is faulty it can affect the 
other units further down the same communication line.
Calibration
"""

positive_output = """
has_error_details= Yes
reason = "the input contains error details such as error_code, components, heading, detection, cause, system_reaction, symptom"
"""

extraction_example_good_input = """
{"error_code":"0296","components":"BCI interface for air suspension control","heading":"The BCI interface air suspension controls have been active too long.","detection":"At least one signal from BCI interface for air suspension control has been active too long and is seen as implausible.","cause":"- The switch is stuck in pressed position.\n- The switch or remote control is broken.\n- The remote control sends corrupt information regarding switch status.","system_reaction":"The signal is ignored as long as the fault is present. The signal is no longer ignored and the DTC is set to inactive if the fault is not present for at least 1 second.","symptom":""}
"""

extraction_example_good_output = """
approved = yes
reason = The error_code looks correct
"""

extraction_example_bad_input = """
{"error_code":"4.85 0296","components":"Invalidation","heading":"","cause":"Redetected degradation","system_reaction":"CMS: 0 - Erasable (can be erased, unconditional","symptom":""}
"""

extraction_example_good_output = """
approved = no
reason = The error_code should be a single string
"""

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


class ErrorCode(BaseModel):
    error_code: str = Field(..., description="The error code of the component")
    component: str = Field(..., description="The component")


class ErrorExistanceCompletion(BaseModel):
    has_error_details: str = Field(
        ...,
        description="yes/no",
    )
    reason: str = Field(..., description="a very short reason for the classification")


class ErrorExtractionCompletion(BaseModel):
    approved: str = Field(
        ...,
        description="yes/no",
    )
    reason: str = Field(..., description="a very short reason for the classification")


class DTCSpecification(BaseModel):
    error_code: str
    components: str
    heading: str
    detection: str
    cause: str
    system_reaction: str
    symptom: str


class State(TypedDict):
    components: list
    error_classification_evaluation: ErrorExistanceCompletion
    error_extraction_evaluation: ErrorExtractionCompletion
    dtc_specification: DTCSpecification
    page_text: str
    attempt: int


def extract_error_codes(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": f"""You are a error code expert, give a page text data please extract the error code information.
                The error code has the following structure:
                
                error_code: The error code of the component
                components: The component(s) of the error code
                heading: The heading of the error code
                detection: The detection of the error code
                cause: The cause of the error code
                system_reaction: The system reaction of the error code
                symptom: The symptom of the error code

                Example Input:
                {example_errorcode_input}

                Example Output:
                {example_errorcode_output}""",
            },
            {
                "role": "user",
                "content": f"""
                "page_text": {state["page_text"]}""",
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.5,
        extra_body={"guided_json": DTCSpecification.model_json_schema(), "top_p": 0.9},
    )
    dtc_specification = DTCSpecification.model_validate_json(
        response.choices[0].message.content
    )

    return {"dtc_specification": dtc_specification, "attempt": state["attempt"] + 1}


def verify_error_presence(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """You are a error code expert, you will receive text from a page and you have to classify if the page has an error data and if it has, you have to say yes or no and provide a reason for your decision.

                Make sure to check if the input has the following fields:
                error_code, components, heading, detection, cause, system_reaction, symptom.

                You can safely ignore a page which just has a list of error codes without all the fields, it's very likely that it's a listing page.

                Example Input:
                {negative_input}
                Example Output:
                {negative_output}

                Example Input:
                {positive_input}
                Example Output:
                {positive_output}""",
            },
            {
                "role": "user",
                "content": f""" "page_text": {state["page_text"]}
                """,
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.5,
        extra_body={
            "guided_json": ErrorExistanceCompletion.model_json_schema(),
            "top_p": 0.9,
        },
    )
    error_classification_evaluation = ErrorExistanceCompletion.model_validate_json(
        response.choices[0].message.content
    )

    return {"error_classification_evaluation": error_classification_evaluation}


def route_error_code_classification(state: State):
    if state["error_classification_evaluation"].has_error_details.lower() == "yes":
        return "Has Error Details"
    else:
        return "No Error Details"


def route_error_code_extraction(state: State):
    if state["error_extraction_evaluation"].approved.lower() == "yes":
        return "Good Extraction"
    elif state["attempt"] < 3:
        return "Bad Extraction"
    else:
        return "Failed Extraction"


def verify_error_extraction(state: State):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": """
                You are a error code expert, you will receive some details about an error extracted. You have to evaluate if the extraction is good or not and provide a reason for your decision.
                Example Input:
                {extraction_example_good_input}
                Example Output:
                {extraction_example_good_output}

                Example Input:
                {extraction_example_bad_input}
                Example Output:
                {extraction_example_good_output}

                RULES:
                1. Focus mainly on the affected components and the error code.
                2. If some other fields are missing, you can ignore them.

                OUTPUT:
                1. description can only be yes or no
                2. reason should be a very short reason for the classification
                """,
            },
            {
                "role": "user",
                "content": f""" "page_text": {
                    state["dtc_specification"].model_dump_json()
                }""",
            },
        ],
        model="NovaSky-AI/Sky-T1-32B-Flash",
        temperature=0.5,
        extra_body={
            "guided_json": ErrorExtractionCompletion.model_json_schema(),
            "top_p": 0.9,
        },
    )
    error_extraction_evaluation = ErrorExtractionCompletion.model_validate_json(
        response.choices[0].message.content
    )

    return {"error_extraction_evaluation": error_extraction_evaluation}


def mark_failed_extraction(state: State):
    return {
        "error_extraction_evaluation": {"approved": "no", "reason": "Failed to extract"}
    }


components_builder = StateGraph(State)

# Add the nodes
components_builder.add_node("extract_error_codes", extract_error_codes)
components_builder.add_node("verify_error_presence", verify_error_presence)
components_builder.add_node("verify_error_extraction", verify_error_extraction)
components_builder.add_node("mark_failed_extraction", mark_failed_extraction)

components_builder.add_edge(START, "verify_error_presence")
components_builder.add_conditional_edges(
    "verify_error_presence",
    route_error_code_classification,
    {
        "Has Error Details": "extract_error_codes",
        "No Error Details": END,
    },
)
components_builder.add_edge("extract_error_codes", "verify_error_extraction")
components_builder.add_conditional_edges(
    "verify_error_extraction",
    route_error_code_extraction,
    {
        "Good Extraction": END,
        "Bad Extraction": "extract_error_codes",
        "Failed Extraction": "mark_failed_extraction",
    },
)
components_builder.add_edge("mark_failed_extraction", END)

# Compile the workflow
graph = components_builder.compile()
