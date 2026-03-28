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

"""WordPress REST API v2 client modules."""

from .blocks import BlocksAPI
from .categories import CategoriesAPI, TagsAPI, TaxonomiesAPI
from .client import WPAPIClient, WPAPIError, WPBaseEndpoint
from .comments import CommentsAPI
from .custom_post_types import CustomPostTypesAPI
from .media import MediaAPI
from .menus import MenusAPI
from .pages import PagesAPI
from .plugins import PluginsAPI
from .posts import PostsAPI
from .search import SearchAPI
from .settings import SettingsAPI
from .themes import ThemesAPI
from .users import UsersAPI

__all__ = [
    "WPAPIClient",
    "WPAPIError",
    "WPBaseEndpoint",
    "PostsAPI",
    "PagesAPI",
    "MediaAPI",
    "UsersAPI",
    "CommentsAPI",
    "CategoriesAPI",
    "TagsAPI",
    "TaxonomiesAPI",
    "BlocksAPI",
    "MenusAPI",
    "SettingsAPI",
    "ThemesAPI",
    "PluginsAPI",
    "SearchAPI",
    "CustomPostTypesAPI",
]
