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

import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtWidgets import QApplication,QFileDialog
from PySide6.QtCore import QPoint
from floorplanner.gui.main_window import MainWindow
from floorplanner.models import Project,Placement

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(); w.actual_sizes={}; w.pr_boundary_sizes={}; w.project_pins={}; w.project_types={}; w.export_control_directory=tmp_path/'absent'; w.show(); app.processEvents(); yield w
    w.dirty=False; w.close()

def test_gui_drag_and_undo(window,app):
    w=window; w.plan.projects=[Project('A01'),Project('A02')]; w.refresh(); w.view.fit(); app.processEvents()
    f=w.plan.frames[0]
    point=w.view.mapFromScene(905,2030)
    w.view.show_preview(point,'A01'); assert w.view.candidate and not w.view.candidate[2]
    w.view.commit(); assert len(f.placements)==1
    # An invalid drag leaves the previous valid position intact.
    w.plan.projects.append(Project('A03')); w.refresh()
    w.view.show_preview(point,'A03'); assert w.view.candidate[2]
    w.view.commit(); assert len(f.placements)==1 and w.plan.assignment('A03')==(None,None)
    w.selected='A01'; w.mirror('x'); assert f.placements[0].mirror_x
    w.undo(); assert not w.plan.frames[0].placements[0].mirror_x
    w.redo(); assert w.plan.frames[0].placements[0].mirror_x
    assert len(w.plan.frames)==4
    # Move the same project to another chip; assignment remains unique.
    second=w.plan.frames[1]
    destination=w.view.mapFromScene(second.canvas_position[0]+905,second.canvas_position[1]+2030)
    w.view.show_preview(destination,'A01'); assert not w.view.candidate[2]
    w.view.commit()
    assert w.plan.assignment('A01')[0] is second
    assert sum(p.project_id=='A01' for f in w.plan.frames for p in f.placements)==1

def test_exports(window,tmp_path,monkeypatch):
    w=window; w.plan.projects=[Project('ACE',block_type='ACE2')]; w.plan.frames[0].placements=[Placement('ACE','ACE2')]; w.refresh()
    for ext in ('png','svg'):
        path=tmp_path/f'plan.{ext}'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,p=path,**k:(str(p),''))
        w.export(ext); assert path.stat().st_size>1000
    text=(tmp_path/'plan.svg').read_text(); assert '<svg' in text and 'ACE' in text

