# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber

"""ADL parser.

Minimal, JDL-inspired DSL for configuring an Agentic Brain instance.

The grammar is intentionally small and regular so that it can be parsed
with a hand-written recursive-descent parser (no external dependencies).

Top-level constructs (all optional, order-independent)::

    application <Name> { ... }
    llm <Name> { ... }
    rag <Name> { ... }
    voice <Name> { ... }
    api <Name> { ... }
    security { ... }
    modes { ... }
    deployment { ... }

    // JDL-style modelling constructs
    enum <Name> { A, B, C }
    entity <Name> {
      fieldName Type required min(1)
    }
    relationship <Kind> {
      From{field} to To
    }

Block bodies are simple key/value pairs where values may be:

* unquoted identifiers (e.g. ``OpenAI``, ``Neo4j``, ``JWT``)
* string literals in double quotes
* numbers (ints or floats)
* lists: ``[A, B, "C"]``
* nested blocks: ``rateLimit { requests 100 window "1m" }``

Comments use ``//`` to end of line.

Annotations (JDL-inspired) can be applied to the *next* construct:

    @priority(high)
    llm Primary { provider OpenAI }

Annotations are supported for all top-level constructs, plus entity fields
and relationship lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---- ADL sensible defaults (no backward-compat required) ----

DEFAULTS: Dict[str, Any] = {
    "application": {
        "name": "Agentic Brain",
        "version": "1.0.0",
        "license": "Apache-2.0",
        "persona": "professional",
    },
    "llm": {
        # Detect: Ollama → OpenAI → Anthropic (runtime chooses best available)
        "provider": "auto",
        # Provide a sensible model default so the brain is runnable even in local-only mode
        "model": "llama3.2:3b",
        "temperature": 0.7,
        "maxTokens": 4096,
        # Always fall back to local where possible
        "fallback": "ollama",
    },
    "rag": {
        # Don"t require Neo4j by default
        "enabled": False,
        "vectorStore": "memory",
        "embeddingModel": "auto",
    },
    "voice": {
        "enabled": True,
        # macOS say command
        "provider": "system",
        # Detect system default voice
        "defaultVoice": "auto",
    },
    "api": {
        "enabled": True,
        "port": 8000,
        # True => allow all ("*")
        "cors": True,
    },
    "security": {
        # Disabled by default for easy start
        "auth": False,
        "rateLimit": True,
    },
}


class ADLValidationError(ValueError):
    """Raised when ADL is syntactically valid but semantically invalid."""


_ALLOWED_LLM_PROVIDERS = {
    "auto",
    "ollama",
    "openai",
    "anthropic",
    "openrouter",
    "groq",
    "together",
    "google",
    "xai",
    "azure_openai",
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dicts (override wins)."""
    out: Dict[str, Any] = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def apply_defaults(cfg: ADLConfig) -> ADLConfig:
    """Mutate config in-place to apply sensible defaults.

    ADL is intentionally *minimal*: missing blocks are created automatically,
    and missing keys are filled from DEFAULTS.
    """

    # Application
    if cfg.application is None:
        cfg.application = Block(
            name=DEFAULTS["application"]["name"], values={}, annotations=[]
        )
    app_vals = dict(cfg.application.values)
    # If user didn"t provide `name`, use application identifier first, then default.
    app_name = (
        app_vals.get("name") or cfg.application.name or DEFAULTS["application"]["name"]
    )
    app_vals = _deep_merge(DEFAULTS["application"], app_vals)
    app_vals["name"] = str(app_name)
    cfg.application.values = app_vals

    # LLMs
    if not cfg.llms:
        cfg.llms["Primary"] = Block(name="Primary", values={}, annotations=[])
    for name, block in list(cfg.llms.items()):
        block.values = _deep_merge(DEFAULTS["llm"], dict(block.values))
        cfg.llms[name] = block

    # RAG
    # If the user declares a rag block, assume they intend to enable it unless
    # they explicitly set enabled=false. If no rag blocks exist, keep it disabled
    # by default (in-memory vector store).
    if not cfg.rags:
        cfg.rags["Default"] = Block(
            name="Default", values={"enabled": False}, annotations=[]
        )
    for name, block in list(cfg.rags.items()):
        user_vals = dict(block.values)
        if "enabled" not in user_vals and user_vals:
            user_vals["enabled"] = True
        block.values = _deep_merge(DEFAULTS["rag"], user_vals)
        cfg.rags[name] = block

    # Voice
    if not cfg.voices:
        cfg.voices["Assistant"] = Block(name="Assistant", values={}, annotations=[])
    for name, block in list(cfg.voices.items()):
        block.values = _deep_merge(DEFAULTS["voice"], dict(block.values))
        cfg.voices[name] = block

    # API
    if not cfg.apis:
        cfg.apis["REST"] = Block(name="REST", values={}, annotations=[])
    for name, block in list(cfg.apis.items()):
        block.values = _deep_merge(DEFAULTS["api"], dict(block.values))
        cfg.apis[name] = block

    # Security
    if cfg.security is None:
        cfg.security = Block(name=None, values={}, annotations=[])
    cfg.security.values = _deep_merge(DEFAULTS["security"], dict(cfg.security.values))

    return cfg


