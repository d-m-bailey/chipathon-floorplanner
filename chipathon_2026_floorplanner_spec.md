# Chipathon 2026 Interactive Floorplanner — Implementation Specification

**Version:** 1.2  
**Target:** Desktop application developed in VS Code  
**Technology:** GF180MCU D  
**Status:** Implementation specification; unresolved items explicitly identified

## 1. Purpose and scope

Build a graphical desktop tool to allocate independent Chipathon projects among multiple chip frames. Each project is assigned a block type from the fixed catalog below. The user can drag a project onto a chip; the block **snaps only to one of four predefined positions** obtained by reflecting its base placement across the chip's horizontal and/or vertical centerlines. No arbitrary translation or 90-degree rotation is allowed in v1.

The tool must display chip frames and project IDs, check physical overlap and pin conflicts, allow reassignment between chips, and save/reopen plans. It is a planning tool, not a placement-and-route engine.

### Functional requirements

- Show several chip frames simultaneously; add, rename, remove, and reposition frames on the canvas.
- Maintain a palette of unassigned projects, each with a selected block type.
- Drag projects to frames; snap to valid base/reflected placements.
- Allow horizontal, vertical, and combined reflections; preserve dimensions (no 90° rotation).
- Display previews of occupied area and candidate pins; indicate invalid placements and reasons.
- Detect occupied-area overlap, physical pin reuse, out-of-bounds geometry, and duplicate project assignments.
- Support undo/redo, JSON save/load, and SVG/PNG export.
- Import project identifiers and available pin information from `info.yaml` where possible; permit manual entry.
- Keep all geometric calculations independent of the GUI.

## 2. Recommended stack

| Area | Implementation |
|---|---|
| Runtime | Python 3.11+ |
| GUI | PySide6 (`QGraphicsScene`, `QGraphicsView`) |
| Geometry | Integer micrometers; axis-aligned rectangles and rectangular unions |
| Configuration | JSON |
| Project metadata | PyYAML for `info.yaml` |
| Persistence | Versioned JSON |
| Export | Qt SVG generator / PNG; optional future GDS using KLayout `pya` |
| Testing | pytest; geometry tests without Qt |

Do not require KLayout or the GDS files for the initial interactive floorplanner.

## 3. Chip coordinate system

- Full chip boundary: **2935 × 2935 µm**.
- Origin `(0, 0)` at bottom left; X increases right and Y increases up.
- Reserved margin: 350 µm on each side (assumed padframe/keepout region).
- Interior planning region: `[350,2585] × [350,2585]`, **2235 × 2235 µm**.
- Reflection axes: `x = 1467.5 µm` and `y = 1467.5 µm`.
- All stored dimensions and positions are integer µm. Half-integer axis locations do not require fractional rectangle coordinates.
- Qt screen Y increases downward: use a view transform, not a change to stored model coordinates.
- The placement column in the block catalog is the **lower-left corner of the unreflected block bounding box**, consistent with the 2935 µm full chip.

## 4. Authoritative block catalog

Use these values as provided. Pin order is a sequence, not merely a set. Areas and utilization are source-table values; calculated geometry may differ and must be separately reported.

