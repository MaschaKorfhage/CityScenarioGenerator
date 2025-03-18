"""
Various utility functions
"""

import logging
from pathlib import Path
import shutil
import sys
import unicodedata
import re


#: name of the logfile produced in each scenario generation
LOGFILENAME = "log.txt"


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        # custom replacement for street names
        value = value.replace("ß", "ss")

        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def descriptive_query_text(query: dict) -> str:
    """returns a text describing a builda query in a format suitable for filenames"""
    filtered_query = {k: v for k, v in query.items() if v}
    return slugify(str(filtered_query))


def configure_log_handler(handler):
    """
    Configures a log handler with the default settings

    :param handler: the handler to configure
    """
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    formatter.datefmt = "%Y-%m-%d %H:%M:%S"
    handler.setFormatter(formatter)


def init_logging(directory: Path | None = None):
    """
    Sets up logging with two handlers: one for the console and one for a log file.

    :param directory: output directory; if None, no log file will be created
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # remove the default handler
    logger.handlers.clear()

    # add a handler writing to the console
    console_handler = logging.StreamHandler(sys.stdout)
    configure_log_handler(console_handler)
    logger.addHandler(console_handler)

    if directory:
        # add a handler writing to a log file in the specified directory
        directory.mkdir(parents=True, exist_ok=True)
        logfile_handler = logging.FileHandler(directory / LOGFILENAME, "w", "utf-8")
        configure_log_handler(logfile_handler)
        logger.addHandler(logfile_handler)


def clear_directory(path: Path):
    """
    Clears the specified directory if it already exists.

    :param path: the directory to clear
    """
    if path.is_dir():
        logging.info(f"Clearing directory: {path}")
        shutil.rmtree(path)
