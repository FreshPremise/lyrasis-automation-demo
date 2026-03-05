"""
Configuration Template for Lyrasis Community Software Automation

Instructions:
1. Copy this file to 'config.py'
2. Update all values with your own credentials and settings
3. Never commit config.py to version control (it's in .gitignore)

All systems run locally via Docker - nothing is uploaded externally.
"""

# =============================================================================
# DSPACE CONFIGURATION
# =============================================================================
# DSpace 7/8 REST API
DSPACE_API_URL = "http://localhost:8081/server/api"
DSPACE_UI_URL = "http://localhost:4000"
DSPACE_EMAIL = "your-email@example.com"
DSPACE_PASSWORD = "your-password"

# Default community/collection names (can be overridden with --prefix)
DSPACE_COMMUNITY_NAME = "My Image Collection"
DSPACE_COLLECTION_NAME = "2025 Images"

# =============================================================================
# ARCHIVESSPACE CONFIGURATION
# =============================================================================
# ArchivesSpace API (backend)
AS_API_URL = "http://localhost:8089"
AS_USERNAME = "admin"
AS_PASSWORD = "admin"
AS_REPO_ID = 2  # Repository ID (usually 2 for first created repo)

# =============================================================================
# VIVO CONFIGURATION
# =============================================================================
# VIVO SPARQL endpoints
VIVO_URL = "http://localhost:8082"
VIVO_EMAIL = "your-email@example.com"
VIVO_PASSWORD = "your-password"
VIVO_NAMESPACE = "http://vivo.mydomain.edu/individual/"
VIVO_GRAPH = "http://vitro.mannlib.cornell.edu/default/vitro-kb-2"

# =============================================================================
# FEDORA CONFIGURATION
# =============================================================================
# Fedora Commons REST API
FEDORA_URL = "http://localhost:8083/fcrepo/rest"
FEDORA_USERNAME = "your-email@example.com"
FEDORA_PASSWORD = "your-password"

# =============================================================================
# COLLECTIONSPACE CONFIGURATION
# =============================================================================
# CollectionSpace REST API
CSPACE_URL = "http://localhost:8180/cspace-services"
CSPACE_UI_URL = "http://localhost:8180/cspace/core"
CSPACE_USERNAME = "admin@core.collectionspace.org"
CSPACE_PASSWORD = "Administrator"  # Must be 8-24 characters

# =============================================================================
# PHOTOGRAPHER/CREATOR INFORMATION
# =============================================================================
# This information is added to all records as the creator/photographer
PHOTOGRAPHER_NAME = "Your Name"
PHOTOGRAPHER_FIRST = "Your"
PHOTOGRAPHER_LAST = "Name"
PHOTOGRAPHER_EMAIL = "your-email@example.com"
PHOTOGRAPHER_LOCATION = "Your City, State"
PHOTOGRAPHER_WEBSITES = [
    "https://www.yourwebsite.com",
]
PHOTOGRAPHER_URI = "http://vivo.mydomain.edu/individual/your-name"

# =============================================================================
# LM STUDIO CONFIGURATION (for AI captioning)
# =============================================================================
# LM Studio runs locally and provides vision model API
LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "your-vision-model-id"  # e.g., "zai-org/glm-4.6v-flash"

# =============================================================================
# IMAGE SERVER CONFIGURATION
# =============================================================================
# Local HTTP server for serving images to ArchivesSpace
LOCAL_IMAGE_SERVER = "http://localhost:8000"
LOCAL_IMAGE_PORT = 8000

# =============================================================================
# FILE SETTINGS
# =============================================================================
CSV_FILE = "captions.csv"
