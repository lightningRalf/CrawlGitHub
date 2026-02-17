from crawl_github_starred import watchlist_exports
from crawl_github_starred.watch import sync as watch_sync


def test_watchlist_exports_keeps_sync_compatibility_shims() -> None:
    assert watchlist_exports.sync_watch_candidates_to_notes is watch_sync.sync_watch_candidates_to_notes
    assert watchlist_exports._npm_candidate_relative_path is watch_sync._npm_candidate_relative_path
    assert watchlist_exports.WATCH_NOTE_FRONTMATTER_ORDER == watch_sync.WATCH_NOTE_FRONTMATTER_ORDER
