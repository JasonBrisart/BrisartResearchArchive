import sys
from pathlib import Path


EXECUTION_DIR = Path(__file__).resolve().parent.parent

if str(EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTION_DIR))


from shared.runtime import run_framework
import framework


def main():
    run_framework(framework)


if __name__ == "__main__":
    main()