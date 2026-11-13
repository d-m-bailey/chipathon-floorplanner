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

import json
import pytest
from floorplanner.models import *
from floorplanner.geometry import Rect
from floorplanner.transforms import bounds,occupied,reflect_rect
from floorplanner.pin_mapping import expand_ranges,mapped_pins
from floorplanner.snapping import snap
from floorplanner.validation import validate,validate_all
from floorplanner.persistence import dumps,loads,save

@pytest.fixture
def catalog():return load_catalog()

def test_catalog(catalog):
    assert len(catalog)==18
    for b in catalog.values():
        assert len(expand_ranges(b.pin_ranges))==b.pin_count
        assert all(type(v) is int for v in b.base_lower_left_um)
    assert expand_ranges(['E03-E01'])==['E03','E02','E01']

def test_a_reflections(catalog):
    assert [(bounds(catalog['A'],x,y).x,bounds(catalog['A'],x,y).y) for x,y in [(False,False),(True,False),(False,True),(True,True)]]==[(350,1475),(1475,1475),(350,350),(1475,350)]
    for b in catalog.values():
        for r in occupied(b):
            assert reflect_rect(reflect_rect(r,True,False),True,False)==r
            assert reflect_rect(reflect_rect(r,False,True),False,True)==r

def test_ace2(catalog):
    b=catalog['ACE2']; assert b.area==4238775; assert b.source_area_um2==4949325
    for mx,my in [(False,False),(True,False),(False,True),(True,True)]:
        parts=occupied(b,mx,my); assert sum(p.area for p in parts)==4238775
        hole=reflect_rect(Rect(350,350,615,615),mx,my)
        assert not any(p.intersects(hole) for p in parts)

def test_edges():
    assert not Rect(0,0,10,10).intersects(Rect(10,0,10,10))
    assert Rect(0,0,10,10).intersects(Rect(9,0,10,10))

def test_snap(catalog):
    b=catalog['A']; center=bounds(b,True,False).center
    assert snap(b,center,.1)==(True,False)
    assert snap(b,(0,0),1,10) is None
    assert snap(b,(center[0]+100,center[1]),.1,11)==(True,False)
    assert snap(b,(center[0]+100,center[1]),1,11) is None

def test_validation(catalog):
    plan=Plan([Project('a'),Project('b')],[Frame('f'),Frame('g')]); f=plan.frames[0]
    p=Placement('a','A'); f.placements.append(p)
    assert not validate(plan,f,p,catalog)[0]
    assert validate(plan,f,Placement('b','A'),catalog)[0]
    assert not validate(plan,f,Placement('b','A',True,False),catalog)[0]
    assert 'Duplicate project assignment' in validate(plan,plan.frames[1],Placement('a','A'),catalog)[0]
    assert not validate(plan,plan.frames[1],Placement('a','A'),catalog,moving=True)[0]
    plan.project('b').pin_count=23
    assert 'Pin count exceeds block capacity' in validate(plan,f,Placement('b','A',True,False),catalog)[0]

def test_pad_mapping(catalog):
    b=catalog['EH']; pads=[]
    for i,p in enumerate(expand_ranges(b.pin_ranges)):
        pads += [dict(id=p,x_um=0,y_um=100+i*50),dict(id=f'E{i:02}',x_um=2935,y_um=100+i*50)]
    normal,ok=mapped_pins(b,False,False,pads); assert ok
    mirrored,ok=mapped_pins(b,True,False,pads); assert ok and mirrored==[f'E{i:02}' for i in range(5)]
    byid={p['id']:p for p in pads}; byxy={(p['x_um'],p['y_um']):p['id'] for p in pads}
    assert [byxy[(2935-byid[p]['x_um'],byid[p]['y_um'])] for p in mirrored]==normal
    assert mapped_pins(b,True,False,[])[1] is False
    # Pad reuse is independent of overlap.
    plan=Plan([Project('a',block_type='EH'),Project('b',block_type='CH')],[Frame('f',pads=pads)])
    plan.frames[0].placements=[Placement('a','EH')]
    assert any('Pad conflict' in e for e in validate(plan,plan.frames[0],Placement('b','CH'),catalog)[0])

