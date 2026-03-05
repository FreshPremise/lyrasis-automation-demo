# Lyrasis Community Software Automation Demo

This project demonstrates that **five Lyrasis Community Supported Software systems** can run together locally via Docker with automated cross-system workflows. A single command creates linked records across all systems with AI-generated descriptions.

## What This Does

1. **AI Image Analysis** - Sends images to a local vision AI model (LM Studio) for automatic captioning
2. **Multi-System Import** - Creates records in 5 different systems simultaneously
3. **Cross-Linking** - Establishes bidirectional links between all records
4. **Zero Cloud Dependency** - Everything runs locally via Docker

### Systems Included

| System | Purpose | Port |
|--------|---------|------|
| **ArchivesSpace** | Archival description & finding aids | 8089 (API), 80 (UI) |
| **DSpace** | Digital repository & preservation | 8081 (API), 4000 (UI) |
| **VIVO** | Research networking & profiles | 8082 |
| **Fedora** | Linked data repository | 8083 |
| **CollectionSpace** | Museum collections management | 8180 |

---

## Quick Start

```bash
# 1. After Docker starts, verify all systems are ready
python start_demo.py

# 2. Place your images in the staging_images/ folder

# 3. Run the full automation (single command)
python import_to_all.py staging_images --prefix "Demo - " --caption
```

This will:
- Verify all 5 systems are responding (pre-flight check)
- Generate AI descriptions for your images
- Create records in all 5 systems with cross-links
- Generate thumbnails in DSpace

---

## Prerequisites

### Software Requirements

