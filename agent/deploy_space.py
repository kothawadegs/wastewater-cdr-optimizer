"""Create or update the Hugging Face Space for the CDR Siting Copilot.

Usage (from the repo root, after `hf auth login`):
    python agent/deploy_space.py <hf-username>/<space-name>
"""

import sys
from pathlib import Path

from huggingface_hub import HfApi

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_ROOT / "agent"


def main(space_id: str) -> None:
    api = HfApi()
    api.create_repo(space_id, repo_type="space", space_sdk="gradio", exist_ok=True)

    for name in ("app.py", "requirements.txt", "README.md"):
        api.upload_file(path_or_fileobj=AGENT_DIR / name, path_in_repo=name, repo_id=space_id, repo_type="space")
    api.upload_file(
        path_or_fileobj=REPO_ROOT / "ca_wwtp_cdr_viability.geojson",
        path_in_repo="ca_wwtp_cdr_viability.geojson",
        repo_id=space_id,
        repo_type="space",
    )
    api.upload_folder(folder_path=REPO_ROOT / "data", path_in_repo="data", repo_id=space_id, repo_type="space")

    print(f"Deployed: https://huggingface.co/spaces/{space_id}")
    print("Next: add an HF_TOKEN secret under the Space's Settings -> Variables and secrets.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        sys.exit(__doc__)
    main(sys.argv[1])
