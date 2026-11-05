"""Startup pin metadata and relative visual markers, not physical pad coordinates."""
from pathlib import Path
import yaml
from .pin_mapping import expand_ranges

DATA_DIRECTORY=Path(__file__).resolve().parent.parent/'data'
PADS_PER_SIDE=22


def load_project_pins(root=DATA_DIRECTORY):
    pins={}; reports=[]
    for path in sorted(Path(root).glob('*/info.yaml')):
        try:
            data=yaml.safe_load(path.read_text(encoding='utf-8'))
            entries=data.get('pins') if isinstance(data,dict) else None
            if not isinstance(entries,list): raise ValueError('pins must be a list')
            names=[]
            for entry in entries:
                name=entry.get('name') if isinstance(entry,dict) else entry
                if not isinstance(name,str) or not name.strip(): raise ValueError('Each pin needs a name')
                names.append(name)
            pins[path.parent.name.upper()]=names
        except (OSError,ValueError,yaml.YAMLError) as error:
            reports.append(f'{path}: {error}')
    return pins,reports


def pin_markers(block,names,mx=False,my=False):
    """Return (name,x,y) in chip coordinates. Order is W up, N right.

    Catalog side allocations partition the ordered logical list. Markers are
    evenly centered in the allocated edge slots; no physical pad lookup is implied.
    E and S allocations continue around the perimeter clockwise.
    """
    pads=expand_ranges(block.pin_ranges)
    counts={side:sum(p.startswith(side) for p in pads) for side in 'WNES'}
    offsets=dict.fromkeys('WNES',0)
    x0,y0=block.base_lower_left_um; w,h=block.width_um,block.height_um
    result=[]
    for name,pad in zip(names,pads):
        side=pad[0]; count=counts[side]
        if count>PADS_PER_SIDE: raise ValueError('More than 22 pads on one side')
        t=(offsets[side]+0.5)/count; offsets[side]+=1
        u,v={'W':(0,t*h),'N':(t*w,h),'E':(w,(1-t)*h),'S':((1-t)*w,0)}[side]
        x,y=x0+u,y0+v
        result.append((name,2935-x if mx else x,2935-y if my else y))
    return result
