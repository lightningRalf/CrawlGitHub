import io
import logging
from pathlib import Path


def _configure_test_logger(log_file: Path, stream: io.StringIO) -> logging.Logger:
    logger = logging.getLogger("crawl_github_starred.tests.logging")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(stream)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def _teardown_logger(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()
        handler.close()
    logger.handlers.clear()


def test_logging_writes_to_file_and_stream(tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    stream = io.StringIO()

    logger = _configure_test_logger(log_file, stream)
    try:
        logger.info("info-message")
        logger.warning("warning-message")
        logger.error("error-message")
    finally:
        _teardown_logger(logger)

    file_content = log_file.read_text(encoding="utf-8")
    assert "INFO:crawl_github_starred.tests.logging:info-message" in file_content
    assert "WARNING:crawl_github_starred.tests.logging:warning-message" in file_content
    assert "ERROR:crawl_github_starred.tests.logging:error-message" in file_content

    stream_content = stream.getvalue()
    assert "INFO:crawl_github_starred.tests.logging:info-message" in stream_content
    assert "WARNING:crawl_github_starred.tests.logging:warning-message" in stream_content
    assert "ERROR:crawl_github_starred.tests.logging:error-message" in stream_content
