"""Read measured GDS sizes for display without changing placement geometry."""
import csv
import math
from pathlib import Path

AUDIT_PATH=Path(__file__).resolve().parent.parent/'gds_project_audit.csv'


def load_actual_sizes(path=AUDIT_PATH):
    sizes={}; reports=[]
    try:
        with Path(path).open(newline='',encoding='utf-8-sig') as source:
            reader=csv.DictReader(source)
            required={'Team','computed_width','computed_height'}
            if not required.issubset(reader.fieldnames or []):
                return {},['GDS audit is missing Team/computed_width/computed_height columns']
            for line,row in enumerate(reader,2):
                code=(row.get('Team') or '').strip()
                try:
                    width=float(row['computed_width']); height=float(row['computed_height'])
                    if not code or any(not math.isfinite(v) or v<=0 for v in (width,height)):
                        raise ValueError('dimensions must be positive finite values')
                    if code.upper() in sizes: raise ValueError('duplicate project code')
                    sizes[code.upper()]=(width,height)
                except (ValueError,TypeError) as error:
                    reports.append(f'GDS audit row {line} ({code}): {error}')
    except OSError as error: reports.append(f'Unable to read GDS audit: {error}')
    return sizes,reports
