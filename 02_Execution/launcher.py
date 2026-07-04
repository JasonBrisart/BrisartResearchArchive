import sys
from pathlib import Path


EXECUTION_DIR = Path(__file__).resolve().parent

if str(EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTION_DIR))


def run_startup_update_check():
    try:
        from shared.updater import startup_update_check

        startup_update_check()

    except Exception as exc:
        print("\nStartup update check failed:")
        print(exc)


def print_header():
    print("\n" + "=" * 80)
    print("BRISART RESEARCH ARCHIVE")
    print("FRAMEWORK EXECUTION SUITE")
    print("=" * 80)


def print_menu():
    print("\nRuntime Options")
    print("-" * 80)
    print("1. Run Temporal Feedback Loop (TFL)")
    print("   Launch the interactive TFL execution module.")
    print()
    print("2. Analyze TFL Output")
    print("   Run the analysis report for the latest TFL output file.")
    print()
    print("3. Check for Updates")
    print("   Manually check GitHub and download the newest archive ZIP.")
    print()
    print("Q. Quit")


def get_choice():
    valid_choices = ["1", "2", "3", "Q"]

    while True:
        choice = input("Select option: ").strip().upper()

        if choice in valid_choices:
            return choice

        print("Invalid choice. Please select 1, 2, 3, or Q.")


def launch_tfl():
    print("\nLaunching TFL Runtime Module")
    print("-" * 80)

    try:
        from shared.runtime import run_framework
        from TFL import framework

        run_framework(framework)

    except KeyboardInterrupt:
        print("\nTFL runtime interrupted by user.")

    except Exception as exc:
        print("\nAn error occurred while launching TFL:")
        print(exc)

    input("\nPress Enter to return to launcher...")


def analyze_tfl():
    print("\nLaunching TFL Analysis Module")
    print("-" * 80)

    try:
        from shared.analysis import run_basic_analysis
        from TFL import framework

        run_basic_analysis(framework)

    except KeyboardInterrupt:
        print("\nTFL analysis interrupted by user.")

    except Exception as exc:
        print("\nAn error occurred while launching TFL analysis:")
        print(exc)

    input("\nPress Enter to return to launcher...")


def check_updates():
    try:
        from shared.updater import startup_update_check

        startup_update_check()

    except KeyboardInterrupt:
        print("\nUpdate check interrupted by user.")

    except Exception as exc:
        print("\nAn error occurred while checking for updates:")
        print(exc)

    input("\nPress Enter to return to launcher...")


def main():
    run_startup_update_check()

    while True:
        print_header()
        print_menu()

        choice = get_choice()

        if choice == "Q":
            print("\nExiting Framework Execution Suite.")
            break

        if choice == "1":
            launch_tfl()

        elif choice == "2":
            analyze_tfl()

        elif choice == "3":
            check_updates()


if __name__ == "__main__":
    main()