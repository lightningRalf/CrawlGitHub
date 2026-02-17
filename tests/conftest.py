import os
from pathlib import Path


TEST_WORKDIR = Path(__file__).resolve().parent / ".tmp_workdir"
TEST_WORKDIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("GITHUB_PAT", "test-token")
os.environ.setdefault("CRAWLGITHUB_WORKING_DIR", str(TEST_WORKDIR.as_posix()))
