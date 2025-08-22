from typing import List
from neo4j import GraphDatabase
import uuid
from qdrant_client import QdrantClient, models
import ollama

from database.app_state import AppState
from config import (
    neo4j_connection,
    neo4j_user,
    neo4j_password,
    qdrant_host,
    qdrant_port,
)

from models.input.physical_quantity import PhysicalQuantity
from utils import get_tokens

# Initialize Qdrant client
qclient = QdrantClient(host=qdrant_host, port=int(qdrant_port))
COLLECTION_NAME = "components"

# Initialize Ollama client
oclient = ollama.Client(host="localhost:11434")

# Create a vector for the Component node
response = oclient.embeddings(model="nomic-embed-text", prompt="Hello, world")
embeddings = response["embedding"]

# Create a collection if it doesn't already exist
if not qclient.collection_exists(COLLECTION_NAME):
    qclient.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=len(embeddings), distance=models.Distance.COSINE
        ),
    )


# Create a collection if it doesn't already exist for function groups

FG_COLLECTION_NAME = "function_groups"

if not qclient.collection_exists(FG_COLLECTION_NAME):
    qclient.create_collection(
        collection_name=FG_COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=len(embeddings), distance=models.Distance.COSINE
        ),
    )


def get_dense_vector(document):
    """
    Convert sparse vector to dense format.
    """
    response = oclient.embeddings(
        model="nomic-embed-text", prompt=" ".join(get_tokens(document))
    )
    embeddings = response["embedding"]

    return embeddings


def get_matching_components(name, ecu_system, data):
    print("data: ", data, "name: ", name, "ecu_system: ", ecu_system)
    embeddings_response = oclient.embeddings(
        model="nomic-embed-text", prompt=" ".join(get_tokens(data))
    )
    embeddings = embeddings_response["embedding"]
    response = qclient.query_points(
        collection_name=COLLECTION_NAME,
        query=embeddings,
        score_threshold=0.5,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="ecu_system",
                    match=models.MatchValue(
                        value=ecu_system,
                    ),
                )
            ]
        ),
    )

    return response.points


def delete_component_vector(name, ecu_system):
    points, _ = qclient.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="name",
                    match=models.MatchValue(value=name),
                ),
                models.FieldCondition(
                    key="ecu_system",
                    match=models.MatchValue(value=ecu_system),
                ),
            ]
        ),
    )
    if len(points) > 0:
        qclient.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(
                points=[point.id for point in points],
            ),
        )


def create_component_vector(name, description, ecu_system):
    # let's delete the existing vector if it exists
    delete_component_vector(name, ecu_system)
    # create a new vector
    response = oclient.embeddings(
        model="nomic-embed-text", prompt=" ".join(get_tokens(name + "\n" + description))
    )
    embeddings = response["embedding"]

    qclient.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings,
                payload={
                    "name": name,
                    "description": description,
                    "type": "Component",
                    "ecu_system": ecu_system,
                },
            )
        ],
    )


driver = GraphDatabase.driver(
    neo4j_connection, auth=(neo4j_user, neo4j_password), encrypted=False
)

with driver.session() as session:
    result = session.run("RETURN 'Neo4j Connection Successful' AS message")
    for record in result:
        print(record["message"])


# Function to create a Component node with multiple fields
def create_component(tx, name, description, ecu_system):
    query = """
    MERGE (c:Component {name: $name, ecu_system: $ecu_system})
    SET c.description = $description, c.exported = false
    """
    tx.run(
        query,
        name=name,
        description=description,
        ecu_system=ecu_system,
    )
    # save the same component as a vector in Qdrant
    create_component_vector(name, description, ecu_system)


def mark_component_as_exported(tx, name, ecu_system):
    query = """
    MATCH (c:Component {name: $name, ecu_system: $ecu_system})
    SET c.exported = true
    """
    tx.run(query, name=name, ecu_system=ecu_system)


def mark_component_as_not_exported(tx, name, ecu_system):
    query = """
    MATCH (c:Component {name: $name, ecu_system: $ecu_system})
    SET c.exported = false
    """
    tx.run(query, name=name, ecu_system=ecu_system)


def get_component(tx, name, ecu_system):
    query = """
    MATCH (c:Component {name: $name, ecu_system: $ecu_system})
    RETURN c.name AS name, c.description AS description, c.exported AS exported
    """
    result = tx.run(query, name=name, ecu_system=ecu_system)
    # return the first record
    return result.single()


