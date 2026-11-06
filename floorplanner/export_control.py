"""Read local export-control document presence for portable plan snapshots."""
from pathlib import Path
import re

EXPORT_CONTROL_DIRECTORY = Path(__file__).resolve().parent.parent / 'data' / 'export_control'


def documented_projects(directory=EXPORT_CONTROL_DIRECTORY):
    """Return project-code prefixes of documents directly inside directory."""
    directory=Path(directory)
    if not directory.is_dir(): return set()
    codes=set()
    for path in directory.iterdir():
        if not path.is_file() or path.name.startswith(('.', '~$')): continue
        match=re.match(r'^([A-Za-z]+\d+)(?=[^A-Za-z0-9]|$)',path.name)
        if match: codes.add(match[1].upper())
    return codes
