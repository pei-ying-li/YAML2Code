import os
import requests

OWNER = "apache"
REPO = "doris"
BRANCH = "master"
TARGET_DIR_SUFFIX = "fe/fe-core/src/main/java"
LOCAL_DIR = "data/doris-fe-core"

# Step 1: Get latest commit SHA for the branch
branch_info_url = f"https://api.github.com/repos/{OWNER}/{REPO}/branches/{BRANCH}"
resp = requests.get(branch_info_url)
resp.raise_for_status()
COMMIT_SHA = resp.json()["commit"]["sha"]

print(f"Using commit SHA: {COMMIT_SHA}")

# Step 2: Get repo tree recursively
GITHUB_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/git/trees/{COMMIT_SHA}?recursive=1"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{COMMIT_SHA}/"

headers = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "doris-java-downloader"
}

resp = requests.get(GITHUB_API_URL, headers=headers)
resp.raise_for_status()
tree = resp.json()["tree"]

# Step 3: Find all .java files under TARGET_DIR_SUFFIX
java_files = [
    item for item in tree
    if item["type"] == "blob"
    and item["path"].endswith(".java")
    and TARGET_DIR_SUFFIX in item["path"]
]

print(f"Found {len(java_files)} Java files.")

# Step 4: Download each file
for file in java_files:
    file_path = file["path"]
    rel_path = file_path.split(TARGET_DIR_SUFFIX, 1)[1].lstrip("/")
    local_path = os.path.join(LOCAL_DIR, rel_path)

    raw_url = RAW_BASE_URL + file_path

    print(f"Downloading {file_path} → {local_path}")
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    raw_content = requests.get(raw_url).text

    with open(local_path, "w", encoding="utf-8") as f:
        f.write(raw_content)
