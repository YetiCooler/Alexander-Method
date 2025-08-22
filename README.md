# Method_Engineer_Support_Tool

## Overview

The **ECU Diagnose Content Processing System** is a powerful framework designed to process circuit diagrams, DTC specifications, system descriptions, and IO lists. The system integrates **Neo4j**, **Qdrant**, and **FastAPI** to enable efficient data extraction, transformation, and storage.

## Features

-   **Circuit Diagram Processing**: Extracts and analyzes circuit components from PDF files.
    
-   **DTC Specification Extraction**: Parses and structures diagnostic trouble codes (DTCs).
    
-   **System Information Processing**: Extracts metadata and component details from system descriptions.
    
-   **IO Mapping and Processing**: Identifies relationships between IO events and system components.
    
-   **Neo4j Graph Database Integration**: Stores component relationships for graph-based querying.
    
-   **Qdrant Vector Database Integration**: Embeds and retrieves components for similarity searches.
    
-   **FastAPI Web Interface**: Provides a REST API for processing requests.
    
-   **Structured Logging**: Logs all processing activities for debugging and monitoring.
    

## Tech Stack

-   **Programming Language**: Python 3.10+
    
-   **Frameworks & Libraries**: FastAPI, Pandas, Pydantic, Langchain, Ollama
    
-   **Databases**: Neo4j (GraphDB), Qdrant (VectorDB)
    
-   **Logging**: Python Logging Module
    

## Directory Structure

```
/
├── config.py                  # Configuration settings
├── main.py                    # FastAPI entry point
├── processor.py                # Core processing logic
├── database/
│   ├── database.py             # Neo4j and Qdrant integration
├── graphs/
│   ├── circuit_extractor.py    # Extracts circuit components
│   ├── dtc_extractor.py        # Extracts DTC information
│   ├── io_processor.py         # Processes IO mapping
│   ├── system_information_extractor.py  # Processes system information
├── inflow/
│   ├── base_config.py          # Parses base configuration
│   ├── io_list.py              # Parses IO list
├── logger.py                   # Logging configuration
├── requirements.txt            # Project dependencies
├── .env.example                # Example environment variables
├── .gitignore                  # Git ignore settings
└── README.md                   # Project documentation
```

## Installation & Setup

### Prerequisites

-   Python 3.10+
    
-   Neo4j installed and running
    
-   Qdrant installed and running
    
-   Pipenv or virtualenv (recommended for dependency management)
    

### Installation Steps

```
# Clone the repository
git clone https://github.com/your-repo/unizen-processing
cd unizen-processing

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # On Windows use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
```

## Running the Application

```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: http://localhost:8000

## API Endpoints

### Process Data

```
GET /
```

Example: 
```
curl --location 'http://127.0.0.1:8000' --header 'Content-Type: application/json' --data '{"ecu": "APS2"}'
```

Response:

```
{
	"zip_file": "zipped execution result"
}
```


## Environment Variables (.env)

Variable

Default Value

Description

`QDRANT_HOST`

localhost

Qdrant database host

`QDRANT_PORT`

6333

Qdrant database port

`NEO4J_CONNECTION`

bolt://localhost:7687

Neo4j connection URL

`NEO4J_USER`

neo4j

Neo4j username

`NEO4J_PASSWORD`

password

Neo4j password

`CIRCUIT_DIAGRAMS_PATH`

./data/input/circuit_diagrams

Path to circuit diagrams

`DTC_SPECIFICATIONS_PATH`

./data/input/dtc_specifications

Path to DTC specifications

`SYSTEM_DESCRIPTIONS_PATH`

./data/input/system_descriptions

Path to system descriptions

`IO_LISTS_PATH`

./data/input/io_lists

Path to IO lists

`BASE_CONFIG_PATH`

./data/input/base_config

Path to base configurations
