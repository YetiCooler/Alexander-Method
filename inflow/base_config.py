import hashlib
import os
import re
from xmltodict import parse


class BaseConfig:
    base_config_circuits: list[str] = []
    base_config: None | dict = None
    other_server_circuits: list[str] = []
    hero_circuits: list[str] = []
    server_can: None | str = None
    id: None | str = None
    filename: None | str = None
    file_hash: None | str = None

    """
    Class Representing the Base Configuration loaded from the xml file.
    """

    def __init__(self, filename: str):
        with open(filename, "r") as file:
            self.filename = os.path.basename(filename)
            file_content = file.read()
            self.base_config = parse(file_content)
            self.file_hash = hashlib.md5(file_content.encode()).hexdigest()

            match = re.search(r"_(\d+)-", filename)
            if match:
                self.id = match.group(1)

            if "BaseConfiguration" in self.base_config["PtConfigSet"]:
                if "CircuitRef" in self.base_config["PtConfigSet"]["BaseConfiguration"]:
                    for circuit in self.base_config["PtConfigSet"]["BaseConfiguration"][
                        "CircuitRef"
                    ]:
                        self.base_config_circuits.append(circuit["#text"])

            if (
                "ServerConfiguration" in self.base_config["PtConfigSet"]
                and type(self.base_config["PtConfigSet"]["ServerConfiguration"]) == list
            ):
                for server_config in self.base_config["PtConfigSet"][
                    "ServerConfiguration"
                ]:
                    if "Hero" in server_config["DisplayName"]:
                        if (
                            "CircuitRef" in server_config
                            and type(server_config["CircuitRef"]) == list
                        ):
                            for circuit in server_config["CircuitRef"]:
                                self.hero_circuits.append(circuit["#text"])
                        elif "CircuitRef" in server_config:
                            self.hero_circuits.append(
                                server_config["CircuitRef"]["#text"]
                            )

                        if (
                            "CircuitRef" in server_config
                            and type(server_config["CircuitRef"]) == list
                        ):
                            for circuit in server_config["CircuitRef"]:
                                self.other_server_circuits.append(circuit["#text"])
                        elif "CircuitRef" in server_config:
                            self.other_server_circuits.append(
                                server_config["CircuitRef"]["#text"]
                            )

            elif "ServerConfiguration" in self.base_config["PtConfigSet"]:
                if (
                    "Hero"
                    in self.base_config["PtConfigSet"]["ServerConfiguration"][
                        "DisplayName"
                    ]
                ):
                    if (
                        "CircuitRef"
                        in self.base_config["PtConfigSet"]["ServerConfiguration"]
                    ):
                        for cicuit in self.base_config["PtConfigSet"][
                            "ServerConfiguration"
                        ]["CircuitRef"]:
                            self.hero_circuits.append(cicuit["#text"])

                else:
                    if (
                        "CircuitRef"
                        in self.base_config["PtConfigSet"]["ServerConfiguration"]
                    ):
                        for cicuit in self.base_config["PtConfigSet"][
                            "ServerConfiguration"
                        ]["CircuitRef"]:
                            self.other_server_circuits.append(cicuit["#text"])

            if "Server" in self.base_config["PtConfigSet"]:
                self.server_can = self.base_config["PtConfigSet"]["Server"]["#text"]
        # remove duplicates
        self.base_config_circuits = list(set(self.base_config_circuits))
        self.other_server_circuits = list(set(self.other_server_circuits))
        self.hero_circuits = list(set(self.hero_circuits))