def validate_config(cfg: ADLConfig) -> None:
    """Validate a defaulted config. Raises ADLValidationError on problems."""

    if cfg.application is None:
        raise ADLValidationError("Missing application block")

    for name, llm in cfg.llms.items():
        provider = str(llm.values.get("provider", "auto")).strip().lower()
        if provider not in _ALLOWED_LLM_PROVIDERS:
            raise ADLValidationError(f"llm {name}: invalid provider '{provider}'")

        try:
            temp = float(llm.values.get("temperature", DEFAULTS["llm"]["temperature"]))
        except Exception as e:
            raise ADLValidationError(f"llm {name}: temperature must be a number") from e
        if not (0.0 <= temp <= 2.0):
            raise ADLValidationError(
                f"llm {name}: temperature must be between 0.0 and 2.0"
            )
        llm.values["temperature"] = temp

        try:
            max_tokens = int(llm.values.get("maxTokens", DEFAULTS["llm"]["maxTokens"]))
        except Exception as e:
            raise ADLValidationError(f"llm {name}: maxTokens must be an integer") from e
        if max_tokens <= 0:
            raise ADLValidationError(f"llm {name}: maxTokens must be > 0")
        llm.values["maxTokens"] = max_tokens

    for name, api in cfg.apis.items():
        enabled = api.values.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ADLValidationError(f"api {name}: enabled must be true/false")

        try:
            port = int(api.values.get("port", DEFAULTS["api"]["port"]))
        except Exception as e:
            raise ADLValidationError(f"api {name}: port must be an integer") from e
        if not (1 <= port <= 65535):
            raise ADLValidationError(f"api {name}: port must be between 1 and 65535")
        api.values["port"] = port

        cors = api.values.get("cors", True)
        if not isinstance(cors, (bool, list)):
            raise ADLValidationError(f"api {name}: cors must be true/false or a list")

    for name, rag in cfg.rags.items():
        enabled = rag.values.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ADLValidationError(f"rag {name}: enabled must be true/false")
        # Allow custom vector stores (complex things should be possible).
        # The generator only needs to special-case Neo4j.
        _ = str(rag.values.get("vectorStore", DEFAULTS["rag"]["vectorStore"]))

    for name, voice in cfg.voices.items():
        enabled = voice.values.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ADLValidationError(f"voice {name}: enabled must be true/false")
        provider = str(voice.values.get("provider", "system")).strip().lower()
        if provider not in {"system", "macos"}:
            raise ADLValidationError(
                f"voice {name}: provider must be system (or macos)"
            )

    if cfg.security is not None:
        authentication = cfg.security.values.get("authentication")
        if authentication is not None and not isinstance(authentication, str):
            raise ADLValidationError(
                "security.authentication must be an identifier or string"
            )

        rate = cfg.security.values.get("rateLimit")
        if rate is not None and not isinstance(rate, (bool, int, str)):
            raise ADLValidationError(
                "security.rateLimit must be a boolean, an integer, or a profile identifier"
            )

        sso = cfg.security.values.get("sso")
        if sso is not None and not isinstance(sso, list):
            raise ADLValidationError("security.sso must be a list")


