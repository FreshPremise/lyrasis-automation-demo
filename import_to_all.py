"""
Unified Import Script: Creates records in DSpace, ArchivesSpace, VIVO, Fedora, AND CollectionSpace
Usage: python import_to_all.py <image_folder> [--prefix "Demo - "] [--caption]

Demonstrates Community Supported Software working together:
1. Optionally runs AI captioning via LM Studio (--caption flag)
2. Reads captions.csv and creates records in all five systems with cross-links
3. All systems run locally via Docker - nothing uploaded externally

Systems:
- DSpace (port 8081/4000) - Digital repository
- ArchivesSpace (port 8089/80) - Archival description
- VIVO (port 8082) - Research networking
- Fedora (port 8083) - Linked data repository
- CollectionSpace (port 8180) - Museum collections (photographic prints)
"""

import argparse
import csv
import requests
from requests.auth import HTTPBasicAuth
import os
import sys
import time
import subprocess
import socket
import uuid
import functools
from pathlib import Path
from urllib.parse import quote


# --- RETRY DECORATOR ---
def retry_on_failure(max_retries=2, delay=2):
    """Decorator to retry a function on failure."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"    Retry {attempt + 1}/{max_retries}: {e}")
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator

# --- CONFIGURATION ---
# Load from config.py if it exists, otherwise use defaults
try:
    from config import *
except ImportError:
    print("Warning: config.py not found. Copy config.example.py to config.py and update credentials.")
    print("Using default placeholder values - authentication will fail.")

    # DSpace (port 8081)
    DSPACE_API_URL = "http://localhost:8081/server/api"
    DSPACE_UI_URL = "http://localhost:4000"
    DSPACE_EMAIL = "your-email@example.com"
    DSPACE_PASSWORD = "your-password"
    DSPACE_COMMUNITY_NAME = "My Image Collection"
    DSPACE_COLLECTION_NAME = "2025 Images"

    # ArchivesSpace (port 8089)
    AS_API_URL = "http://localhost:8089"
    AS_USERNAME = "admin"
    AS_PASSWORD = "admin"
    AS_REPO_ID = 2

    # VIVO (port 8082)
    VIVO_URL = "http://localhost:8082"
    VIVO_EMAIL = "your-email@example.com"
    VIVO_PASSWORD = "your-password"
    VIVO_NAMESPACE = "http://vivo.mydomain.edu/individual/"
    VIVO_GRAPH = "http://vitro.mannlib.cornell.edu/default/vitro-kb-2"

    # Fedora (port 8083)
    FEDORA_URL = "http://localhost:8083/fcrepo/rest"
    FEDORA_USERNAME = "your-email@example.com"
    FEDORA_PASSWORD = "your-password"

    # CollectionSpace (port 8180)
    CSPACE_URL = "http://localhost:8180/cspace-services"
    CSPACE_UI_URL = "http://localhost:8180/cspace/core"
    CSPACE_USERNAME = "admin@core.collectionspace.org"
    CSPACE_PASSWORD = "Administrator"

    # Photographer Information
    PHOTOGRAPHER_URI = "http://vivo.mydomain.edu/individual/photographer"
    PHOTOGRAPHER_NAME = "Photographer Name"
    PHOTOGRAPHER_FIRST = "First"
    PHOTOGRAPHER_LAST = "Last"
    PHOTOGRAPHER_EMAIL = "your-email@example.com"
    PHOTOGRAPHER_LOCATION = "City, State"
    PHOTOGRAPHER_WEBSITES = ["https://www.example.com"]

# File settings
CSV_FILE = "captions.csv"

# Local HTTP server for serving images to ArchivesSpace
LOCAL_IMAGE_SERVER = "http://localhost:8000"
LOCAL_IMAGE_PORT = 8000

# LM Studio for captioning
LMSTUDIO_URL = "http://localhost:1234/v1"


def preflight_check():
    """
    Verify all 5 systems are responding before starting import.
    Returns True if all systems are ready, False otherwise.
    """
    print("\n" + "=" * 70)
    print("PRE-FLIGHT CHECK: Verifying all systems are responding...")
    print("=" * 70)

    services = [
        ("ArchivesSpace API", AS_API_URL, None),
        ("DSpace API", f"{DSPACE_API_URL}/core/communities", None),
        ("VIVO", VIVO_URL, None),
        ("Fedora", f"{FEDORA_URL}/", (FEDORA_USERNAME, FEDORA_PASSWORD)),
        ("CollectionSpace", f"{CSPACE_URL}/collectionobjects", (CSPACE_USERNAME, CSPACE_PASSWORD)),
        ("Image Server", f"{LOCAL_IMAGE_SERVER}/", None),
    ]

    all_ok = True
    for name, url, auth in services:
        try:
            if auth:
                r = requests.get(url, auth=HTTPBasicAuth(*auth), timeout=10)
            else:
                r = requests.get(url, timeout=10)

            # Image server returns 403 for directory listing, which is OK
            if r.status_code in [200, 403]:
                print(f"  [OK]   {name}")
            else:
                print(f"  [FAIL] {name} - HTTP {r.status_code}")
                all_ok = False
        except requests.RequestException as e:
            print(f"  [FAIL] {name} - {e}")
            all_ok = False

    print("-" * 70)

    if all_ok:
        print("All systems ready!")
        return True
    else:
        print("\nSome systems are not responding.")
        print("Run 'python start_demo.py' to fix common issues after Docker restart.")
        return False


def run_captioning(image_folder):
    """
    Run AI captioning on images using LM Studio.
    Returns True on success, False on failure.
    """
    print("\n" + "=" * 70)
    print("CAPTIONING: Generating AI descriptions via LM Studio...")
    print("=" * 70)

    # Check if LM Studio is running
    try:
        r = requests.get(f"{LMSTUDIO_URL}/models", timeout=5)
        if r.status_code != 200:
            print(f"[ERROR] LM Studio not responding (HTTP {r.status_code})")
            print("Please start LM Studio and load a vision model.")
            return False
    except requests.RequestException:
        print("[ERROR] LM Studio not running at localhost:1234")
        print("Please start LM Studio and load a vision model.")
        return False

    # Run caption_folder.py
    try:
        result = subprocess.run(
            [sys.executable, "caption_folder.py", str(image_folder)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for large batches
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"[ERROR] Captioning failed: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("[ERROR] Captioning timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"[ERROR] Captioning error: {e}")
        return False


def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def start_image_server(image_folder):
    """Start HTTP server to serve images for ArchivesSpace."""
    if is_port_in_use(LOCAL_IMAGE_PORT):
        print(f"[HTTP Server] Already running on port {LOCAL_IMAGE_PORT}")
        return None

    print(f"[HTTP Server] Starting on port {LOCAL_IMAGE_PORT}...")
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(LOCAL_IMAGE_PORT)],
        cwd=str(image_folder),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    time.sleep(1)
    print(f"[HTTP Server] Running (PID: {process.pid})")
    return process


class FedoraClient:
    """Handles Fedora Commons REST API interactions."""

    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        self._test_connection()

    def _test_connection(self):
        """Test Fedora connection."""
        try:
            r = requests.get(self.base_url, auth=self.auth, timeout=10)
            if r.status_code == 200:
                print(f"[Fedora] Connected successfully (LOCAL instance)")
            else:
                raise Exception(f"Fedora connection failed: {r.status_code}")
        except requests.RequestException as e:
            raise Exception(f"[Fedora] Connection failed: {e}")

    def get_or_create_collection(self, name):
        """Get or create a collection container in Fedora."""
        # Sanitize name for URI
        safe_name = name.lower().replace(" ", "-").replace("'", "")[:50]
        collection_uri = f"{self.base_url}/{safe_name}"

        # Check if exists
        r = requests.head(collection_uri, auth=self.auth)
        if r.status_code == 200:
            print(f"[Fedora] Found collection: {collection_uri}")
            return collection_uri

        # Create collection container with metadata (don't specify ldp:Container - Fedora manages that)
        turtle = f"""
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix dcterms: <http://purl.org/dc/terms/> .