def test_persistence(catalog,tmp_path):
    plan=Plan([Project('a','Alpha')],[Frame('f','One',[10,20],[Placement('a','A',True,True)])])
    path=tmp_path/'plan.json'; save(path,plan,catalog)
    assert loads(path.read_text(),catalog)==plan
    save(path,plan,catalog); assert loads(path.read_text(),catalog)==plan
    data=json.loads(dumps(plan,catalog)); data['schema_version']=9
    with pytest.raises(ValueError): loads(json.dumps(data),catalog)
    data=json.loads(dumps(plan,catalog)); data['frames'].append(dict(id='g',placements=[dict(project_id='a',block_type='A')]))
    with pytest.raises(ValueError,match='Duplicate project'):loads(json.dumps(data),catalog)

def test_import(tmp_path):
    from floorplanner.project_loader import import_projects
    p=tmp_path/'demo'; p.mkdir(); (p/'info.yaml').write_text('id: P12\nname: Test\npins: [vdd, gnd]\nextra: 1\n')
    projects,reports=import_projects(tmp_path,'EV')
    assert projects[0].id=='P12' and projects[0].block_type=='EV'
    assert projects[0].pin_count==2
    assert any('unknown fields' in r for r in reports)

def test_project_count_and_legacy_plans(catalog):
    assert Project('P01').name=='P01'
    with pytest.raises(ValueError): Project('bad',pin_count=-1)
    with pytest.raises(ValueError): Project('bad',pin_count=True)
    plan=Plan([Project('P01',pin_count=7)])
    data=json.loads(dumps(plan,catalog))
    assert data['projects'][0]['pin_count']==7
    assert 'logical_pins' not in data['projects'][0]
    del data['projects'][0]['pin_count']
    data['projects'][0]['logical_pins']=['a','b','c']
    assert loads(json.dumps(data),catalog).projects[0].pin_count==3

def test_import_pin_count(tmp_path):
    from floorplanner.project_loader import import_projects
    p=tmp_path/'example'; p.mkdir()
    (p/'info.yaml').write_text('id: P01\nname: Example\npin_count: 12\n')
    projects,reports=import_projects(tmp_path)
    assert not reports
    assert projects[0].pin_count==12 and projects[0].name=='Example'

def test_frame_grid():
    from floorplanner.snapping import snap_frame_position, FRAME_PITCH_UM
    assert FRAME_PITCH_UM==3000
    assert snap_frame_position(2935,2935)==[3000,3000]
    assert snap_frame_position(3400,3500)==[3500,3500]
    assert snap_frame_position(249,-251)==[0,-500]
    assert snap_frame_position(251,-249)==[500,0]

def test_undefined_block(catalog):
    plan=Plan([Project('TBD',block_type='?',pin_count=12)],[Frame('f')])
    assert loads(dumps(plan,catalog),catalog)==plan
    placement=Placement('TBD','?')
    assert 'Undefined block type' in validate(plan,plan.frames[0],placement,catalog)[0][0]
    plan.frames[0].placements.append(placement)
    with pytest.raises(ValueError,match='Undefined block type'): loads(dumps(plan,catalog),catalog)

def test_gds_audit_sizes(tmp_path):
    from floorplanner.gds_audit import load_actual_sizes
    path=tmp_path/'audit.csv'
    path.write_text('Team,width,height,computed_width,computed_height\nA01,1110,550,603.13,269.59\nA02,1,1,nan,20\nA03,1,1,,5\n')
    sizes,reports=load_actual_sizes(path)
    assert sizes=={'A01':(603.13,269.59)}
    assert len(reports)==2
    assert load_actual_sizes(tmp_path/'missing.csv')[0]=={}

def test_project_pin_markers(catalog,tmp_path):
    from floorplanner.project_pins import load_project_pins,pin_markers
    p=tmp_path/'A01'; p.mkdir(); (p/'info.yaml').write_text('pins:\n- name: VSS\n- name: VDD\n')
    pins,reports=load_project_pins(tmp_path)
    assert pins=={'A01':[{'name':'VSS','io_type':'unknown'},{'name':'VDD','io_type':'unknown'}]} and not reports
    names=[f'p{i}' for i in range(22)]
    b=catalog['A']; normal=pin_markers(b,names)
    assert len(normal)==22
    assert all(x==350 for _,x,y in normal[:11])
    assert all(y==2585 for _,x,y in normal[11:])
    assert normal[0][2]<normal[10][2] and normal[11][1]<normal[21][1]
    for mx,my in [(True,False),(False,True),(True,True)]:
        assert pin_markers(b,names,mx,my)==[(n,2935-x if mx else x,2935-y if my else y) for n,x,y in normal]
    assert len(pin_markers(b,names+['excess']))==22

