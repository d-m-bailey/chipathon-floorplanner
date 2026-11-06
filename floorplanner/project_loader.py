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

"""Default adapter fields: id, name, pin_count (nonnegative integer), shared_nets (mapping).
Nested field paths can be configured via an adapter JSON mapping.
No block type is inferred from a project identifier.
"""
from pathlib import Path
from .models import Project

def extract(data,path):
    for part in path.split('.'):
        if not isinstance(data,dict): return None
        data=data.get(part)
    return data

def import_projects(root,block_type='A',adapter=None):
    import yaml
    adapter=adapter or {'id':'id','name':'name','pin_count':'pin_count','pins':'pins','shared_nets':'shared_nets'}
    projects=[]; reports=[]
    for path in sorted(Path(root).rglob('info.yaml')):
        try:
            data=yaml.safe_load(path.read_text())
            if not isinstance(data,dict): raise ValueError('Expected a YAML mapping')
            fields={key:extract(data,value) for key,value in adapter.items()}
            for key in ('id','name'):
                if fields.get(key) is None: reports.append(f'{path}: missing {key}')
            known={v.split('.')[0] for v in adapter.values()}
            unknown=set(data)-known
            if unknown: reports.append(f'{path}: unknown fields: {", ".join(sorted(map(str,unknown)))}')
            pin_count=fields.get('pin_count')
            if pin_count is None:
                pins=fields.get('pins')
                if pins is None:
                    reports.append(f'{path}: missing pin_count; defaulting to 0')
                    pin_count=0
                elif isinstance(pins,list): pin_count=len(pins)
                else: raise ValueError('Legacy pins must be a list')
            if type(pin_count) is not int or pin_count < 0:
                raise ValueError('pin_count must be a nonnegative integer')
            shared=fields.get('shared_nets') or {}
            if not isinstance(shared,dict): raise ValueError('shared_nets must be a mapping')
            projects.append(Project(str(fields.get('id') or path.parent.name),str(fields.get('name') or path.parent.name),block_type,pin_count,shared))
        except Exception as e: reports.append(f'{path}: {e}')
    return projects,reports
