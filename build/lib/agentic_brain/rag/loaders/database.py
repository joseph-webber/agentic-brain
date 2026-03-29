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

"""Database loaders for RAG pipelines.

Supports:
- PostgreSQL
- MySQL
- Oracle Database

SECURITY NOTE: This module uses SQL identifier validation to prevent SQL injection.
All table and column names are validated using _validate_sql_identifier() from base.py.
"""

import logging
import os
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument, _validate_sql_identifier

logger = logging.getLogger(__name__)

# Check for psycopg2
try:
    import psycopg2

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

# Check for MySQL
try:
    import mysql.connector

    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class PostgreSQLLoader(BaseLoader):
    """Load documents from PostgreSQL database.

    Extracts text content from tables for RAG ingestion.

    SECURITY: Table and column names are validated to prevent SQL injection.

    Example:
        loader = PostgreSQLLoader(
            host="localhost",
            database="knowledge_base",
            user="postgres",
            password="secret"
        )
        docs = loader.load_folder("articles")  # table name
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "postgres",
        user: str = "postgres",
        password: Optional[str] = None,
        connection_string: Optional[str] = None,
        content_column: str = "content",
        id_column: str = "id",
        metadata_columns: Optional[list[str]] = None,
    ):
        if not POSTGRES_AVAILABLE:
            raise ImportError(
                "psycopg2 not installed. Run: pip install psycopg2-binary"
            )

        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password or os.environ.get("POSTGRES_PASSWORD")
        self.connection_string = connection_string or os.environ.get("DATABASE_URL")
        self.content_column = _validate_sql_identifier(content_column)
        self.id_column = _validate_sql_identifier(id_column)
        self.metadata_columns = [
            _validate_sql_identifier(c) for c in (metadata_columns or [])
        ]
        self._conn = None

    @property
    def source_name(self) -> str:
        return "postgresql"

    def authenticate(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            if self.connection_string:
                self._conn = psycopg2.connect(self.connection_string)
            else:
                self._conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                )
            logger.info(f"PostgreSQL connection successful to {self.database}")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._conn and not self.authenticate():
            raise RuntimeError("Failed to connect to PostgreSQL")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single row by ID. doc_id format: table_name/row_id"""
        self._ensure_authenticated()
        try:
            parts = doc_id.split("/", 1)
            table = _validate_sql_identifier(parts[0])
            row_id = parts[1] if len(parts) > 1 else doc_id

            columns = [self.id_column, self.content_column] + self.metadata_columns
            columns_str = ", ".join(columns)

            with self._conn.cursor() as cur:
                cur.execute(
                    f"SELECT {columns_str} FROM {table} WHERE {self.id_column} = %s",
                    (row_id,),
                )
                row = cur.fetchone()

            if not row:
                return None

            content = str(row[1]) if row[1] else ""
            metadata = {}
            for i, col in enumerate(self.metadata_columns):
                metadata[col] = row[i + 2]

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"{table}_{row_id}",
                metadata={"table": table, "row_id": row_id, **metadata},
            )
        except Exception as e:
            logger.error(f"Failed to load row {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all rows from a table. folder_path is the table name."""
        self._ensure_authenticated()
        docs = []
        table = _validate_sql_identifier(folder_path)

        try:
            columns = [self.id_column, self.content_column] + self.metadata_columns
            columns_str = ", ".join(columns)

            with self._conn.cursor() as cur:
                cur.execute(f"SELECT {columns_str} FROM {table}")
                rows = cur.fetchall()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                metadata = {}
                for i, col in enumerate(self.metadata_columns):
                    metadata[col] = row[i + 2]

                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table}/{row_id}",
                        filename=f"{table}_{row_id}",
                        metadata={"table": table, "row_id": row_id, **metadata},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load table {table}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for text in content column."""
        logger.warning(
            "PostgreSQL search requires specifying table. Use load_with_query instead."
        )
        return []

    def load_with_query(
        self, sql: str, params: Optional[tuple] = None
    ) -> list[LoadedDocument]:
        """Load documents using custom SQL query.

        Query must return columns in order: id, content, [metadata_columns...]

        Example:
            docs = loader.load_with_query(
                "SELECT id, body, title, author FROM articles WHERE category = %s",
                ("tech",)
            )
        """
        self._ensure_authenticated()
        docs = []

        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params or ())
                rows = cur.fetchall()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                metadata = {}
                for i, col in enumerate(self.metadata_columns):
                    if i + 2 < len(row):
                        metadata[col] = row[i + 2]

                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=row_id,
                        filename=f"query_{row_id}",
                        metadata={"row_id": row_id, **metadata},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")

        return docs


class MySQLLoader(BaseLoader):
    """Load documents from MySQL database.

    SECURITY: Table and column names are validated to prevent SQL injection.

    Example:
        loader = MySQLLoader(
            host="localhost",
            database="knowledge_base",
            user="root",
            password="secret"
        )
        docs = loader.load_folder("articles")  # table name
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        database: str = "mysql",
        user: str = "root",
        password: Optional[str] = None,
        content_column: str = "content",
        id_column: str = "id",
        metadata_columns: Optional[list[str]] = None,
    ):
        if not MYSQL_AVAILABLE:
            raise ImportError(
                "mysql-connector-python not installed. Run: pip install mysql-connector-python"
            )

        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password or os.environ.get("MYSQL_PASSWORD")
        self.content_column = _validate_sql_identifier(content_column)
        self.id_column = _validate_sql_identifier(id_column)
        self.metadata_columns = [
            _validate_sql_identifier(c) for c in (metadata_columns or [])
        ]
        self._conn = None

    @property
    def source_name(self) -> str:
        return "mysql"

    def authenticate(self) -> bool:
        """Connect to MySQL."""
        try:
            self._conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            logger.info(f"MySQL connection successful to {self.database}")
            return True
        except Exception as e:
            logger.error(f"MySQL connection failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._conn and not self.authenticate():
            raise RuntimeError("Failed to connect to MySQL")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single row by ID."""
        self._ensure_authenticated()
        try:
            parts = doc_id.split("/", 1)
            table = _validate_sql_identifier(parts[0])
            row_id = parts[1] if len(parts) > 1 else doc_id

            columns = [self.id_column, self.content_column] + self.metadata_columns
            columns_str = ", ".join(f"`{c}`" for c in columns)

            cursor = self._conn.cursor()
            cursor.execute(
                f"SELECT {columns_str} FROM `{table}` WHERE `{self.id_column}` = %s",
                (row_id,),
            )
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            content = str(row[1]) if row[1] else ""
            metadata = {}
            for i, col in enumerate(self.metadata_columns):
                metadata[col] = row[i + 2]

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"{table}_{row_id}",
                metadata={"table": table, "row_id": row_id, **metadata},
            )
        except Exception as e:
            logger.error(f"Failed to load row {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all rows from a table."""
        self._ensure_authenticated()
        docs = []
        table = _validate_sql_identifier(folder_path)

        try:
            columns = [self.id_column, self.content_column] + self.metadata_columns
            columns_str = ", ".join(f"`{c}`" for c in columns)

            cursor = self._conn.cursor()
            cursor.execute(f"SELECT {columns_str} FROM `{table}`")
            rows = cursor.fetchall()
            cursor.close()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                metadata = {}
                for i, col in enumerate(self.metadata_columns):
                    metadata[col] = row[i + 2]

                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table}/{row_id}",
                        filename=f"{table}_{row_id}",
                        metadata={"table": table, "row_id": row_id, **metadata},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load table {table}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Full-text search (requires FULLTEXT index)."""
        logger.warning("MySQL search requires specifying table and FULLTEXT index.")
        return []


class OracleLoader(BaseLoader):
    """Load documents from Oracle Database.

    SECURITY: Table and column names are validated to prevent SQL injection.

    Example:
        loader = OracleLoader(
            host="oracle.example.com",
            service_name="ORCL",
            user="system",
            password="secret"
        )
        docs = loader.load_folder("HR.EMPLOYEES")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1521,
        service_name: Optional[str] = None,
        sid: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        content_column: str = "content",
        id_column: str = "id",
    ):
        self.host = host
        self.port = port
        self.service_name = service_name
        self.sid = sid
        self.user = user or os.environ.get("ORACLE_USER")
        self.password = password or os.environ.get("ORACLE_PASSWORD")
        self.content_column = _validate_sql_identifier(content_column)
        self.id_column = _validate_sql_identifier(id_column)
        self._conn = None

    @property
    def source_name(self) -> str:
        return "oracle"

    def authenticate(self) -> bool:
        """Connect to Oracle Database."""
        try:
            import oracledb

            dsn = f"{self.host}:{self.port}"
            if self.service_name:
                dsn += f"/{self.service_name}"
            elif self.sid:
                dsn = oracledb.makedsn(self.host, self.port, sid=self.sid)

            self._conn = oracledb.connect(
                user=self.user, password=self.password, dsn=dsn
            )
            logger.info("Oracle connection successful")
            return True
        except ImportError:
            logger.error("oracledb not installed. Run: pip install oracledb")
            return False
        except Exception as e:
            logger.error(f"Oracle connection failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._conn and not self.authenticate():
            raise RuntimeError("Failed to connect to Oracle")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single row by ID."""
        self._ensure_authenticated()
        try:
            parts = doc_id.split("/", 1)
            table = _validate_sql_identifier(parts[0])
            row_id = parts[1] if len(parts) > 1 else doc_id

            cursor = self._conn.cursor()
            cursor.execute(
                f"SELECT {self.id_column}, {self.content_column} FROM {table} WHERE {self.id_column} = :id",
                {"id": row_id},
            )
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            return LoadedDocument(
                content=str(row[1]) if row[1] else "",
                source=self.source_name,
                source_id=doc_id,
                filename=f"{table}_{row_id}",
                metadata={"table": table, "row_id": row_id},
            )
        except Exception as e:
            logger.error(f"Failed to load row {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all rows from a table."""
        self._ensure_authenticated()
        docs = []
        table = _validate_sql_identifier(folder_path)

        try:
            cursor = self._conn.cursor()
            cursor.execute(
                f"SELECT {self.id_column}, {self.content_column} FROM {table} WHERE ROWNUM <= 10000"
            )
            rows = cursor.fetchall()
            cursor.close()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table}/{row_id}",
                        filename=f"{table}_{row_id}",
                        metadata={"table": table, "row_id": row_id},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load table {table}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search using Oracle Text (if available)."""
        logger.warning("Oracle search requires Oracle Text index on content column.")
        return []


__all__ = [
    "PostgreSQLLoader",
    "MySQLLoader",
    "OracleLoader",
]
