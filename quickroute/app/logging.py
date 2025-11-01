import logging
import sys
from .settings import settings


def setup_logging():
    """Configure logging using settings.LOGGING configuration"""

    log_config = settings.LOGGING

    logging.basicConfig(
        level=getattr(logging, log_config["root"]["level"]),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    if not settings.DEBUG:
        file_handler = logging.FileHandler("quickroute.log")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(log_config["formatters"]["verbose"]["format"])
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_config["loggers"]["app"]["level"])

    return app_logger


logger = setup_logging()
