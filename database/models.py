from neomodel import (
    config,
    db,
    ArrayProperty,
    StringProperty,
    IntegerProperty,
    UniqueIdProperty,
    StructuredNode,
    JSONProperty,
    RelationshipTo,
    StructuredRel,
    DateTimeProperty,
)
from database.database import driver

config.DATABASE_URL = "bolt://neo4j:password@localhost:7687"  # default


class PhysicalQuantityNode(StructuredNode):
    name = StringProperty(required=True, index=True)
    payload = JSONProperty(required=True)


class FunctionViewNode(StructuredNode):
    name = StringProperty(required=True, index=True)
    payload = JSONProperty(required=True)


class FunctionPropertyGroupNode(StructuredNode):
    name = StringProperty(required=True, index=True)
    payload = JSONProperty(required=True)


class PtComponentNode(StructuredNode):
    name = StringProperty(required=True, index=True)


class AddedPtComponentRel(StructuredRel):
    created_at = DateTimeProperty(default_now=True)


class Inference(StructuredNode):
    uid = UniqueIdProperty()
    ecu = StringProperty(required=False)
    version = IntegerProperty()
    STATUSES = {"P": "Pending", "R": "Running", "C": "Completed", "F": "Failed"}
    TYPES = {"IO": "IOMapping", "FP": "FunctionParameter"}
    type = StringProperty(required=False, choices=TYPES)
    status = StringProperty(required=True, choices=STATUSES)
    messages = ArrayProperty(StringProperty(), required=True)
    webhook_url = StringProperty(required=True)

    # realtionships
    physical_quantities = RelationshipTo(
        "PhysicalQuantityNode", "ADDED_PHYSICAL_QUANTITY"
    )
    function_views = RelationshipTo("FunctionViewNode", "ADDED_FUNCTION_VIEW")
    function_property_groups = RelationshipTo(
        "FunctionPropertyGroupNode", "ADDED_FUNCTION_PROPERTY_GROUP"
    )
    pt_components = RelationshipTo(
        "PtComponentNode", "ADDED_PT_COMPONENT", model=AddedPtComponentRel
    )
