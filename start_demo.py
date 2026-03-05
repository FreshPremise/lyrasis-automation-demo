"""
Demo Startup Script - Ensures all 5 Lyrasis systems are ready
Run this after Docker Desktop starts to verify all services are working.

Usage: python start_demo.py
"""

import subprocess
import time
import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path

# Load credentials from config.py
try:
    from config import FEDORA_USERNAME, FEDORA_PASSWORD, CSPACE_USERNAME, CSPACE_PASSWORD
except ImportError:
    FEDORA_USERNAME = "fedoraAdmin"
    FEDORA_PASSWORD = "fedoraAdmin"
    CSPACE_USERNAME = "admin@core.collectionspace.org"
    CSPACE_PASSWORD = "Administrator"

# Path to staging images folder
STAGING_IMAGES = Path(__file__).parent / "staging_images"

SERVICES = [
    ("ArchivesSpace UI", "http://localhost/", None),
    ("ArchivesSpace API", "http://localhost:8089", None),
    ("DSpace UI", "http://localhost:4000", None),
    ("DSpace API", "http://localhost:8081/server/api", None),
    ("VIVO", "http://localhost:8082", None),
    ("Fedora", "http://localhost:8083/fcrepo/rest/", (FEDORA_USERNAME, FEDORA_PASSWORD)),
    ("CollectionSpace", "http://localhost:8180/cspace-services/collectionobjects", (CSPACE_USERNAME, CSPACE_PASSWORD)),
]

CONTAINERS_TO_RESTART = [
    "image-server",    # Often has stale port bindings
    "proxy",           # Nginx proxy for ArchivesSpace UI
    "archivesspace",   # API port can get stale
]

CONTAINERS_NEEDING_STARTUP = [
    ("collectionspace", "cd /apache-tomcat-8.5.51 && ./bin/startup.sh"),
]


def run_cmd(cmd):
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except:
        return False


def check_service(name, url, auth=None):
    """Check if a service is responding."""
    try:
        if auth:
            r = requests.get(url, auth=HTTPBasicAuth(*auth), timeout=10)
        else:
            r = requests.get(url, timeout=10)
        return r.status_code == 200
    except:
        return False


def check_image_server():
    """Check image server by testing with an actual image file."""
    # Find an image file in staging_images
    if not STAGING_IMAGES.exists():
        return False, "staging_images folder not found"

    images = list(STAGING_IMAGES.glob("*.jpg")) + list(STAGING_IMAGES.glob("*.jpeg"))
    if not images:
        return True, "No images to test (OK)"

    # Test if the first image is accessible
    test_image = images[0].name
    try:
        r = requests.get(f"http://localhost:8000/{test_image}", timeout=10)
        if r.status_code == 200:
            return True, f"Serving {test_image}"
        else:
            return False, f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, str(e)


def restart_container(name):
    """Restart a Docker container."""
    print(f"  Restarting {name}...")
    run_cmd(f"docker restart {name}")
    time.sleep(3)


def start_container_service(container, command):
    """Run a startup command inside a container."""
    print(f"  Starting service in {container}...")
    run_cmd(f'docker exec {container} sh -c "{command}"')
    time.sleep(2)


def main():
    print("=" * 60)
    print("LYRASIS DEMO STARTUP CHECK")
    print("=" * 60)

    # Step 1: Restart containers that often have stale port bindings
    print("\n[1/4] Restarting containers with potential stale ports...")
    for container in CONTAINERS_TO_RESTART:
        restart_container(container)

    # Step 2: Start services that don't auto-start
    print("\n[2/4] Starting services that require manual startup...")
    for container, command in CONTAINERS_NEEDING_STARTUP:
        start_container_service(container, command)

    # Step 3: Wait for services to initialize
    print("\n[3/4] Waiting for services to initialize...")
    time.sleep(15)

    # Step 4: Check all services
    print("\n[4/4] Checking service status...")
    print("-" * 60)

    all_ok = True
    for name, url, auth in SERVICES:
        status = check_service(name, url, auth)
        icon = "OK" if status else "FAIL"
        print(f"  {name:20} {icon}")
        if not status:
            all_ok = False

    # Check image server with actual file
    img_ok, img_msg = check_image_server()
    icon = "OK" if img_ok else "FAIL"
    print(f"  {'Image Server':20} {icon} ({img_msg})")
    if not img_ok:
        all_ok = False

    print("-" * 60)

    # Retry failed services
    if not all_ok:
        print("\nSome services failed. Retrying in 15 seconds...")
        time.sleep(15)

        print("\nRetrying failed services...")
        print("-" * 60)
        all_ok = True
        for name, url, auth in SERVICES:
            status = check_service(name, url, auth)
            icon = "OK" if status else "FAIL"
            print(f"  {name:20} {icon}")
            if not status:
                all_ok = False

        # Recheck image server
        img_ok, img_msg = check_image_server()
        icon = "OK" if img_ok else "FAIL"
        print(f"  {'Image Server':20} {icon} ({img_msg})")
        if not img_ok:
            all_ok = False

        print("-" * 60)

    if all_ok:
        print("\n*** ALL SYSTEMS READY FOR DEMO ***")
        print("\nSystem URLs:")
        print("  ArchivesSpace:   http://localhost/")
        print("  DSpace:          http://localhost:4000")
        print("  VIVO:            http://localhost:8082")
        print("  Fedora:          http://localhost:8083/fcrepo/rest/")
        print("  CollectionSpace: http://localhost:8180/cspace/core/login")
    else:
        print("\n*** SOME SERVICES NOT READY ***")
        print("Try waiting a bit longer or restart Docker Desktop.")

    print("=" * 60)


if __name__ == "__main__":
    main()
