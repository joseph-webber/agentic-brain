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

"""Document loaders for RAG pipelines.

This package provides modular document loaders for various sources:

Local Files:
    - TextLoader, MarkdownLoader: Text and Markdown files
    - JSONLoader, JSONLLoader: JSON and JSON Lines
    - PDFLoader: PDF documents
    - DocxLoader, WordLoader: Word documents
    - HTMLLoader, WebLoader: HTML files and web pages
    - CSVLoader, ExcelLoader: Spreadsheets

Cloud Storage:
    - S3Loader: Amazon S3 and S3-compatible (MinIO)
    - GCSLoader: Google Cloud Storage
    - AzureBlobLoader: Azure Blob Storage
    - MinIOLoader: Self-hosted S3-compatible

Databases (SQL Injection Protected):
    - PostgreSQLLoader: PostgreSQL
    - MySQLLoader: MySQL
    - OracleLoader: Oracle Database

NoSQL:
    - MongoDBLoader: MongoDB
    - RedisLoader: Redis
    - ElasticsearchLoader: Elasticsearch
    - FirestoreLoader: Firebase Firestore

Email:
    - GmailLoader: Google Gmail
    - Microsoft365Loader: Microsoft 365 (includes Outlook)

Social/Collaboration:
    - SlackLoader: Slack messages
    - NotionLoader: Notion pages and databases
    - GitHubLoader: GitHub repositories, issues, PRs

Enterprise:
    - SAPLoader: SAP ERP/S4HANA
    - WorkdayLoader: Workday HCM
    - ServiceNowLoader: ServiceNow ITSM
    - Dynamics365Loader: Microsoft Dynamics 365

CRM (SQL Injection Protected):
    - SalesforceLoader: Salesforce CRM

Australian Business:
    - MYOBLoader: MYOB accounting
    - XeroLoader: Xero accounting
    - DeputyLoader: Deputy workforce
    - EmploymentHeroLoader: Employment Hero HR

Payments/E-commerce:
    - ShopifyLoader: Shopify stores
    - StripeLoader: Stripe payments
    - PayPalLoader: PayPal
    - AfterpayLoader: Afterpay BNPL
    - WooCommerceLoader: WooCommerce

Other:
    - APILoader, RESTLoader: Generic REST APIs
    - CMISLoader: CMIS content management
    - iCloudLoader: Apple iCloud Drive
    - QuickBooksLoader: QuickBooks accounting

Example:
    from agentic_brain.rag.loaders import S3Loader, PostgreSQLLoader, GmailLoader

    # Load from S3
    with S3Loader(bucket="documents") as loader:
        docs = loader.load_folder("reports/")

    # Load from PostgreSQL (SQL injection safe)
    loader = PostgreSQLLoader(database="knowledge", content_column="body")
    docs = loader.load_folder("articles")

    # Load emails
    loader = GmailLoader()
    docs = loader.search("project update", max_results=50)
"""

# Base classes and utilities
# API loaders
from .api import APILoader, RESTLoader

# Australian business
from .australian import DeputyLoader, EmploymentHeroLoader, MYOBLoader, XeroLoader
from .base import (
    BaseLoader,
    LoadedDocument,
    RateLimitError,
    _validate_salesforce_object,
    _validate_sql_identifier,
    with_rate_limit,
)

# Cloud storage
from .cloud import BOTO3_AVAILABLE, AzureBlobLoader, GCSLoader, MinIOLoader, S3Loader

# Content management
from .cmis import CMISLoader

# Confluence
from .confluence import CONFLUENCE_AVAILABLE, ConfluenceLoader
from .csv_loader import CSVLoader, ExcelLoader

# Databases (SQL injection protected)
from .database import MySQLLoader, OracleLoader, PostgreSQLLoader

# SQLAlchemy-based loaders (modern, with connection pooling)
from .database_sqlalchemy import (
    SQLALCHEMY_AVAILABLE,
    MSSQLAlchemyLoader,
    MySQLAlchemyLoader,
    OracleAlchemyLoader,
    PostgreSQLAlchemyLoader,
    SQLAlchemyLoader,
    SQLiteAlchemyLoader,
)
from .docx import DocxLoader, WordLoader

# Email
from .email import GOOGLE_API_AVAILABLE, MSAL_AVAILABLE, GmailLoader, Microsoft365Loader

