import urllib.error
import urllib.request
from pathlib import Path


GITHUB_OWNER = "JasonBrisart"
GITHUB_REPO = "BrisartResearchArchive"
GITHUB_BRANCH = "main"

LOCAL_VERSION_FILE = Path(__file__).resolve().parent.parent / "version.txt"
UPDATES_DIR = Path(__file__).resolve().parent.parent / "updates"

REMOTE_VERSION_URL = (
    f"https://raw.githubusercontent.com/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version.txt"
)

REMOTE_ZIP_URL = (
    f"https://github.com/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
)


def read_local_version():
    if not LOCAL_VERSION_FILE.exists():
        return "0.0.0"

    return LOCAL_VERSION_FILE.read_text(encoding="utf-8").strip()


def fetch_remote_version():
    request = urllib.request.Request(
        REMOTE_VERSION_URL,
        headers={
            "User-Agent": "BrisartResearchArchive-Updater",
        },
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8").strip()


def normalize_version(version_text):
    version_text = str(version_text).strip()

    if version_text.startswith("v"):
        version_text = version_text[1:]

    parts = version_text.split(".")
    numbers = []

    for part in parts:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)

    while len(numbers) < 3:
        numbers.append(0)

    return tuple(numbers[:3])


def is_remote_newer(remote_version, local_version):
    return normalize_version(remote_version) > normalize_version(local_version)


def download_latest_zip(remote_version):
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)

    output_file = UPDATES_DIR / f"BrisartResearchArchive_{remote_version}.zip"

    if output_file.exists():
        print(f"Update already downloaded: {output_file}")
        return output_file

    request = urllib.request.Request(
        REMOTE_ZIP_URL,
        headers={
            "User-Agent": "BrisartResearchArchive-Updater",
        },
    )

    print("Downloading newest GitHub version...")
    print(f"Source: {REMOTE_ZIP_URL}")

    with urllib.request.urlopen(request, timeout=120) as response:
        with open(output_file, "wb") as f:
            while True:
                chunk = response.read(1024 * 1024)

                if not chunk:
                    break

                f.write(chunk)

    print("Download complete.")
    print(f"Saved to: {output_file}")

    return output_file


def startup_update_check():
    """
    Checks GitHub automatically when the launcher starts.

    If GitHub version.txt is newer than local version.txt,
    this downloads the latest repository ZIP into /updates.

    This does not install the update.
    It only downloads the newest available package.
    """

    print("\nChecking for updates...")

    try:
        local_version = read_local_version()
        remote_version = fetch_remote_version()

        print(f"Local Version:  {local_version}")
        print(f"GitHub Version: {remote_version}")

        if is_remote_newer(remote_version, local_version):
            print("\nUpdate found.")
            download_latest_zip(remote_version)
            print("\nUpdate package downloaded.")
            print("Install/apply step is not automatic yet.")
        else:
            print("No update found.")

    except urllib.error.HTTPError as exc:
        print("\nUpdate check failed.")
        print(f"HTTP Error: {exc.code}")
        print("Check that your GitHub repo, branch, and version.txt path are correct.")

    except urllib.error.URLError as exc:
        print("\nUpdate check failed.")
        print("Network error:")
        print(exc)

    except Exception as exc:
        print("\nUpdate check failed.")
        print(exc)