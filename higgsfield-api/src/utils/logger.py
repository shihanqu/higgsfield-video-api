import logging
import os
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


class DailyFileHandler(TimedRotatingFileHandler):
    """
    A TimedRotatingFileHandler that, at each midnight rollover, opens a new file
    named YYYY_MM_DD.log (and does NOT append any suffix to the old file).
    """

    def __init__(self, log_dir: str, backupCount: int = 14, encoding: str = "utf-8"):
        os.makedirs(log_dir, exist_ok=True)
        # Initial filename is today’s date
        today = datetime.now().strftime("%Y_%m_%d")
        filename = os.path.join(log_dir, f"{today}.log")
        super().__init__(
            filename=filename,
            when="midnight",
            interval=1,
            backupCount=backupCount,
            encoding=encoding,
        )

    def doRollover(self):
        # 1. Close the current stream
        if self.stream:
            self.stream.close()

        # 2. Recompute the log filename based on the new date
        new_date = datetime.now().strftime("%Y_%m_%d")
        self.baseFilename = os.path.join(
            os.path.dirname(self.baseFilename), f"{new_date}.log"
        )
        # 3. Open the new file
        self.stream = self._open()

        # 4. Compute next rollover time
        currentTime = int(time.time())
        self.rolloverAt = self.computeRollover(currentTime)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("higgsfield")
    # allow override via environment
    logger.setLevel(os.getenv("HIGGSFIELD_LOG_LEVEL", "INFO").upper())

    if not logger.handlers:
        log_dir = os.getenv("HIGGSFIELD_LOG_DIR", "logs")

        handler = DailyFileHandler(log_dir=log_dir, backupCount=14)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # (Optional) also log to console
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


# Configure logging immediately when this module is imported
def configure_logging():
    """Configure logging for the entire application."""
    setup_logger()


# Auto-configure when module is imported
configure_logging()