# Function to add additional fields to an existing component (or create if it doesn't exist)
def add_component_fields(
    tx,
    name,
    more_description,
    purpose,
    ecu_system,
):
    query = """
    MERGE (c:Component {name: $name, ecu_system: $ecu_system})
    SET c.purpose = $purpose, c.more_description = $more_description, c.exported = false
    """
    tx.run(
        query,
        name=name,
        more_description=more_description,
        purpose=purpose,
        ecu_system=ecu_system,
    )
    # save the same component as a vector in Qdrant
    # create_component_vector(
    #     name, description + "\n" + more_description + "\n" + purpose, ecu_system
    # )


# Function to create a Component node with multiple fields
def create_component_meta(tx, name, meta_description, file_id, ecu_system):
    # create a ComponentMeta node and link it to the Component node
    query = """
    MATCH (c:Component {name: $name, ecu_system: $ecu_system})
    MERGE (cm:ComponentMeta {meta_description: $meta_description, file_id: $file_id})
    MERGE (c)-[:HAS_META]->(cm)
    """
    tx.run(
        query,
        name=name,
        meta_description=meta_description,
        file_id=file_id,
        ecu_system=ecu_system,
    )


def get_component_meta(tx, name, ecu_system):
    query = """
    MATCH (c:Component {name: $name, ecu_system: $ecu_system})
    MATCH (c)-[:HAS_META]->(cm:ComponentMeta)
    RETURN c.name AS name, collect(cm.meta_description) AS meta_description
    """
    result = tx.run(query, name=name, ecu_system=ecu_system)
    return [record for record in result]


def get_dtc_with_components(tx, ecu_system, excluded_components):
    query = """
    MATCH (d:DTC {ecu_system: $ecu_system})-[:AFFECTS]->(c:Component {ecu_system: $ecu_system})
    WHERE c.name IS NULL OR NOT c.name IN $excluded_components
    RETURN DISTINCT d.dtc_code AS dtc_code, d.heading AS heading, d.components AS components,
                    d.detection AS detection, d.cause AS cause, d.system_reaction AS system_reaction,
                    d.symptom AS symptom, c.name AS component_name
    """
    return [
        record
        for record in tx.run(
            query, ecu_system=ecu_system, excluded_components=excluded_components
        )
    ]


def get_all_components(tx, ecu_system):
    query = """
    MATCH (c:Component {ecu_system: $ecu_system})
    RETURN c.name AS name, c.description AS description, c.file_id AS file_id,
    c.purpose AS purpose, c.more_description AS more_description
    """
    return [record for record in tx.run(query, ecu_system=ecu_system)]


def create_dtc(
    tx,
    dtc_code,
    heading,
    components,
    detection,
    cause,
    system_reaction,
    symptom,
    ecu_system,
):
    query = """
    MERGE (:DTC {dtc_code: $dtc_code, heading: $heading, components: $components, detection: $detection, cause: $cause, system_reaction: $system_reaction, symptom: $symptom, ecu_system: $ecu_system})
    """
    tx.run(
        query,
        dtc_code=dtc_code,
        heading=heading,
        components=components,
        detection=detection,
        cause=cause,
        system_reaction=system_reaction,
        symptom=symptom,
        ecu_system=ecu_system,
    )


def create_relationship_if_component_exists(
    tx, dtc_code, component_name, relationship_type, ecu_system
):
    query = (
        """
    MATCH (d:DTC {dtc_code: $dtc_code, ecu_system: $ecu_system}), (c:Component {name: $component_name, ecu_system: $ecu_system})
    MERGE (d)-[r:`"""
        + relationship_type
        + """`]->(c)
    RETURN d, r, c
    """
    )
    tx.run(
        query, dtc_code=dtc_code, component_name=component_name, ecu_system=ecu_system
    )


