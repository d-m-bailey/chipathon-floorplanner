from .geometry import Rect

def reflect_rect(r, mirror_x, mirror_y, width=2935, height=2935):
    return Rect(width-r.x-r.w if mirror_x else r.x, height-r.y-r.h if mirror_y else r.y,r.w,r.h)

def bounds(block, mx=False, my=False):
    return reflect_rect(Rect(*block.base_lower_left_um,block.width_um,block.height_um),mx,my)

def occupied(block, mx=False, my=False):
    x,y=block.base_lower_left_um
    return [reflect_rect(Rect(x+r.x,y+r.y,r.w,r.h),mx,my) for r in block.occupied]
