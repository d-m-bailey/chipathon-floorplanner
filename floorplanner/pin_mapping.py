import re

def expand_ranges(ranges):
    result=[]
    for item in ranges:
        m=re.fullmatch(r'([WNES])(\d{2})(?:-([WNES])(\d{2}))?', item)
        if not m or (m[3] and m[1]!=m[3]): raise ValueError(f'Invalid pin range: {item}')
        a,b=int(m[2]),int(m[4] or m[2]); step=1 if b>=a else -1
        result.extend(f'{m[1]}{i:02}' for i in range(a,b+step,step))
    return result

def validate_pad_catalog(pads):
    if not isinstance(pads,list): raise ValueError('pads must be a list')
    for pad in pads:
        if not isinstance(pad,dict) or not isinstance(pad.get('id'),str) or not pad['id']:
            raise ValueError('Every pad needs an ID')
        if any(type(pad.get(k)) is not int or not 0<=pad[k]<=2935 for k in ('x_um','y_um')):
            raise ValueError('Pad coordinates must be integer micrometers within the chip')
    if len({p['id'] for p in pads})!=len(pads) or len({(p['x_um'],p['y_um']) for p in pads})!=len(pads):
        raise ValueError('Pad IDs and coordinates must be unique')

def mapped_pins(block, mx, my, pads):
    pins=expand_ranges(block.pin_ranges)
    by_id={p['id']:p for p in pads}
    by_xy={(p['x_um'],p['y_um']):p['id'] for p in pads}
    if len(by_id)!=len(pads) or len(by_xy)!=len(pads):
        raise ValueError('Pad IDs and coordinates must be unique')
    if not pads: return (pins if not (mx or my) else []), False
    result=[]
    for pin in pins:
        if pin not in by_id: return (pins if not (mx or my) else []),False
        p=by_id[pin]; x,y=p['x_um'],p['y_um']
        target=by_xy.get((2935-x if mx else x,2935-y if my else y))
        if target is None: return (pins if not (mx or my) else []),False
        result.append(target)
    return result,True
