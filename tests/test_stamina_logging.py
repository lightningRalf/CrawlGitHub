import stamina
import logging
import sys
import os
import requests
from crawl_github_starred import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.WORKING_DIRECTORY, config.LOG_FILE)),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("test_stamina")

# Activate structlog-based instrumentation.
stamina.instrumentation.set_on_retry_hooks(
    [stamina.instrumentation.StructlogOnRetryHook]
)

@stamina.retry(
    on=requests.exceptions.RequestException,
    attempts=3,
    wait_initial=1.0,
    wait_max=5.0,
    wait_jitter=1.0,
)
def test_failing_request():
    """A function that will fail and trigger retries"""
    logger.info("Attempting request that will fail")
    raise requests.exceptions.ConnectionError("Test failure to trigger retry")

if __name__ == "__main__":
    logger.info("Starting Stamina retry test")
    try:
        test_failing_request()
    except Exception as e:
        logger.error(f"Final error after retries: {e}")