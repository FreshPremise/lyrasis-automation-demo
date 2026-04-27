import base64
import csv
import json
import re
import sys
from pathlib import Path
import requests

# --- CONFIGURATION ---
LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
MODEL_ID = "zai-org/glm-4.6v-flash" 
OUTPUT_CSV = "captions.csv"

def b64_data_url(image_path: Path) -> str:
    data = image_path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def capitalize_first(text: str) -> str:
    """Ensure first character is capitalized."""
    if text and len(text) > 0:
        return text[0].upper() + text[1:]
    return text

def title_case_fix(text: str) -> str:
    """Convert to title case if all lowercase."""
    if text and text == text.lower():
        return text.title()
    return capitalize_first(text)

def extract_json(text: str) -> dict:
    """Extracts JSON, forces lowercase keys, and fixes capitalization."""
    text = text.strip()
    # Remove <think> blocks and markdown formatting
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            # Force all keys to lowercase
            result = {k.lower(): v for k, v in data.items()}
            # Fix capitalization on title and scope_content
            if "title" in result:
                result["title"] = title_case_fix(result["title"])
            if "scope_content" in result:
                result["scope_content"] = capitalize_first(result["scope_content"])
            return result
        except json.JSONDecodeError:
            pass
    return {"title": "Error", "scope_content": "Could not parse JSON", "keywords": []}

def caption_one(image_path: Path, max_retries: int = 2) -> dict:
    url = f"{LMSTUDIO_BASE_URL}/chat/completions"

    # Generic archival prompt for any photograph
    prompt = (
        "As an archivist, describe this photograph. "
        "Describe people, objects, setting, and any visible text. "
        "FORMATTING RULES: "
        "1. Title: Start with a capital letter, use title case (e.g., 'Musicians at Night Parade'). "
        "2. Description: Start with a capital letter, use proper sentences. "
        "3. Keywords: lowercase, separated by semicolons. "
        "Be concise. Do not explain your reasoning. "
        "Return ONLY valid JSON with these exact lowercase keys: title, scope_content, keywords. "
        "Example: {\"title\": \"Parade Float at Night\", \"scope_content\": \"A colorful float moves down the street.\", \"keywords\": \"parade; float; night\"}"
    )

    payload = {
        "model": MODEL_ID,
        "temperature": 0.15,
        "max_tokens": 600,  # JSON response needs ~200-400 tokens; keep low for speed
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": b64_data_url(image_path)}},
                ],
            }
        ],
    }

    for attempt in range(max_retries + 1):
        r = requests.post(url, json=payload, timeout=600)
        r.raise_for_status()
        data = r.json()
        result = extract_json(data["choices"][0]["message"]["content"])

        # If we got a valid result (not an error), return it
        if result.get("title") != "Error":
            return result

        # If this was the last attempt, return the error result
        if attempt == max_retries:
            print(f"    Warning: Failed to parse JSON after {max_retries + 1} attempts")
            return result

        print(f"    Retry {attempt + 1}: JSON parse failed, trying again...")

    return result

def main():
    if len(sys.argv) != 2:
        print("Usage: python caption_folder.py <folder-path>")
        sys.exit(2)

    folder = Path(sys.argv[1]).expanduser()
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(2)

    images = sorted({p.resolve() for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg"}})
    if not images:
        print("No images found."); sys.exit(0)

    print(f"Starting processing for {len(images)} images. (Wait for GPU processing...)")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "title", "scope_content", "keywords"])
        writer.writeheader()

        for img in images:
            print(f"Processing {img.name}...")
            try:
                res = caption_one(img)
                # Handle potential list or string for keywords
                kw = res.get("keywords", "")
                writer.writerow({
                    "filename": img.name,
                    "title": res.get("title", ""),
                    "scope_content": res.get("scope_content", ""),
                    "keywords": "; ".join(kw) if isinstance(kw, list) else kw
                })
            except Exception as e:
                print(f"ERROR on {img.name}: {e}")

    print(f"\nDone. Results written to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()