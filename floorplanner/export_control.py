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

"""Read local export-control document presence for portable plan snapshots."""
from pathlib import Path
import re

EXPORT_CONTROL_DIRECTORY = Path(__file__).resolve().parent.parent / 'data' / 'export_control'


def documented_projects(directory=EXPORT_CONTROL_DIRECTORY):
    """Return project-code prefixes of documents directly inside directory."""
    directory=Path(directory)
    if not directory.is_dir(): return set()
    codes=set()
    for path in directory.iterdir():
        if not path.is_file() or path.name.startswith(('.', '~$')): continue
        match=re.match(r'^([A-Za-z]+\d+)(?=[^A-Za-z0-9]|$)',path.name)
        if match: codes.add(match[1].upper())
    return codes
