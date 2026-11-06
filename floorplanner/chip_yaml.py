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

"""Export chip assembly YAML using the IEEE sample schema."""
from pathlib import Path
import os
import re
import tempfile
import yaml
from .validation import validate_all

BASE_CHIP='chipathon2026_gf180mcu_202609.yaml'
QUADRANTS={(False,False):'NW',(True,False):'NE',(False,True):'SW',(True,True):'SE'}
ORDER={'NW':0,'NE':1,'SE':2,'SW':3}


def chip_documents(plan,catalog):
    errors=[f'{f.id}/{p.project_id}: {e}' for f,p,es,_ in validate_all(plan,catalog) for e in es]
    if errors: raise ValueError('Cannot export invalid placements:\n'+'\n'.join(errors))
    documents={}
    for index,frame in enumerate(plan.frames,1):
        match=re.fullmatch(r'chip_(\d+)',frame.id)
        number=int(match[1]) if match else index
        filename=f'IEEE{number}.yaml'
        if filename in documents: raise ValueError(f'Duplicate output filename: {filename}')
        projects=[{'team':p.project_id,'variant':p.block_type,'quadrant':QUADRANTS[p.mirror_x,p.mirror_y]} for p in frame.placements]
        projects.sort(key=lambda p:ORDER[p['quadrant']])
        documents[filename]={'schema_version':2,'base_chip':BASE_CHIP,
                            'chip':{'name':f'SSCS_2026_{number:02}','minimum_project_gap_um':10},
                            'projects':projects}
    return documents


def export_chip_yaml(directory,plan,catalog):
    documents=chip_documents(plan,catalog)
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    # Use the same license notice as other source files, in YAML comments.
    header='\n'.join(Path(__file__).read_text().splitlines()[:15])+'\n\n'
    paths=[]
    for filename,document in documents.items():
        target=directory/filename; temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=directory,delete=False) as stream:
                temporary=stream.name
                stream.write(header+yaml.safe_dump(document,sort_keys=False,allow_unicode=True))
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary,target); paths.append(target)
        finally:
            if temporary and os.path.exists(temporary): os.unlink(temporary)
    return paths
