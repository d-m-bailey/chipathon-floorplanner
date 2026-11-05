# Chipathon 2026 Floorplanner

Desktop planning tool for the GF180MCU D chip frames. Requires Python 3.11+.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Open a saved floorplan directly at startup:

```sh
python main.py floorplan-chipathon2026.json
```

The filename is optional; quote paths containing spaces. Invalid or unreadable files show an error and leave the initial empty plan available.

Create a project with **Add Project**, explicitly choose its block type and enter its pin count (shown as `pin_count/max_pins`). Placed blocks display the project name. Manual project entry uses the project ID as its name without a separate display-name prompt. Each project-list row shows the project ID, block type, pin count/max pins, and assigned chip; hover to see its name. Drag a palette entry onto a chip near a candidate center. Green previews can be committed; red previews explain rejected placements in the status bar. Drag assigned blocks between frames. Double-click a placed block or its project-list entry to edit project information. Select a project and press X/Y to reflect, Delete to unassign, F to fit. Drag a chip background to reposition it on a 500 µm grid (the 2935 µm frames use a default 3000 µm pitch), drag empty space to pan, and scroll to zoom. Frame removal returns its projects to the unassigned palette. Editing a project returns it to the palette for revalidation.

Four empty frames are provided at startup. Choose block type `?` for projects whose block size is undefined. They remain searchable and editable in the list, show `pin_count/?`, and cannot be placed until a defined type is selected.

The Floorplan menu contains frame management, project import, pad configuration, validation, SVG/PNG export, and save/open. All model changes support undo/redo. Saved plans include project metadata, individual frame pad catalogs, and a catalog hash; incompatible or invalid files are rejected before changing the current plan. Saves replace files atomically.

## Pads and logical pins

No physical pad numbering is guessed. **Load Pads** accepts either a JSON array or an object containing `pads`, with entries such as `{"id":"W12","x_um":0,"y_um":1500}`. Coordinates must be actual integer micrometers in the chip coordinate system. Reflection uses coordinate lookup. Missing mappings remain explicitly **UNVERIFIED**; geometric placement is still available. Explicit unreflected pad allocations can detect known conflicts without coordinates.

Projects store a pin count rather than individual logical pin names. Capacity validation compares this count with the selected block’s maximum pins. Physical pad allocations still follow the block catalog for conflict detection. Source area and utilization remain separate from calculated geometry; the ACE2 area discrepancy is displayed.

## YAML import

Import recursively finds `info.yaml`. The default adapter reads `id`, `name`, `pin_count` (nonnegative integer), and `shared_nets` (mapping). Missing ID/name falls back to the parent folder and is reported. Unknown fields and invalid files are reported. No ID prefix determines a block type. Choose an explicit default type during import; edit individual projects afterward.

Legacy saved plans and YAML pin lists are converted to counts automatically. New saves store only the count.

The optional adapter file maps these keys to dotted field paths, for example:

```json
{"id":"project.id","name":"project.title","pin_count":"interface.pin_count","shared_nets":"interface.shared_nets"}
```

## Verification

```sh
python -m pytest -q
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_gui.py
```

Core geometry, transforms, snapping, validation, pin mapping and persistence import no Qt. Configuration is in `config/blocks.json` and `config/chip_frames.json`. The current chip size and keepout are intentionally fixed by the v1 specification. KLayout/GDS is not required.

Export-control document status is checked from `data/export_control` beside the application source on startup and whenever the project display refreshes (including project edits). Filenames must start with the project code followed by a separator, for example `A01_Export_Control.docx`. Missing documents produce red project-list text and a red placement outline; assigned-project highlighting remains. The status is never stored in the plan JSON and does not prevent placement.

Block fill colors are automatically distributed across distinct hues within each frame and recalculated when assignments change. Colors are derived for display and are not stored in the plan.

At startup, `gds_project_audit.csv` is read using `Team` as the project code and `computed_width`/`computed_height` as the actual GDS dimensions in µm. Placed blocks show a centered white rectangle at that physical size, without scaling to fit or rotation. The inspector shows the dimensions; SVG/PNG exports include the rectangle. Missing or invalid dimensions omit the rectangle. These display measurements do not alter validation or saved plan data. Restart to reload changes to the CSV.

At startup, ordered pin names are loaded from `data/<project_id>/info.yaml` (`pins` entries with `name`). Dots on allocated block edges show their relative positions: left bottom-to-top, then top left-to-right, following catalog side allocations (up to 22 pads per side). E/S allocations continue clockwise. Dots reflect with the block; hover shows the name. They are visual markers, not authoritative physical pad coordinates. Excess pins beyond capacity are reported in the inspector and omitted from the drawing. This metadata stays out of plan JSON; restart to reload YAML changes.
