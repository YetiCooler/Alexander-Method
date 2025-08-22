import logging
import io
import os
import sys
from logging.handlers import SysLogHandler

# Create a log capture buffer for audit logs
log_capture = io.StringIO()

# Setup audit_logger
audit_logger = logging.getLogger("audit_logger")
audit_logger.setLevel(logging.DEBUG)
audit_logger.propagate = False  # Don't send logs to root logger

# Setup system_logger
system_logger = logging.getLogger("system_logger")
system_logger.setLevel(logging.DEBUG)
system_logger.propagate = False  # Don't send logs to root logger

# Handlers for audit_logger
audit_buffer_handler = None
audit_console_handler = None


def setup_loggers(system_log_filename):
    """
    Setup both audit and system loggers.

    :param system_log_filename: Path to the file where system logs should be written.
    """
    global audit_buffer_handler, audit_console_handler

    # === Audit Logger (like your original logger) ===
    # Remove existing handlers to avoid duplicates
    for handler in audit_logger.handlers[:]:
        audit_logger.removeHandler(handler)

    # Capture logs to in-memory buffer
    audit_buffer_handler = logging.StreamHandler(log_capture)
    audit_buffer_handler.setLevel(logging.DEBUG)

    # Print logs to stdout
    audit_console_handler = logging.StreamHandler(sys.stdout)
    audit_console_handler.setLevel(logging.DEBUG)

    # Formatter for audit logs
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    audit_buffer_handler.setFormatter(formatter)
    audit_console_handler.setFormatter(formatter)

    # Add handlers to audit_logger
    audit_logger.addHandler(audit_buffer_handler)
    audit_logger.addHandler(audit_console_handler)

    # === System Logger (logs to stdout and file) ===
    for handler in system_logger.handlers[:]:
        system_logger.removeHandler(handler)

    # System logger logs to stdout
    system_stdout_handler = logging.StreamHandler(sys.stdout)
    system_stdout_handler.setLevel(logging.DEBUG)

    # make the directory if it doesn't exist
    os.makedirs(os.path.dirname(system_log_filename), exist_ok=True)

    # System logger also logs to file
    system_file_handler = logging.FileHandler(
        system_log_filename, mode="a", encoding="utf-8"
    )
    system_file_handler.setLevel(logging.DEBUG)

    system_formatter = logging.Formatter(
        "system_logger [%(threadName)s - %(thread)d]: %(levelname)s - %(message)s"
    )

    system_stdout_handler.setFormatter(system_formatter)
    system_file_handler.setFormatter(system_formatter)

    system_logger.addHandler(system_stdout_handler)
    system_logger.addHandler(system_file_handler)

    # Optional: Filter out noisy external library logs
    logging.getLogger("some_external_library").setLevel(logging.WARNING)


def get_audit_log_messages():
    """Retrieve logs from the audit capture buffer."""
    return log_capture.getvalue()


def clear_audit_log_buffer():
    """Clear the audit log buffer."""
    log_capture.truncate(0)
    log_capture.seek(0)


def remove_audit_log_handlers():
    """Remove audit log handlers to avoid duplicates."""
    global audit_buffer_handler, audit_console_handler

    for handler in audit_logger.handlers[:]:
        audit_logger.removeHandler(handler)

    clear_audit_log_buffer()