def test_audit_project_types(tmp_path):
    from floorplanner.gds_audit import load_project_types
    path=tmp_path/'audit.csv'
    path.write_text('Team,type\nA01,Digital\nA02,Analog\nA03,Mixed signal\nA04,Mixed-signal\nA05,unknown\n')
    assert load_project_types(path)=={'A01':'DIG','A02':'ANA','A03':'MIX','A04':'MIX'}
    assert load_project_types(tmp_path/'absent.csv')=={}

def test_chip_yaml_samples(catalog,tmp_path):
    import yaml
    from floorplanner.chip_yaml import chip_documents,export_chip_yaml
    projects=[Project('P1'),Project('P2'),Project('P3'),Project('P4')]
    placements=[Placement(p.id,'A',mx,my) for p,(mx,my) in zip(projects,[(False,False),(True,False),(True,True),(False,True)])]
    plan=Plan(projects,[Frame('chip_01',placements=placements),Frame('chip_02')])
    docs=chip_documents(plan,catalog)
    assert docs['IEEE1.yaml']=={'schema_version':2,'base_chip':'chipathon2026_gf180mcu_202609.yaml','chip':{'name':'SSCS_2026_01','minimum_project_gap_um':10},'projects':[{'team':f'P{i}','variant':'A','quadrant':q} for i,q in enumerate(['NW','NE','SE','SW'],1)]}
    paths=export_chip_yaml(tmp_path,plan,catalog)
    assert len(paths)==2
    assert yaml.safe_load(paths[0].read_text())==docs['IEEE1.yaml']
    assert yaml.safe_load(paths[1].read_text())['projects']==[]
    export_chip_yaml(tmp_path,plan,catalog)


def test_audit_pin_counts_exclude_unmatched(tmp_path,catalog):
    from floorplanner.gds_audit import load_pin_counts
    path=tmp_path/'audit.csv'
    path.write_text('Team,power,ground,analog,input_cmos,input_schmitt,bidirectional,bidirectional_24ma,unmatched\n'
                    'p01,1:VDD,1:VSS,2:a b,3:c d e,1:f,2:g h,1:i,50:internal\n'
                    'P02,0:,0:,0:,0:,0:,0:,0:,9:internal\n'
                    'P03,invalid,0:,0:,0:,0:,0:,0:,0:\n')
    counts,reports=load_pin_counts(path)
    assert counts=={'P01':11,'P02':0}
    assert len(reports)==1
    # Correct counts before capacity validation, and preserve them on save.
    plan=Plan([Project('p01',pin_count=61),Project('other',pin_count=5)],
              [Frame('f',placements=[Placement('p01','A')])])
    corrected=loads(dumps(plan,catalog),catalog,counts)
    assert [p.pin_count for p in corrected.projects]==[11,5]
    assert loads(dumps(corrected,catalog),catalog)==corrected
    assert load_pin_counts(tmp_path/'missing.csv')[0]=={}


def test_pr_boundary_sizes(tmp_path,catalog):
    from floorplanner.gds_audit import load_pr_boundary_sizes
    path=tmp_path/'audit.csv'
    path.write_text('Team,width,height,computed_width,computed_height\nP01,1110,550,600,200\nP02,,550,600,200\nP03,nan,0,600,200\n')
    sizes,reports=load_pr_boundary_sizes(path)
    assert sizes=={'P01':(1110,550)} and len(reports)==2
    plan=Plan([Project('P01')],project_metadata={'P01':{'pr_boundary_size_um':[1110,550]}})
    assert loads(dumps(plan,catalog),catalog)==plan
    plan.project_metadata['P01']['pr_boundary_size_um']=[0,550]
    with pytest.raises(ValueError): loads(dumps(plan,catalog),catalog)
