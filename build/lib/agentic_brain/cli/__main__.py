# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Agentic Brain CLI — The Universal AI Platform
==============================================

Enables running: python -m agentic_brain.cli

Install. Run. Create. Zero to AI in 60 seconds.

Copyright (C) 2024-2026 Joseph Webber
License: Apache-2.0
"""

import sys

from agentic_brain.cli import main

if __name__ == "__main__":
    sys.exit(main())
