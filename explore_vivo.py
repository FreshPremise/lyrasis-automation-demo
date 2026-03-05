"""
Explore VIVO API - understand the data model and how to create records
"""
import requests
import uuid

# Load from config.py if it exists
try:
    from config import VIVO_URL, VIVO_EMAIL as EMAIL, VIVO_PASSWORD as PASSWORD, VIVO_NAMESPACE as NAMESPACE, VIVO_GRAPH as GRAPH
except ImportError:
    VIVO_URL = "http://localhost:8082"
    EMAIL = "your-email@example.com"
    PASSWORD = "your-password"
    NAMESPACE = "http://vivo.mydomain.edu/individual/"
    GRAPH = "http://vitro.mannlib.cornell.edu/default/vitro-kb-2"

def sparql_query(query):
    """Execute a SPARQL query against VIVO"""
    url = f"{VIVO_URL}/api/sparqlQuery"
    data = {
        "email": EMAIL,
        "password": PASSWORD,
        "query": query
    }
    response = requests.post(url, data=data)
    return response.text

def sparql_update(update):
    """Execute a SPARQL UPDATE against VIVO"""
    url = f"{VIVO_URL}/api/sparqlUpdate"
    data = {
        "email": EMAIL,
        "password": PASSWORD,
        "update": update
    }
    response = requests.post(url, data=data)
    return response.status_code, response.text

def create_person(first_name, last_name, uri=None):
    """Create a Person in VIVO"""
    if uri is None:
        uri = f"{NAMESPACE}person-{uuid.uuid4().hex[:8]}"

    full_name = f"{first_name} {last_name}"

    update = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX vivo: <http://vivoweb.org/ontology/core#>
PREFIX obo: <http://purl.obolibrary.org/obo/>

INSERT DATA {{
    GRAPH <{GRAPH}> {{
        <{uri}> a foaf:Person ;
            rdfs:label "{full_name}" ;
            obo:ARG_2000028 <{uri}-vcard> .
        <{uri}-vcard> a <http://www.w3.org/2006/vcard/ns#Individual> ;
            <http://www.w3.org/2006/vcard/ns#hasName> <{uri}-vcard-name> .
        <{uri}-vcard-name> a <http://www.w3.org/2006/vcard/ns#Name> ;
            <http://www.w3.org/2006/vcard/ns#givenName> "{first_name}" ;
            <http://www.w3.org/2006/vcard/ns#familyName> "{last_name}" .
    }}
}}
"""
    status, result = sparql_update(update)
    return uri, status, result

def create_dataset(title, description=None, uri=None, related_person_uri=None, dspace_url=None, archivesspace_url=None):
    """Create a Dataset in VIVO with optional links to other systems"""
    if uri is None:
        uri = f"{NAMESPACE}dataset-{uuid.uuid4().hex[:8]}"

    # Build the INSERT statement
    triples = f"""
        <{uri}> a <http://vivoweb.org/ontology/core#Dataset> ;
            rdfs:label "{title}" """

    if description:
        # Escape quotes in description
        desc_escaped = description.replace('"', '\\"')
        triples += f""";
            <http://purl.org/ontology/bibo/abstract> "{desc_escaped}" """

    if dspace_url:
        triples += f""";
            <http://vivoweb.org/ontology/core#hasURL> <{uri}-dspace-link> .
        <{uri}-dspace-link> a <http://vivoweb.org/ontology/core#URLLink> ;
            rdfs:label "DSpace Record" ;
            <http://vivoweb.org/ontology/core#linkURI> "{dspace_url}" """

    if archivesspace_url:
        triples += f""";
            <http://vivoweb.org/ontology/core#hasURL> <{uri}-as-link> .
        <{uri}-as-link> a <http://vivoweb.org/ontology/core#URLLink> ;
            rdfs:label "ArchivesSpace Record" ;
            <http://vivoweb.org/ontology/core#linkURI> "{archivesspace_url}" """

    triples += " ."

    update = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX vivo: <http://vivoweb.org/ontology/core#>
PREFIX bibo: <http://purl.org/ontology/bibo/>

INSERT DATA {{
    GRAPH <{GRAPH}> {{
        {triples}
    }}
}}
"""
    status, result = sparql_update(update)
    return uri, status, result

def delete_resource(uri):
    """Delete a resource and its related triples"""
    update = f"""
DELETE WHERE {{
    GRAPH <{GRAPH}> {{
        <{uri}> ?p ?o .
    }}
}}
"""
    status, result = sparql_update(update)
    return status, result

# Test: Create a person
print("=" * 60)
print("Creating a test Person")
print("=" * 60)
person_uri, status, result = create_person("Steve", "Automation")
print(f"Person URI: {person_uri}")
print(f"Status: {status}")
if status != 200:
    print(f"Error: {result[:500]}")

# Verify person was created
print("\n" + "=" * 60)
print("Verify Person was created")
print("=" * 60)
query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?person ?label WHERE {
    ?person a foaf:Person .
    ?person rdfs:label ?label .
}
"""
print(sparql_query(query))

# Test: Create a Dataset with links
print("\n" + "=" * 60)
print("Creating a test Dataset with cross-system links")
print("=" * 60)
dataset_uri, status, result = create_dataset(
    title="Test Digital Image Collection",
    description="A test dataset representing digitized archival materials",
    dspace_url="http://localhost:4000/items/test-123",
    archivesspace_url="http://localhost/staff/resolve/readonly?uri=/repositories/2/digital_objects/1"
)
print(f"Dataset URI: {dataset_uri}")
print(f"Status: {status}")
if status != 200:
    print(f"Error: {result[:500]}")

# Verify dataset was created
print("\n" + "=" * 60)
print("Verify Dataset was created")
print("=" * 60)
query2 = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX vivo: <http://vivoweb.org/ontology/core#>

SELECT ?dataset ?label WHERE {
    ?dataset a vivo:Dataset .
    ?dataset rdfs:label ?label .
}
"""
print(sparql_query(query2))

# Get all properties of the dataset
print("\n" + "=" * 60)
print("Dataset properties")
print("=" * 60)
query3 = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?p ?o WHERE {{
    <{dataset_uri}> ?p ?o .
}}
"""
print(sparql_query(query3))

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print(f"""
VIVO API Test Results:
- Person created: {person_uri}
- Dataset created: {dataset_uri}

The Dataset class in VIVO is ideal for our automation workflow.
We can create a Dataset for each image/collection and link it to:
- DSpace item URL
- ArchivesSpace digital object URL

Next step: Create import_to_trio.py that extends the existing workflow.
""")
