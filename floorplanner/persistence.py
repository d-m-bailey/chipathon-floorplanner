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

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from .models import Plan,Project,Frame,Placement,config_hash
from .validation import validate_all
from .pin_mapping import validate_pad_catalog

def validate_metadata(metadata):
    import math
    if not isinstance(metadata,dict): raise ValueError('Invalid project metadata')
    for code,entry in metadata.items():
        if not isinstance(code,str) or not isinstance(entry,dict): raise ValueError('Invalid project metadata entry')
        for size_key in ('actual_size_um','pr_boundary_size_um'):
            if size_key not in entry: continue
            size=entry[size_key]
            if not isinstance(size,list) or len(size)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in size):
                raise ValueError(f'Invalid {size_key}')
        if 'export_control' in entry and type(entry['export_control']) is not bool: raise ValueError('Invalid export control status')
        if 'design_type' in entry and entry['design_type'] not in ('DIG','ANA','MIX'): raise ValueError('Invalid design type')
        if 'pins' in entry:
            if not isinstance(entry['pins'],list): raise ValueError('Invalid saved pins')
            for pin in entry['pins']:
                if not isinstance(pin,dict) or not isinstance(pin.get('name'),str) or not isinstance(pin.get('io_type'),str): raise ValueError('Invalid saved pin')


def dumps(plan,catalog):
    return json.dumps(dict(schema_version=1,chip_type='gf180mcuD',configuration_hash=config_hash(catalog),**asdict(plan)),indent=2)

def loads(text,catalog,pin_counts=None):
    data=json.loads(text)
    if data.get('schema_version')!=1: raise ValueError('Unsupported schema version')
    if data.get('chip_type')!='gf180mcuD': raise ValueError('Unsupported chip type')
    if data.get('configuration_hash')!=config_hash(catalog): raise ValueError('Block configuration hash mismatch')
    projects=[]
    for item in data['projects']:
        p=dict(item)
        legacy_pins=p.pop('logical_pins', [])
        p.setdefault('pin_count',len(legacy_pins))
        if pin_counts is not None and p['id'].upper() in pin_counts:
            p['pin_count']=pin_counts[p['id'].upper()]
        projects.append(Project(**p))
    frames=[Frame(**{**f,'placements':[Placement(**p) for p in f['placements']]}) for f in data['frames']]
    if len({p.id for p in projects})!=len(projects) or len({f.id for f in frames})!=len(frames): raise ValueError('Duplicate IDs')
    for f in frames:
        validate_pad_catalog(f.pads)
        if len(f.canvas_position)!=2 or any(type(v) is not int for v in f.canvas_position): raise ValueError('Frame positions must be integer coordinates')
        for pad in f.pads:
            if not isinstance(pad.get('id'),str) or any(type(pad.get(k)) is not int for k in ('x_um','y_um')): raise ValueError('Invalid pad coordinates')
    for p in projects:
        if not p.id or (p.block_type not in catalog and p.block_type!='?'): raise ValueError('Invalid project or block type')
    metadata=data.get('project_metadata',{})
    validate_metadata(metadata)
    plan=Plan(projects,frames,project_metadata=metadata)
    errors=[f'{p.project_id}: {e}' for f,p,es,ws in validate_all(plan,catalog) for e in es]
    if errors: raise ValueError('\n'.join(errors))
    return plan

def save(path,plan,catalog):
    path=Path(path); temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False,encoding='utf-8') as out:
            temp=out.name; out.write(dumps(plan,catalog)); out.flush(); os.fsync(out.fileno())
        os.replace(temp,path)
    finally:
        if temp and os.path.exists(temp): os.unlink(temp)