def save_app_state(tx, app_state: AppState):
    """
    Saves an AppState instance to Neo4j:
    - Uses 'hash' as the unique key.
    - Stores 'file_name' as metadata.
    - Stores 'ecu_system' as metadata.
    - Links files to AppState.
    """

    # Ensure AppState node exists
    tx.run("MERGE (:AppState)")

    # Helper function to save and link file nodes
    def save_files(file_list, node_type, relationship):
        if file_list:
            # Separate creation (MERGE) and setting of optional properties
            query = f"""
            UNWIND $file_list AS file_entry
            MERGE (f:{node_type} {{hash: file_entry.hash}})
            SET f.file_name = file_entry.file_name
            FOREACH (_ IN CASE WHEN file_entry.ecu_system IS NOT NULL THEN [1] ELSE [] END |
                SET f.ecu_system = file_entry.ecu_system
            )
            MERGE (a:AppState)
            MERGE (a)-[:{relationship}]->(f)
            """
            tx.run(query, file_list=file_list)

    # Save different file types
    save_files(app_state.circuit_diagrams, "CircuitDiagram", "HAS_CIRCUIT")
    save_files(
        app_state.system_descriptions, "SystemInformation", "HAS_SYSTEM_DESCRIPTION"
    )
    save_files(
        app_state.dtc_specifications, "DTCSpecification", "HAS_DTC_SPECIFICATION"
    )
    save_files(app_state.io_list_files, "IOList", "HAS_IO_LIST")


def get_app_state(tx) -> AppState:
    """
    Fetches AppState from Neo4j and returns an AppState object.
    Filters out NULL values to prevent None entries.
    """
    query = """
    MATCH (a:AppState)
    OPTIONAL MATCH (a)-[:HAS_CIRCUIT]->(c:CircuitDiagram)
    OPTIONAL MATCH (a)-[:HAS_SYSTEM_DESCRIPTION]->(s:SystemInformation)
    OPTIONAL MATCH (a)-[:HAS_DTC_SPECIFICATION]->(d:DTCSpecification)
    OPTIONAL MATCH (a)-[:HAS_IO_LIST]->(i:IOList)
    RETURN 
        [entry IN COLLECT(DISTINCT {hash: c.hash, file_name: c.file_name, ecu_system: c.ecu_system }) WHERE entry.hash IS NOT NULL] AS circuit_diagrams,
        [entry IN COLLECT(DISTINCT {hash: s.hash, file_name: s.file_name, ecu_system: c.ecu_system }) WHERE entry.hash IS NOT NULL] AS system_descriptions,
        [entry IN COLLECT(DISTINCT {hash: d.hash, file_name: d.file_name, ecu_system: c.ecu_system }) WHERE entry.hash IS NOT NULL] AS dtc_specifications,
        [entry IN COLLECT(DISTINCT {hash: i.hash, file_name: i.file_name, ecu_system: c.ecu_system }) WHERE entry.hash IS NOT NULL] AS io_list_files
    """
    result = tx.run(query).single()

    return AppState(
        circuit_diagrams=result["circuit_diagrams"],
        system_descriptions=result["system_descriptions"],
        dtc_specifications=result["dtc_specifications"],
        io_list_files=result["io_list_files"],
    )


def link_component_to_system(
    tx, component_name: str, system_description_hash: str, ecu_system: str
):
    """
    Links a Component to a SystemInformation node with a HAS_BEEN_CHECKED_IN relationship.

    :param tx: Neo4j transaction
    :param component_name: Name of the component
    :param system_description_hash: Hash of the SystemInformation to link to
    :param ecu_system: The ECU system identifier
    """
    query = """
    MERGE (c:Component {name: $component_name, ecu_system: $ecu_system})
    MERGE (s:SystemInformation {hash: $system_description_hash, ecu_system: $ecu_system})
    MERGE (c)-[:HAS_BEEN_CHECKED_IN]->(s)
    """
    tx.run(
        query,
        component_name=component_name,
        system_description_hash=system_description_hash,
        ecu_system=ecu_system,
    )


def find_unlinked_components(tx, system_description_hash: str, ecu_system: str):
    """
    Finds all components within a given ecu_system that have NOT been checked into
    the SystemInformation with the given hash.

    :param tx: Neo4j transaction
    :param system_description_hash: Hash of the target SystemInformation
    :param ecu_system: The ECU system identifier
    :return: List of component names
    """
    query = """
    MATCH (c:Component {ecu_system: $ecu_system})
    OPTIONAL MATCH (s:SystemInformation {hash: $system_description_hash, ecu_system: $ecu_system})
    WITH c, s
    WHERE s IS NULL OR NOT (c)-[:HAS_BEEN_CHECKED_IN]->(s)
    RETURN c.name AS component_name
    """
    result = tx.run(
        query, system_description_hash=system_description_hash, ecu_system=ecu_system
    )
    return [record["component_name"] for record in result]


