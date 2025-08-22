import os
import database.database
from database.models import PtComponentNode


def add_pt_component(file_name: str):
    """
    Takes a file name like PtComponent_B16.xml and extracts the component name and add a entry in the database
    :param file_name: The name of the file to be processed
    :return: None
    """

    # extract the component name from the file name
    component_name = file_name.split("_")[1].split(".")[0]

    pt_node = PtComponentNode(name=component_name)

    pt_node.save()
    print(f"PtComponent added to the database: {component_name}")


if __name__ == "__main__":
    # take the folder name argument from the command line
    import sys

    path = sys.argv[1]

    # recursively find all the files in the folder which match the pattern PtComponent_*.xml
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.startswith("PtComponent_") and file.endswith(".xml"):
                # call the add_pt_component function
                print(f"Processing file: {file}")
                add_pt_component(file)
