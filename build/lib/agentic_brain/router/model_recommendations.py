# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Model recommendations based on task type.
"""

TASK_RECOMMENDATIONS = {
    "code_review": ["CL2", "OP2", "GR2"],  # Claude, GPT-4o, Groq 70b
    "chat": ["GR", "GO", "CL"],  # Fast models
    "research": ["CL2", "GO2", "OP2"],  # Quality models
    "creative": ["OP2", "CL2", "XA"],  # Creative models
    "private": ["L2", "L3", "L4"],  # Local only
    "budget": ["GR", "L1", "CL"],  # Free/cheap
}


def get_recommended_models(task: str) -> list[str]:
    """Get recommended model codes for a task."""
    return TASK_RECOMMENDATIONS.get(task, ["GR2", "CL2", "OP2"])