def link_component_to_circuit_diagram(
    tx, component_name: str, circuit_diagram_hash: str, ecu_system: str
):
    """
    Links a Component to a CircuitDiagram node with a HAS_BEEN_CHECKED_IN relationship.

    :param tx: Neo4j transaction
    :param component_name: Name of the component
    :param circuit_diagram_hash: Hash of the CircuitDiagram to link to
    :param ecu_system: The ECU system identifier
    """
    query = """
    MERGE (c:Component {name: $component_name, ecu_system: $ecu_system})
    MERGE (cd:CircuitDiagram {hash: $circuit_diagram_hash, ecu_system: $ecu_system})
    MERGE (c)-[:HAS_BEEN_EXTRACTED_FROM]->(cd)
    """
    tx.run(
        query,
        component_name=component_name,
        circuit_diagram_hash=circuit_diagram_hash,
        ecu_system=ecu_system,
    )


# Function to create a Component node with multiple fields
def create_io(tx, name, description, name_representation, ecu_system):
    # create a ComponentMeta node and link it to the Component node
    query = """
    MERGE (c:IO {
        name: $name, ecu_system: $ecu_system, name_representation: $name_representation, description: $description
    })
    """
    tx.run(
        query,
        name=name,
        description=description,
        name_representation=name_representation,
        ecu_system=ecu_system,
    )


def create_io_mapping_with_component(tx, io_name, component_name, ecu_system):
    query = """
    MATCH (io:IO {name: $io_name, ecu_system: $ecu_system})
    MATCH (c:Component {name: $component_name, ecu_system: $ecu_system})
    MERGE (io)-[:MAPPED_TO]->(c)
    """
    tx.run(query, io_name=io_name, component_name=component_name, ecu_system=ecu_system)


def update_io_file_io_mapping(tx, io_name, file_id, ecu_system):
    query = """
    MATCH (io:IO {name: $io_name, ecu_system: $ecu_system})
    MATCH (f:IOList {file_id: $file_id, ecu_system: $ecu_system})
    MERGE (f)-[:CONTAINS]->(io)
    """
    tx.run(query, io_name=io_name, file_id=file_id, ecu_system=ecu_system)

def store_physical_quantity(tx, pq: PhysicalQuantity):
    tx.run("""
        MERGE (pq:PhysicalQuantity {name: $name})
        SET pq.namePresentation = $name_presentation,
            pq.standardUnit = $standard_unit_value,
            pq.standardUnitRef = $standard_unit_ref

        WITH pq
        UNWIND $units AS unit
            MERGE (u:Unit {name: unit.name})
            SET u.namePresentation = unit.name_presentation,
                u.factor = unit.factor
            MERGE (pq)-[:HAS_UNIT]->(u)
    """,
    name=pq.name,
    name_presentation=pq.namePresentation.value,
    standard_unit_value=pq.standardUnit.value,
    standard_unit_ref=pq.standardUnit.ref,
    units=[{
        "name": u.name,
        "name_presentation": u.namePresentation.value,
        "factor": u.factor
    } for u in pq.unit])
    
def save_ecu_family(tx, family, system, server):
    tx.run("""
        MERGE (f:ECUFamily {name: $family})
        MERGE (s:ECUSystem {name: $system})
        MERGE (v:Server {code: $server})
        MERGE (f)-[:HAS_SYSTEM]->(s)
        MERGE (s)-[:USES_SERVER]->(v)
    """, family=family, system=system, server=server)   
    
def get_physical_quantity_by_unit(tx,unit_name: str) -> List[str]:
    query = """
        MATCH (u:Unit {name: $unit_name})<-[:HAS_UNIT]-(pq:PhysicalQuantity)
        RETURN pq.name AS physical_quantity_name
        """
    result = tx.run(query, unit_name=unit_name)
    results = [record["physical_quantity_name"] for record in result]
    return results 

def get_ecu_info(tx, ecu_system_name):
    query = """
    MATCH (family:ECUFamily)-[:HAS_SYSTEM]->(system:ECUSystem {name: $system_name})
    MATCH (system)-[:USES_SERVER]->(server:Server)
    RETURN family.name AS family, system.name AS system, server.code AS server
    """
    result = tx.run(query, system_name=ecu_system_name)
    return result.single()