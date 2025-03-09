import logging
import os
from datetime import datetime

def setup_logging(log_dir="logs", log_level=logging.INFO):
    """Configure application logging"""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = os.path.join(log_dir, f"app-{timestamp}.log")
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    #todo not good gotta start over :'((
    return logger