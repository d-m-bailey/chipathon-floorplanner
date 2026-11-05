from .geometry import Rect
from .transforms import occupied
from .pin_mapping import mapped_pins

def validate(plan, frame, placement, catalog, moving=False):
    errors=[]; warnings=[]
    if placement.block_type=='?': return ['Undefined block type: choose a block type before placement'],[]
    if placement.block_type not in catalog: return ['Unknown block type'],[]
    try: project=plan.project(placement.project_id)
    except StopIteration: return ['Unknown project'],[]
    if type(placement.mirror_x) is not bool or type(placement.mirror_y) is not bool: return ['Invalid reflection'],[]
    block=catalog[placement.block_type]
    if project.block_type!=block.name: errors.append('Project block type differs from placement')
    if project.pin_count>block.pin_count: errors.append('Pin count exceeds block capacity')
    parts=occupied(block,placement.mirror_x,placement.mirror_y)
    if any(not Rect(350,350,2235,2235).contains(r) for r in parts): errors.append('Outside chip interior')
    pins,verified=mapped_pins(block,placement.mirror_x,placement.mirror_y,frame.pads)
    if not verified: warnings.append('Physical pad mapping UNVERIFIED: supply a complete pad catalog')
    if block.area!=block.source_area_um2: warnings.append(f'Source area {block.source_area_um2:,} differs from calculated {block.area:,} µm²')
    for f in plan.frames:
        for other in f.placements:
            if other is placement: continue
            if other.project_id==placement.project_id:
                if moving: continue
                errors.append('Duplicate project assignment'); continue
            if f is not frame: continue
            if other.block_type not in catalog: continue
            ob=catalog[other.block_type]
            if any(a.intersects(b) for a in parts for b in occupied(ob,other.mirror_x,other.mirror_y)): errors.append(f'Overlaps {other.project_id}')
            op,ov=mapped_pins(ob,other.mirror_x,other.mirror_y,f.pads)
            # Base allocations are explicit even without a physical coordinate catalog.
            conflict=set(pins)&set(op)
            if conflict: errors.append(f'Pad conflict with {other.project_id}: {", ".join(sorted(conflict))}')
    return list(dict.fromkeys(errors)),warnings

def validate_all(plan,catalog):
    return [(f,p,*validate(plan,f,p,catalog)) for f in plan.frames for p in f.placements]
