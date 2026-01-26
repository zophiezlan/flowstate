"""
Path Utilities

This module provides utility functions for path and directory operations.
"""

import os
from pathlib import Path
from typing import Union


def ensure_parent_dir(path: Union[str, Path]) -> Path:
    """
    Ensure the parent directory of a file path exists.

    This consolidates the common pattern of creating parent directories
    before writing to a file.

    Args:
        path: Path to a file (the parent directory will be created)

    Returns:
        Path object of the input path

    Example:
        >>> ensure_parent_dir("/data/logs/app.log")
        # Creates /data/logs/ if it doesn't exist
    """
    path = Path(path)
    parent = path.parent
    if parent and str(parent) != ".":
        parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists.

    Args:
        path: Directory path to create

    Returns:
        Path object of the directory

    Example:
        >>> ensure_dir("/data/backups")
        # Creates /data/backups/ if it doesn't exist
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
