from threading import RLock
from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field
from queue import Queue
from database.app_state import AppState
from inflow.base_config import BaseConfig
from database.models import Inference


class State(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    inference_type: Literal["IO", "FP"]
    inference: Inference
    server_can: Optional[str] = None
    ecu_system_execution: str
    ecu_system_family: str
    inference_base_folder: str
    update_queue: Queue
    app_state: AppState
    all_base_config_circuits: list
    all_self_server_circuits: list
    all_other_server_circuits: list
    lock: RLock = Field(default_factory=RLock)
    processable_components: dict[str, dict] = {}
    updated_components: list[str] = []
    base_configs: list[BaseConfig] = []
