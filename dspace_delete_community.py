"""Delete a DSpace community."""
import argparse
import requests

# Load from config.py if it exists
try:
    from config import DSPACE_API_URL, DSPACE_EMAIL as EMAIL, DSPACE_PASSWORD as PASSWORD, DSPACE_COMMUNITY_NAME as BASE_COMMUNITY_NAME
except ImportError:
    DSPACE_API_URL = "http://localhost:8081/server/api"
    EMAIL = "your-email@example.com"
    PASSWORD = "your-password"
    BASE_COMMUNITY_NAME = "My Image Collection"

# Parse optional prefix argument
parser = argparse.ArgumentParser(description="Delete DSpace community")
parser.add_argument("--prefix", "-p", default="", help="Prefix used when creating (e.g., 'Demo 1 - ')")
args = parser.parse_args()

COMMUNITY_NAME = f"{args.prefix}{BASE_COMMUNITY_NAME}" if args.prefix else BASE_COMMUNITY_NAME
print(f"Looking for community: {COMMUNITY_NAME}")

session = requests.Session()

# Get CSRF
r = session.get(f"{DSPACE_API_URL}/security/csrf")
csrf = r.json().get("token") if r.status_code == 200 else None
if "DSPACE-XSRF-COOKIE" in session.cookies:
    csrf = session.cookies["DSPACE-XSRF-COOKIE"]

# Login
headers = {"Content-Type": "application/x-www-form-urlencoded", "X-XSRF-TOKEN": csrf}
r = session.post(f"{DSPACE_API_URL}/authn/login", data={"user": EMAIL, "password": PASSWORD}, headers=headers)
auth = r.headers.get("Authorization")
print(f"Logged in: {r.status_code}")

# Refresh CSRF
if "DSPACE-XSRF-COOKIE" in session.cookies:
    csrf = session.cookies["DSPACE-XSRF-COOKIE"]

# Find and delete community
headers = {"Authorization": auth, "X-XSRF-TOKEN": csrf}
r = session.get(f"{DSPACE_API_URL}/core/communities", headers=headers)

if r.status_code == 200:
    communities = r.json().get("_embedded", {}).get("communities", [])
    for c in communities:
        if c.get("name") == COMMUNITY_NAME:
            uuid = c["uuid"]
            print(f"Found community: {uuid}")

            # Refresh CSRF before delete
            if "DSPACE-XSRF-COOKIE" in session.cookies:
                csrf = session.cookies["DSPACE-XSRF-COOKIE"]

            headers = {"Authorization": auth, "X-XSRF-TOKEN": csrf}
            r = session.delete(f"{DSPACE_API_URL}/core/communities/{uuid}", headers=headers)
            print(f"Delete response: {r.status_code}")
            if r.status_code == 204:
                print("Community deleted successfully!")
            else:
                print(f"Delete failed: {r.text}")
            break
    else:
        print("Community not found - may already be deleted.")
