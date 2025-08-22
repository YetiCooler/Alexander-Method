from typing import List

from pathlib import Path
from models.input.physical_quantity import PhysicalQuantity


def load_physical_quantities_from_folder() -> List[PhysicalQuantity]:
    physical_quantities = []
    directory_path = Path("/home/ubuntu/PhysicalQuantity")  
    physical_quantity_files = list(directory_path.glob("*.xml"))
    print(physical_quantity_files)
    physical_quantity_files = [
    file for file in physical_quantity_files if file.name.startswith("PhysicalQuantity")
    ]
    for file in physical_quantity_files:
        try:
            with open(file, "rb") as f:
                xml_data = f.read()
                obj = PhysicalQuantity.from_xml(xml_data)
                physical_quantities.append(obj)
        except Exception as e:
            print(f"❌ Error parsing {file.name}: {e}")
    print(physical_quantities)        
    return physical_quantities
