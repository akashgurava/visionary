from pathlib import Path


def convert_bytes(num):
    """
    this function will convert bytes to MB.... GB... etc
    """
    for x in ["bytes", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


def file_size(path: Path):
    """
    this function will return the file size
    """
    if path.is_file():
        return convert_bytes(path.stat().st_size)