def test_pin_count_entry_and_display(window,monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    calls=[]
    def text(parent,title,prompt,**kwargs):
        calls.append((prompt,kwargs.get('text')))
        return ('ProjectName',True) if prompt=='Project ID:' else ('',True)
    monkeypatch.setattr(QInputDialog,'getText',text)
    monkeypatch.setattr(QInputDialog,'getItem',lambda *a,**k:('A',True))
    monkeypatch.setattr(QInputDialog,'getInt',lambda *a,**k:(12,True))
    window.add_project()
    assert calls==[('Project ID:','')]
    project=window.plan.projects[0]
    assert project.name=='ProjectName' and project.pin_count==12
    assert '12/22' in window.palette.item(0).text()
    assert 'Pins: 12/22' in window.inspector.toPlainText()

def test_frame_click_and_drag_preserves_frame_and_projects(window,app):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from floorplanner.gui.main_window import FrameItem
    w=window
    w.plan.projects=[Project('P01')]
    w.plan.frames[0].placements=[Placement('P01','A')]
    w.refresh(); w.view.fit(); app.processEvents()
    frame=w.plan.frames[0]
    start=w.view.mapFromScene(150,150)
    QTest.mouseClick(w.view.viewport(),Qt.LeftButton,pos=start)
    app.processEvents()
    assert len([i for i in w.view.scene().items() if isinstance(i,FrameItem)])==4
    assert frame.canvas_position==[0,0]
    item=w.frame_items[0]
    block=next(i for i in item.childItems() if i.data(0)=='P01')
    before=block.scenePos()
    end=start+QPoint(70,-60)
    QTest.mousePress(w.view.viewport(),Qt.LeftButton,pos=start)
    QTest.mouseMove(w.view.viewport(),end,delay=20)
    # Projects follow the frame during the drag, before the scene is rebuilt.
    assert item.pos()!=before
    assert block.scenePos()==item.pos()
    QTest.mouseRelease(w.view.viewport(),Qt.LeftButton,pos=end)
    app.processEvents()
    assert frame.canvas_position!=[0,0]
    assert all(v % 500 == 0 for v in frame.canvas_position)
    assert len(w.plan.frames)==4 and len(frame.placements)==1
    assert len([i for i in w.view.scene().items() if isinstance(i,FrameItem)])==4
    w.undo(); assert w.plan.frames[0].canvas_position==[0,0]
    w.redo(); assert w.plan.frames[0].canvas_position!=[0,0]

def test_undefined_project_is_listed_but_not_placeable(window):
    from PySide6.QtCore import Qt
    w=window; w.plan.projects=[Project('TBD',block_type='?',pin_count=12)]; w.selected='TBD'; w.refresh()
    row=w.palette.item(0)
    assert 'TBD · ? · 12/? pins · unassigned' in row.text()
    assert not row.flags() & Qt.ItemIsDragEnabled
    assert 'choose a defined block type' in w.inspector.toPlainText()
    w.view.show_preview(w.view.mapFromScene(905,2030),'TBD')
    assert w.view.candidate is None and w.view.preview is None
    w.view.commit(); assert w.plan.assignment('TBD')==(None,None)

def test_startup_file_loading(window,tmp_path):
    from main import parse_args
    from floorplanner.models import Plan,Frame
    from floorplanner.persistence import save
    path=tmp_path/'initial plan.json'
    plan=Plan([Project('Startup',pin_count=5)],[Frame('initial')])
    save(path,plan,window.catalog)
    assert parse_args([str(path)]).filename==str(path)
    assert parse_args([]).filename is None
    window.load_file(path,record_history=False)
    assert window.plan==plan and window.path==str(path.resolve())
    assert not window.dirty and not window.undo_stack
    bad=tmp_path/'bad.json'; bad.write_text('{}')
    with pytest.raises(ValueError): window.load_file(bad,record_history=False)
    assert window.plan==plan and window.path==str(path.resolve())

def test_export_control_status_is_live_and_saved(window,tmp_path):
    from PySide6.QtGui import QColor
    from floorplanner.persistence import dumps
    w=window; w.export_control_directory=tmp_path
    w.plan.projects=[Project('A01',pin_count=12)]
    w.plan.frames[0].placements=[Placement('A01','A')]; w.selected='A01'
    serialized=dumps(w.plan,w.catalog)
    def block(): return next(i for i in w.frame_items[0].childItems() if i.data(0)=='A01')
    w.refresh()
    assert w.palette.item(0).foreground().color()==QColor('#c62828')
    assert 'Missing export control' in w.palette.item(0).toolTip()
    assert block().pen().color()==QColor('#ff3030')
    # A different project and a directory must not count as documents.
    (tmp_path/'A010_Export.docx').write_text('')
    (tmp_path/'A01_directory').mkdir()
    w.refresh(); assert block().pen().color()==QColor('#ff3030')
    doc=tmp_path/'A01_Export_Control.pdf'; doc.write_text('')
    w.refresh()
    assert w.palette.item(0).foreground().color()==QColor('#174b32')
    assert block().pen().color()==QColor('white')
    doc.unlink(); w.refresh()
    assert block().pen().color()==QColor('#ff3030')
    assert w.plan.project_metadata['A01']['export_control'] is False
    assert 'export_control' in dumps(w.plan,w.catalog)

def test_double_click_block_opens_project_editor(window,app,monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    w=window
    w.plan.projects=[Project('P01',pin_count=12)]
    w.plan.frames[0].placements=[Placement('P01','A')]
    w.refresh(); w.view.fit(); app.processEvents()
    calls=[]
    monkeypatch.setattr(w,'project_values',lambda project:calls.append(project.id))
    block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
    label=next(i for i in block.childItems() if isinstance(i,QGraphicsSimpleTextItem))
    for point in (block.mapToScene(900,1800),label.mapToScene(label.boundingRect().center())):
        QTest.mouseDClick(w.view.viewport(),Qt.LeftButton,pos=w.view.mapFromScene(point))
        QTest.mouseRelease(w.view.viewport(),Qt.LeftButton,pos=w.view.mapFromScene(point))
        app.processEvents()
        assert w.view.drag_id is None and w.view.candidate is None
        assert w.plan.assignment('P01')[0] is w.plan.frames[0]
    assert calls==['P01','P01']
    assert w.selected=='P01'

def test_actual_size_box_is_centered_and_to_scale(window):
    from PySide6.QtWidgets import QGraphicsRectItem
    from PySide6.QtGui import QColor
    w=window; w.actual_sizes={'P01':(603.13,269.59)}; w.selected='P01'
    w.plan.projects=[Project('P01')]
    for mx,my in [(False,False),(True,False),(False,True),(True,True)]:
        w.plan.frames[0].placements=[Placement('P01','A',mx,my)]; w.refresh()
        block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
        box=next(i for i in block.childItems() if isinstance(i,QGraphicsRectItem))
        assert box.rect().width()==pytest.approx(603.13)
        assert box.rect().height()==pytest.approx(269.59)
        assert box.rect().center()==block.path().boundingRect().center()
        assert box.pen().color()==QColor('white')
        assert '603.13 × 269.59 µm' in w.inspector.toPlainText()

def test_pin_dots_reflect_and_show_names(window):
    from PySide6.QtWidgets import QGraphicsEllipseItem
    w=window; w.project_pins={'P01':['VSS','VDD']}; w.plan.projects=[Project('P01')]
    positions=[]
    for mx in (False,True):
        w.plan.frames[0].placements=[Placement('P01','A',mx,False)]; w.refresh()
        block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
        dots=[i for i in block.childItems() if isinstance(i,QGraphicsEllipseItem)]
        assert {d.toolTip() for d in dots}=={'VSS (unknown)','VDD (unknown)'}
        positions.append(sorted(d.rect().center().x() for d in dots))
    assert positions==[[350,350],[2585,2585]]

def test_pin_type_colors_and_zoom_labels(window):
    from PySide6.QtGui import QColor,QImage,QPainter
    from PySide6.QtWidgets import QGraphicsEllipseItem,QStyleOptionGraphicsItem
    from floorplanner.gui.main_window import PinLabel
    from floorplanner.project_pins import pin_color
    types=['ground','power','input_cmos','input_schmitt','bidirectional']
    assert [pin_color(t) for t in types]==['#000000','#ff0000','#00b050','#ffff00','#0066ff']
    w=window; w.project_pins={'P01':[{'name':t,'io_type':t} for t in types]}
    w.plan.projects=[Project('P01')]; w.plan.frames[0].placements=[Placement('P01','A')]; w.refresh()
    block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
    dots=[i for i in block.childItems() if isinstance(i,QGraphicsEllipseItem)]
    assert {d.brush().color().name() for d in dots}=={pin_color(t) for t in types}
    ground=next(d for d in dots if d.toolTip().startswith('ground'))
    label=next(i for i in ground.childItems() if isinstance(i,PinLabel))
    assert label.brush().color()==QColor('white')
    assert label.mapToParent(label.boundingRect().center()).x()==pytest.approx(ground.rect().center().x())
    assert label.mapToParent(label.boundingRect().center()).y()==pytest.approx(ground.rect().center().y())
    assert label.boundingRect().height()*(label.transform().m11()**2+label.transform().m12()**2)**0.5==pytest.approx(ground.rect().height()*0.75)
    transform=label.transform()
    assert abs(transform.m12()/transform.m11())==pytest.approx(1)
    for lod,visible in [(0.15,False),(0.6,True)]:
        image=QImage(300,100,QImage.Format_ARGB32); image.fill(0)
        painter=QPainter(image); painter.scale(lod,lod)
        label.paint(painter,QStyleOptionGraphicsItem()); painter.end()
        assert any(image.pixelColor(x,y).alpha()>0 for x in range(image.width()) for y in range(image.height()))==visible

def test_pin_label_angle_tracks_single_axis_reflection(window):
    from PySide6.QtWidgets import QGraphicsEllipseItem
    from floorplanner.gui.main_window import PinLabel
    w=window; w.project_pins={'P01':[{'name':'VDD','io_type':'power'}]}
    w.plan.projects=[Project('P01')]
    for mx,my in [(False,False),(True,False),(False,True),(True,True)]:
        w.plan.frames[0].placements=[Placement('P01','A',mx,my)]; w.refresh()
        block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
        dot=next(i for i in block.childItems() if isinstance(i,QGraphicsEllipseItem))
        label=next(i for i in dot.childItems() if isinstance(i,PinLabel))
        assert label.background==dot.brush().color()
        # Y inversion for screen readability reverses the transform's slope.
        assert label.transform().m12()/label.transform().m11()==pytest.approx(1 if mx!=my else -1)

def test_json_only_metadata_renders_without_local_sources(window,tmp_path):
    from floorplanner.models import Plan,Frame
    from floorplanner.persistence import save
    from PySide6.QtWidgets import QGraphicsEllipseItem,QGraphicsRectItem
    from PySide6.QtGui import QColor
    metadata={'P01':{'actual_size_um':[603.13,269.59],'export_control':True,'pins':[{'name':'VSS','io_type':'ground'}]}}
    plan=Plan([Project('P01')],[Frame('f',placements=[Placement('P01','A')])],project_metadata=metadata)
    path=tmp_path/'portable.json'; save(path,plan,window.catalog)
    window.load_file(path,record_history=False)
    assert window.plan.project_metadata==metadata and not window.dirty
    block=next(i for i in window.frame_items[0].childItems() if i.data(0)=='P01')
    assert any(isinstance(i,QGraphicsRectItem) and i.rect().width()==pytest.approx(603.13) for i in block.childItems())
    assert any(isinstance(i,QGraphicsEllipseItem) and i.brush().color()==QColor('black') for i in block.childItems())
    assert 'Missing export control' not in window.palette.item(0).toolTip()
    # Local sources refresh saved information when present.
    window.actual_sizes={'P01':(700,300)}; window.project_pins={'P01':[{'name':'VDD','io_type':'power'}]}
    window.export_control_directory=tmp_path/'documents'; window.export_control_directory.mkdir()
    window.refresh()
    assert window.dirty
    assert window.plan.project_metadata['P01']=={'actual_size_um':[700,300],'export_control':False,'pins':[{'name':'VDD','io_type':'power'}]}

@pytest.mark.parametrize('source',['absent','directory','link','broken_link'])
def test_export_control_updates_only_with_available_directory(window,tmp_path,source):
    from floorplanner.persistence import loads
    w=window; w.plan.projects=[Project('P01'),Project('P02')]
    w.plan.project_metadata={'P01':{'export_control':True},'P02':{'export_control':False}}
    target=tmp_path/'documents'
    if source in ('directory','link'):
        target.mkdir(); (target/'P02_Export.pdf').write_text('')
    if source in ('link','broken_link'):
        link=tmp_path/'export_control'; link.symlink_to(target,target_is_directory=True)
        w.export_control_directory=link
    else: w.export_control_directory=target
    w.path=str(tmp_path/'saved.json'); w.refresh(); w.save_plan()
    saved=loads((tmp_path/'saved.json').read_text(),w.catalog)
    expected={'P01':False,'P02':True} if source in ('directory','link') else {'P01':True,'P02':False}
    assert {code:entry['export_control'] for code,entry in saved.project_metadata.items()}==expected

def test_design_type_label_is_inset_bottom_center_and_portable(window):
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    from floorplanner.persistence import loads,dumps
    from floorplanner.transforms import bounds
    w=window; w.plan.projects=[Project('P01')]; w.project_types={'P01':'MIX'}
    for mx,my in [(False,False),(True,False),(False,True),(True,True)]:
        w.plan.frames[0].placements=[Placement('P01','A',mx,my)]; w.refresh()
        block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
        label=next(i for i in block.childItems() if isinstance(i,QGraphicsSimpleTextItem) and i.text()=='MIX')
        center=label.mapToParent(label.boundingRect().center()); rect=bounds(w.catalog['A'],mx,my)
        assert center.x()==pytest.approx(rect.center[0])
        assert center.y()==pytest.approx(rect.y+160)
    w.plan=loads(dumps(w.plan,w.catalog),w.catalog); w.project_types={}; w.refresh()
    assert w.plan.project_metadata['P01']['design_type']=='MIX'


def test_delete_project_menu_and_undo(window):
    w=window
    w.plan.projects=[Project('P01'),Project('P02')]
    w.plan.frames[0].placements=[Placement('P01','A')]
    w.plan.project_metadata={'P01':{'design_type':'DIG'}}
    w.selected='P01'; w.refresh()
    action=next(a for a in w.menuBar().actions()[0].menu().actions() if a.text()=='Delete Project')
    action.trigger()
    assert [p.id for p in w.plan.projects]==['P02']
    assert not w.plan.frames[0].placements
    assert 'P01' not in w.plan.project_metadata
    assert w.selected is None and w.dirty
    w.undo()
    assert [p.id for p in w.plan.projects]==['P01','P02']
    assert w.plan.frames[0].placements==[Placement('P01','A')]
    assert w.plan.project_metadata['P01']=={'design_type':'DIG'}
    w.redo()
    assert [p.id for p in w.plan.projects]==['P02']
    # Unassigned projects can also be deleted; no selection is a no-op.
    w.selected='P02'; action.trigger()
    assert not w.plan.projects
    history=len(w.undo_stack)
    action.trigger()
    assert len(w.undo_stack)==history


def test_pr_boundary_match_highlighting(window):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    from PySide6.QtCore import Qt
    w=window; b=w.catalog['A']
    w.plan.projects=[Project('P01')]
    w.plan.frames[0].placements=[Placement('P01','A')]
    w.pr_boundary_sizes={'P01':(b.width_um,b.height_um)}
    w.selected='P01'; w.refresh()
    assert f'PR boundary size: {b.width_um:g} × {b.height_um:g} µm' in w.inspector.toPlainText()
    assert w.palette.item(0).foreground().color()==QColor('#008000')
    block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
    assert block.pen().color()!=QColor('#008000')
    assert block.brush().style()==Qt.SolidPattern
    label=next(i for i in block.childItems() if isinstance(i,QGraphicsSimpleTextItem) and 'P01' in i.text())
    assert label.brush().color()==QColor('black')
    w.pr_boundary_sizes={'P01':(b.width_um+1,b.height_um)}; w.refresh()
    assert not w.boundary_matches('P01','A')
    block=next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01')
    assert block.brush().style()==Qt.TexturePattern
    texture=block.brush().textureImage()
    assert texture.pixelColor(32,0)==QColor('#cccccc')
    assert texture.pixelColor(32,32)!=QColor('#cccccc')
    assert w.palette.item(0).foreground().color()!=QColor('#008000')
    # Embedded boundary metadata works without the local audit.
    w.pr_boundary_sizes={}; w.plan.project_metadata['P01']['pr_boundary_size_um']=[b.width_um,b.height_um]
    w.refresh()
    assert w.boundary_matches('P01','A')
    assert not w.boundary_matches('P01','?')


def test_layout_colors_follow_position(window):
    from floorplanner.gui.main_window import layout_block_color,POSITION_COLORS
    from PySide6.QtGui import QColor
    catalog=window.catalog
    for mx,my,corner in [(False,False,'NW'),(True,False,'NE'),(True,True,'SE'),(False,True,'SW')]:
        for kind in ('D','A','BH','BV','ACH','ACV','ACE'):
            assert layout_block_color(catalog[kind],mx,my)==QColor(POSITION_COLORS[corner])
    for kind,mx,my,side in [('EH',False,False,'W'),('EH',True,False,'E'),('EV',False,False,'N'),('EV',False,True,'S')]:
        assert layout_block_color(catalog[kind],mx,my)==QColor(POSITION_COLORS[side])
    # ACE2 has cut-outs at NE and SW; its occupied NW corner wins over sides.
    assert layout_block_color(catalog['ACE2'])==QColor(POSITION_COLORS['NW'])
    assert layout_block_color(catalog['ACE2'],True)==QColor(POSITION_COLORS['NE'])
    w=window; w.plan.projects=[Project('P01')]
    w.plan.frames[0].placements=[Placement('P01','A')]; w.refresh()
    def color():
        return next(i for i in w.frame_items[0].childItems() if i.data(0)=='P01').brush().color()
    original=color()
    w.plan.projects.append(Project('P02')); w.plan.frames[0].placements.append(Placement('P02','A',True,True)); w.refresh()
    assert color()==original
