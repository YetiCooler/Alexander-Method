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

class PhysicalQuantitySelection(BaseModel):
    PhysicalQuantity: str
    IODescription: str
    
def select_physical_quantity_description_for_io(
    io_name: str,
    unit: str,
    ecu_family: str,
    ecu_system: str,
    physical_quantities: str,
) -> PhysicalQuantitySelection:
    chat_response = client.chat.completions.create(
         model="NovaSky-AI/Sky-T1-32B-Flash",
        messages=[
            {
                "role": "system",
                "content": """
You are a vehicle diagnostics configuration expert.

Your task is to:
1. Select the most appropriate Physical Quantity for the given IO.
2. Provide a short human-readable description of the context of the ECU.

---

### Selection Rules:
- The selected Physical Quantity must support the declared unit.
- Prefer general-purpose Physical Quantities unless the IO or ECU context clearly requires specialization.
- Consider the ECU Family and System to determine physical context (e.g., TPM = Tire Pressure Monitoring, EMS = Engine).
- Avoid unnecessary unit conversions.
- Interpret IO names using patterns (e.g., "RefPressure" likely means reference pressure).
- Provide only one Physical Quantity.
- Keep the IO description short and clear (1–2 sentences).

### Output format (strictly JSON):
{
  "PhysicalQuantity": "<best_match_here>",
  "IODescription": "<short_description_here>"
}
"""
            },
            {
                "role": "user",
                "content": f"""
IO Name: {io_name}  
Declared Unit: {unit}  
ECU Family: {ecu_family}  
ECU System: {ecu_system}  
Available Physical Quantities: {physical_quantities}
"""
            }
        ],
        temperature=0,
        extra_body={
            "guided_json": PhysicalQuantitySelection.model_json_schema(),
            "top_p": 1
        }
    )

    return PhysicalQuantitySelection.model_validate_json(
        chat_response.choices[0].message.content  # type: ignore
    )