| Type | Pin order | Base lower-left (µm) | Pins | Width (µm) | Height (µm) | Source area (µm²) | Source utilization |
|---|---|---|---:|---:|---:|---:|---:|
| EH | W12-W16 | (350,1475) | 5 | 605 | 495 | 299475 | 6.25% |
| EV | N07-N11 | (965,1980) | 5 | 495 | 605 | 299475 | 6.25% |
| EH2 | W07-W16 | (350,965) | 10 | 605 | 1005 | 608025 | 12.50% |
| EV2 | N07-N16 | (965,1980) | 10 | 1005 | 605 | 608025 | 12.50% |
| D | W17-W22,N01-N06 | (350,1980) | 12 | 605 | 605 | 366025 | 6.25% |
| CH | W12-W16 | (350,1475) | 5 | 1110 | 495 | 549450 | 12.50% |
| CH2 | W07-W16 | (350,965) | 10 | 1110 | 1005 | 1115550 | 25.00% |
| CV | N07-N11 | (965,1475) | 5 | 495 | 1110 | 549450 | 12.50% |
| CV2 | N07-N16 | (965,1475) | 10 | 1005 | 1110 | 1115550 | 25.00% |
| BV | W12-W22,N01-N06 | (350,1475) | 17 | 605 | 1110 | 671550 | 12.50% |
| BVE | W07-W22,N01-N06 | (350,965) | 22 | 605 | 1620 | 980100 | 18.75% |
| BH | W17-W22,N01-N11 | (350,1980) | 17 | 1110 | 605 | 671550 | 12.50% |
| BHE | W17-W22,N01-N16 | (350,1980) | 22 | 1620 | 605 | 980100 | 18.75% |
| A | W12-W22,N01-N11 | (350,1475) | 22 | 1110 | 1110 | 1232100 | 25.00% |
| ACV | W12-W22,N01-N16 | (350,1475) | 27 | 1620 | 1110 | 1798200 | 37.50% |
| ACH | W07-W22,N01-N11 | (350,965) | 27 | 1110 | 1620 | 1798200 | 37.50% |
| ACE | W07-W22,N01-N16 | (350,965) | 32 | 1620 | 1620 | 2624400 | 56.25% |
| ACE2 | W07-W22,N01-N16,E16-E01,S22-S07 | (350,350) | 64 | 2235 | 2235 | 4949325 | 87.50% |

### ACE2 special geometry

ACE2 occupies its 2235 × 2235 µm bounding box **except** two excluded 615 × 615 µm squares. The source table expresses these in **block-local coordinates**:

- `(0,0)` to `(615,615)`
- `(1620,1620)` to `(2235,2235)`

Transform the exclusions together with the occupied geometry for every reflection. The computed occupied area is `2235² − 2 × 615² = 4,238,775 µm²`, whereas the source table reports `4,949,325 µm²`. Preserve both values and flag the difference. The source utilization percentage also must not be silently reinterpreted as physical occupied-area fraction.

## 5. Reflections and candidate positions

For a block with lower-left `(x,y)`, width `w`, height `h`, and chip size `W=H=2935`:

```python
new_x = W - x - w if mirror_x else x
new_y = H - y - h if mirror_y else y
```

`mirror_x` means left/right reflection (about the vertical centerline); `mirror_y` means top/bottom reflection (about the horizontal centerline). A reflected local point `(u,v)` becomes `(w-u,v)` for X, `(u,h-v)` for Y, or `(w-u,h-v)` for both, before translation to the reflected block's new lower-left.

Each block has up to four candidate placements: `normal`, `mirror_x`, `mirror_y`, `mirror_xy`. Deduplicate candidates if two transformations yield identical geometry and pin assignments.

Example for type A (1110 × 1110 at 350,1475):

| Orientation | Lower-left |
|---|---|
| Normal | (350,1475) |
| Mirror X | (1475,1475) |
| Mirror Y | (350,350) |
| Mirror XY | (1475,350) |

Do not rotate dimensions or exchange width and height. Reflect project shape, excluded regions, and pad mapping as one operation.

## 6. Pad and pin model

Pin identifiers follow the supplied W/N/E/S conventions (e.g., `W12`, `N01`). Expand a range inclusively, preserving direction: `W12-W16` means W12, W13, W14, W15, W16; `E16-E01` is descending.

Store a pad catalog for each chip frame with `{id, x_um, y_um}` for every physical pad. **Do not infer the numbering direction from the identifiers.** Reflect each pad's physical coordinate across the chip axes, then look up the matching physical pad ID. This makes the mapping independent of clockwise/counterclockwise numbering conventions.

Pad coordinate data and the exact reflection mapping are required configuration inputs before pin-conflict validation can be considered authoritative. Until available, the GUI may show transformed geometric placements but must label reflected pin assignments **unverified** rather than guessing.