# Enterprise
from .enterprise import Dynamics365Loader, SAPLoader, ServiceNowLoader, WorkdayLoader

# Factory functions
from .factory import create_loader, get_available_loaders, load_from_multiple_sources
from .github import PYGITHUB_AVAILABLE, GitHubLoader

# Google Drive
from .google_drive import GOOGLE_DRIVE_AVAILABLE, GoogleDriveLoader
from .html import HTMLLoader, WebLoader

# Apple iCloud
from .icloud import PYICLOUD_AVAILABLE, iCloudLoader

# JSON loaders
from .json_loader import JSONLLoader, JSONLoader

# NoSQL
from .nosql import (
    FIREBASE_AVAILABLE,
    PYMONGO_AVAILABLE,
    ElasticsearchLoader,
    FirestoreLoader,
    MongoDBLoader,
    RedisLoader,
)

# Document loaders
from .pdf import PDFLoader

# Accounting
from .quickbooks import QuickBooksLoader

# Payments/E-commerce
from .saas import (
    AfterpayLoader,
    PayPalLoader,
    ShopifyLoader,
    StripeLoader,
    WooCommerceLoader,
)

# CRM (SQL injection protected)
from .salesforce import SalesforceLoader

# Social/Collaboration
from .social import NOTION_AVAILABLE, SLACK_AVAILABLE, NotionLoader, SlackLoader

# Text loaders
from .text import MarkdownLoader, TextLoader

__all__ = [
    # Base
    "BaseLoader",
    "LoadedDocument",
    "RateLimitError",
    "with_rate_limit",
    "_validate_sql_identifier",
    "_validate_salesforce_object",
    # Text
    "TextLoader",
    "MarkdownLoader",
    # JSON
    "JSONLoader",
    "JSONLLoader",
    # Documents
    "PDFLoader",
    "DocxLoader",
    "WordLoader",
    "HTMLLoader",
    "WebLoader",
    "CSVLoader",
    "ExcelLoader",
    # Cloud
    "S3Loader",
    "GCSLoader",
    "AzureBlobLoader",
    "MinIOLoader",
    "BOTO3_AVAILABLE",
    # Databases
    "PostgreSQLLoader",
    "MySQLLoader",
    "OracleLoader",
    # SQLAlchemy (modern)
    "SQLAlchemyLoader",
    "PostgreSQLAlchemyLoader",
    "MySQLAlchemyLoader",
    "SQLiteAlchemyLoader",
    "OracleAlchemyLoader",
    "MSSQLAlchemyLoader",
    "SQLALCHEMY_AVAILABLE",
    # NoSQL
    "MongoDBLoader",
    "RedisLoader",
    "ElasticsearchLoader",
    "FirestoreLoader",
    # Email
    "GmailLoader",
    "Microsoft365Loader",
    # Social
    "SlackLoader",
    "NotionLoader",
    "GitHubLoader",
    # Enterprise
    "SAPLoader",
    "WorkdayLoader",
    "ServiceNowLoader",
    "Dynamics365Loader",
    # CRM
    "SalesforceLoader",
    # Australian
    "MYOBLoader",
    "XeroLoader",
    "DeputyLoader",
    "EmploymentHeroLoader",
    # Payments/E-commerce
    "ShopifyLoader",
    "StripeLoader",
    "PayPalLoader",
    "AfterpayLoader",
    "WooCommerceLoader",
    # Accounting
    "QuickBooksLoader",
    # API
    "APILoader",
    "RESTLoader",
    # CMIS
    "CMISLoader",
    # iCloud
    "iCloudLoader",
    "PYICLOUD_AVAILABLE",
    # Google Drive
    "GoogleDriveLoader",
    "GOOGLE_DRIVE_AVAILABLE",
    # Confluence
    "ConfluenceLoader",
    "CONFLUENCE_AVAILABLE",
    # Factory
    "create_loader",
    "load_from_multiple_sources",
    "get_available_loaders",
    # Availability flags
    "BOTO3_AVAILABLE",
    "FIREBASE_AVAILABLE",
    "GOOGLE_API_AVAILABLE",
    "MSAL_AVAILABLE",
    "NOTION_AVAILABLE",
    "PYGITHUB_AVAILABLE",
    "PYMONGO_AVAILABLE",
    "SLACK_AVAILABLE",
]
