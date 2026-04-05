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

"""SQLAlchemy-based database loaders for RAG pipelines.

Modern, type-safe database loaders using SQLAlchemy ORM.
Provides better security, connection pooling, and database abstraction.

Supports:
- PostgreSQL
- MySQL
- SQLite
- Oracle Database
- Microsoft SQL Server

Benefits over raw SQL:
- SQL injection prevention via parameterized queries
- Connection pooling for performance
- Type hints and IDE support
- Database-agnostic where possible
- Async support ready
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional
from urllib.parse import quote_plus

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for SQLAlchemy
try:
    from sqlalchemy import (
        Column,
        MetaData,
        String,
        Table,
        Text,
        create_engine,
        inspect,
        select,
        text,
    )
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import QueuePool

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


class SQLAlchemyLoader(BaseLoader):
    """Base SQLAlchemy loader with connection pooling.

    Provides common functionality for all SQLAlchemy-based database loaders.
    Uses connection pooling for efficient resource management.

    Example:
        loader = SQLAlchemyLoader(
            connection_url="postgresql://user:pass@localhost/db"
        )
        with loader.session() as session:
            result = session.execute(select(table))
    """

    def __init__(
        self,
        connection_url: Optional[str] = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False,
        content_column: str = "content",
        id_column: str = "id",
        metadata_columns: Optional[list[str]] = None,
    ):
        """Initialize SQLAlchemy loader.

        Args:
            connection_url: SQLAlchemy connection URL (e.g., postgresql://user:pass@host/db)
            pool_size: Number of connections to keep in pool
            max_overflow: Max connections beyond pool_size
            pool_timeout: Seconds to wait for available connection
            pool_recycle: Seconds before recycling connection
            echo: Log SQL statements (for debugging)
            content_column: Column containing document content
            id_column: Column containing document ID
            metadata_columns: Additional columns to include as metadata
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError("SQLAlchemy not installed. Run: pip install sqlalchemy")

        self._connection_url = connection_url
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._pool_timeout = pool_timeout
        self._pool_recycle = pool_recycle
        self._echo = echo

        self.content_column = content_column
        self.id_column = id_column
        self.metadata_columns = metadata_columns or []

        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._metadata = MetaData()

    @property
    def source_name(self) -> str:
        return "sqlalchemy"

    @property
    def engine(self) -> Engine:
        """Get or create SQLAlchemy engine with connection pooling."""
        if self._engine is None:
            if not self._connection_url:
                raise ValueError("No connection URL configured")

            self._engine = create_engine(
                self._connection_url,
                poolclass=QueuePool,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_timeout=self._pool_timeout,
                pool_recycle=self._pool_recycle,
                echo=self._echo,
            )
            self._session_factory = sessionmaker(bind=self._engine)
            logger.info(f"SQLAlchemy engine created with pool_size={self._pool_size}")

        return self._engine

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup.

        Example:
            with loader.session() as session:
                result = session.execute(query)
        """
        if self._session_factory is None:
            _ = self.engine  # Initialize engine and session factory

        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def authenticate(self) -> bool:
        """Test database connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("SQLAlchemy connection successful")
            return True
        except Exception as e:
            logger.error(f"SQLAlchemy connection failed: {e}")
            return False

    def get_table(self, table_name: str) -> Table:
        """Reflect a table from the database.

        Args:
            table_name: Name of table to reflect

        Returns:
            SQLAlchemy Table object
        """
        return Table(
            table_name,
            self._metadata,
            autoload_with=self.engine,
        )

    def list_tables(self) -> list[str]:
        """List all tables in the database."""
        inspector = inspect(self.engine)
        return inspector.get_table_names()

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single row by ID.

        Args:
            doc_id: Format "table_name/row_id"
        """
        try:
            parts = doc_id.split("/", 1)
            table_name = parts[0]
            row_id = parts[1] if len(parts) > 1 else doc_id

            table = self.get_table(table_name)
            id_col = table.c[self.id_column]
            content_col = table.c[self.content_column]

            columns = [id_col, content_col]
            for col_name in self.metadata_columns:
                if col_name in table.c:
                    columns.append(table.c[col_name])

            query = select(*columns).where(id_col == row_id)

            with self.session() as session:
                result = session.execute(query).fetchone()

            if not result:
                return None

            content = str(result[1]) if result[1] else ""
            metadata = {"table": table_name, "row_id": row_id}
            for i, col_name in enumerate(self.metadata_columns):
                if i + 2 < len(result):
                    metadata[col_name] = result[i + 2]

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"{table_name}_{row_id}",
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to load document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all rows from a table.

        Args:
            folder_path: Table name
            recursive: Ignored for database loaders
        """
        docs = []
        table_name = folder_path

        try:
            table = self.get_table(table_name)
            id_col = table.c[self.id_column]
            content_col = table.c[self.content_column]

            columns = [id_col, content_col]
            for col_name in self.metadata_columns:
                if col_name in table.c:
                    columns.append(table.c[col_name])

            query = select(*columns)

            with self.session() as session:
                results = session.execute(query).fetchall()

            for row in results:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                metadata = {"table": table_name, "row_id": row_id}
                for i, col_name in enumerate(self.metadata_columns):
                    if i + 2 < len(row):
                        metadata[col_name] = row[i + 2]

                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table_name}/{row_id}",
                        filename=f"{table_name}_{row_id}",
                        metadata=metadata,
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load table {table_name}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search is database-specific - override in subclasses."""
        logger.warning(
            "Generic SQLAlchemy search not implemented. Use database-specific loader."
        )
        return []

    def execute_query(
        self, sql: str, params: Optional[dict] = None
    ) -> list[LoadedDocument]:
        """Execute raw SQL and return results as documents.

        Uses SQLAlchemy's text() for parameterized queries.

        Args:
            sql: SQL query (use :param for parameters)
            params: Dictionary of parameter values

        Example:
            docs = loader.execute_query(
                "SELECT id, content FROM articles WHERE category = :cat",
                {"cat": "tech"}
            )
        """
        docs = []
        try:
            with self.session() as session:
                result = session.execute(text(sql), params or {})
                rows = result.fetchall()

            for i, row in enumerate(rows):
                row_id = str(row[0]) if row else str(i)
                content = str(row[1]) if len(row) > 1 and row[1] else ""
                metadata = {}
                for j, col_name in enumerate(self.metadata_columns):
                    if j + 2 < len(row):
                        metadata[col_name] = row[j + 2]

                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=row_id,
                        filename=f"query_{row_id}",
                        metadata=metadata,
                    )
                )
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")

        return docs

    def close(self):
        """Close the engine and all pooled connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("SQLAlchemy engine disposed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PostgreSQLAlchemyLoader(SQLAlchemyLoader):
    """PostgreSQL loader using SQLAlchemy.

    Supports PostgreSQL-specific features like full-text search.

    Example:
        loader = PostgreSQLAlchemyLoader(
            host="localhost",
            database="knowledge_base",
            user="postgres",
            password="secret"
        )
        docs = loader.load_folder("articles")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "postgres",
        user: str = "postgres",
        password: Optional[str] = None,
        connection_url: Optional[str] = None,
        **kwargs,
    ):
        # Build connection URL if not provided
        if not connection_url:
            pwd = password or os.environ.get("POSTGRES_PASSWORD", "")
            connection_url = (
                f"postgresql://{user}:{quote_plus(pwd)}@{host}:{port}/{database}"
            )

        super().__init__(connection_url=connection_url, **kwargs)

    @property
    def source_name(self) -> str:
        return "postgresql"

    def search(
        self, query: str, table_name: str = None, max_results: int = 50
    ) -> list[LoadedDocument]:
        """Full-text search using PostgreSQL ts_vector.

        Requires a tsvector index on the content column.
        """
        if not table_name:
            logger.warning("Table name required for PostgreSQL search")
            return []

        docs = []
        try:
            sql = f"""
                SELECT {self.id_column}, {self.content_column}
                FROM {table_name}
                WHERE to_tsvector('english', {self.content_column}) @@ plainto_tsquery('english', :query)
                LIMIT :limit
            """
            with self.session() as session:
                result = session.execute(
                    text(sql), {"query": query, "limit": max_results}
                )
                rows = result.fetchall()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table_name}/{row_id}",
                        filename=f"{table_name}_{row_id}",
                        metadata={"table": table_name, "row_id": row_id},
                    )
                )
        except Exception as e:
            logger.error(f"PostgreSQL search failed: {e}")

        return docs


class MySQLAlchemyLoader(SQLAlchemyLoader):
    """MySQL loader using SQLAlchemy.

    Supports MySQL-specific features like FULLTEXT search.

    Example:
        loader = MySQLAlchemyLoader(
            host="localhost",
            database="knowledge_base",
            user="root",
            password="secret"
        )
        docs = loader.load_folder("articles")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        database: str = "mysql",
        user: str = "root",
        password: Optional[str] = None,
        connection_url: Optional[str] = None,
        **kwargs,
    ):
        # Build connection URL if not provided
        if not connection_url:
            pwd = password or os.environ.get("MYSQL_PASSWORD", "")
            connection_url = f"mysql+mysqlconnector://{user}:{quote_plus(pwd)}@{host}:{port}/{database}"

        super().__init__(connection_url=connection_url, **kwargs)

    @property
    def source_name(self) -> str:
        return "mysql"

    def search(
        self, query: str, table_name: str = None, max_results: int = 50
    ) -> list[LoadedDocument]:
        """Full-text search using MySQL FULLTEXT index.

        Requires a FULLTEXT index on the content column.
        """
        if not table_name:
            logger.warning("Table name required for MySQL search")
            return []

        docs = []
        try:
            sql = f"""
                SELECT {self.id_column}, {self.content_column}
                FROM {table_name}
                WHERE MATCH({self.content_column}) AGAINST(:query IN NATURAL LANGUAGE MODE)
                LIMIT :limit
            """
            with self.session() as session:
                result = session.execute(
                    text(sql), {"query": query, "limit": max_results}
                )
                rows = result.fetchall()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table_name}/{row_id}",
                        filename=f"{table_name}_{row_id}",
                        metadata={"table": table_name, "row_id": row_id},
                    )
                )
        except Exception as e:
            logger.error(f"MySQL search failed: {e}")

        return docs


