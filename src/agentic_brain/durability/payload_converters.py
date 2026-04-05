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
Payload Converters for Agentic Brain

Payload converters handle serialization and deserialization of workflow data.
Custom converters allow using Protobuf, encryption, compression, or other formats.

Features:
- Pluggable serialization
- Built-in JSON converter (default)
- Protobuf support
- Encryption support
- Compression support
- Converter chaining

Use Cases:
- Protobuf for efficient binary serialization
- Encryption for sensitive data
- Compression for large payloads
- Custom formats for legacy systems

Usage:
    # Create custom converter
    class ProtobufConverter(PayloadConverter):
        def to_payload(self, value: Any) -> bytes:
            return value.SerializeToString()

        def from_payload(self, data: bytes, type_hint: Type) -> Any:
            msg = type_hint()
            msg.ParseFromString(data)
            return msg

    # Register converter
    register_converter("protobuf", ProtobufConverter())

    # Use in workflow
    @workflow(name="my-workflow", payload_converter="protobuf")
    class MyWorkflow(DurableWorkflow):
        pass
"""

import base64
import gzip
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PayloadEncoding(Enum):
    """Encoding types for payloads"""

    JSON = "json"
    BINARY = "binary"
    BASE64 = "base64"


@dataclass
class Payload:
    """
    Serialized payload container
    """

    data: bytes
    encoding: PayloadEncoding
    metadata: Dict[str, Any]

    def __post_init__(self):
        if "converter" not in self.metadata:
            self.metadata["converter"] = "json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": base64.b64encode(self.data).decode("utf-8"),
            "encoding": self.encoding.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Payload":
        return cls(
            data=base64.b64decode(data["data"]),
            encoding=PayloadEncoding(data["encoding"]),
            metadata=data.get("metadata", {}),
        )


class PayloadConverter(ABC):
    """
    Base class for payload converters

    Implement this to add custom serialization formats.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Converter name"""
        pass

    @property
    def encoding(self) -> PayloadEncoding:
        """Default encoding for this converter"""
        return PayloadEncoding.BINARY

    @abstractmethod
    def to_payload(self, value: Any) -> bytes:
        """
        Serialize a value to bytes

        Args:
            value: Value to serialize

        Returns:
            Serialized bytes
        """
        pass

    @abstractmethod
    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        """
        Deserialize bytes to a value

        Args:
            data: Serialized bytes
            type_hint: Optional type hint for deserialization

        Returns:
            Deserialized value
        """
        pass

    def wrap(self, value: Any) -> Payload:
        """Wrap a value in a Payload"""
        return Payload(
            data=self.to_payload(value),
            encoding=self.encoding,
            metadata={"converter": self.name},
        )

    def unwrap(self, payload: Payload, type_hint: Optional[Type[T]] = None) -> T:
        """Unwrap a Payload to a value"""
        return self.from_payload(payload.data, type_hint)


class JSONConverter(PayloadConverter):
    """
    JSON payload converter (default)

    Handles standard Python types with JSON serialization.
    """

    @property
    def name(self) -> str:
        return "json"

    @property
    def encoding(self) -> PayloadEncoding:
        return PayloadEncoding.JSON

    def to_payload(self, value: Any) -> bytes:
        return json.dumps(value, default=self._json_default).encode("utf-8")

    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        return json.loads(data.decode("utf-8"))

    def _json_default(self, obj: Any) -> Any:
        """Handle non-JSON-serializable types"""
        if isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        if isinstance(obj, bytes):
            return {"__bytes__": base64.b64encode(obj).decode("utf-8")}
        if isinstance(obj, Enum):
            return {"__enum__": f"{obj.__class__.__name__}.{obj.name}"}
        if hasattr(obj, "to_dict"):
            return {"__class__": obj.__class__.__name__, **obj.to_dict()}
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class CompressedConverter(PayloadConverter):
    """
    Compressed payload converter

    Wraps another converter with gzip compression.
    """

    def __init__(
        self,
        inner: PayloadConverter,
        level: int = 6,
    ):
        self._inner = inner
        self._level = level

    @property
    def name(self) -> str:
        return f"compressed:{self._inner.name}"

    def to_payload(self, value: Any) -> bytes:
        inner_bytes = self._inner.to_payload(value)
        return gzip.compress(inner_bytes, compresslevel=self._level)

    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        decompressed = gzip.decompress(data)
        return self._inner.from_payload(decompressed, type_hint)


class EncryptedConverter(PayloadConverter):
    """
    Encrypted payload converter

    Wraps another converter with encryption.
    Uses Fernet symmetric encryption from cryptography library.
    """

    def __init__(
        self,
        inner: PayloadConverter,
        key: Optional[bytes] = None,
    ):
        self._inner = inner
        self._key = key
        self._fernet = None

    @property
    def name(self) -> str:
        return f"encrypted:{self._inner.name}"

    def _get_fernet(self):
        """Lazy load Fernet to avoid import if not used"""
        if self._fernet is None:
            try:
                from cryptography.fernet import Fernet

                if self._key is None:
                    # Generate a key if not provided
                    self._key = Fernet.generate_key()
                    logger.warning(
                        "Generated encryption key. Store this securely: "
                        f"{self._key.decode()}"
                    )

                self._fernet = Fernet(self._key)
            except ImportError:
                raise ImportError(
                    "cryptography package required for encryption. "
                    "Install with: pip install cryptography"
                )
        return self._fernet

    def to_payload(self, value: Any) -> bytes:
        inner_bytes = self._inner.to_payload(value)
        return self._get_fernet().encrypt(inner_bytes)

    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        decrypted = self._get_fernet().decrypt(data)
        return self._inner.from_payload(decrypted, type_hint)


class ProtobufConverter(PayloadConverter):
    """
    Protocol Buffers payload converter

    Requires protobuf message types.
    """

    @property
    def name(self) -> str:
        return "protobuf"

    def to_payload(self, value: Any) -> bytes:
        if not hasattr(value, "SerializeToString"):
            raise TypeError(f"Value must be a protobuf message, got {type(value)}")
        return value.SerializeToString()

    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        if type_hint is None:
            raise ValueError("type_hint required for protobuf deserialization")
        if not hasattr(type_hint, "ParseFromString"):
            raise TypeError(
                f"type_hint must be a protobuf message class, got {type_hint}"
            )
        message = type_hint()
        message.ParseFromString(data)
        return message


class MessagePackConverter(PayloadConverter):
    """
    MessagePack payload converter

    More efficient than JSON for many payloads.
    """

    @property
    def name(self) -> str:
        return "msgpack"

    def to_payload(self, value: Any) -> bytes:
        try:
            import msgpack

            return msgpack.packb(value, use_bin_type=True)
        except ImportError:
            raise ImportError(
                "msgpack package required. Install with: pip install msgpack"
            )

    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        try:
            import msgpack

            return msgpack.unpackb(data, raw=False)
        except ImportError:
            raise ImportError(
                "msgpack package required. Install with: pip install msgpack"
            )


class PickleConverter(PayloadConverter):
    """
    Pickle payload converter

    WARNING: Only use with trusted data! Pickle can execute arbitrary code.
    """

    @property
    def name(self) -> str:
        return "pickle"

    def to_payload(self, value: Any) -> bytes:
        import pickle

        return pickle.dumps(value)

    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        import pickle

        return pickle.loads(data)


class ChainedConverter(PayloadConverter):
    """
    Chain multiple converters

    Applies converters in order for to_payload,
    reverse order for from_payload.
    """

    def __init__(self, converters: List[PayloadConverter]):
        if not converters:
            raise ValueError("At least one converter required")
        self._converters = converters

    @property
    def name(self) -> str:
        names = [c.name for c in self._converters]
        return f"chain:{'+'.join(names)}"

    def to_payload(self, value: Any) -> bytes:
        result = value
        for converter in self._converters:
            result = converter.to_payload(result)
        return result

    def from_payload(self, data: bytes, type_hint: Optional[Type[T]] = None) -> T:
        result = data
        for converter in reversed(self._converters):
            if converter == self._converters[0]:
                result = converter.from_payload(result, type_hint)
            else:
                result = converter.from_payload(result, bytes)
        return result


# Converter Registry
class ConverterRegistry:
    """
    Registry for payload converters
    """

    def __init__(self):
        self._converters: Dict[str, PayloadConverter] = {}

        # Register built-in converters
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in converters"""
        self.register(JSONConverter())

    def register(self, converter: PayloadConverter) -> None:
        """Register a converter"""
        self._converters[converter.name] = converter
        logger.debug(f"Registered payload converter: {converter.name}")

    def get(self, name: str) -> PayloadConverter:
        """Get a converter by name"""
        converter = self._converters.get(name)
        if converter is None:
            raise KeyError(f"Unknown converter: {name}")
        return converter

    def list(self) -> List[str]:
        """List all registered converter names"""
        return list(self._converters.keys())

    def create_compressed(
        self,
        base: str = "json",
        level: int = 6,
    ) -> CompressedConverter:
        """Create a compressed converter"""
        inner = self.get(base)
        converter = CompressedConverter(inner, level)
        self.register(converter)
        return converter

    def create_encrypted(
        self,
        base: str = "json",
        key: Optional[bytes] = None,
    ) -> EncryptedConverter:
        """Create an encrypted converter"""
        inner = self.get(base)
        converter = EncryptedConverter(inner, key)
        self.register(converter)
        return converter

    def create_chained(
        self,
        names: List[str],
    ) -> ChainedConverter:
        """Create a chained converter from named converters"""
        converters = [self.get(name) for name in names]
        chained = ChainedConverter(converters)
        self.register(chained)
        return chained


