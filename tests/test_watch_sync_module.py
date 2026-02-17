from crawl_github_starred.watch import candidates as watch_candidates
from crawl_github_starred.watch import export as watch_export
from crawl_github_starred.watch import io as watch_io
from crawl_github_starred.watch import sync as watch_sync


def test_sync_module_uses_candidates_and_io_modules() -> None:
    assert watch_sync.watch_candidates is watch_candidates
    assert watch_sync.watch_io is watch_io


def test_watch_modules_expose_canonical_entry_points() -> None:
    assert callable(watch_sync.sync_watch_candidates_to_notes)
    assert callable(watch_export.export_watch_seed_files)