class SQLiteAlchemyLoader(SQLAlchemyLoader):
    """SQLite loader using SQLAlchemy.

    Great for local development and testing.

    Example:
        loader = SQLiteAlchemyLoader(database_path="./knowledge.db")
        docs = loader.load_folder("articles")
    """

    def __init__(
        self,
        database_path: str = ":memory:",
        connection_url: Optional[str] = None,
        **kwargs,
    ):
        # Build connection URL if not provided
        if not connection_url:
            connection_url = f"sqlite:///{database_path}"

        # SQLite doesn't need large pools
        kwargs.setdefault("pool_size", 1)
        kwargs.setdefault("max_overflow", 0)

        super().__init__(connection_url=connection_url, **kwargs)

    @property
    def source_name(self) -> str:
        return "sqlite"

    def search(
        self, query: str, table_name: str = None, max_results: int = 50
    ) -> list[LoadedDocument]:
        """Simple LIKE search for SQLite.

        For better search, consider using SQLite FTS5.
        """
        if not table_name:
            logger.warning("Table name required for SQLite search")
            return []

        docs = []
        try:
            sql = f"""
                SELECT {self.id_column}, {self.content_column}
                FROM {table_name}
                WHERE {self.content_column} LIKE :query
                LIMIT :limit
            """
            with self.session() as session:
                result = session.execute(
                    text(sql), {"query": f"%{query}%", "limit": max_results}
                )
                rows = result.fetchall()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table_name}/{row_id}",
                        filename=f"{table_name}_{row_id}",
                        metadata={"table": table_name, "row_id": row_id},
                    )
                )
        except Exception as e:
            logger.error(f"SQLite search failed: {e}")

        return docs