<> dc:title "{name}" ;
    dc:creator "{PHOTOGRAPHER_NAME}" ;
    dcterms:description "Collection of images - Lyrasis Community Software Demo" .
"""
        headers = {"Content-Type": "text/turtle", "Slug": safe_name}
        r = requests.post(self.base_url, auth=self.auth, data=turtle, headers=headers)

        if r.status_code in [200, 201]:
            uri = r.headers.get("Location", collection_uri)
            print(f"[Fedora] Created collection: {uri}")
            return uri
        else:
            print(f"[Fedora] Failed to create collection: {r.status_code} - {r.text[:200]}")
            return None

    def create_resource(self, collection_uri, title, description, file_path, filename,
                        dspace_url=None, archivesspace_url=None, vivo_url=None):
        """Create a resource in Fedora with metadata and binary."""
        # Sanitize title for URI slug
        safe_slug = filename.replace(" ", "-").replace(".", "-")[:30] + f"-{int(time.time())}"

        # Create container with metadata
        turtle = f"""
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<> dc:title "{title.replace('"', '\\"')}" ;
    dc:creator "{PHOTOGRAPHER_NAME}" ;
    dcterms:description "{description.replace('"', '\\"').replace(chr(10), ' ')[:500]}" ;
    dc:type "Image" """

        if dspace_url:
            turtle += f""";
    rdfs:seeAlso <{dspace_url}> ;
    dcterms:relation "{dspace_url}" """

        if archivesspace_url:
            turtle += f""";
    rdfs:seeAlso <{archivesspace_url}> """

        if vivo_url:
            turtle += f""";
    rdfs:seeAlso <{vivo_url}> """

        turtle += " ."

        headers = {"Content-Type": "text/turtle", "Slug": safe_slug}
        r = requests.post(collection_uri, auth=self.auth, data=turtle, headers=headers)

        if r.status_code not in [200, 201]:
            print(f"  [Fedora] Failed to create resource: {r.status_code}")
            return None, None

        resource_uri = r.headers.get("Location")
        print(f"  [Fedora] Created resource: {resource_uri}")

        # Upload binary file
        binary_uri = self._upload_binary(resource_uri, file_path, filename)

        return resource_uri, binary_uri

    def _upload_binary(self, resource_uri, file_path, filename):
        """Upload a binary file to a Fedora resource."""
        with open(file_path, "rb") as f:
            content_type = "image/jpeg" if filename.lower().endswith(('.jpg', '.jpeg')) else "application/octet-stream"
            headers = {
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Slug": "image"
            }
            r = requests.post(resource_uri, auth=self.auth, data=f, headers=headers)

            if r.status_code in [200, 201]:
                binary_uri = r.headers.get("Location")
                print(f"  [Fedora] Uploaded binary: {binary_uri}")
                return binary_uri
            else:
                print(f"  [Fedora] Binary upload failed: {r.status_code}")
                return None

    def add_cross_links(self, resource_uri, dspace_url=None, archivesspace_url=None, vivo_url=None):
        """Add cross-system links to an existing Fedora resource using SPARQL Update."""
        if not any([dspace_url, archivesspace_url, vivo_url]):
            return

        # Build SPARQL INSERT for links
        insert_triples = ""
        if dspace_url:
            insert_triples += f'<> <http://purl.org/dc/terms/relation> "{dspace_url}" . '
        if archivesspace_url:
            insert_triples += f'<> <http://purl.org/dc/terms/relation> "{archivesspace_url}" . '
        if vivo_url:
            insert_triples += f'<> <http://purl.org/dc/terms/relation> "{vivo_url}" . '

        sparql = f"INSERT {{ {insert_triples} }} WHERE {{}}"
        headers = {"Content-Type": "application/sparql-update"}
        r = requests.patch(resource_uri, auth=self.auth, data=sparql, headers=headers)

        if r.status_code in [200, 204]:
            print(f"  [Fedora] Added cross-links")


class CollectionSpaceClient:
    """Handles CollectionSpace REST API interactions."""

    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        self._test_connection()

    def _test_connection(self):
        """Test CollectionSpace connection."""
        try:
            r = requests.get(f"{self.base_url}/collectionobjects", auth=self.auth, timeout=10)
            if r.status_code == 200:
                print(f"[CollectionSpace] Connected successfully (LOCAL instance)")
            else:
                raise Exception(f"CollectionSpace connection failed: {r.status_code}")
        except requests.RequestException as e:
            raise Exception(f"[CollectionSpace] Connection failed: {e}")

    def create_collection_object(self, title, description, keywords, filename,
                                  dspace_url=None, archivesspace_url=None, vivo_url=None, fedora_url=None):
        """Create a collection object (photographic print) in CollectionSpace."""
        # Generate object number
        object_number = f"PHOTO.{int(time.time())}"

        # Build comments with cross-links
        comments = f"Photographic print. {description}\n\nKeywords: {keywords}"
        if dspace_url:
            comments += f"\n\nDSpace: {dspace_url}"
        if archivesspace_url:
            comments += f"\n\nArchivesSpace: {archivesspace_url}"
        if vivo_url:
            comments += f"\n\nVIVO: {vivo_url}"
        if fedora_url:
            comments += f"\n\nFedora: {fedora_url}"

        # Escape special characters for XML
        title_escaped = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        description_escaped = description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        comments_escaped = comments.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        # Brief description combines title, description, and format
        brief_desc = f"{title_escaped}. {description_escaped} 8 x 12 photographic print."

        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<document>
    <ns2:collectionobjects_common xmlns:ns2="http://collectionspace.org/services/collectionobject">
        <objectNumber>{object_number}</objectNumber>
        <objectNameList>
            <objectNameGroup>
                <objectName>Photographic print</objectName>
            </objectNameGroup>
        </objectNameList>
        <titleGroupList>
            <titleGroup>
                <title>{title_escaped}</title>
            </titleGroup>
        </titleGroupList>
        <objectProductionPersonGroupList>
            <objectProductionPersonGroup>
                <objectProductionPerson>{PHOTOGRAPHER_NAME}</objectProductionPerson>
                <objectProductionPersonRole>Photographer</objectProductionPersonRole>
            </objectProductionPersonGroup>
        </objectProductionPersonGroupList>
        <comments>{comments_escaped}</comments>
        <briefDescriptions>
            <briefDescription>{brief_desc}</briefDescription>
        </briefDescriptions>
    </ns2:collectionobjects_common>
</document>'''

        headers = {"Content-Type": "application/xml"}
        r = requests.post(f"{self.base_url}/collectionobjects", auth=self.auth, data=payload, headers=headers, timeout=30)

        if r.status_code in [200, 201]:
            # Extract CSID from Location header or response
            location = r.headers.get("Location", "")
            csid = location.split("/")[-1] if location else None
            if csid:
                print(f"  [CollectionSpace] Created object: {csid}")
                return csid, object_number
            else:
                print(f"  [CollectionSpace] Created object but couldn't get CSID")
                return None, object_number
        else:
            print(f"  [CollectionSpace] Failed: {r.status_code} - {r.text[:200]}")
            return None, None

    def get_object_url(self, csid):
        """Get the UI URL for a collection object."""
        return f"{CSPACE_UI_URL}/record/collectionobject/{csid}"


class VIVOClient:
    """Handles VIVO SPARQL API interactions."""

    def __init__(self, base_url, email, password):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.namespace = VIVO_NAMESPACE
        self.graph = VIVO_GRAPH
        self._test_connection()

    def _test_connection(self):
        """Test VIVO connection with a simple query."""
        query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
        try:
            result = self.sparql_query(query)
            if "error" not in result.lower() and "403" not in result:
                print(f"[VIVO] Connected successfully (LOCAL instance)")
            else:
                raise Exception(f"VIVO connection test failed: {result[:200]}")
        except requests.RequestException as e:
            raise Exception(f"[VIVO] Connection failed: {e}")

    def get_or_create_photographer(self):
        """Get or create the photographer (Steve Eberhardt) in VIVO."""
        query = f"""
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?person WHERE {{
    <{PHOTOGRAPHER_URI}> a foaf:Person .
    BIND(<{PHOTOGRAPHER_URI}> AS ?person)
}}
"""
        result = self.sparql_query(query)
        if PHOTOGRAPHER_URI in result:
            print(f"[VIVO] Found photographer: {PHOTOGRAPHER_NAME}")
            return PHOTOGRAPHER_URI

        websites_triples = ""
        for i, url in enumerate(PHOTOGRAPHER_WEBSITES):
            websites_triples += f"""
        <{PHOTOGRAPHER_URI}> vivo:hasURL <{PHOTOGRAPHER_URI}-website-{i}> .
        <{PHOTOGRAPHER_URI}-website-{i}> a vivo:URLLink ;
            rdfs:label "{url.replace('https://www.', '')}" ;
            vivo:linkURI "{url}" ."""

        update = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX vivo: <http://vivoweb.org/ontology/core#>
PREFIX vcard: <http://www.w3.org/2006/vcard/ns#>
PREFIX obo: <http://purl.obolibrary.org/obo/>

INSERT DATA {{
    GRAPH <{self.graph}> {{
        <{PHOTOGRAPHER_URI}> a foaf:Person ;
            rdfs:label "{PHOTOGRAPHER_NAME}" ;
            obo:ARG_2000028 <{PHOTOGRAPHER_URI}-vcard> .
        <{PHOTOGRAPHER_URI}-vcard> a vcard:Individual ;
            vcard:hasName <{PHOTOGRAPHER_URI}-vcard-name> ;
            vcard:hasEmail <{PHOTOGRAPHER_URI}-vcard-email> ;
            vcard:hasAddress <{PHOTOGRAPHER_URI}-vcard-address> .
        <{PHOTOGRAPHER_URI}-vcard-name> a vcard:Name ;
            vcard:givenName "{PHOTOGRAPHER_FIRST}" ;
            vcard:familyName "{PHOTOGRAPHER_LAST}" .
        <{PHOTOGRAPHER_URI}-vcard-email> a vcard:Email ;
            vcard:email "{PHOTOGRAPHER_EMAIL}" .
        <{PHOTOGRAPHER_URI}-vcard-address> a vcard:Address ;
            vcard:locality "{PHOTOGRAPHER_LOCATION}" .
        {websites_triples}
    }}
}}
"""
        status, result = self.sparql_update(update)
        if status == 200:
            print(f"[VIVO] Created photographer: {PHOTOGRAPHER_NAME}")
            return PHOTOGRAPHER_URI
        else:
            print(f"[VIVO] Error creating photographer: {result[:200]}")
            return None

    def sparql_query(self, query):
        """Execute a SPARQL query against VIVO."""
        url = f"{self.base_url}/api/sparqlQuery"
        data = {"email": self.email, "password": self.password, "query": query}
        response = requests.post(url, data=data, timeout=30)
        return response.text

    def sparql_update(self, update):
        """Execute a SPARQL UPDATE against VIVO."""
        url = f"{self.base_url}/api/sparqlUpdate"
        data = {"email": self.email, "password": self.password, "update": update}
        response = requests.post(url, data=data, timeout=30)
        return response.status_code, response.text

    def create_dataset(self, title, description, dspace_url=None, archivesspace_url=None,
                       fedora_url=None, keywords=None, photographer_uri=None, image_url=None):
        """Create a Dataset record in VIVO with links to all systems."""
        uri = f"{self.namespace}dataset-{uuid.uuid4().hex[:8]}"

        title_escaped = title.replace('"', '\\"').replace('\n', ' ')
        desc_escaped = description.replace('"', '\\"').replace('\n', ' ') if description else ""

        triples = f"""
        <{uri}> a <http://vivoweb.org/ontology/core#Dataset> ;
            rdfs:label "{title_escaped}" """

        if image_url:
            triples += f""";
            <http://xmlns.com/foaf/0.1/depiction> <{image_url}> ;
            <http://vivoweb.org/ontology/core#hasURL> <{uri}-image-link> .
        <{uri}-image-link> a <http://vivoweb.org/ontology/core#URLLink> ;
            rdfs:label "View Photograph" ;
            <http://vivoweb.org/ontology/core#linkURI> "{image_url}" """

        if desc_escaped:
            triples += f""";
            <http://purl.org/ontology/bibo/abstract> "{desc_escaped}" """

        if photographer_uri:
            authorship_uri = f"{uri}-authorship"
            triples += f""";
            <http://vivoweb.org/ontology/core#relatedBy> <{authorship_uri}> .
        <{authorship_uri}> a <http://vivoweb.org/ontology/core#Authorship> ;
            rdfs:label "Photographer: {PHOTOGRAPHER_NAME}" ;
            <http://vivoweb.org/ontology/core#relates> <{uri}> ;
            <http://vivoweb.org/ontology/core#relates> <{photographer_uri}> """

        if dspace_url:
            triples += f""";
            <http://vivoweb.org/ontology/core#hasURL> <{uri}-dspace-link> .
        <{uri}-dspace-link> a <http://vivoweb.org/ontology/core#URLLink> ;
            rdfs:label "View in DSpace" ;
            <http://vivoweb.org/ontology/core#linkURI> "{dspace_url}" """

        if archivesspace_url:
            triples += f""";
            <http://vivoweb.org/ontology/core#hasURL> <{uri}-aspace-link> .
        <{uri}-aspace-link> a <http://vivoweb.org/ontology/core#URLLink> ;
            rdfs:label "View in ArchivesSpace" ;
            <http://vivoweb.org/ontology/core#linkURI> "{archivesspace_url}" """

        if fedora_url:
            triples += f""";
            <http://vivoweb.org/ontology/core#hasURL> <{uri}-fedora-link> .
        <{uri}-fedora-link> a <http://vivoweb.org/ontology/core#URLLink> ;
            rdfs:label "View in Fedora Repository" ;
            <http://vivoweb.org/ontology/core#linkURI> "{fedora_url}" """

        triples += " ."

        update = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX vivo: <http://vivoweb.org/ontology/core#>
