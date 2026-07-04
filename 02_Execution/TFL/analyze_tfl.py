import sys
from pathlib import Path


EXECUTION_DIR = Path(__file__).resolve().parent.parent

if str(EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTION_DIR))


from shared.analysis import run_basic_analysis
import framework


def main():
    run_basic_analysis(framework)


if __name__ == "__main__":
    main()