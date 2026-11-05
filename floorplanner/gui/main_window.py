import copy
import json
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QMimeData, QTimer, QPointF
from PySide6.QtGui import QAction, QColor, QPen, QBrush, QPainterPath, QTransform, QDrag, QPainter, QImage, QKeySequence
from PySide6.QtWidgets import (QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,QGraphicsView,QGraphicsScene,QGraphicsItem,QGraphicsRectItem,QGraphicsSimpleTextItem,QTextEdit,QSplitter,QInputDialog,QFileDialog,QMessageBox,QCheckBox,QSpinBox,QLabel)
from PySide6.QtSvg import QSvgGenerator
from ..models import Plan, Project, Frame, Placement, load_catalog, CONFIG
from ..transforms import bounds, occupied
from ..snapping import snap, snap_frame_position, FRAME_PITCH_UM
from ..validation import validate, validate_all
from ..pin_mapping import mapped_pins
from ..persistence import save, loads
from ..project_loader import import_projects

class Palette(QListWidget):
    def startDrag(self, actions):
        if not self.currentItem() or not self.currentItem().flags() & Qt.ItemIsDragEnabled: return
        mime=QMimeData(); mime.setText(self.currentItem().data(Qt.UserRole))
        drag=QDrag(self); drag.setMimeData(mime); drag.exec(Qt.MoveAction)

class FrameItem(QGraphicsRectItem):
    def __init__(self, frame, window):
        super().__init__(0,0,2935,2935)
        self.frame=frame; self.window=window
        self.setPos(*frame.canvas_position)
        self.setPen(QPen(QColor('#8cabc1'),12)); self.setBrush(QColor('#172737'))
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(-5)
        inner=QGraphicsRectItem(350,350,2235,2235,self)
        inner.setPen(QPen(QColor('#506578'),6,Qt.DashLine)); inner.setBrush(QColor('#203448'))
        label=QGraphicsSimpleTextItem(frame.name or frame.id,self)
        label.setBrush(QColor('#e1edf7')); label.setScale(10); label.setPos(0,3070); label.setTransform(QTransform.fromScale(1,-1))
        for pad in frame.pads:
            marker=QGraphicsRectItem(pad['x_um']-12,pad['y_um']-12,24,24,self); marker.setBrush(QColor('#f5c56c'))
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange:
            return QPointF(*snap_frame_position(value.x(),value.y()))
        return super().itemChange(change,value)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        pos=[round(self.pos().x()),round(self.pos().y())]
        if pos!=self.frame.canvas_position:
            self.window.checkpoint(); self.frame.canvas_position=pos
            # Rebuild only after Qt finishes dispatching this item's release event.
            QTimer.singleShot(0,self.window.refresh)

