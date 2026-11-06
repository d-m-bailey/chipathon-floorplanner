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

from .geometry import Rect

def reflect_rect(r, mirror_x, mirror_y, width=2935, height=2935):
    return Rect(width-r.x-r.w if mirror_x else r.x, height-r.y-r.h if mirror_y else r.y,r.w,r.h)

def bounds(block, mx=False, my=False):
    return reflect_rect(Rect(*block.base_lower_left_um,block.width_um,block.height_um),mx,my)

def occupied(block, mx=False, my=False):
    x,y=block.base_lower_left_um
    return [reflect_rect(Rect(x+r.x,y+r.y,r.w,r.h),mx,my) for r in block.occupied]
