# Copyright 2026 D. Mitch Bailey
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Read measured GDS sizes for display without changing placement geometry."""
import csv
import math
from pathlib import Path

AUDIT_PATH=Path(__file__).resolve().parent.parent/'gds_project_audit.csv'


def _load_sizes(path,width_column,height_column):
    sizes={}; reports=[]
    try:
        with Path(path).open(newline='',encoding='utf-8-sig') as source:
            reader=csv.DictReader(source)
            required={'Team',width_column,height_column}
            if not required.issubset(reader.fieldnames or []):
                return {},[f'GDS audit is missing Team/{width_column}/{height_column} columns']
            for line,row in enumerate(reader,2):
                code=(row.get('Team') or '').strip()
                try:
                    width=float(row[width_column]); height=float(row[height_column])
                    if not code or any(not math.isfinite(v) or v<=0 for v in (width,height)):
                        raise ValueError('dimensions must be positive finite values')
                    if code.upper() in sizes: raise ValueError('duplicate project code')
                    sizes[code.upper()]=(width,height)
                except (ValueError,TypeError) as error:
                    reports.append(f'GDS audit row {line} ({code}): {error}')
    except OSError as error: reports.append(f'Unable to read GDS audit: {error}')
    return sizes,reports


def load_actual_sizes(path=AUDIT_PATH):
    return _load_sizes(path,'computed_width','computed_height')


def load_pr_boundary_sizes(path=AUDIT_PATH):
    """Read PR boundary dimensions independently of measured content dimensions."""
    return _load_sizes(path,'width','height')


def load_project_types(path=AUDIT_PATH):
    """Read type separately so missing/invalid dimensions do not hide classification."""
    types={}
    aliases={'digital':'DIG','analog':'ANA','mixed signal':'MIX','mixed-signal':'MIX','mixed_signal':'MIX'}
    try:
        with Path(path).open(newline='',encoding='utf-8-sig') as source:
            for row in csv.DictReader(source):
                code=(row.get('Team') or '').strip().upper()
                kind=aliases.get((row.get('type') or '').strip().lower())
                if code and kind: types[code]=kind
    except OSError: pass
    return types


PIN_COUNT_COLUMNS=('power','ground','analog','input_cmos','input_schmitt','bidirectional','bidirectional_24ma')


def load_pin_counts(path=AUDIT_PATH):
    """Count layout pins from recognized audit categories, excluding unmatched."""
    counts={}; reports=[]
    try:
        with Path(path).open(newline='',encoding='utf-8-sig') as source:
            reader=csv.DictReader(source)
            if not {'Team',*PIN_COUNT_COLUMNS}.issubset(reader.fieldnames or []):
                return {},['GDS audit is missing pin count columns']
            for line,row in enumerate(reader,2):
                code=(row.get('Team') or '').strip().upper()
                try:
                    values=[int(row[column].split(':',1)[0]) for column in PIN_COUNT_COLUMNS]
                    if not code or any(value<0 for value in values):
                        raise ValueError('pin counts must be nonnegative integers with a project code')
                    if code in counts: raise ValueError('duplicate project code')
                    counts[code]=sum(values)
                except (ValueError,TypeError,AttributeError) as error:
                    reports.append(f'GDS audit row {line} ({code}): {error}')
    except OSError as error: reports.append(f'Unable to read GDS audit: {error}')
    return counts,reports