class View(QGraphicsView):
    def __init__(self,window):
        super().__init__(); self.window=window; self.setScene(QGraphicsScene(self)); self.scale(1,-1)
        self.setRenderHint(QPainter.Antialiasing); self.setBackgroundBrush(QColor('#101c29'))
        self.setAcceptDrops(True); self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.drag_id=None; self.preview=None; self.candidate=None
    def wheelEvent(self,event):
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        factor=1.15 if event.angleDelta().y()>0 else 1/1.15
        self.scale(factor,factor)
    def fit(self):
        self.fitInView(self.scene().itemsBoundingRect().adjusted(-250,-250,250,250),Qt.KeepAspectRatio)
    def mousePressEvent(self,event):
        item=self.itemAt(event.position().toPoint())
        while item and not item.data(0) and item.parentItem(): item=item.parentItem()
        if event.button()==Qt.LeftButton and item and item.data(0):
            self.drag_id=item.data(0); self.window.selected=self.drag_id; self.window.inspect(); event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.drag_id: self.show_preview(event.position().toPoint(),self.drag_id); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self.drag_id:
            self.commit(); self.drag_id=None; return
        super().mouseReleaseEvent(event)
    def dragEnterEvent(self,event):
        if event.mimeData().hasText(): event.acceptProposedAction()
    def dragMoveEvent(self,event):
        self.show_preview(event.position().toPoint(),event.mimeData().text()); event.acceptProposedAction()
    def dragLeaveEvent(self,event): self.clear_preview()
    def dropEvent(self,event):
        self.show_preview(event.position().toPoint(),event.mimeData().text()); self.commit(); event.acceptProposedAction()
    def clear_preview(self):
        if self.preview: self.scene().removeItem(self.preview)
        self.preview=None; self.candidate=None
    def show_preview(self,point,pid):
        self.clear_preview(); w=self.window
        try: project=w.plan.project(pid)
        except StopIteration: return
        if project.block_type=='?':
            w.statusBar().showMessage('Choose a defined block type before placing this project'); return
        pos=self.mapToScene(point)
        for frame in reversed(w.plan.frames):
            fx,fy=frame.canvas_position
            if not (fx<=pos.x()<=fx+2935 and fy<=pos.y()<=fy+2935): continue
            b=w.catalog[project.block_type]
            c=snap(b,(pos.x()-fx,pos.y()-fy),self.transform().m11(),w.snap_distance.value(),frame.pads)
            if c is None: w.statusBar().showMessage('Move closer to a candidate center'); return
            p=Placement(pid,b.name,*c); errors,warnings=validate(w.plan,frame,p,w.catalog,moving=True)
            pins,verified=mapped_pins(b,*c,frame.pads)
            w.statusBar().showMessage(('; '.join(errors+warnings) or 'Valid placement')+' | Candidate pads: '+(', '.join(pins) or 'unverified'))
            self.candidate=(frame,p,errors)
            if errors and not w.invalid.isChecked(): return
            path=QPainterPath()
            for r in occupied(b,*c): path.addRect(fx+r.x,fy+r.y,r.w,r.h)
            color=QColor('#ef6363' if errors else '#57daa3'); color.setAlpha(125)
            self.preview=self.scene().addPath(path,QPen(color,18),QBrush(color)); self.preview.setZValue(20)
            for pad in frame.pads:
                if pad['id'] in pins:
                    marker=QGraphicsRectItem(fx+pad['x_um']-22,fy+pad['y_um']-22,44,44,self.preview)
                    marker.setBrush(QColor('#ffe28a')); marker.setPen(QPen(QColor('white'),5))
            return
    def commit(self):
        if self.candidate and not self.candidate[2]:
            frame,p,_=self.candidate; self.window.checkpoint(); self.window.plan.unassign(p.project_id); frame.placements.append(p); self.window.selected=p.project_id
        self.clear_preview(); self.window.refresh()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape: self.drag_id=None; self.clear_preview(); return
        super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Chipathon 2026 · Floorplanner'); self.resize(1440,900)
        self.catalog=load_catalog(); self.defaults=json.loads((CONFIG/'chip_frames.json').read_text())
        self.plan=Plan(frames=[Frame(f'chip_{i+1:02}',f'Chip {i+1}',[(i%2)*FRAME_PITCH_UM,(i//2)*FRAME_PITCH_UM],pads=copy.deepcopy(self.defaults['pads'])) for i in range(4)])
        self.selected=None; self.path=None; self.undo_stack=[]; self.redo_stack=[]; self.dirty=False
        splitter=QSplitter(); self.setCentralWidget(splitter)
        left=QWidget(); layout=QVBoxLayout(left); layout.addWidget(QLabel('PROJECTS'))
        self.search=QLineEdit(); self.search.setPlaceholderText('Search projects'); self.search.textChanged.connect(self.refresh_palette); layout.addWidget(self.search)
        self.palette=Palette(); self.palette.setDragEnabled(True); self.palette.currentItemChanged.connect(self.palette_selected); self.palette.itemDoubleClicked.connect(self.edit_project); layout.addWidget(self.palette)
        self.invalid=QCheckBox('Preview invalid candidates'); self.invalid.setChecked(True); layout.addWidget(self.invalid)
        layout.addWidget(QLabel('Maximum snap distance (pixels)')); self.snap_distance=QSpinBox(); self.snap_distance.setRange(10,1000); self.snap_distance.setValue(180); layout.addWidget(self.snap_distance)
        splitter.addWidget(left); self.view=View(self); splitter.addWidget(self.view)
        self.inspector=QTextEdit(); self.inspector.setReadOnly(True); splitter.addWidget(self.inspector); splitter.setSizes([260,900,280])
        actions=[('New',self.new,QKeySequence.New),('Open',self.open,QKeySequence.Open),('Save',self.save_plan,QKeySequence.Save),('Save As',lambda:self.save_plan(True),QKeySequence.SaveAs),('Add Project',self.add_project,None),('Edit Project',self.edit_project,None),('Import Projects',self.import_yaml,None),('Add Frame',self.add_frame,None),('Rename Frame',self.rename_frame,None),('Remove Frame',self.remove_frame,None),('Load Pads',self.load_pads,None),('Mirror X',lambda:self.mirror('x'),'X'),('Mirror Y',lambda:self.mirror('y'),'Y'),('Unassign',self.unassign,'Delete'),('Undo',self.undo,QKeySequence.Undo),('Redo',self.redo,QKeySequence.Redo),('Validate All',self.validate_plan,None),('Export SVG',lambda:self.export('svg'),None),('Export PNG',lambda:self.export('png'),None),('Fit View',self.view.fit,'F')]
        menu=self.menuBar().addMenu('Floorplan'); toolbar=self.addToolBar('Plan')
        for text,fn,key in actions:
            action=QAction(text,self); action.triggered.connect(lambda checked=False,fn=fn: self.guarded(fn))
            if key: action.setShortcut(key)
            menu.addAction(action)
            if text in ('Save','Add Project','Add Frame','Mirror X','Mirror Y','Undo','Redo','Fit View'): toolbar.addAction(action)
        self.refresh(); self.view.fit()
    def guarded(self,fn):
        try: fn()
        except Exception as e: QMessageBox.warning(self,'Unable to complete action',str(e))
    def checkpoint(self):
        self.undo_stack.append(copy.deepcopy(self.plan)); self.redo_stack.clear(); self.dirty=True
    def refresh_palette(self):
        selected=self.selected; self.palette.blockSignals(True); self.palette.clear()
        for p in self.plan.projects:
            if self.search.text().lower() not in (p.id+' '+p.name).lower(): continue
            f,_=self.plan.assignment(p.id)
            capacity=self.catalog[p.block_type].pin_count if p.block_type in self.catalog else '?'
            item=QListWidgetItem(f'{p.id} · {p.block_type} · {p.pin_count}/{capacity} pins · {f.name or f.id if f else "unassigned"}')
            if p.block_type=='?': item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
            item.setToolTip(p.name if p.block_type!='?' else p.name+' — Choose a block type to enable placement')
            if f:
                item.setText('✓ '+item.text())
                item.setBackground(QColor('#d5eee0'))
                item.setForeground(QColor('#174b32'))
                font=item.font(); font.setBold(True); item.setFont(font)
                item.setToolTip(f'{p.name} — Placed on {f.name or f.id}')
            item.setData(Qt.UserRole,p.id); self.palette.addItem(item)
            if p.id==selected: self.palette.setCurrentItem(item)
        self.palette.blockSignals(False)
    def refresh(self):
        self.view.preview=None; self.view.candidate=None; self.view.scene().clear()
        # Keep Python subclasses alive while Qt dispatches mouse events.
        self.frame_items=[]
        for f in self.plan.frames:
            frame_item=FrameItem(f,self); self.frame_items.append(frame_item); self.view.scene().addItem(frame_item)
            for p in f.placements:
                b=self.catalog[p.block_type]; path=QPainterPath()
                for r in occupied(b,p.mirror_x,p.mirror_y): path.addRect(r.x,r.y,r.w,r.h)
                color=QColor.fromHsv(sum(map(ord,p.project_id))*37%360,135,210)
                item=self.view.scene().addPath(path,QPen(QColor('white') if self.selected==p.project_id else color,15),QBrush(color)); item.setParentItem(frame_item); item.setData(0,p.project_id); item.setZValue(1)
                project=self.plan.project(p.project_id)
                r=bounds(b,p.mirror_x,p.mirror_y)
                label=QGraphicsSimpleTextItem(f'{project.name} · {p.block_type}\n{project.pin_count}/{b.pin_count} pins',item)
                label.setBrush(QColor('#101c29'))
                label.setScale(min(7,(r.w-70)/max(1,label.boundingRect().width()),(r.h-80)/max(1,label.boundingRect().height())))
                label.setPos(r.x+35,r.y+r.h-40); label.setTransform(QTransform.fromScale(1,-1))
        self.refresh_palette(); self.inspect(); self.setWindowTitle(('● ' if self.dirty else '')+'Chipathon 2026 · '+(str(self.path) if self.path else 'Untitled'))
    def palette_selected(self,item,previous):
        if item: self.selected=item.data(Qt.UserRole); self.inspect()
    def inspect(self):
        if not self.selected:
            self.inspector.setPlainText('Select a project.\n\nDrag from the palette to a chip. X/Y reflect; Delete unassigns. Drag chip backgrounds to reposition frames. Scroll to zoom; drag empty canvas to pan.\n\nPhysical pad mapping is UNVERIFIED until coordinates are loaded.'); return
        try: p=self.plan.project(self.selected)
        except StopIteration: self.selected=None; self.inspect(); return
        if p.block_type=='?':
            self.inspector.setPlainText(f'{p.id}\n\n{p.name}\n\nType: ?\n\nPins: {p.pin_count}/?\n\nUnassigned: choose a defined block type before placing this project.'); return
        b=self.catalog[p.block_type]; f,pl=self.plan.assignment(p.id)
        lines=[p.id,p.name,f'Type: {b.name}',f'Pins: {p.pin_count}/{b.pin_count}',f'Dimensions: {b.width_um} × {b.height_um} µm',f'Source area: {b.source_area_um2:,} µm²',f'Calculated area: {b.area:,} µm²',f'Source utilization: {b.source_utilization:.2%}',f'Base lower-left: {b.base_lower_left_um}',f'Frame: {f.name or f.id if f else "Unassigned"}']
        if pl:
            r=bounds(b,pl.mirror_x,pl.mirror_y); pins,verified=mapped_pins(b,pl.mirror_x,pl.mirror_y,f.pads); es,ws=validate(self.plan,f,pl,self.catalog)
            lines += [f'Current lower-left: ({r.x}, {r.y})',f'Mirror X: {pl.mirror_x}; Y: {pl.mirror_y}',f'Pads ({"verified" if verified else "UNVERIFIED"}): '+', '.join(pins),'Validation: '+('; '.join(es+ws) or 'Valid')]
        if b.area!=b.source_area_um2: lines+=['WARNING: source and calculated areas differ.']
        self.inspector.setPlainText('\n\n'.join(lines))
    def project_values(self,existing=None):
        pid,ok=QInputDialog.getText(self,'Project','Project ID:',text=existing.id if existing else '')
        if not ok or not pid.strip(): return
        pid=pid.strip()
        if any(p.id==pid and p is not existing for p in self.plan.projects): raise ValueError('Project ID already exists')
        types=list(self.catalog)+['?']; bt,ok=QInputDialog.getItem(self,'Block type','Choose block type:',types,types.index(existing.block_type) if existing else types.index('A'),False)
        if not ok:return
        pin_count,ok=QInputDialog.getInt(self,'Pin count',f'Pin count (max_pins: {self.catalog[bt].pin_count if bt in self.catalog else '?'}):',existing.pin_count if existing else 0,0,2147483647)
        if not ok:return
        return Project(pid,pid,bt,pin_count,copy.deepcopy(existing.shared_nets) if existing else {})
    def add_project(self):
        p=self.project_values()
        if p: self.checkpoint(); self.plan.projects.append(p); self.selected=p.id; self.refresh()
    def edit_project(self,*args):
        if not self.selected:return
        old=self.plan.project(self.selected); p=self.project_values(old)
        if p:
            self.checkpoint(); self.plan.unassign(old.id); self.plan.projects[self.plan.projects.index(old)]=p; self.selected=p.id; self.refresh()
    def unassign(self):
        if self.selected: self.checkpoint(); self.plan.unassign(self.selected); self.refresh()
    def mirror(self,axis):
        f,p=self.plan.assignment(self.selected)
        if not p:return
        candidate=copy.copy(p); setattr(candidate,'mirror_'+axis,not getattr(p,'mirror_'+axis)); es,ws=validate(self.plan,f,candidate,self.catalog,moving=True)
        if es: raise ValueError('\n'.join(es))
        self.checkpoint(); f.placements[f.placements.index(p)]=candidate; self.refresh()
    def choose_frame(self):
        if not self.plan.frames:return
        ids=[f.id for f in self.plan.frames]; id,ok=QInputDialog.getItem(self,'Frame','Frame:',ids,0,False)
        return next(f for f in self.plan.frames if f.id==id) if ok else None
    def add_frame(self):
        i=1
        while any(f.id==f'chip_{i:02}' for f in self.plan.frames): i+=1
        self.checkpoint(); self.plan.frames.append(Frame(f'chip_{i:02}',f'Chip {i}',[len(self.plan.frames)*FRAME_PITCH_UM,0],pads=copy.deepcopy(self.defaults['pads']))); self.refresh(); self.view.fit()
    def rename_frame(self):
        f=self.choose_frame()
        if not f:return
        name,ok=QInputDialog.getText(self,'Frame','Name:',text=f.name)
        if ok: self.checkpoint(); f.name=name; self.refresh()
    def remove_frame(self):
        f=self.choose_frame()
        if f: self.checkpoint(); self.plan.frames.remove(f); self.refresh()
    def load_pads(self):
        f=self.choose_frame()
        if not f:return
        path,_=QFileDialog.getOpenFileName(self,'Load physical pad catalog','','JSON (*.json)')
        if not path:return
        data=json.loads(Path(path).read_text()); pads=data['pads'] if isinstance(data,dict) else data
        candidate=copy.deepcopy(self.plan); next(c for c in candidate.frames if c.id==f.id).pads=pads
        # Round trip validates pad schema and every existing assignment before mutation.
        from ..persistence import dumps
        loads(dumps(candidate,self.catalog),self.catalog)
        self.checkpoint(); self.plan=candidate; self.refresh()
    def import_yaml(self):
        root=QFileDialog.getExistingDirectory(self,'Select project root')
        if not root:return
        bt,ok=QInputDialog.getItem(self,'Import','Default block type (explicit selection):',list(self.catalog)+['?'],0,False)
        if not ok:return
        adapter=None
        adapter_path,_=QFileDialog.getOpenFileName(self,'Optional field adapter JSON (Cancel uses id/name/pin_count/shared_nets)','','JSON (*.json)')
        if adapter_path: adapter=json.loads(Path(adapter_path).read_text())
        projects,reports=import_projects(root,bt,adapter); self.checkpoint()
        for p in projects:
            if any(q.id==p.id for q in self.plan.projects): reports.append(f'Skipped duplicate ID: {p.id}')
            else:self.plan.projects.append(p)
        self.refresh(); QMessageBox.information(self,'Import report','\n'.join(reports) or f'Imported {len(projects)} projects')
    def undo(self):
        if self.undo_stack: self.redo_stack.append(copy.deepcopy(self.plan)); self.plan=self.undo_stack.pop(); self.dirty=True; self.refresh()
    def redo(self):
        if self.redo_stack: self.undo_stack.append(copy.deepcopy(self.plan)); self.plan=self.redo_stack.pop(); self.dirty=True; self.refresh()
    def validate_plan(self):
        lines=[f'{f.id}/{p.project_id}: '+('; '.join(es+ws) or 'Valid') for f,p,es,ws in validate_all(self.plan,self.catalog)]
        QMessageBox.information(self,'Validation','\n'.join(lines) or 'No assigned projects')
    def discard_ok(self):
        if not self.dirty:return True
        result=QMessageBox.question(self,'Unsaved changes','Save changes before continuing?',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        if result==QMessageBox.Cancel:return False
        if result==QMessageBox.Save:return self.save_plan()
        return True
    def new(self):
        if self.discard_ok(): self.checkpoint(); self.plan=Plan(); self.path=None; self.selected=None; self.refresh()
    def open(self):
        if not self.discard_ok():return
        path,_=QFileDialog.getOpenFileName(self,'Open floorplan','','JSON (*.json)')
        if path: self.load_file(path)
    def load_file(self,path,record_history=True):
        path=str(Path(path).expanduser().resolve())
        plan=loads(Path(path).read_text(),self.catalog)
        if record_history: self.checkpoint()
        else: self.undo_stack.clear(); self.redo_stack.clear()
        self.plan=plan; self.path=path; self.selected=None; self.dirty=False
        self.refresh(); self.view.fit()
    def save_plan(self,save_as=False):
        path=self.path
        if not path or save_as:path,_=QFileDialog.getSaveFileName(self,'Save floorplan',path or 'floorplan.json','JSON (*.json)')
        if not path:return False
        save(path,self.plan,self.catalog); self.path=path; self.dirty=False; self.refresh(); return True
    def export(self,kind):
        path,_=QFileDialog.getSaveFileName(self,'Export canvas',f'floorplan.{kind}',f'{kind.upper()} (*.{kind})')
        if not path:return
        self.view.clear_preview(); scene=self.view.scene(); source=scene.itemsBoundingRect().adjusted(-100,-100,100,100)
        width=2400; height=max(1,round(width*source.height()/source.width()))
        if kind=='svg':
            target=QSvgGenerator(); target.setFileName(path)
            from PySide6.QtCore import QSize
            target.setSize(QSize(width,height)); target.setViewBox(QRectF(0,0,width,height)); target.setTitle('Chipathon 2026 floorplan')
        else:
            target=QImage(width,height,QImage.Format_ARGB32); target.fill(QColor('#101c29'))
        painter=QPainter(target); painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(0,height); painter.scale(1,-1)
        scene.render(painter,QRectF(0,0,width,height),source,Qt.KeepAspectRatio); painter.end()
        if kind=='png' and not target.save(path):raise ValueError('Unable to write PNG')
    def closeEvent(self,event):
        try: event.accept() if self.discard_ok() else event.ignore()
        except Exception as e: QMessageBox.warning(self,'Save failed',str(e)); event.ignore()