A project has a logical pin list (from `info.yaml` or manual entry), which is distinct from the physical pad IDs allocated by its block type. Define the ordering/mapping between logical and physical pins explicitly; warn if logical pin count exceeds block capacity. Keep each project's power and ground distinct unless the project metadata explicitly defines a shared net.

## 7. Snapping and interaction

1. Drag a project from the unassigned palette or from an existing frame.
2. Identify the frame under the cursor.
3. Generate all base/reflected candidate positions for that project's block type.
4. Choose the candidate whose **bounding-box center** is nearest the cursor in scene coordinates, subject to a configurable maximum snap distance in screen pixels.
5. Preview the candidate in green if valid, red if invalid, and show the reason(s).
6. On release, commit only if valid. Otherwise restore the original placement or return the project to the unassigned palette.
7. A selected project's X and Y commands toggle reflections and update its snapped candidate; the same validation applies.

Provide a setting to preview invalid candidates without committing them. Zooming must not change the physical snapping positions or the apparent pixel snap threshold.

## 8. Validation rules

| Rule | Behavior |
|---|---|
| Chip interior | Reject occupied geometry outside `[350,2585]²` unless a future configuration explicitly permits it |
| Geometry overlap | Reject any positive-area intersection; shared edges are allowed |
| ACE2 | Test occupied geometry, not its full bounding box; excluded corners do not cause false overlap |
| Pad conflict | Reject reuse of a physical pad by two projects on the same chip |
| Pin capacity | Reject projects whose required pin count exceeds the chosen block capacity |
| Duplicate project | Reject placing one project more than once across all frames by default |
| Block type | Reject unknown block types or dimensions inconsistent with catalog |
| Reflection | Only normal/X/Y/XY are valid |
| Unverified pad mapping | Report clearly; do not silently mark as electrically valid |

Geometry validation should operate on integer µm coordinates, not rendered pixels. Use rectangle intersection and subtraction/union for ACE2; a full polygon library is optional.

## 9. User interface

### Main window

- **Left: project palette** — searchable project IDs, name, block type, required/available pins, assigned/unassigned status; option to edit a project's block type.
- **Center: canvas** — several labeled 2935 × 2935 chip frames, 350 µm margins, optional pad markers, draggable project blocks, labels, selection outlines, previews, zoom/pan, and fit-to-view.
- **Right: inspector** — project ID, block type, dimensions, source area, calculated area, frame, base and current lower-left, reflection state, assigned pads, logical pins, validation results.
- **Toolbar/menu** — New/Open/Save, Add/Remove Frame, Mirror X, Mirror Y, Undo/Redo, Validate All, Export SVG/PNG, Fit View.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| X | Toggle left/right reflection |
| Y | Toggle top/bottom reflection |
| Delete | Unassign selected project |
| Cmd/Ctrl+Z | Undo |
| Cmd/Ctrl+Shift+Z | Redo |
| Cmd/Ctrl+S | Save |
| F | Fit all frames |
| Escape | Cancel drag |

Use distinguishable project colors and visible text labels; color alone must not be the sole validation signal.

## 10. Configuration and saved data

Suggested `blocks.json` entry:

```json
{
  "name": "A",
  "width_um": 1110,
  "height_um": 1110,
  "base_lower_left_um": [350, 1475],
  "pin_ranges": ["W12-W22", "N01-N11"],
  "pin_count": 22,
  "source_area_um2": 1232100,
  "source_utilization": 0.25,
  "excluded_rectangles_local_um": []
}
```

Suggested `chip_frames.json`:

```json
{
  "chip_type": "gf180mcuD",
  "width_um": 2935,
  "height_um": 2935,
  "margin_um": 350,
  "pads": []
}
```

`pads` must be populated with actual IDs and coordinates before physical pin mapping can be validated.

Suggested saved floorplan:

```json
{
  "schema_version": 1,
  "chip_type": "gf180mcuD",
  "frames": [
    {
      "id": "chip_01",
      "canvas_position": [0, 0],
      "placements": [
        {
          "project_id": "A01",
          "block_type": "A",
          "mirror_x": false,
          "mirror_y": true
        }
      ]
    }
  ]
}
```

