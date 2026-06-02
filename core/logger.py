"""
core/logger.py — shared logging setup for the whole harness.

WHAT: get_agent_logger(log_file) → singleton logger writing to stdout (INFO)
      and, when a path is given, a per-run file (DEBUG).
CALLED BY: pipeline.py, core/process_detector.py, and stages that want the
           per-run `00_pipeline_execution.log`.
CALLS: stdlib logging only.
"""
import logging
import os
import sys


def get_agent_logger(log_file_path: str = None) -> logging.Logger:
    """Create/return the shared logger; attach a file handler for `log_file_path`."""
    logger = logging.getLogger("agentic_cad_pipeline")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(module)s:%(funcName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in logger.handlers):
        ch = logging.StreamHandler(sys.stdout); ch.setLevel(logging.INFO); ch.setFormatter(fmt)
        logger.addHandler(ch)

    if log_file_path:
        abs_path = os.path.abspath(log_file_path)
        if not any(isinstance(h, logging.FileHandler) and os.path.abspath(h.baseFilename) == abs_path
                   for h in logger.handlers):
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            fh = logging.FileHandler(abs_path); fh.setLevel(logging.DEBUG); fh.setFormatter(fmt)
            logger.addHandler(fh)
    return logger