# Global registry
_registry: Optional[ConverterRegistry] = None


def get_converter_registry() -> ConverterRegistry:
    """Get the global converter registry"""
    global _registry
    if _registry is None:
        _registry = ConverterRegistry()
    return _registry


def register_converter(converter: PayloadConverter) -> None:
    """Register a converter globally"""
    get_converter_registry().register(converter)


def get_converter(name: str = "json") -> PayloadConverter:
    """Get a converter by name"""
    return get_converter_registry().get(name)


# Convenience functions
def to_payload(value: Any, converter: str = "json") -> Payload:
    """Convert a value to a Payload"""
    return get_converter(converter).wrap(value)


def from_payload(
    payload: Payload,
    type_hint: Optional[Type[T]] = None,
) -> T:
    """Convert a Payload back to a value"""
    converter_name = payload.metadata.get("converter", "json")
    converter = get_converter(converter_name)
    return converter.unwrap(payload, type_hint)


# Pre-configured converter factories
def create_secure_converter(key: bytes) -> EncryptedConverter:
    """
    Create a secure converter (compressed + encrypted JSON)

    Good for sensitive workflow data.
    """
    registry = get_converter_registry()
    json_conv = registry.get("json")
    compressed = CompressedConverter(json_conv)
    encrypted = EncryptedConverter(compressed, key)
    registry.register(encrypted)
    return encrypted


def create_efficient_converter() -> CompressedConverter:
    """
    Create an efficient converter (compressed JSON)

    Good for large payloads.
    """
    return get_converter_registry().create_compressed("json", level=9)


# Decorator for workflows with custom converters
def with_converter(converter_name: str):
    """
    Decorator to set default converter for a workflow

    Usage:
        @with_converter("compressed:json")
        @workflow(name="my-workflow")
        class MyWorkflow(DurableWorkflow):
            pass
    """

    def decorator(cls):
        cls._payload_converter = converter_name
        return cls

    return decorator
