from dataclasses import dataclass, field, asdict
from pathlib import Path
import hashlib
import json
from .geometry import Rect

CONFIG = Path(__file__).resolve().parent.parent / 'config'

@dataclass(frozen=True)
class Block:
    name: str
    pin_ranges: list[str]
    base_lower_left_um: list[int]
    pin_count: int
    width_um: int
    height_um: int
    source_area_um2: int
    source_utilization: float
    excluded_rectangles_local_um: list[list[int]]

    @property
    def occupied(self):
        parts=[Rect(0,0,self.width_um,self.height_um)]
        for x1,y1,x2,y2 in self.excluded_rectangles_local_um:
            parts=[p for r in parts for p in r.subtract(Rect(x1,y1,x2-x1,y2-y1))]
        return parts

    @property
    def area(self): return sum(r.area for r in self.occupied)

@dataclass
class Project:
    id: str
    name: str = ''
    block_type: str = 'A'
    pin_count: int = 0
    shared_nets: dict[str,str] = field(default_factory=dict)

    def __post_init__(self):
        if type(self.pin_count) is not int or self.pin_count < 0:
            raise ValueError('Pin count must be a nonnegative integer')
        if not self.name.strip(): self.name = self.id

@dataclass
class Placement:
    project_id: str
    block_type: str
    mirror_x: bool = False
    mirror_y: bool = False

@dataclass
class Frame:
    id: str
    name: str = ''
    canvas_position: list[int] = field(default_factory=lambda: [0,0])
    placements: list[Placement] = field(default_factory=list)
    pads: list[dict] = field(default_factory=list)

@dataclass
class Plan:
    projects: list[Project] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)

    def project(self, id): return next(p for p in self.projects if p.id == id)

    def assignment(self, id):
        return next(((f,p) for f in self.frames for p in f.placements if p.project_id==id), (None,None))

    def unassign(self, id):
        for f in self.frames: f.placements[:]=[p for p in f.placements if p.project_id!=id]


def load_catalog(path=CONFIG/'blocks.json'):
    blocks=[Block(**b) for b in json.loads(Path(path).read_text())]
    for b in blocks:
        if b.width_um<=0 or b.height_um<=0: raise ValueError('Invalid block dimensions')
    return {b.name:b for b in blocks}


def config_hash(catalog):
    return hashlib.sha256(json.dumps({k:asdict(v) for k,v in catalog.items()},sort_keys=True).encode()).hexdigest()
