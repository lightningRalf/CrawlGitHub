# test_logging.py
import logging
import os
import sys
from crawl_github_starred import config

def test_logging():
    # Configure logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(config.WORKING_DIRECTORY, config.LOG_FILE)),
            logging.StreamHandler(sys.stdout)  # Add console output
        ]
    )
    
    logger = logging.getLogger("test")
    
    logger.info("This is a test INFO message")
    logger.warning("This is a test WARNING message")
    logger.error("This is a test ERROR message")
    
    # Test directory permissions
    if not os.path.exists(config.WORKING_DIRECTORY):
        logger.error(f"Working directory does not exist: {config.WORKING_DIRECTORY}")
        os.makedirs(config.WORKING_DIRECTORY, exist_ok=True)
        logger.info(f"Created working directory: {config.WORKING_DIRECTORY}")
    
    logger.info(f"Working directory: {config.WORKING_DIRECTORY}")
    logger.info(f"Write permission: {os.access(config.WORKING_DIRECTORY, os.W_OK)}")
    
    # Test if files can be created/written
    test_file_path = os.path.join(config.WORKING_DIRECTORY, "test_logging_file.txt")
    try:
        with open(test_file_path, "w") as f:
            f.write("Test write successful")
        logger.info(f"Successfully wrote to test file: {test_file_path}")
        os.remove(test_file_path)
        logger.info(f"Successfully removed test file: {test_file_path}")
    except Exception as e:
        logger.error(f"Failed to write/remove test file: {e}")

if __name__ == "__main__":
    test_logging()