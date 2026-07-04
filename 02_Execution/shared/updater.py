import json
import urllib.error
import urllib.request
from pathlib import Path


GITHUB_OWNER = "JasonBrisart"
GITHUB_REPO = "BrisartResearchArchive"
GITHUB_BRANCH = "main"

EXECUTION_DIR = Path(__file__).resolve().parent.parent

LOCAL_VERSION_FILE = EXECUTION_DIR / "version.txt"
SETTINGS_FILE = EXECUTION_DIR / "settings.json"
UPDATES_DIR = EXECUTION_DIR / "updates"

REMOTE_VERSION_URL = (
    f"https://raw.githubusercontent.com/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version.txt"
)

REMOTE_ZIP_URL = (
    f"https://github.com/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
)


DEFAULT_SETTINGS = {
    "check_for_updates_on_startup": True,
    "ask_before_downloading_updates": True,
    "download_prompt_enabled": True
}


def load_settings():
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)

        merged = dict(DEFAULT_SETTINGS)
        merged.update(settings)

        return merged

    except Exception:
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


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

    print("\nDownloading newest GitHub version...")
    print(f"Source: {REMOTE_ZIP_URL}")

    with urllib.request.urlopen(request, timeout=120) as response:
        with open(output_file, "wb") as f:
            while True:
                chunk = response.read(1024 * 1024)

                if not chunk:
                    break

                f.write(chunk)

    print("\nDownload complete.")
    print(f"Saved to: {output_file}")

    return output_file


def ask_download_choice(remote_version):
    while True:
        print()
        print(f"Update found: {remote_version}")
        print("-" * 80)
        print("Y. Download update package now")
        print("N. Not now")
        print("D. Do not ask again")
        print()

        choice = input("Choice: ").strip().upper()

        if choice in ["Y", "N", "D"]:
            return choice

        print("Invalid choice. Please select Y, N, or D.")


def startup_update_check():
    """
    Checks GitHub automatically when the launcher starts.

    If GitHub version.txt is newer than local version.txt, the user is asked
    whether to download the latest repository ZIP into /updates.

    This does not install the update.
    It only downloads the newest available package when approved.
    """

    settings = load_settings()

    if not settings.get("check_for_updates_on_startup", True):
        return

    print("\nChecking for updates...")

    try:
        local_version = read_local_version()
        remote_version = fetch_remote_version()

        print(f"Local Version:  {local_version}")
        print(f"GitHub Version: {remote_version}")

        if not is_remote_newer(remote_version, local_version):
            print("No update found.")
            return

        if not settings.get("download_prompt_enabled", True):
            print("\nUpdate available, but update download prompts are disabled.")
            print("No files were downloaded.")
            return

        if settings.get("ask_before_downloading_updates", True):
            choice = ask_download_choice(remote_version)

            if choice == "N":
                print("\nUpdate skipped.")
                return

            if choice == "D":
                settings["download_prompt_enabled"] = False
                save_settings(settings)

                print("\nUpdate prompts disabled.")
                print("No files were downloaded.")
                return

        download_latest_zip(remote_version)

        print("\nUpdate package downloaded.")
        print("Install/apply step is not automatic yet.")
        print("No local runtime files were replaced.")

    except urllib.error.HTTPError as exc:
        print("\nUpdate check failed.")
        print(f"HTTP Error: {exc.code}")
        print("Check that the GitHub repo, branch, and version.txt path are correct.")

    except urllib.error.URLError as exc:
        print("\nUpdate check failed.")
        print("Network error:")
        print(exc)

    except Exception as exc:
        print("\nUpdate check failed.")
        print(exc)


def manual_update_check():
    """
    Manual update check from the launcher.

    This ignores the 'download_prompt_enabled' preference so the user can still
    manually check and choose to download later.
    """

    print("\nChecking for updates...")

    try:
        local_version = read_local_version()
        remote_version = fetch_remote_version()

        print(f"Local Version:  {local_version}")
        print(f"GitHub Version: {remote_version}")

        if not is_remote_newer(remote_version, local_version):
            print("No update found.")
            return

        choice = ask_download_choice(remote_version)

        if choice == "N":
            print("\nUpdate skipped.")
            return

        if choice == "D":
            settings = load_settings()
            settings["download_prompt_enabled"] = False
            save_settings(settings)

            print("\nUpdate prompts disabled.")
            print("No files were downloaded.")
            return

        download_latest_zip(remote_version)

        print("\nUpdate package downloaded.")
        print("Install/apply step is not automatic yet.")
        print("No local runtime files were replaced.")

    except urllib.error.HTTPError as exc:
        print("\nUpdate check failed.")
        print(f"HTTP Error: {exc.code}")
        print("Check that the GitHub repo, branch, and version.txt path are correct.")

    except urllib.error.URLError as exc:
        print("\nUpdate check failed.")
        print("Network error:")
        print(exc)

    except Exception as exc:
        print("\nUpdate check failed.")
        print(exc)