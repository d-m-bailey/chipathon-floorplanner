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
