# Docker Compose Files

This directory contains Docker Compose configurations for each system.

## Directory Structure

```
docker-compose/
├── archivesspace.yml     # ArchivesSpace configuration
├── dspace.yml            # DSpace configuration
├── vivo.yml              # VIVO configuration
├── fedora.yml            # Fedora configuration
├── collectionspace.yml   # CollectionSpace configuration
├── proxy-config/         # Nginx configuration for ArchivesSpace
│   └── default.conf
└── dspace-config/        # DSpace configuration
    └── local.cfg
```

## Quick Start

Each system should be run from its own directory. Copy the relevant files:

```bash
# Create directories
mkdir -p ~/archivespace/{archivesspace,dspace,vivo,fedora,collectionspace}

# Copy compose files
cp archivesspace.yml ~/archivespace/archivesspace/docker-compose.yml
cp -r proxy-config ~/archivespace/archivesspace/
cp dspace.yml ~/archivespace/dspace/docker-compose.yml
cp -r dspace-config ~/archivespace/dspace/
cp vivo.yml ~/archivespace/vivo/docker-compose.yml
cp fedora.yml ~/archivespace/fedora/docker-compose.yml
cp collectionspace.yml ~/archivespace/collectionspace/docker-compose.yml
```

## Starting Systems

Start each system from its directory:

```bash
# Start ArchivesSpace
cd ~/archivespace/archivesspace
docker compose up -d

# Start DSpace
cd ~/archivespace/dspace
docker compose up -d

# Start VIVO
cd ~/archivespace/vivo
docker compose up -d

# Start Fedora
cd ~/archivespace/fedora
docker compose up -d

# Start CollectionSpace (requires additional build steps)
cd ~/archivespace/collectionspace
docker compose up -d
# See CollectionSpace build instructions in main README
```

## Ports Reference

| System | Ports |
|--------|-------|
| ArchivesSpace | 80 (UI), 8089 (API), 8983 (Solr), 8000 (Images) |
| DSpace | 4000 (UI), 8081 (API), 8984 (Solr) |
| VIVO | 8082 (UI), 8985 (Solr) |
| Fedora | 8083 (API) |
| CollectionSpace | 8180 (UI/API) |

## Notes

- **ArchivesSpace** includes an image-server container that serves images from `staging_images/`
- **DSpace** requires the `local.cfg` file to be properly configured
- **CollectionSpace** requires building from source after initial container setup
- All systems use named volumes for persistent data
