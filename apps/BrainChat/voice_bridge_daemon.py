#!/usr/bin/env python3
"""Fallback BrainChat voice bridge daemon."""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import hashlib
import json
import os
import struct
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

COPILOT_PATH = "/Users/joe/.local/bin/copilot"
COPILOT_CWD = "/Users/joe/brain"
CODING_KEYWORDS = {
    "code", "swift", "python", "javascript", "typescript", "java", "kotlin",
    "rust", "golang", "go ", "fix", "debug", "refactor", "function", "class",
    "method", "compile", "build", "test", "cli", "shell", "script", "api",
    "endpoint", "regex", "sql", "database", "websocket",
}


class BridgeError(RuntimeError):
    pass


@dataclass
class VoiceBridgeRequest:
    id: str
    message: str
    history: list[dict[str, Any]]
    systemPrompt: str
    preferredTarget: str = "auto"
    yolo: bool = False
    claudeAPIKey: str = ""
    claudeModel: str = "claude-sonnet-4-20250514"
    openAIAPIKey: str = ""
    openAIModel: str = "gpt-4o"
    ollamaEndpoint: str = "http://localhost:11434/api/chat"
    ollamaModel: str = "llama3.2:3b"


def cleaned_prompt(message: str) -> str:
    trimmed = message.strip()
    for command in ("/yolo", "/copilot", "/claude", "/gpt", "/ollama"):
        if trimmed.lower().startswith(command):
            remainder = trimmed[len(command):].strip()
            return remainder or trimmed
    return trimmed


def contains_coding_intent(message: str) -> bool:
    return any(keyword in message for keyword in CODING_KEYWORDS)


def resolve_route(request: VoiceBridgeRequest) -> str:
    lower = request.message.strip().lower()
    if request.yolo or lower.startswith("/yolo"):
        return "copilot"
    if lower.startswith("/copilot"):
        return "copilot"
    if lower.startswith("/claude"):
        return "claude"
    if lower.startswith("/gpt") or "chatgpt" in lower or "openai" in lower:
        return "gpt"
    if lower.startswith("/ollama"):
        return "ollama"
    if contains_coding_intent(lower):
        return "copilot"
    if request.preferredTarget != "auto":
        return request.preferredTarget
    return "claude" if request.claudeAPIKey else "ollama"


def routes_to_try(primary: str, request: VoiceBridgeRequest) -> list[str]:
    if primary == "claude" and not request.claudeAPIKey:
        return ["ollama"]
    if primary == "gpt" and not request.openAIAPIKey:
        return ["ollama"]
    if primary == "ollama":
        return ["ollama"]
    return list(dict.fromkeys([primary, "ollama"]))


def provider_name(route: str, request: VoiceBridgeRequest) -> str:
    if route == "copilot":
        return "GitHub Copilot CLI /yolo" if request.yolo else "GitHub Copilot CLI"
    if route == "claude":
        return request.claudeModel
    if route == "gpt":
        return request.openAIModel
    return request.ollamaModel


def call_copilot(prompt: str, yolo: bool) -> str:
    if not os.path.exists(COPILOT_PATH):
        raise BridgeError(f"Copilot CLI not found at {COPILOT_PATH}")

    args = [COPILOT_PATH, "-p", prompt, "--output-format", "text"]
    if yolo:
        args.extend(["--yolo", "--autopilot", "--max-autopilot-continues", "6"])
    else:
        args.append("--allow-all")

    env = os.environ.copy()
    extra_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/Users/joe/.local/bin"]
    env["PATH"] = ":".join(extra_paths + [env.get("PATH", "/usr/bin:/bin")])

    completed = subprocess.run(
        args,
        cwd=COPILOT_CWD,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise BridgeError(completed.stderr.strip() or "Copilot CLI failed")

    output = completed.stdout.strip()
    if not output:
        raise BridgeError("Copilot CLI returned an empty response")
    return output


def http_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    for key, value in headers.items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise BridgeError(exc.read().decode("utf-8", errors="replace") or f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise BridgeError(str(exc.reason)) from exc


def anthropic_messages(history: list[dict[str, Any]], fallback_prompt: str) -> list[dict[str, Any]]:
    cleaned = [item for item in history if item.get("role") != "system"]
    if not cleaned:
        cleaned = [{"role": "user", "content": fallback_prompt}]
    return [
        {
            "role": item["role"],
            "content": [{"type": "text", "text": item["content"]}],
        }
        for item in cleaned
    ]


def openai_messages(system_prompt: str, history: list[dict[str, Any]], fallback_prompt: str) -> list[dict[str, str]]:
    cleaned = [item for item in history if item.get("role") != "system"]
    if not cleaned:
        cleaned = [{"role": "user", "content": fallback_prompt}]
    return [{"role": "system", "content": system_prompt}] + [
        {"role": item["role"], "content": item["content"]}
        for item in cleaned
    ]


def call_claude(prompt: str, request: VoiceBridgeRequest) -> str:
    if not request.claudeAPIKey:
        raise BridgeError("Claude API key is missing")
    data = http_json(
        "https://api.anthropic.com/v1/messages",
        {
            "Content-Type": "application/json",
            "x-api-key": request.claudeAPIKey,
            "anthropic-version": "2023-06-01",
        },
        {
            "model": request.claudeModel,
            "max_tokens": 1024,
            "system": request.systemPrompt,
            "messages": anthropic_messages(request.history, prompt),
        },
    )
    text = "".join(item.get("text", "") for item in data.get("content", []) if isinstance(item, dict)).strip()
    if not text:
        raise BridgeError("Claude returned an empty response")
    return text


def call_gpt(prompt: str, request: VoiceBridgeRequest) -> str:
    if not request.openAIAPIKey:
        raise BridgeError("OpenAI API key is missing")
    data = http_json(
        "https://api.openai.com/v1/chat/completions",
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.openAIAPIKey}",
        },
        {
            "model": request.openAIModel,
            "messages": openai_messages(request.systemPrompt, request.history, prompt),
            "max_tokens": 1024,
        },
    )
    choices = data.get("choices", [])
    text = ""
    if choices and isinstance(choices[0], dict):
        text = choices[0].get("message", {}).get("content", "").strip()
    if not text:
        raise BridgeError("GPT returned an empty response")
    return text


