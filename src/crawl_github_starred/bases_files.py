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


def write_base_files() -> tuple[str, str]:
    repo_index_path = os.path.join(config.WORKING_DIRECTORY, config.REPO_INDEX_BASE_FILE)
    review_queue_path = os.path.join(config.WORKING_DIRECTORY, config.REVIEW_QUEUE_BASE_FILE)

    with open(repo_index_path, "w", encoding="utf-8") as f:
        f.write(REPO_INDEX_BASE_CONTENT.rstrip() + "\n")

    with open(review_queue_path, "w", encoding="utf-8") as f:
        f.write(REVIEW_QUEUE_BASE_CONTENT.rstrip() + "\n")

    return repo_index_path, review_queue_path
