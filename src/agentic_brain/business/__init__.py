# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Business models for agentic-brain framework."""

from .base import BusinessEntity, Repository
from .retail import (
    Category,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductCategory,
)

__all__ = [
    # Base classes
    "BusinessEntity",
    "Repository",
    # Retail models
    "Product",
    "Order",
    "OrderItem",
    "Customer",
    "Category",
    # Enums
    "OrderStatus",
    "ProductCategory",
]

__version__ = "2.5.0"