- **Docker Desktop** (Windows/Mac) or Docker Engine (Linux)
- **Python 3.8+** with pip
- **LM Studio** (free, for AI captioning) - [Download](https://lmstudio.ai/)
- **16GB+ RAM** recommended (running 5 systems simultaneously)

### Python Dependencies

```bash
pip install -r requirements.txt
```

---

## Installation Guide

### Step 1: Clone This Repository

```bash
git clone https://github.com/YOUR_USERNAME/lyrasis-automation-demo.git
cd lyrasis-automation-demo
```

### Step 2: Configure Credentials

```bash
# Copy the example config
cp config.example.py config.py

# Edit config.py with your preferred credentials
```

### Step 3: Set Up Docker Containers

Each system needs its own Docker setup. See the [Docker Setup Guide](#docker-setup-guide) below.

### Step 4: Install LM Studio

1. Download LM Studio from [lmstudio.ai](https://lmstudio.ai/)
2. Install and open LM Studio
3. Download a vision model (e.g., `zai-org/glm-4.6v-flash`)
4. Start the local server (runs on port 1234)

### Step 5: Verify Installation

```bash
python start_demo.py
```

You should see all systems report "OK".

---

## Docker Setup Guide

### Directory Structure

```
C:\Archivespace\           (or /home/user/archivespace on Linux)
├── archivesspace/         # ArchivesSpace docker-compose
├── dspace/                # DSpace docker-compose
├── vivo/                  # VIVO docker-compose
├── fedora/                # Fedora docker-compose
├── collectionspace/       # CollectionSpace docker-compose
└── Automation/            # This repository
    ├── staging_images/    # Place your images here
    ├── import_to_all.py   # Main automation script
    └── ...
```

### ArchivesSpace

Create `archivesspace/docker-compose.yml`:

```yaml
services:
  mysql:
    container_name: mysql
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: archivesspace
      MYSQL_USER: archivesspace
      MYSQL_PASSWORD: archivesspace
    volumes:
      - mysql-data:/var/lib/mysql

  solr:
    container_name: solr
    image: solr:9
    ports:
      - 8983:8983
    volumes:
      - solr-data:/var/solr

  archivesspace:
    container_name: archivesspace
    image: archivesspace/archivesspace:latest
    environment:
      ARCHIVESSPACE_DB_TYPE: mysql
      ARCHIVESSPACE_DB_HOST: mysql
      ARCHIVESSPACE_DB_NAME: archivesspace
      ARCHIVESSPACE_DB_USER: archivesspace
      ARCHIVESSPACE_DB_PASS: archivesspace
    ports:
      - 8089:8089
      - 8080:8080
    depends_on:
      - mysql
      - solr

  proxy:
    container_name: proxy
    image: nginx:alpine
    ports:
      - 80:80
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - archivesspace

  image-server:
    container_name: image-server
    image: nginx:alpine
    ports:
      - 8000:80
    volumes:
      - ../Automation/staging_images:/usr/share/nginx/html:ro

volumes:
  mysql-data:
  solr-data:
```

### DSpace

Create `dspace/docker-compose.yml`:

```yaml
services:
  dspacedb:
    container_name: dspacedb
    image: postgres:13
    environment:
      POSTGRES_DB: dspace
      POSTGRES_USER: dspace
      POSTGRES_PASSWORD: dspace
    volumes:
      - dspace-db:/var/lib/postgresql/data

  dspacesolr:
    container_name: dspacesolr
    image: dspace/dspace-solr:latest
    ports:
      - 8984:8983
    volumes:
      - dspace-solr:/var/solr

  dspace:
    container_name: dspace
    image: dspace/dspace:latest
    environment:
      DB_URL: jdbc:postgresql://dspacedb:5432/dspace
    ports:
      - 8081:8080
    depends_on:
      - dspacedb
      - dspacesolr

  dspace-ui:
    container_name: dspace-ui
    image: dspace/dspace-angular:latest
    ports:
      - 4000:4000
    environment:
      DSPACE_REST_URL: http://localhost:8081/server

volumes:
  dspace-db:
  dspace-solr:
```

### VIVO

Create `vivo/docker-compose.yml`:

```yaml
services:
  vivo-solr:
    container_name: vivo-solr
    image: vivoweb/vivo-solr:latest
    ports:
      - 8985:8983
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:8983/solr/vivocore/admin/ping || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 5

  vivo:
    container_name: vivo
    image: vivoweb/vivo:latest
    environment:
      SOLR_URL: http://vivo-solr:8983/solr/vivocore
    ports:
      - 8082:8080
    depends_on:
      vivo-solr:
        condition: service_healthy
```

### Fedora

Create `fedora/docker-compose.yml`:

```yaml
services:
  fcrepo:
    container_name: fcrepo
    image: fcrepo/fcrepo:6.5.1-tomcat9
    environment:
      FEDORA_ADMIN_USERNAME: fedoraAdmin
      FEDORA_ADMIN_PASSWORD: fedoraAdmin
    ports:
      - 8083:8080
    volumes:
      - fcrepo-data:/usr/local/tomcat/fcrepo-home

volumes:
  fcrepo-data:
```

### CollectionSpace

CollectionSpace requires building from source. See the [CollectionSpace Setup Guide](#collectionspace-setup-guide) section.

---

## Usage

### Basic Usage

```bash
# Run with AI captioning (recommended)
python import_to_all.py staging_images --prefix "Demo - " --caption

# Run without captioning (uses existing captions.csv)
python import_to_all.py staging_images --prefix "Demo - "

# Skip pre-flight check (not recommended)
python import_to_all.py staging_images --prefix "Demo - " --caption --skip-preflight
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--prefix`, `-p` | Prefix for record titles (e.g., "Demo - ") |
| `--caption`, `-c` | Run AI captioning before import |
| `--skip-preflight` | Skip service verification (not recommended) |

### After Docker Restarts

Always run the startup script after Docker restarts:

```bash
python start_demo.py
```

This fixes common issues like stale port bindings and starts services that don't auto-start.

---

## How It Works

### Workflow Diagram

```
┌─────────────────┐
│  staging_images │  Your JPG/JPEG photos
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   LM Studio     │  AI vision model generates descriptions
│  (localhost:1234)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  captions.csv   │  Title, description, keywords for each image
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    import_to_all.py                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────┐  ┌────────┐  ┌─────┐ │
│  │ DSpace   │  │ Archives │  │ VIVO │  │ Fedora │  │CSpace│ │
│  │          │◄─┼─►Space   │◄─┼──────┼──►        │◄─┼─────┤ │
│  └──────────┘  └──────────┘  └──────┘  └────────┘  └─────┘ │
│       ▲              ▲           ▲          ▲         ▲     │
│       └──────────────┴───────────┴──────────┴─────────┘     │
│                    Cross-System Links                        │
└─────────────────────────────────────────────────────────────┘
```

### Cross-System Links

Every record links to its counterparts in other systems:

- **ArchivesSpace** → Links to DSpace, VIVO, Fedora (External Documents)
- **DSpace** → Links to ArchivesSpace (datacite.relation.isReferencedBy)
- **VIVO** → Links to DSpace, ArchivesSpace, Fedora (URLLink objects)
- **Fedora** → Links to DSpace, ArchivesSpace, VIVO (dcterms:relation)
- **CollectionSpace** → Links to all systems (Comments field)

---

## File Reference

| File | Description |
|------|-------------|
| `import_to_all.py` | Main automation script (5 systems) |
| `caption_folder.py` | AI captioning via LM Studio |
| `start_demo.py` | Post-restart health check |
| `dspace_delete_community.py` | Cleanup utility |
| `config.example.py` | Configuration template |
| `requirements.txt` | Python dependencies |

---

## Troubleshooting

### After Docker Desktop Restarts

Run the startup script to fix stale port bindings:

```bash
python start_demo.py
```

### Images Not Appearing in ArchivesSpace

The image-server container may have stale port bindings:

```bash
docker restart image-server
```

### DSpace Thumbnails Not Appearing

Generate thumbnails manually:

```bash
docker exec dspace //dspace/bin/dspace filter-media
```

Note: Use `//dspace` (double slash) on Windows to prevent Git Bash path translation.

### VIVO Shows 500 Error

VIVO needs time to initialize after restart. Wait 30-60 seconds and try again.

### CollectionSpace Not Responding

CollectionSpace Tomcat doesn't auto-start. Start it manually:

```bash
docker exec collectionspace sh -c "cd /apache-tomcat-8.5.51 && ./bin/startup.sh"
```

### LM Studio Not Found

Ensure LM Studio is running with a vision model loaded on port 1234.

---

## CollectionSpace Setup Guide

CollectionSpace requires building from source and is more complex than the other systems.

### Prerequisites

- Docker with at least 8GB RAM allocated
- Patience (build takes 30-60 minutes)

### Docker Compose

Create `collectionspace/docker-compose.yml`:

```yaml
services:
  db:
    container_name: cspace-db
    image: postgres:12
    environment:
      POSTGRES_USER: csadmin
      POSTGRES_PASSWORD: csadmin
      POSTGRES_DB: cspace_demo
    ports:
      - 5434:5432
    volumes:
      - cspace-db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U csadmin"]
      interval: 10s
      timeout: 5s
      retries: 5

  es:
    container_name: cspace-es
    image: elasticsearch:7.17.9
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - 9202:9200
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -q 'green\\|yellow'"]
      interval: 15s
      timeout: 10s
      retries: 10

  collectionspace:
    container_name: collectionspace
    image: collectionspace/dev:latest
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_CSADMIN_PASSWORD=csadmin
      - ES_HOST=http://es:9200
    ports:
      - 8180:8180
    volumes:
      - cspace-tomcat:/apache-tomcat-8.5.51
    depends_on:
      db:
        condition: service_healthy
      es:
        condition: service_healthy

volumes:
  cspace-db:
  cspace-tomcat:
```

### Building CollectionSpace

After starting the containers, you need to build and deploy:

```bash
# Enter the container
docker exec -it collectionspace bash

# Clone and build services layer
cd /
git clone https://github.com/collectionspace/services
cd services
mvn clean install -DskipTests

# Deploy to Tomcat
ant deploy -Djee.dir=/apache-tomcat-8.5.51

# Initialize database
ant create_db -Djee.dir=/apache-tomcat-8.5.51
ant import -Djee.dir=/apache-tomcat-8.5.51

# Start Tomcat
cd /apache-tomcat-8.5.51
./bin/startup.sh
```

---

## Credits

- **Photographer/Test Images**: Steve Eberhardt ([FreshPremise.com](https://freshpremise.com))
- **Lyrasis Systems**: [lyrasis.org](https://www.lyrasis.org/)
- **Automation**: Built with assistance from Claude AI

---

## License

This project is provided as a demonstration of Lyrasis Community Supported Software working together. Each Lyrasis system has its own license - please refer to their respective documentation.

The automation scripts in this repository are released under the MIT License.
