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
def window(app):
    w=MainWindow(); w.show(); app.processEvents(); yield w
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
    assert calls[1]==('Display name:','ProjectName')
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
    end=start+QPoint(30,-20)
    QTest.mousePress(w.view.viewport(),Qt.LeftButton,pos=start)
    QTest.mouseMove(w.view.viewport(),end,delay=20)
    # Projects follow the frame during the drag, before the scene is rebuilt.
    assert item.pos()!=before
    assert block.scenePos()==item.pos()
    QTest.mouseRelease(w.view.viewport(),Qt.LeftButton,pos=end)
    app.processEvents()
    assert frame.canvas_position!=[0,0]
    assert len(w.plan.frames)==4 and len(frame.placements)==1
    assert len([i for i in w.view.scene().items() if isinstance(i,FrameItem)])==4
    w.undo(); assert w.plan.frames[0].canvas_position==[0,0]
    w.redo(); assert w.plan.frames[0].canvas_position!=[0,0]