class TokenKind(Enum):
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()
    NEWLINE = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    AT = auto()
    SEMICOLON = auto()
    EOF = auto()


@dataclass
class Token:
    kind: TokenKind
    value: str
    line: int
    column: int


class ADLParseError(ValueError):
    """Raised when ADL parsing fails."""


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_ident_part(ch: str) -> bool:
    # Allow dash/dot/slash/colon so we can express things like Apache-2.0, gpt-4o, llama3.2:8b
    return ch.isalnum() or ch in {"_", "-", ".", "/", ":"}


class Lexer:
    """Simple, line/column-aware tokenizer for ADL."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _advance(self) -> str:
        ch = self._peek()
        if not ch:
            return ""
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _skip_spaces_and_comments(self) -> None:
        while True:
            ch = self._peek()
            if ch in {" ", "\t", "\r"}:
                self._advance()
                continue
            # Line comments
            if (
                ch == "/"
                and self.pos + 1 < len(self.text)
                and self.text[self.pos + 1] == "/"
            ):
                while self._peek() not in {"", "\n"}:
                    self._advance()
                continue
            break

    def _lex_string(self) -> Token:
        line, col = self.line, self.col
        assert self._advance() == '"'  # consume opening quote
        chars: List[str] = []
        while True:
            ch = self._peek()
            if ch == "":
                raise ADLParseError(f"Unterminated string at line {line} column {col}")
            if ch == '"':
                self._advance()
                break
            if ch == "\\":
                self._advance()
                esc = self._peek()
                if esc == "":
                    raise ADLParseError(
                        f"Unterminated escape sequence at line {line} column {col}"
                    )
                self._advance()
                if esc == "n":
                    chars.append("\n")
                elif esc == "t":
                    chars.append("\t")
                else:
                    chars.append(esc)
            else:
                chars.append(self._advance())
        return Token(TokenKind.STRING, "".join(chars), line, col)

    def _lex_number_or_ident(self) -> Token:
        line, col = self.line, self.col
        ch = self._peek()
        if ch.isdigit():
            # Number: digits with optional single decimal point
            num_chars: List[str] = []
            has_dot = False
            while True:
                ch = self._peek()
                if ch.isdigit():
                    num_chars.append(self._advance())
                    continue
                if ch == "." and not has_dot:
                    has_dot = True
                    num_chars.append(self._advance())
                    continue
                break
            return Token(TokenKind.NUMBER, "".join(num_chars), line, col)

        # Identifier
        ident_chars: List[str] = []
        while True:
            ch = self._peek()
            if ch and _is_ident_part(ch):
                ident_chars.append(self._advance())
            else:
                break
        return Token(TokenKind.IDENT, "".join(ident_chars), line, col)

    def tokens(self) -> List[Token]:
        toks: List[Token] = []
        while True:
            self._skip_spaces_and_comments()
            ch = self._peek()
            if not ch:
                toks.append(Token(TokenKind.EOF, "", self.line, self.col))
                break

            line, col = self.line, self.col

            if ch == "\n":
                self._advance()
                toks.append(Token(TokenKind.NEWLINE, "\n", line, col))
            elif ch == '"':
                toks.append(self._lex_string())
            elif ch.isdigit() or _is_ident_start(ch):
                toks.append(self._lex_number_or_ident())
            elif ch == "{":
                self._advance()
                toks.append(Token(TokenKind.LBRACE, "{", line, col))
            elif ch == "}":
                self._advance()
                toks.append(Token(TokenKind.RBRACE, "}", line, col))
            elif ch == "[":
                self._advance()
                toks.append(Token(TokenKind.LBRACKET, "[", line, col))
            elif ch == "]":
                self._advance()
                toks.append(Token(TokenKind.RBRACKET, "]", line, col))
            elif ch == "(":
                self._advance()
                toks.append(Token(TokenKind.LPAREN, "(", line, col))
            elif ch == ")":
                self._advance()
                toks.append(Token(TokenKind.RPAREN, ")", line, col))
            elif ch == ",":
                self._advance()
                toks.append(Token(TokenKind.COMMA, ",", line, col))
            elif ch == "@":
                self._advance()
                toks.append(Token(TokenKind.AT, "@", line, col))
            elif ch == ";":
                self._advance()
                toks.append(Token(TokenKind.SEMICOLON, ";", line, col))
            elif ch == "*":
                # JDL wildcard: treat as identifier
                self._advance()
                toks.append(Token(TokenKind.IDENT, "*", line, col))
            else:
                raise ADLParseError(
                    f"Unexpected character '{ch}' at line {line} column {col}"
                )
        return toks


# ---- model ----


@dataclass
class Annotation:
    name: str
    args: List[Any] = field(default_factory=list)


@dataclass
class Block:
    name: Optional[str]
    values: Dict[str, Any] = field(default_factory=dict)
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class Validator:
    name: str
    args: List[Any] = field(default_factory=list)


@dataclass
class FieldDef:
    name: str
    type: str
    validators: List[Validator] = field(default_factory=list)
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class EntityDef:
    name: str
    fields: List[FieldDef] = field(default_factory=list)
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class EnumDef:
    name: str
    values: List[str] = field(default_factory=list)
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class RelationshipEnd:
    entity: str
    field: Optional[str] = None


@dataclass
class RelationshipDef:
    kind: str
    from_end: RelationshipEnd
    to_end: RelationshipEnd
    options: List[str] = field(default_factory=list)
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class PaginationDef:
    """JDL-style pagination directive: ``paginate Entity with pagination``."""

    entities: List[str]  # entity names or ["*"] / ["all"]
    style: str  # "pagination", "infinite-scroll", "pager"


@dataclass
class DtoDef:
    """JDL-style DTO directive: ``dto Entity with mapstruct``."""

    entities: List[str]
    mapper: str  # "mapstruct", "dataclass", "pydantic"


@dataclass
class ServiceDef:
    """JDL-style service directive: ``service Entity with serviceImpl``."""

    entities: List[str]
    impl: str  # "serviceImpl", "serviceClass"


@dataclass
class ADLConfig:
    """Top-level parsed representation of an ADL file."""

    application: Optional[Block] = None
    llms: Dict[str, Block] = field(default_factory=dict)
    rags: Dict[str, Block] = field(default_factory=dict)
    voices: Dict[str, Block] = field(default_factory=dict)
    apis: Dict[str, Block] = field(default_factory=dict)
    security: Optional[Block] = None
    modes: Optional[Block] = None
    deployment: Optional[Block] = None

    # Modelling constructs
    entities: Dict[str, EntityDef] = field(default_factory=dict)
    enums: Dict[str, EnumDef] = field(default_factory=dict)
    relationships: List[RelationshipDef] = field(default_factory=list)

    # JDL-style directives
    paginations: List[PaginationDef] = field(default_factory=list)
    dtos: List[DtoDef] = field(default_factory=list)
    services: List[ServiceDef] = field(default_factory=list)

    # Raw blocks for forward-compat / unknown keywords
    raw_blocks: List[Block] = field(default_factory=list)


class Parser:
    """Recursive-descent parser over lexer tokens."""

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        tok = self._peek()
        if tok.kind != TokenKind.EOF:
            self.index += 1
        return tok

    def _expect(self, kind: TokenKind, message: str) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ADLParseError(f"{message} at line {tok.line} column {tok.column}")
        return self._advance()

    def _accept(self, kind: TokenKind) -> Optional[Token]:
        tok = self._peek()
        if tok.kind == kind:
            return self._advance()
        return None

    def _skip_newlines(self) -> None:
        while self._accept(TokenKind.NEWLINE):
            pass

    # ---- expressions ----

    def _parse_value(self) -> Any:
        tok = self._peek()
        if tok.kind == TokenKind.STRING:
            self._advance()
            return tok.value
        if tok.kind == TokenKind.NUMBER:
            self._advance()
            return float(tok.value) if "." in tok.value else int(tok.value)
        if tok.kind == TokenKind.LBRACKET:
            return self._parse_list()
        if tok.kind == TokenKind.LBRACE:
            # Anonymous nested block as dict
            block = self._parse_kv_block_body(name=None, annotations=[])
            return block.values
        if tok.kind == TokenKind.IDENT:
            self._advance()
            # Booleans
            lower = tok.value.lower()
            if lower == "true":
                return True
            if lower == "false":
                return False
            return tok.value
        raise ADLParseError(
            f"Unexpected token {tok.kind.name} when parsing value at line {tok.line} column {tok.column}"
        )

    def _parse_list(self) -> List[Any]:
        items: List[Any] = []
        self._expect(TokenKind.LBRACKET, "Expected '[' to start list")
        self._skip_newlines()
        while True:
            tok = self._peek()
            if tok.kind == TokenKind.RBRACKET:
                self._advance()
                break
            items.append(self._parse_value())
            self._skip_newlines()
            if self._accept(TokenKind.COMMA):
                self._skip_newlines()
                continue
            tok = self._peek()
            if tok.kind == TokenKind.RBRACKET:
                continue
        return items

    # ---- annotations ----

    def _parse_annotation(self) -> Annotation:
        at_tok = self._expect(TokenKind.AT, "Expected '@' to start annotation")
        name_tok = self._expect(TokenKind.IDENT, "Expected annotation name")
        args: List[Any] = []

        # Support bare @flag without args
        if not self._accept(TokenKind.LPAREN):
            return Annotation(name=name_tok.value, args=[])

        self._skip_newlines()
        if self._accept(TokenKind.RPAREN):
            return Annotation(name=name_tok.value, args=[])

        while True:
            self._skip_newlines()
            tok = self._peek()
            if tok.kind == TokenKind.RPAREN:
                self._advance()
                break
            if tok.kind == TokenKind.EOF:
                raise ADLParseError(
                    f"Unterminated annotation '@{name_tok.value}' starting at line {at_tok.line} column {at_tok.column}"
                )
            args.append(self._parse_value())
            self._skip_newlines()
            if self._accept(TokenKind.COMMA):
                continue
            if self._peek().kind == TokenKind.RPAREN:
                continue
        return Annotation(name=name_tok.value, args=args)

    def _parse_leading_annotations(self) -> List[Annotation]:
        anns: List[Annotation] = []
        while self._peek().kind == TokenKind.AT:
            anns.append(self._parse_annotation())
            self._skip_newlines()
        return anns

    # ---- blocks ----

    def _parse_kv_block_body(
        self, name: Optional[str], annotations: List[Annotation]
    ) -> Block:
        self._expect(TokenKind.LBRACE, "Expected '{' to start block body")
        values: Dict[str, Any] = {}
        while True:
            self._skip_newlines()
            tok = self._peek()
            if tok.kind == TokenKind.RBRACE:
                self._advance()
                break
            if tok.kind == TokenKind.EOF:
                raise ADLParseError(
                    f"Unterminated block starting at line {tok.line} column {tok.column}"
                )
            if tok.kind not in (TokenKind.IDENT, TokenKind.STRING):
                raise ADLParseError(
                    f"Expected identifier or string inside block at line {tok.line} column {tok.column}"
                )
            key = self._advance().value
            # Optional ':' for readability (JDL-style): allow `Key:` or `Key`.
            if key.endswith(":"):
                key = key[:-1]

            self._skip_newlines()

            # Support nested blocks: key { ... }
            if self._peek().kind == TokenKind.LBRACE:
                nested = self._parse_kv_block_body(key, annotations=[])
                values[key] = nested.values
                continue

            self._skip_newlines()
            values[key] = self._parse_value()
            self._skip_newlines()
        return Block(name=name, values=values, annotations=annotations)

    def _parse_enum_body(self, name: str, annotations: List[Annotation]) -> EnumDef:
        self._expect(TokenKind.LBRACE, "Expected '{' to start enum body")
        values: List[str] = []
        while True:
            self._skip_newlines()
            tok = self._peek()
            if tok.kind == TokenKind.RBRACE:
                self._advance()
                break
            if tok.kind == TokenKind.EOF:
                raise ADLParseError(
                    f"Unterminated enum '{name}' starting at line {tok.line} column {tok.column}"
                )
            if tok.kind != TokenKind.IDENT:
                raise ADLParseError(
                    f"Expected enum value in enum '{name}' at line {tok.line} column {tok.column}"
                )
            values.append(self._advance().value)
            self._skip_newlines()
            self._accept(TokenKind.COMMA)
        return EnumDef(name=name, values=values, annotations=annotations)

    def _parse_validator(self) -> Validator:
        name_tok = self._expect(TokenKind.IDENT, "Expected validator name")
        args: List[Any] = []
        if self._accept(TokenKind.LPAREN):
            self._skip_newlines()
            if not self._accept(TokenKind.RPAREN):
                while True:
                    self._skip_newlines()
                    if self._peek().kind == TokenKind.RPAREN:
                        self._advance()
                        break
                    args.append(self._parse_value())
                    self._skip_newlines()
                    if self._accept(TokenKind.COMMA):
                        continue
                    if self._peek().kind == TokenKind.RPAREN:
                        continue
        return Validator(name=name_tok.value, args=args)

    def _parse_entity_body(self, name: str, annotations: List[Annotation]) -> EntityDef:
        self._expect(TokenKind.LBRACE, "Expected '{' to start entity body")
        fields: List[FieldDef] = []
        while True:
            self._skip_newlines()
            tok = self._peek()
            if tok.kind == TokenKind.RBRACE:
                self._advance()
                break
            if tok.kind == TokenKind.EOF:
                raise ADLParseError(
                    f"Unterminated entity '{name}' starting at line {tok.line} column {tok.column}"
                )

            field_annotations = self._parse_leading_annotations()
            self._skip_newlines()

            field_name_tok = self._expect(TokenKind.IDENT, "Expected field name")
            field_type_tok = self._expect(TokenKind.IDENT, "Expected field type")

            validators: List[Validator] = []
            while True:
                tok = self._peek()
                if tok.kind in {TokenKind.NEWLINE, TokenKind.RBRACE, TokenKind.EOF}:
                    break
                if tok.kind == TokenKind.SEMICOLON:
                    self._advance()
                    break
                if tok.kind == TokenKind.COMMA:
                    self._advance()
                    continue
                if tok.kind != TokenKind.IDENT:
                    raise ADLParseError(
                        f"Expected validator or end-of-line after field '{field_name_tok.value}' at line {tok.line} column {tok.column}"
                    )
                validators.append(self._parse_validator())

            fields.append(
                FieldDef(
                    name=field_name_tok.value,
                    type=field_type_tok.value,
                    validators=validators,
                    annotations=field_annotations,
                )
            )
        return EntityDef(name=name, fields=fields, annotations=annotations)

    def _parse_relationship_end(self) -> RelationshipEnd:
        entity_tok = self._expect(TokenKind.IDENT, "Expected entity name")
        field_name: Optional[str] = None
        if self._accept(TokenKind.LBRACE):
            self._skip_newlines()
            field_tok = self._expect(
                TokenKind.IDENT, "Expected relationship field name"
            )
            self._skip_newlines()
            self._expect(TokenKind.RBRACE, "Expected '}' after relationship field")
            field_name = field_tok.value
        return RelationshipEnd(entity=entity_tok.value, field=field_name)

    def _parse_relationship_body(
        self, kind: str, annotations: List[Annotation]
    ) -> List[RelationshipDef]:
        self._expect(TokenKind.LBRACE, "Expected '{' to start relationship body")
        rels: List[RelationshipDef] = []
        while True:
            self._skip_newlines()
            tok = self._peek()
            if tok.kind == TokenKind.RBRACE:
                self._advance()
                break
            if tok.kind == TokenKind.EOF:
                raise ADLParseError(
                    f"Unterminated relationship '{kind}' starting at line {tok.line} column {tok.column}"
                )

            line_annotations = self._parse_leading_annotations()
            self._skip_newlines()

            from_end = self._parse_relationship_end()

            to_kw = self._expect(TokenKind.IDENT, "Expected 'to' in relationship")
            if to_kw.value.lower() != "to":
                raise ADLParseError(
                    f"Expected 'to' in relationship at line {to_kw.line} column {to_kw.column}"
                )

            to_end = self._parse_relationship_end()

            options: List[str] = []
            while True:
                tok = self._peek()
                if tok.kind in {TokenKind.NEWLINE, TokenKind.RBRACE, TokenKind.EOF}:
                    break
                if tok.kind == TokenKind.COMMA:
                    self._advance()
                    continue
                if tok.kind == TokenKind.SEMICOLON:
                    self._advance()
                    break
                if tok.kind != TokenKind.IDENT:
                    raise ADLParseError(
                        f"Unexpected token in relationship '{kind}' at line {tok.line} column {tok.column}"
                    )
                options.append(self._advance().value)

            rels.append(
                RelationshipDef(
                    kind=kind,
                    from_end=from_end,
                    to_end=to_end,
                    options=options,
                    annotations=line_annotations,
                )
            )

        # Relationship-level annotations are applied to each relationship line
        if annotations:
            for r in rels:
                r.annotations = list(annotations) + list(r.annotations)

        return rels

    # ---- JDL-style directives ----

    def _parse_directive(self) -> tuple:
        """Parse ``<targets> with <impl>`` used by paginate/dto/service.

        Returns (entity_list, impl_string).
        """
        entities: List[str] = []
        while True:
            tok = self._peek()
            if tok.kind != TokenKind.IDENT:
                raise ADLParseError(
                    f"Expected entity name or '*' in directive at line {tok.line} column {tok.column}"
                )
            if tok.value.lower() == "with":
                break
            entities.append(self._advance().value)
            self._skip_newlines()
            self._accept(TokenKind.COMMA)
            self._skip_newlines()

        # consume 'with'
        self._expect(TokenKind.IDENT, "Expected 'with' in directive")
        impl_tok = self._expect(TokenKind.IDENT, "Expected implementation name")
        return (entities, impl_tok.value)

    # ---- top-level ----

    def parse(self) -> ADLConfig:
        cfg = ADLConfig()
        while True:
            self._skip_newlines()
            tok = self._peek()
            if tok.kind == TokenKind.EOF:
                break

            annotations = self._parse_leading_annotations()
            self._skip_newlines()

            tok = self._peek()
            if tok.kind == TokenKind.EOF:
                break
            if tok.kind != TokenKind.IDENT:
                raise ADLParseError(
                    f"Expected top-level keyword at line {tok.line} column {tok.column}"
                )

            keyword = self._advance().value
            keyword_lower = keyword.lower()

            if keyword_lower == "enum":
                enum_name = self._expect(TokenKind.IDENT, "enum requires a name").value
                enum_def = self._parse_enum_body(enum_name, annotations)
                cfg.enums[enum_name] = enum_def
                continue

            if keyword_lower == "entity":
                entity_name = self._expect(
                    TokenKind.IDENT, "entity requires a name"
                ).value
                entity_def = self._parse_entity_body(entity_name, annotations)
                cfg.entities[entity_name] = entity_def
                continue

            if keyword_lower == "relationship":
                rel_kind = self._expect(
                    TokenKind.IDENT, "relationship requires a kind"
                ).value
                rels = self._parse_relationship_body(rel_kind, annotations)
                cfg.relationships.extend(rels)
                continue

            # JDL-style directives: paginate/dto/service <targets> with <impl>
            if keyword_lower == "paginate":
                directive = self._parse_directive()
                cfg.paginations.append(
                    PaginationDef(entities=directive[0], style=directive[1])
                )
                continue

            if keyword_lower == "dto":
                directive = self._parse_directive()
                cfg.dtos.append(DtoDef(entities=directive[0], mapper=directive[1]))
                continue

            if keyword_lower == "service":
                # Peek ahead: if next is LBRACE or an IDENT followed by LBRACE,
                # it's a block (not a directive).  Directives have "... with ..."
                saved = self.index
                is_directive = False
                try:
                    while self._peek().kind == TokenKind.IDENT:
                        if self._peek().value.lower() == "with":
                            is_directive = True
                            break
                        self._advance()
                        self._accept(TokenKind.COMMA)
                except ADLParseError:
                    pass
                self.index = saved  # rewind

                if is_directive:
                    directive = self._parse_directive()
                    cfg.services.append(
                        ServiceDef(entities=directive[0], impl=directive[1])
                    )
                    continue

            # Optional name for most blocks except global blocks.
            name: Optional[str] = None
            if keyword_lower not in {"security", "modes", "deployment"}:
                next_tok = self._peek()
                if next_tok.kind == TokenKind.IDENT:
                    name = self._advance().value

            block = self._parse_kv_block_body(name, annotations)
            cfg.raw_blocks.append(block)

            if keyword_lower == "application":
                cfg.application = block
            elif keyword_lower == "llm":
                if not name:
                    raise ADLParseError("llm block requires a name")
                cfg.llms[name] = block
            elif keyword_lower == "rag":
                if not name:
                    raise ADLParseError("rag block requires a name")
                cfg.rags[name] = block
            elif keyword_lower == "voice":
                if not name:
                    raise ADLParseError("voice block requires a name")
                cfg.voices[name] = block
            elif keyword_lower == "api":
                if not name:
                    raise ADLParseError("api block requires a name")
                cfg.apis[name] = block
            elif keyword_lower == "security":
                cfg.security = block
            elif keyword_lower == "modes":
                cfg.modes = block
            elif keyword_lower == "deployment":
                cfg.deployment = block
            else:
                # Unknown top-level keyword: keep in raw_blocks only
                continue

        return cfg


def parse_adl(text: str) -> ADLConfig:
    """Parse ADL source text into :class:`ADLConfig`.

    This function applies sensible defaults and validates the resulting
    configuration so that minimal ADL "just works".

    Raises :class:`ADLParseError` on invalid syntax and :class:`ADLValidationError`
    on invalid configuration values.
    """

    lexer = Lexer(text)
    tokens = lexer.tokens()
    parser = Parser(tokens)
    cfg = parser.parse()
    cfg = apply_defaults(cfg)
    validate_config(cfg)
    return cfg


# Alias for clarity in installer
parse_adl_string = parse_adl


def parse_adl_file(path: str | Path) -> ADLConfig:
    """Parse an ADL file from disk."""

    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_adl(text)
