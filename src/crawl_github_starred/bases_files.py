import os

from . import config


REPO_INDEX_BASE_CONTENT = """filters:
  and:
    - 'source == "github-star"'
views:
  - type: table
    name: Repo index
    order:
      - file.name
      - repo
      - review_status
      - why_starred
      - next_action
      - stars
      - watchers
      - forks
      - maintained
      - last_pushed_at
      - last_release
      - topics
      - language
      - repo_url
  - type: list
    name: Quick triage
    filters:
      and:
        - 'source == "github-star"'
        - or:
            - 'review_status == "inbox"'
            - 'why_starred == ""'
    order:
      - file.name
      - review_status
      - why_starred
      - next_action
      - stars
"""


REVIEW_QUEUE_BASE_CONTENT = """filters:
  and:
    - 'source == "github-star"'
    - or:
        - 'review_status == "inbox"'
        - 'why_starred == ""'
views:
  - type: table
    name: Review queue
    order:
      - file.name
      - why_starred
      - next_action
      - review_status
      - stars
      - last_pushed_at
      - maintained
      - repo_url
  - type: table
    name: Ready to decide
    filters:
      and:
        - 'source == "github-star"'
        - 'review_status != "done"'
        - 'why_starred != ""'
    order:
      - file.name
      - why_starred
      - next_action
      - stars
      - maintained
      - last_pushed_at
"""


WATCH_CANDIDATES_BASE_CONTENT = """filters:
  and:
    - 'watch_candidate == "true"'
views:
  - type: table
    name: Needs triage
    filters:
      and:
        - 'watch_candidate == "true"'
        - or:
            - 'watch_status == "new"'
            - 'watch_status == "inbox"'
    order:
      - watch_updated_at
      - file.name
      - watch_type
      - watch_owner
      - watch_confidence
      - watch_signal_sources
      - watch_signal_count
      - watch_tags
      - watch_why
      - watch_discovered_at
      - repo
      - package
  - type: table
    name: Active watch candidates
    filters:
      and:
        - 'watch_candidate == "true"'
        - 'watch_status != "archived"'
    order:
      - watch_updated_at
      - file.name
      - watch_type
      - watch_status
      - watch_owner
      - watch_confidence
      - watch_signal_sources
      - watch_signal_count
      - watch_tags
      - watch_why
      - repo
      - package
      - repo_url
  - type: table
    name: Reactivated
    filters:
      and:
        - 'watch_candidate == "true"'
        - 'watch_status != "archived"'
        - 'watch_reactivated_at != ""'
    order:
      - watch_reactivated_at
      - file.name
      - watch_type
      - watch_status
      - watch_confidence
      - watch_signal_sources
      - watch_signal_count
      - watch_tags
      - watch_why
  - type: table
    name: npm candidates
    filters:
      and:
        - 'watch_candidate == "true"'
        - 'watch_type == "npm"'
        - 'watch_status != "archived"'
    order:
      - watch_updated_at
      - file.name
      - package
      - watch_status
      - watch_confidence
      - watch_signal_sources
      - watch_signal_count
      - watch_tags
      - watch_why
      - from_repos
      - repo_url
  - type: table
    name: Archived
    filters:
      and:
        - 'watch_candidate == "true"'
        - 'watch_status == "archived"'
    order:
      - watch_archived_at
      - watch_updated_at
      - file.name
      - watch_type
      - watch_confidence
      - watch_signal_sources
      - watch_signal_count
      - watch_tags
      - watch_why
"""


def write_base_files() -> tuple[str, str]:
    repo_index_path = os.path.join(config.WORKING_DIRECTORY, config.REPO_INDEX_BASE_FILE)
    review_queue_path = os.path.join(config.WORKING_DIRECTORY, config.REVIEW_QUEUE_BASE_FILE)

    with open(repo_index_path, "w", encoding="utf-8") as f:
        f.write(REPO_INDEX_BASE_CONTENT.rstrip() + "\n")

    with open(review_queue_path, "w", encoding="utf-8") as f:
        f.write(REVIEW_QUEUE_BASE_CONTENT.rstrip() + "\n")

    return repo_index_path, review_queue_path


def write_watch_candidates_base() -> str:
    watch_candidates_path = os.path.join(config.WORKING_DIRECTORY, config.WATCH_CANDIDATES_BASE_FILE)
    with open(watch_candidates_path, "w", encoding="utf-8") as f:
        f.write(WATCH_CANDIDATES_BASE_CONTENT.rstrip() + "\n")
    return watch_candidates_path