class OracleAlchemyLoader(SQLAlchemyLoader):
    """Oracle Database loader using SQLAlchemy.

    Example:
        loader = OracleAlchemyLoader(
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
        connection_url: Optional[str] = None,
        **kwargs,
    ):
        # Build connection URL if not provided
        if not connection_url:
            usr = user or os.environ.get("ORACLE_USER", "")
            pwd = password or os.environ.get("ORACLE_PASSWORD", "")
            if service_name:
                connection_url = f"oracle+oracledb://{usr}:{quote_plus(pwd)}@{host}:{port}/?service_name={service_name}"
            elif sid:
                connection_url = (
                    f"oracle+oracledb://{usr}:{quote_plus(pwd)}@{host}:{port}/{sid}"
                )
            else:
                raise ValueError("Either service_name or sid must be provided")

        super().__init__(connection_url=connection_url, **kwargs)

    @property
    def source_name(self) -> str:
        return "oracle"


class MSSQLAlchemyLoader(SQLAlchemyLoader):
    """Microsoft SQL Server loader using SQLAlchemy.

    Example:
        loader = MSSQLAlchemyLoader(
            host="sqlserver.example.com",
            database="knowledge_base",
            user="sa",
            password="secret"
        )
        docs = loader.load_folder("dbo.articles")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1433,
        database: str = "master",
        user: Optional[str] = None,
        password: Optional[str] = None,
        driver: str = "ODBC Driver 18 for SQL Server",
        connection_url: Optional[str] = None,
        **kwargs,
    ):
        # Build connection URL if not provided
        if not connection_url:
            usr = user or os.environ.get("MSSQL_USER", "sa")
            pwd = password or os.environ.get("MSSQL_PASSWORD", "")
            connection_url = (
                f"mssql+pyodbc://{usr}:{quote_plus(pwd)}@{host}:{port}/{database}"
                f"?driver={quote_plus(driver)}"
            )

        super().__init__(connection_url=connection_url, **kwargs)

    @property
    def source_name(self) -> str:
        return "mssql"

    def search(
        self, query: str, table_name: str = None, max_results: int = 50
    ) -> list[LoadedDocument]:
        """Full-text search using SQL Server CONTAINS.

        Requires a FULLTEXT index on the content column.
        """
        if not table_name:
            logger.warning("Table name required for SQL Server search")
            return []

        docs = []
        try:
            sql = f"""
                SELECT TOP (:limit) {self.id_column}, {self.content_column}
                FROM {table_name}
                WHERE CONTAINS({self.content_column}, :query)
            """
            with self.session() as session:
                result = session.execute(
                    text(sql), {"query": query, "limit": max_results}
                )
                rows = result.fetchall()

            for row in rows:
                row_id = str(row[0])
                content = str(row[1]) if row[1] else ""
                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=f"{table_name}/{row_id}",
                        filename=f"{table_name}_{row_id}",
                        metadata={"table": table_name, "row_id": row_id},
                    )
                )
        except Exception as e:
            logger.error(f"SQL Server search failed: {e}")

        return docs


__all__ = [
    "SQLAlchemyLoader",
    "PostgreSQLAlchemyLoader",
    "MySQLAlchemyLoader",
    "SQLiteAlchemyLoader",
    "OracleAlchemyLoader",
    "MSSQLAlchemyLoader",
    "SQLALCHEMY_AVAILABLE",
]