def call_ollama(prompt: str, request: VoiceBridgeRequest) -> str:
    data = http_json(
        request.ollamaEndpoint,
        {"Content-Type": "application/json"},
        {
            "model": request.ollamaModel,
            "messages": openai_messages(request.systemPrompt, request.history, prompt),
            "stream": False,
        },
    )
    text = data.get("message", {}).get("content", "").strip()
    if not text:
        raise BridgeError("Ollama returned an empty response")
    return text


async def route_request(request_dict: dict[str, Any]) -> dict[str, Any]:
    request = VoiceBridgeRequest(**request_dict)
    started_at = time.time()
    primary = resolve_route(request)
    prompt = cleaned_prompt(request.message)
    last_error: str | None = None

    for route in routes_to_try(primary, request):
        try:
            if route == "copilot":
                reply = await asyncio.to_thread(call_copilot, prompt, request.yolo)
            elif route == "claude":
                reply = await asyncio.to_thread(call_claude, prompt, request)
            elif route == "gpt":
                reply = await asyncio.to_thread(call_gpt, prompt, request)
            else:
                reply = await asyncio.to_thread(call_ollama, prompt, request)

            return {
                "id": request.id,
                "success": True,
                "route": route,
                "provider": provider_name(route, request),
                "reply": reply,
                "mode": "yolo" if request.yolo else "standard",
                "duration": time.time() - started_at,
                "error": last_error,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    return {
        "id": request.id,
        "success": False,
        "route": "ollama",
        "provider": provider_name("ollama", request),
        "reply": f"Sorry, the voice bridge could not get a response. {last_error or 'No backend was available.'}",
        "mode": "yolo" if request.yolo else "standard",
        "duration": time.time() - started_at,
        "error": last_error,
    }


def websocket_accept(key: str) -> str:
    magic = key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1(magic.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


async def read_http_request(reader: asyncio.StreamReader) -> str:
    data = await reader.readuntil(b"\r\n\r\n")
    return data.decode("utf-8", errors="replace")


async def send_frame(writer: asyncio.StreamWriter, payload: bytes, opcode: int = 0x1) -> None:
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    writer.write(bytes(header) + payload)
    await writer.drain()


async def read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    first_two = await reader.readexactly(2)
    opcode = first_two[0] & 0x0F
    masked = (first_two[1] & 0x80) != 0
    length = first_two[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]

    mask = await reader.readexactly(4) if masked else b""
    payload = bytearray(await reader.readexactly(length))
    if masked:
        for index in range(length):
            payload[index] ^= mask[index % 4]
    return opcode, bytes(payload)


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request = await read_http_request(reader)
        key = None
        for line in request.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
                break
        if not key:
            writer.close()
            await writer.wait_closed()
            return

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {websocket_accept(key)}\r\n\r\n"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()

        while True:
            opcode, payload = await read_frame(reader)
            if opcode == 0x8:
                await send_frame(writer, b"", opcode=0x8)
                break
            if opcode == 0x9:
                await send_frame(writer, payload, opcode=0xA)
                continue
            if opcode != 0x1:
                continue

            request_dict = json.loads(payload.decode("utf-8"))
            response_dict = await route_request(request_dict)
            await send_frame(writer, json.dumps(response_dict).encode("utf-8"))
    except asyncio.IncompleteReadError:
        pass
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


async def run_server(host: str, port: int) -> None:
    server = await asyncio.start_server(handle_client, host, port)
    print(f"Voice bridge daemon listening on {host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BrainChat fallback voice bridge daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    asyncio.run(run_server(args.host, args.port))