PREFIX bibo: <http://purl.org/ontology/bibo/>

INSERT DATA {{
    GRAPH <{self.graph}> {{
        {triples}
    }}
}}
"""
        status, result = self.sparql_update(update)
        if status == 200:
            return uri
        else:
            print(f"  [VIVO] Error creating dataset: {result[:200]}")
            return None

    def get_dataset_url(self, uri):
        """Get the public URL for a VIVO dataset."""
        return uri.replace(self.namespace, f"{self.base_url}/individual/")

    def upload_image(self, entity_uri, image_path):
        """Upload an image to a VIVO entity."""
        from PIL import Image

        try:
            img = Image.open(image_path)
            img_width, img_height = img.size
        except Exception:
            img_width, img_height = 800, 600

        crop_size = min(img_width, img_height)
        x_offset = (img_width - crop_size) // 2
        y_offset = (img_height - crop_size) // 2

        session = requests.Session()
        session.get(f"{self.base_url}/authenticate")
        session.post(f"{self.base_url}/authenticate",
                     data={"loginName": self.email, "loginPassword": self.password, "loginForm": "Log in"})

        add_url = f"{self.base_url}/uploadImages?entityUri={quote(entity_uri)}&action=add"
        session.get(add_url)

        upload_url = f"{self.base_url}/uploadImages?entityUri={quote(entity_uri)}&action=upload"
        with open(image_path, "rb") as f:
            filename = os.path.basename(image_path)
            r = session.post(upload_url, files={"datafile": (filename, f, "image/jpeg")})

        if r.status_code != 200:
            return False

        save_url = f"{self.base_url}/uploadImages?entityUri={quote(entity_uri)}&action=save"
        crop_data = {"x": str(x_offset), "y": str(y_offset), "w": str(crop_size), "h": str(crop_size)}
        r = session.post(save_url, data=crop_data)

        return r.status_code == 200


class DSpaceClient:
    """Handles DSpace 7/8 REST API interactions."""

    def __init__(self, base_url, email, password):
        self.base_url = base_url
        self.session = requests.Session()
        self.csrf_token = None
        self.auth_token = None
        self._authenticate(email, password)

    def _authenticate(self, email, password):
        self.session.get(f"{self.base_url}")
        r = self.session.get(f"{self.base_url}/security/csrf")
        if r.status_code == 200:
            self.csrf_token = r.json().get("token")
        if "DSPACE-XSRF-COOKIE" in self.session.cookies:
            self.csrf_token = self.session.cookies["DSPACE-XSRF-COOKIE"]

        headers = {"Content-Type": "application/x-www-form-urlencoded", "X-XSRF-TOKEN": self.csrf_token}
        r = self.session.post(f"{self.base_url}/authn/login", data={"user": email, "password": password}, headers=headers)
        if r.status_code == 200:
            self.auth_token = r.headers.get("Authorization")
            if "DSPACE-XSRF-COOKIE" in self.session.cookies:
                self.csrf_token = self.session.cookies["DSPACE-XSRF-COOKIE"]
            print(f"[DSpace] Authenticated as {email}")
        else:
            raise Exception(f"[DSpace] Auth failed: {r.status_code} - {r.text}")

    def _headers(self, content_type="application/json"):
        h = {"Authorization": self.auth_token}
        if content_type:
            h["Content-Type"] = content_type
        if self.csrf_token:
            h["X-XSRF-TOKEN"] = self.csrf_token
        return h

    def _refresh_csrf(self):
        if "DSPACE-XSRF-COOKIE" in self.session.cookies:
            self.csrf_token = self.session.cookies["DSPACE-XSRF-COOKIE"]

    def get_or_create_community(self, name):
        r = self.session.get(f"{self.base_url}/core/communities", headers=self._headers())
        if r.status_code == 200:
            communities = r.json().get("_embedded", {}).get("communities", [])
            for c in communities:
                if c.get("name") == name:
                    print(f"[DSpace] Found community: {c['uuid']}")
                    return c["uuid"]

        self._refresh_csrf()
        payload = {"name": name, "metadata": {"dc.title": [{"value": name}], "dc.description": [{"value": "Lyrasis Community Software Demo"}]}}
        r = self.session.post(f"{self.base_url}/core/communities", json=payload, headers=self._headers())
        if r.status_code == 201:
            uuid = r.json()["uuid"]
            print(f"[DSpace] Created community: {uuid}")
            return uuid
        else:
            raise Exception(f"[DSpace] Failed to create community: {r.text}")

    def get_or_create_collection(self, community_uuid, name):
        r = self.session.get(f"{self.base_url}/core/communities/{community_uuid}/collections", headers=self._headers())
        if r.status_code == 200:
            collections = r.json().get("_embedded", {}).get("collections", [])
            for c in collections:
                if c.get("name") == name:
                    print(f"[DSpace] Found collection: {c['uuid']}")
                    return c["uuid"]

        self._refresh_csrf()
        payload = {"name": name, "metadata": {"dc.title": [{"value": name}]}}
        r = self.session.post(f"{self.base_url}/core/collections", json=payload, headers=self._headers(), params={"parent": community_uuid})
        if r.status_code == 201:
            uuid = r.json()["uuid"]
            print(f"[DSpace] Created collection: {uuid}")
            return uuid
        else:
            raise Exception(f"[DSpace] Failed to create collection: {r.text}")

    def create_and_publish_item(self, collection_uuid, title, description, keywords, file_path, filename):
        self._refresh_csrf()
        metadata = {
            "dc.title": [{"value": title, "language": None}],
            "dc.description.abstract": [{"value": description, "language": None}],
            "dc.type": [{"value": "Image", "language": None}],
            "dc.creator": [{"value": PHOTOGRAPHER_NAME, "language": None}],
            "dc.rights": [{"value": f"Photograph by {PHOTOGRAPHER_NAME}", "language": None}]
        }
        for kw in keywords.split(";"):
            kw = kw.strip()
            if kw:
                if "dc.subject" not in metadata:
                    metadata["dc.subject"] = []
                metadata["dc.subject"].append({"value": kw, "language": None})

        item_payload = {"name": title, "metadata": metadata, "inArchive": True, "discoverable": True, "withdrawn": False}
        r = self.session.post(f"{self.base_url}/core/items", json=item_payload, headers=self._headers(), params={"owningCollection": collection_uuid})

        if r.status_code not in [200, 201]:
            print(f"  [DSpace] Item creation failed: {r.status_code}")
            return None, None

        item = r.json()
        item_uuid = item.get("uuid")
        print(f"  [DSpace] Created item: {item_uuid}")

        bitstream_uuid = self._upload_bitstream_to_item(item_uuid, file_path, filename)
        return item_uuid, bitstream_uuid

    def _upload_bitstream_to_item(self, item_uuid, file_path, filename):
        self._refresh_csrf()
        r = self.session.get(f"{self.base_url}/core/items/{item_uuid}/bundles", headers=self._headers())

        bundle_uuid = None
        if r.status_code == 200:
            bundles = r.json().get("_embedded", {}).get("bundles", [])
            for b in bundles:
                if b.get("name") == "ORIGINAL":
                    bundle_uuid = b["uuid"]
                    break

        if not bundle_uuid:
            self._refresh_csrf()
            bundle_payload = {"name": "ORIGINAL", "metadata": {}}
            r = self.session.post(f"{self.base_url}/core/items/{item_uuid}/bundles", json=bundle_payload, headers=self._headers())
            if r.status_code in [200, 201]:
                bundle_uuid = r.json().get("uuid")

        self._refresh_csrf()
        upload_name = filename[:-4] + '.jpeg' if filename.lower().endswith('.jpg') else filename

        with open(file_path, "rb") as f:
            headers = {"Authorization": self.auth_token, "X-XSRF-TOKEN": self.csrf_token}
            files = {"file": (upload_name, f, "image/jpeg")}
            r = self.session.post(f"{self.base_url}/core/bundles/{bundle_uuid}/bitstreams", files=files, headers=headers)
            if r.status_code in [200, 201]:
                bitstream_uuid = r.json().get("uuid")
                print(f"  [DSpace] Uploaded bitstream: {bitstream_uuid}")
                return bitstream_uuid
        return None

    def add_links(self, item_uuid, aspace_uri, vivo_uri, fedora_uri, shared_id):
        """Add reverse links to other systems."""
        if not item_uuid:
            return

        self._refresh_csrf()
        aspace_staff_url = f"http://localhost/staff/resolve/readonly?uri={aspace_uri}" if aspace_uri else None

        patch_fields = [("/metadata/dc.identifier.other", [{"value": shared_id, "language": None}])]
        if aspace_staff_url:
            patch_fields.append(("/metadata/datacite.relation.isReferencedBy", [{"value": aspace_staff_url, "language": None}]))
        if fedora_uri:
            patch_fields.append(("/metadata/dc.relation", [{"value": f"Fedora: {fedora_uri}", "language": None}]))

        for field_path, field_value in patch_fields:
            self._refresh_csrf()
            patch_payload = [{"op": "add", "path": field_path, "value": field_value}]
            self.session.patch(f"{self.base_url}/core/items/{item_uuid}", json=patch_payload, headers=self._headers())

        print(f"  [DSpace] Added cross-system links")

    def get_item_handle(self, item_uuid):
        r = self.session.get(f"{self.base_url}/core/items/{item_uuid}", headers=self._headers())
        if r.status_code == 200:
            return r.json().get("handle")
        return None

    def get_item_url(self, item_uuid):
        return f"{DSPACE_UI_URL}/items/{item_uuid}"


class ArchivesSpaceClient:
    """Handles ArchivesSpace API interactions."""

    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.session = self._authenticate(username, password)

    def _authenticate(self, username, password):
        url = f"{self.base_url}/users/{username}/login?password={password}"
        r = requests.post(url)
        r.raise_for_status()
        token = r.json().get("session")
        print(f"[ArchivesSpace] Authenticated as {username}")
        return token

    def create_digital_object(self, repo_id, title, description, keywords, filename, image_url,
                              dspace_page_url, shared_id, dspace_handle=None, vivo_url=None, fedora_url=None):
        """Create a Digital Object with links to all systems."""
        headers = {"X-ArchivesSpace-Session": self.session}

        file_versions = []
        if image_url:
            file_versions.append({
                "jsonmodel_type": "file_version", "file_uri": image_url, "publish": True,
                "xlink_show_attribute": "embed", "xlink_actuate_attribute": "onLoad",
                "file_format_name": "jpeg", "use_statement": "image-thumbnail"
            })
        if dspace_page_url:
            file_versions.append({
                "jsonmodel_type": "file_version", "file_uri": dspace_page_url, "publish": True,
                "xlink_show_attribute": "new", "xlink_actuate_attribute": "onRequest"
            })

        external_documents = []
        if dspace_page_url:
            external_documents.append({"jsonmodel_type": "external_document", "title": "Link to DSpace Record", "location": dspace_page_url, "publish": True})
        if dspace_handle:
            external_documents.append({"jsonmodel_type": "external_document", "title": f"DSpace Persistent Handle ({dspace_handle})", "location": f"http://localhost:4000/handle/{dspace_handle}", "publish": True})
        if vivo_url:
            external_documents.append({"jsonmodel_type": "external_document", "title": "Link to VIVO Research Record", "location": vivo_url, "publish": True})
        if fedora_url:
            external_documents.append({"jsonmodel_type": "external_document", "title": "Link to Fedora Repository", "location": fedora_url, "publish": True})

        notes_content = description
        if dspace_handle:
            notes_content += f"\n\nDSpace Handle: {dspace_handle}"
        if fedora_url:
            notes_content += f"\n\nFedora: {fedora_url}"
        notes_content += f"\n\nKeywords: {keywords}"

        payload = {
            "jsonmodel_type": "digital_object", "title": title, "digital_object_id": shared_id, "publish": True,
            "file_versions": file_versions, "external_documents": external_documents,
            "notes": [{"jsonmodel_type": "note_digital_object", "type": "summary", "content": [notes_content], "publish": True}]
        }

        url = f"{self.base_url}/repositories/{repo_id}/digital_objects"
        r = requests.post(url, headers=headers, json=payload, timeout=120)

        if r.status_code == 200:
            uri = r.json().get("uri")
            print(f"  [ArchivesSpace] Created Digital Object: {uri}")
            return uri
        else:
            print(f"  [ArchivesSpace] Failed: {r.text}")
            return None

    def create_collection_link(self, repo_id, collection_name, dspace_collection_url):
        headers = {"X-ArchivesSpace-Session": self.session}
        shared_id = f"dspace_collection_{int(time.time())}"

        payload = {
            "jsonmodel_type": "digital_object", "title": f"{collection_name} - DSpace Collection",
            "digital_object_id": shared_id, "publish": True,
            "file_versions": [{"jsonmodel_type": "file_version", "file_uri": dspace_collection_url, "publish": True, "xlink_show_attribute": "new", "xlink_actuate_attribute": "onRequest"}],
            "external_documents": [{"jsonmodel_type": "external_document", "title": "Link to DSpace Collection - View All Items", "location": dspace_collection_url, "publish": True}],
            "notes": [{"jsonmodel_type": "note_digital_object", "type": "summary", "content": [f"This record links to the full DSpace collection: {collection_name}."], "publish": True}]
        }

        url = f"{self.base_url}/repositories/{repo_id}/digital_objects"
        r = requests.post(url, headers=headers, json=payload, timeout=120)

        if r.status_code == 200:
            uri = r.json().get("uri")
            print(f"[ArchivesSpace] Created collection link: {uri}")
            return uri
        return None


def main():
    parser = argparse.ArgumentParser(description="Import images to all 5 Lyrasis systems")
    parser.add_argument("image_folder", help="Path to folder containing images")
    parser.add_argument("--prefix", "-p", default="", help="Prefix for titles (e.g., 'Demo - ')")
    parser.add_argument("--caption", "-c", action="store_true", help="Run AI captioning first (requires LM Studio)")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip pre-flight service check")
    args = parser.parse_args()

    image_folder = Path(args.image_folder)
    prefix = args.prefix

    print("=" * 70)
    print("LYRASIS COMMUNITY SOFTWARE DEMO")
    print("Import to: DSpace + ArchivesSpace + VIVO + Fedora + CollectionSpace")
    print("=" * 70)

    # Step 1: Pre-flight check (unless skipped)
    if not args.skip_preflight:
        if not preflight_check():
            print("\nAborting due to failed pre-flight check.")
            print("Use --skip-preflight to bypass this check.")
            sys.exit(1)

    # Step 2: Run captioning if requested
    if args.caption:
        if not run_captioning(image_folder):
            print("\nAborting due to captioning failure.")
            sys.exit(1)

    # Step 3: Check for captions.csv
    if not os.path.exists(CSV_FILE):
        print(f"\nError: {CSV_FILE} not found.")
        print("Use --caption flag to generate captions, or run caption_folder.py first.")
        sys.exit(1)

    http_server = start_image_server(image_folder)

    # Step 4: Initialize all five clients
    print("\n--- Connecting to systems ---")
    try:
        dspace = DSpaceClient(DSPACE_API_URL, DSPACE_EMAIL, DSPACE_PASSWORD)
        aspace = ArchivesSpaceClient(AS_API_URL, AS_USERNAME, AS_PASSWORD)
        vivo = VIVOClient(VIVO_URL, VIVO_EMAIL, VIVO_PASSWORD)
        fedora = FedoraClient(FEDORA_URL, FEDORA_USERNAME, FEDORA_PASSWORD)
        cspace = CollectionSpaceClient(CSPACE_URL, CSPACE_USERNAME, CSPACE_PASSWORD)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    # Setup photographer in VIVO
    print("\n--- Setting up VIVO photographer ---")
    photographer_uri = vivo.get_or_create_photographer()

    # Setup DSpace structure
    print("\n--- Setting up DSpace structure ---")
    community_name = f"{prefix}{DSPACE_COMMUNITY_NAME}" if prefix else DSPACE_COMMUNITY_NAME
    collection_name = f"{prefix}{DSPACE_COLLECTION_NAME}" if prefix else DSPACE_COLLECTION_NAME
    community_uuid = dspace.get_or_create_community(community_name)
    collection_uuid = dspace.get_or_create_collection(community_uuid, collection_name)

    # Setup Fedora collection
    print("\n--- Setting up Fedora collection ---")
    fedora_collection = fedora.get_or_create_collection(collection_name)

    # Create collection-level link in ArchivesSpace
    print("\n--- Creating collection-level link ---")
    dspace_collection_url = f"{DSPACE_UI_URL}/collections/{collection_uuid}"
    aspace.create_collection_link(AS_REPO_ID, collection_name, dspace_collection_url)

    # Process each image
    print("\n--- Processing images ---")
    results = []

    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row['filename']
            title = f"{prefix}{row['title']}" if prefix else row['title']
            description = row['scope_content']
            keywords = row['keywords']

            file_path = image_folder / filename
            if not file_path.exists():
                print(f"Warning: {file_path} not found, skipping")
                continue

            print(f"\nProcessing: {filename}")
            shared_id = f"img_{int(time.time())}_{filename}"

            # 1. Create DSpace Item
            item_uuid, bitstream_uuid = None, None
            dspace_page_url, dspace_handle = None, None
            try:
                item_uuid, bitstream_uuid = dspace.create_and_publish_item(collection_uuid, title, description, keywords, str(file_path), filename)
                dspace_page_url = dspace.get_item_url(item_uuid) if item_uuid else None
                dspace_handle = dspace.get_item_handle(item_uuid) if item_uuid else None
            except Exception as e:
                print(f"  DSpace error: {e}")

            # 2. Create Fedora Resource
            fedora_uri, fedora_binary = None, None
            try:
                fedora_uri, fedora_binary = fedora.create_resource(
                    fedora_collection, title, description, str(file_path), filename,
                    dspace_url=dspace_page_url
                )
            except Exception as e:
                print(f"  Fedora error: {e}")

            # 3. Build image URL for ArchivesSpace
            local_image_url = f"{LOCAL_IMAGE_SERVER}/{quote(filename)}"

            # 4. Create VIVO Dataset
            vivo_uri, vivo_url = None, None
            try:
                vivo_uri = vivo.create_dataset(
                    title=title, description=description, dspace_url=dspace_page_url,
                    fedora_url=fedora_uri, keywords=keywords, photographer_uri=photographer_uri,
                    image_url=local_image_url
                )
                if vivo_uri:
                    vivo_url = vivo.get_dataset_url(vivo_uri)
                    print(f"  [VIVO] Created Dataset: {vivo_uri}")
                    if vivo.upload_image(vivo_uri, str(file_path)):
                        print(f"  [VIVO] Uploaded photo")
            except Exception as e:
                print(f"  VIVO error: {e}")

            # 5. Create ArchivesSpace Digital Object
            as_uri = aspace.create_digital_object(
                AS_REPO_ID, title, description, keywords, filename, local_image_url,
                dspace_page_url, shared_id, dspace_handle, vivo_url, fedora_uri
            )

            # 6. Create CollectionSpace Collection Object (Photographic Print)
            cspace_csid, cspace_object_num = None, None
            cspace_url = None
            try:
                aspace_staff_url = f"http://localhost/staff/resolve/readonly?uri={as_uri}" if as_uri else None
                cspace_csid, cspace_object_num = cspace.create_collection_object(
                    title=title, description=description, keywords=keywords, filename=filename,
                    dspace_url=dspace_page_url, archivesspace_url=aspace_staff_url,
                    vivo_url=vivo_url, fedora_url=fedora_uri
                )
                if cspace_csid:
                    cspace_url = cspace.get_object_url(cspace_csid)
            except Exception as e:
                print(f"  CollectionSpace error: {e}")

            # 7. Add reverse links to DSpace
            if item_uuid:
                dspace.add_links(item_uuid, as_uri, vivo_uri, fedora_uri, shared_id)

            # 8. Update Fedora with all links
            if fedora_uri:
                aspace_staff_url = f"http://localhost/staff/resolve/readonly?uri={as_uri}" if as_uri else None
                fedora.add_cross_links(fedora_uri, dspace_page_url, aspace_staff_url, vivo_url)

            # 9. Update VIVO with ArchivesSpace link
            if vivo_uri and as_uri:
                aspace_staff_url = f"http://localhost/staff/resolve/readonly?uri={as_uri}"
                update = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX vivo: <http://vivoweb.org/ontology/core#>

INSERT DATA {{
    GRAPH <{VIVO_GRAPH}> {{
        <{vivo_uri}> <http://vivoweb.org/ontology/core#hasURL> <{vivo_uri}-aspace-link> .
        <{vivo_uri}-aspace-link> a <http://vivoweb.org/ontology/core#URLLink> ;
            rdfs:label "View in ArchivesSpace" ;
            <http://vivoweb.org/ontology/core#linkURI> "{aspace_staff_url}" .
    }}
}}
"""
                vivo.sparql_update(update)

            results.append({
                "filename": filename,
                "dspace_item": item_uuid,
                "dspace_page": dspace_page_url,
                "aspace_uri": as_uri,
                "vivo_uri": vivo_uri,
                "vivo_url": vivo_url,
                "fedora_uri": fedora_uri,
                "cspace_csid": cspace_csid,
                "cspace_url": cspace_url
            })

            time.sleep(0.5)

    # Summary
    print("\n" + "=" * 70)
    print("LYRASIS COMMUNITY SOFTWARE DEMO COMPLETE")
    print("=" * 70)
    print(f"Records created in 5 systems: {len(results)}")
    print(f"\nSystem URLs:")
    print(f"  DSpace:          {DSPACE_UI_URL}")
    print(f"  ArchivesSpace:   http://localhost/staff/")
    print(f"  VIVO:            {VIVO_URL}")
    print(f"  Fedora:          {FEDORA_URL}")
    print(f"  CollectionSpace: {CSPACE_UI_URL}")
    print("\nResults:")
    for r in results:
        print(f"  {r['filename']}")
        print(f"    DSpace:          {r['dspace_page']}")
        print(f"    ArchivesSpace:   {r['aspace_uri']}")
        print(f"    VIVO:            {r['vivo_url']}")
        print(f"    Fedora:          {r['fedora_uri']}")
        print(f"    CollectionSpace: {r['cspace_url']}")

    # Generate DSpace thumbnails
    print("\n--- Generating DSpace thumbnails ---")
    try:
        result = subprocess.run(
            ["docker", "exec", "dspace", "//dspace/bin/dspace", "filter-media"],
            capture_output=True, text=True, timeout=300
        )
        filtered_count = result.stdout.count("FILTERED:")
        print(f"[DSpace] Generated {filtered_count} thumbnail(s)")
    except Exception as e:
        print(f"[DSpace] Thumbnail generation error: {e}")

    print("\n" + "-" * 70)
    if http_server:
        print(f"NOTE: Image server running on port {LOCAL_IMAGE_PORT} (PID: {http_server.pid})")
    print("-" * 70)


if __name__ == "__main__":
    main()
