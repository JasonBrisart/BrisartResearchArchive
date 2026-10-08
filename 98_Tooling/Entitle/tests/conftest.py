import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from entitle.bootstrap import ensure_bsr_on_path  # noqa: E402
ensure_bsr_on_path()

import pytest  # noqa: E402


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "records" / "entitle_records.log"