Derive placement coordinates and pad IDs from the catalog and reflection state; do not store redundant authoritative geometry. Include a configuration version or hash in production saved files to detect incompatible catalog changes. Save atomically to avoid truncating existing plans.

## 11. Project import

Search recursively for `info.yaml` files in a selected project root. The parent folder is the project directory. Import project ID, display name, and logical pins from documented fields where present. Since the exact YAML schema is not supplied here, isolate field extraction in a configurable adapter and report missing/unknown fields. Do not require GDS rendering for this tool.

Allow manual project creation and block type assignment. Project block type is not necessarily identical to the first character of its project ID; do not infer it without an explicit rule or user confirmation.

## 12. Suggested source tree

```text
chipathon-floorplanner/
├── main.py
├── requirements.txt
├── config/
│   ├── blocks.json
│   └── chip_frames.json
├── floorplanner/
│   ├── models.py
│   ├── geometry.py
│   ├── transforms.py
│   ├── snapping.py
│   ├── validation.py
│   ├── pin_mapping.py
│   ├── persistence.py
│   ├── project_loader.py
│   └── gui/
│       ├── main_window.py
│       ├── floorplan_view.py
│       ├── chip_frame_item.py
│       ├── project_item.py
│       └── property_panel.py
└── tests/
    ├── test_geometry.py
    ├── test_reflection.py
    ├── test_snapping.py
    ├── test_overlap.py
    ├── test_pin_mapping.py
    └── test_persistence.py
```

## 13. Implementation phases

1. **Data and geometry:** Load all 18 block types; implement bounding boxes, ACE2 exclusions, area calculations, and reflections with tests.
2. **GUI:** Display multiple chip frames and project palette; drag, snap, reflect, zoom, pan, and select.
3. **Validation:** Implement overlap, bounds, duplicate assignment, and pin capacity. Add pad conflicts once pad coordinates are configured.
4. **Import:** Read project metadata from `info.yaml` and allow manual edits.
5. **Persistence/export:** Versioned JSON, undo/redo, SVG/PNG export, and robust error reporting.
6. **Optional later work:** GDS export, real project GDS thumbnails, automatic floorplan optimization, alternative die dimensions.

## 14. Acceptance tests

- All 18 catalog entries load with exactly the supplied dimensions, anchors, pin sequences, and source metadata.
- Four reflections of A produce `(350,1475)`, `(1475,1475)`, `(350,350)`, `(1475,350)`.
- Reflection twice about the same axis restores the original geometry and pin mapping.
- ACE2 excluded squares reflect correctly; area computed as 4,238,775 µm², and the source area discrepancy is shown.
- Shared boundaries between blocks are allowed; positive-area overlap is rejected.
- An invalid drag does not alter the last valid saved position.
- A project can move between frames but cannot exist in two frames simultaneously.
- At least four chip frames remain independently editable.
- Pin conflict is detected for two projects assigned the same pad once pad mapping is configured.
- Saving and reopening reproduces project/frame assignments and orientations.
- SVG/PNG output preserves chip proportions, block shapes, and labels.
- Geometry tests pass headlessly without Qt.

## 15. Open questions / assumptions

1. **Pad numbering and coordinates:** Supply the complete physical W/N/E/S pad catalog so reflections map pad IDs reliably. The source table alone does not define numbering directions.
2. **Project-to-pad ordering:** Confirm how logical pins in `info.yaml` map to the ordered physical pin list.
3. **Source utilization:** Percentages in the supplied table are preserved as metadata; they appear to describe allocations rather than simple occupied-area / full-chip-area ratios.
4. **ACE2 source area:** Listed 4,949,325 µm² versus 4,238,775 µm² computed from the two excluded corners. Show both until clarified.
5. **350 µm margins:** Treated as placement keepout/padframe; confirm whether any project shapes may enter these margins.
6. **Project block type:** User-selected by default; no assumption that project ID prefix determines geometry.

**Recommended MVP boundary:** Build geometric drag/snap/reflection and multi-frame management first. Do not present reflected pin allocations as verified until the pad-coordinate catalog has been supplied.
