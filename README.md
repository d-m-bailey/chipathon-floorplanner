<!--
Copyright 2026 D. Mitch Bailey

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
-->

# Chipathon 2026 Floorplanner

Desktop planning tool for the GF180MCU D chip frames.

## Installation

Install Python 3.11 or newer, including pip and virtual-environment support. Download or clone this repository, then open a terminal in its root directory. A desktop graphical session is needed to run the application. KLayout and GDS files are not required.

On macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py <json_floorplan>
```

On Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Dependencies include PySide6 for the desktop interface, PyYAML for project metadata, and pytest for verification. Keep the `config` and `floorplanner` directories alongside `main.py`. On later launches, activate the environment again or invoke its Python executable directly. If PySide6 has no compatible wheel, use a Python version and operating system supported by the selected PySide6 release.

Local `data/` and `gds_project_audit.csv` files are optional. To use a portable plan, install the application and open its JSON file; saved metadata supplies the size, pin, and export-control information.

## Running

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

Export-control document status is checked from `data/export_control` beside the application source on startup and whenever the project display refreshes (including project edits). Filenames must start with the project code followed by a separator, for example `A01_Export_Control.docx`. Missing documents produce red project-list text and a red placement outline; assigned-project highlighting remains. The status is saved in the plan JSON and does not prevent placement.

Block fill colors are automatically distributed across distinct hues within each frame and recalculated when assignments change. Colors are derived for display and are not stored in the plan.

At startup, `gds_project_audit.csv` is read using `Team` as the project code and `computed_width`/`computed_height` as the actual GDS dimensions in µm. Placed blocks show a centered white rectangle at that physical size, without scaling to fit or rotation. The inspector shows the dimensions; SVG/PNG exports include the rectangle. Missing or invalid dimensions omit the rectangle. These display measurements do not alter placement validation. Restart to reload changes to the CSV.

At startup, ordered pin names are loaded from `data/<project_id>/info.yaml` (`pins` entries with `name`). Dots on allocated block edges show their relative positions: left bottom-to-top, then top left-to-right, following catalog side allocations (up to 22 pads per side). E/S allocations continue clockwise. Dots reflect with the block; hover shows the name. They are visual markers, not authoritative physical pad coordinates. Excess pins beyond capacity are reported in the inspector and omitted from the drawing. Pin names and types are saved in plan JSON; restart to reload YAML changes.

Pin names appear automatically when zoomed in far enough to read them. Circles use YAML `io_type`: ground black with white text, power red, `input_cmos` green, `input_schmitt` (or Schottky spelling) yellow, and bidirectional blue. Analog/unknown types are gray. Pin text is centered on the circle, rotated 45°, and sized to 75% of the circle diameter. Label backgrounds match the pin color. Text rotates −45° for blocks reflected on exactly one axis; normal and doubly reflected blocks use +45°.


## Portable plans

Saved JSON includes a `project_metadata` section keyed by project code, containing `actual_size_um`, `export_control` (document present/absent), and `pins` (name and io_type). People with the application and just this JSON can see actual-size outlines, document-status highlighting, and typed pin markers without the local audit or data directory. The documents and GDS themselves are not embedded.

On startup, available CSV and YAML records override their saved metadata. Missing records retain the saved values. If `data/export_control` exists, its document listing overrides saved status (including marking missing documents); if that directory is absent, saved status is retained. A symlink to an existing directory is supported; a broken symlink also leaves saved status unchanged. Changed metadata marks the plan unsaved; save to distribute the refreshed snapshot. Older plans without metadata still open normally. Local project metadata is also attached when projects are added or edited.


## License

Copyright 2026 D. Mitch Bailey. Licensed under the [Apache License, Version 2.0](LICENSE).

Source and documentation carry license headers. JSON files use adjacent `.license` notices to preserve valid JSON. External data and audit symlinks retain their original ownership and licensing.
