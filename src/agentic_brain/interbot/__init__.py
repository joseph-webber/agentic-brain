# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Inter-Bot Communication - LLMs talking to each other."""

from .coordinator import BotCoordinator
from .protocol import (
    CHANNELS,
    FINAL_PROTOCOL,
    PROTOCOL,
    BotMessage,
    InterBotProtocol,
    MessageType,
    Priority,
)

__all__ = [
    "BotMessage",
    "MessageType",
    "Priority",
    "CHANNELS",
    "PROTOCOL",
    "FINAL_PROTOCOL",
    "InterBotProtocol",
    "BotCoordinator",
]
