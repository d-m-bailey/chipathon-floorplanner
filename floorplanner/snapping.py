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

from .transforms import bounds, occupied
from .pin_mapping import mapped_pins

def candidates(block,pads=()):
    seen=set()
    for mx,my in [(False,False),(True,False),(False,True),(True,True)]:
        pins,verified=mapped_pins(block,mx,my,pads)
        # Unverified orientations cannot safely be considered electrically equivalent.
        key=(tuple(sorted((r.x,r.y,r.w,r.h) for r in occupied(block,mx,my))),tuple(pins),None if verified else (mx,my))
        if key not in seen:
            seen.add(key); yield mx,my

def snap(block, point, scale, max_pixels=180, pads=()):
    choices=list(candidates(block,pads))
    choice=min(choices,key=lambda c: sum((a-b)**2 for a,b in zip(bounds(block,*c).center,point)))
    distance=sum((a-b)**2 for a,b in zip(bounds(block,*choice).center,point))**0.5*abs(scale)
    return choice if distance<=max_pixels else None

FRAME_GRID_UM = 500
# Smallest whole number of grid steps that fits a 2935 µm frame.
FRAME_PITCH_UM = ((2935 + FRAME_GRID_UM - 1) // FRAME_GRID_UM) * FRAME_GRID_UM

def snap_frame_position(x, y):
    """Snap a frame's lower-left to the canvas grid in physical micrometers."""
    from math import floor
    return [floor(value / FRAME_GRID_UM + 0.5) * FRAME_GRID_UM for value in (x, y)]
