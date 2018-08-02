import logging
from config import settings
import os


class Logger:

    def __init__(self, logger_type):
        self.logger_type = logger_type

    def logger(self):
        self.logger = logging.getLogger(self.logger_type)
        self.logger.setLevel(logging.INFO)

        log_path = os.path.join(settings.BASE_DIR, "log", "%s.log" % self.logger_type)
        self.fh = logging.FileHandler(log_path, encoding="utf-8")
        self.fh.setLevel(logging.INFO)

        self.file_fmt = logging.Formatter("%(asctime)s -- %(levelname)s -- %(message)s")
        self.fh.setFormatter(self.file_fmt)

        self.logger.addHandler(self.fh)

        return self.logger
