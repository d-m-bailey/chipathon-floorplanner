from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from .models import Plan,Project,Frame,Placement,config_hash
from .validation import validate_all
from .pin_mapping import validate_pad_catalog

def dumps(plan,catalog):
    return json.dumps(dict(schema_version=1,chip_type='gf180mcuD',configuration_hash=config_hash(catalog),**asdict(plan)),indent=2)

def loads(text,catalog):
    data=json.loads(text)
    if data.get('schema_version')!=1: raise ValueError('Unsupported schema version')
    if data.get('chip_type')!='gf180mcuD': raise ValueError('Unsupported chip type')
    if data.get('configuration_hash')!=config_hash(catalog): raise ValueError('Block configuration hash mismatch')
    projects=[]
    for item in data['projects']:
        p=dict(item)
        legacy_pins=p.pop('logical_pins', [])
        p.setdefault('pin_count',len(legacy_pins))
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
    plan=Plan(projects,frames)
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
