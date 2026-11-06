"""RadvinSPlus Docs Bot — تک‌فایل: کتابخانه radvinsplus + بات مستندات.

توکن را در TOKEN بگذار.
"""
from __future__ import annotations


# ============================================================
# ---- radvinsplus/exceptions.py ----
# ============================================================
"""Exception hierarchy for radvinsplus."""


class RadvinsPlusError(Exception):
    """Base exception for all radvinsplus errors."""


class ConfigurationError(RadvinsPlusError, ValueError):
    """Raised when the client configuration is invalid."""


class NetworkError(RadvinsPlusError):
    """Raised when an HTTP request cannot reach the Soroush Plus API."""

    def __init__(self, message, *, method=None, cause=None):
        super().__init__(message)
        self.method = method
        self.cause = cause


class APIError(RadvinsPlusError):
    """An error returned by the Soroush Plus Bot API."""

    def __init__(self, description, *, error_code=None, method=None, parameters=None, response=None):
        self.description = str(description or "Unknown API error")
        self.error_code = error_code
        self.method = method
        self.parameters = parameters or {}
        self.response = response or {}
        self.retry_after = self.parameters.get("retry_after")
        prefix = f"{method}: " if method else ""
        code = f" [HTTP/API {error_code}]" if error_code is not None else ""
        super().__init__(f"{prefix}{self.description}{code}")

# ============================================================
# ---- radvinsplus/filters.py ----
# ============================================================
"""Composable update filters."""

import re


def _message(update):
    return update.get("message") or update.get("edited_message") or {}


class Filter:
    def __init__(self, function, name="custom"):
        self.function = function
        self.name = name

    def __call__(self, update):
        try:
            return bool(self.function(update))
        except Exception:
            return False

    def __and__(self, other):
        other = as_filter(other)
        return Filter(lambda u: self(u) and other(u), f"({self.name}&{other.name})")

    def __or__(self, other):
        other = as_filter(other)
        return Filter(lambda u: self(u) or other(u), f"({self.name}|{other.name})")

    def __invert__(self):
        return Filter(lambda u: not self(u), f"~{self.name}")

    def __repr__(self):
        return f"Filter({self.name})"


def as_filter(value):
    if value is None:
        return Filter(lambda _: True, "all")
    if isinstance(value, Filter):
        return value
    if callable(value):
        return Filter(value, getattr(value, "__name__", "custom"))
    raise TypeError("filters must be Filter objects or callables")


class Filters:
    """Ready-made filters; combine them with ``&``, ``|`` and ``~``."""

    all = Filter(lambda _: True, "all")
    text = Filter(lambda u: isinstance(_message(u).get("text"), str), "text")
    photo = Filter(lambda u: bool(_message(u).get("photo")), "photo")
    video = Filter(lambda u: bool(_message(u).get("video")), "video")
    audio = Filter(lambda u: bool(_message(u).get("audio")), "audio")
    document = Filter(lambda u: bool(_message(u).get("document")), "document")
    contact = Filter(lambda u: bool(_message(u).get("contact")), "contact")
    location = Filter(lambda u: bool(_message(u).get("location")), "location")
    sticker = Filter(lambda u: bool(_message(u).get("sticker")), "sticker")
    private = Filter(lambda u: (_message(u).get("chat") or {}).get("type") == "private", "private")
    group = Filter(lambda u: (_message(u).get("chat") or {}).get("type") in ("group", "supergroup"), "group")
    channel = Filter(lambda u: (_message(u).get("chat") or {}).get("type") == "channel", "channel")
    callback_query = Filter(lambda u: bool(u.get("callback_query")), "callback_query")
    edited = Filter(lambda u: bool(u.get("edited_message")), "edited")

    @staticmethod
    def regex(pattern, flags=0, *, field="text"):
        compiled = re.compile(pattern, flags)
        return Filter(lambda u: bool(compiled.search(str(_message(u).get(field, "")))), f"regex:{pattern}")

    @staticmethod
    def startswith(prefix, *, field="text"):
        return Filter(lambda u: str(_message(u).get(field, "")).startswith(prefix), f"startswith:{prefix}")

    @staticmethod
    def custom(function):
        return as_filter(function)

# ============================================================
# ---- radvinsplus/keyboards.py ----
# ============================================================
"""Small, chainable keyboard builders."""


class InlineButton:
    @staticmethod
    def callback(text, data):
        if not isinstance(data, str) or not data:
            raise ValueError("callback data must be a non-empty string")
        if len(data.encode("utf-8")) > 64:
            raise ValueError("callback data must be at most 64 bytes")
        return {"text": str(text), "callback_data": data}

    @staticmethod
    def url(text, url):
        return {"text": str(text), "url": str(url)}


class InlineKeyboard:
    """Build an InlineKeyboardMarkup object.

    Example::

        keyboard = (InlineKeyboard()
                    .row(InlineButton.callback("شروع", "start"),
                         InlineButton.url("وب‌سایت", "https://example.com"))
                    .row(InlineButton.callback("راهنما", "help")))
        bot.send_message(chat_id, "سلام", reply_markup=keyboard)
    """

    def __init__(self):
        self.inline_keyboard = []

    def row(self, *buttons):
        if not buttons:
            raise ValueError("a keyboard row cannot be empty")
        row = []
        for button in buttons:
            if not isinstance(button, dict) or "text" not in button:
                raise TypeError("each inline button must be a dict with a text field")
            if sum(k in button for k in ("url", "callback_data")) != 1:
                raise ValueError("each inline button needs exactly one of url or callback_data")
            row.append(dict(button))
        self.inline_keyboard.append(row)
        return self

    def add(self, text, *, callback_data=None, url=None):
        if (callback_data is None) == (url is None):
            raise ValueError("provide exactly one of callback_data or url")
        button = InlineButton.callback(text, callback_data) if callback_data is not None else InlineButton.url(text, url)
        if not self.inline_keyboard:
            self.inline_keyboard.append([])
        self.inline_keyboard[-1].append(button)
        return self

    def build(self):
        return {"inline_keyboard": [list(row) for row in self.inline_keyboard]}

    def to_dict(self):
        return self.build()


class ReplyKeyboard:
    """Build a ReplyKeyboardMarkup object."""

    def __init__(self, *, resize=True, one_time=False, placeholder=None):
        self.keyboard = []
        self.resize_keyboard = bool(resize)
        self.one_time_keyboard = bool(one_time)
        self.input_field_placeholder = placeholder

    def row(self, *buttons):
        if not buttons:
            raise ValueError("a keyboard row cannot be empty")
        self.keyboard.append([b if isinstance(b, str) else dict(b) for b in buttons])
        return self

    def add(self, text, *, request_contact=False, request_location=False):
        if request_contact and request_location:
            raise ValueError("a button cannot request contact and location together")
        button = {"text": str(text)}
        if request_contact:
            button["request_contact"] = True
        if request_location:
            button["request_location"] = True
        if not self.keyboard:
            self.keyboard.append([])
        self.keyboard[-1].append(button if len(button) > 1 else str(text))
        return self

    def build(self):
        result = {
            "keyboard": [list(row) for row in self.keyboard],
            "resize_keyboard": self.resize_keyboard,
            "one_time_keyboard": self.one_time_keyboard,
        }
        if self.input_field_placeholder is not None:
            result["input_field_placeholder"] = self.input_field_placeholder
        return result

    def to_dict(self):
        return self.build()


def remove_keyboard():
    """Return the payload that removes the current reply keyboard."""
    return {"remove_keyboard": True}

# ============================================================
# ---- radvinsplus/files.py ----
# ============================================================
"""File and media helpers. No third-party packages are required."""


import mimetypes
import os
from pathlib import Path
from typing import Any, BinaryIO


class InputFile:
    """Wrap a local file, bytes, or binary file object for a Bot API upload.

    Examples::

        InputFile("photo.jpg")
        InputFile.from_bytes(b"...", filename="photo.jpg")
        InputFile.from_file(open("photo.jpg", "rb"), filename="photo.jpg")

    A file object passed to this class remains owned by the caller and is not closed.
    """

    def __init__(self, source: Any, filename: str | None = None, content_type: str | None = None):
        self.source = source
        self.filename = filename
        self.content_type = content_type

    @classmethod
    def from_bytes(cls, data: bytes, filename: str = "upload.bin", content_type: str | None = None):
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        return cls(bytes(data), filename=filename, content_type=content_type)

    @classmethod
    def from_file(cls, fileobj: BinaryIO, filename: str | None = None, content_type: str | None = None):
        return cls(fileobj, filename=filename, content_type=content_type)

    def read(self) -> tuple[str, str, bytes]:
        source = self.source
        if isinstance(source, (str, os.PathLike, Path)):
            path = Path(source)
            data = path.read_bytes()
            filename = self.filename or path.name
        elif isinstance(source, (bytes, bytearray, memoryview)):
            data = bytes(source)
            filename = self.filename or "upload.bin"
        elif hasattr(source, "read"):
            stream = source
            filename = self.filename or os.path.basename(getattr(stream, "name", "upload.bin"))
            try:
                position = stream.tell()
            except (AttributeError, OSError):
                position = None
            data = stream.read()
            if position is not None:
                try:
                    stream.seek(position)
                except (AttributeError, OSError):
                    pass
            if not isinstance(data, (bytes, bytearray, memoryview)):
                raise TypeError("InputFile requires a binary file object")
            data = bytes(data)
        else:
            raise TypeError("InputFile source must be a path, bytes, or binary file object")

        content_type = self.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return filename, content_type, data


class InputMedia(dict):
    """Dictionary-like helper for sendMediaGroup and editMessageMedia."""

    @classmethod
    def photo(cls, media, *, caption=None, parse_mode=None, **kwargs):
        return cls._make("photo", media, caption=caption, parse_mode=parse_mode, **kwargs)

    @classmethod
    def live_photo(cls, media, *, caption=None, parse_mode=None, **kwargs):
        return cls._make("live_photo", media, caption=caption, parse_mode=parse_mode, **kwargs)

    @classmethod
    def video(cls, media, *, caption=None, parse_mode=None, **kwargs):
        return cls._make("video", media, caption=caption, parse_mode=parse_mode, **kwargs)

    @classmethod
    def audio(cls, media, *, caption=None, parse_mode=None, **kwargs):
        return cls._make("audio", media, caption=caption, parse_mode=parse_mode, **kwargs)

    @classmethod
    def document(cls, media, *, caption=None, parse_mode=None, **kwargs):
        return cls._make("document", media, caption=caption, parse_mode=parse_mode, **kwargs)

    @classmethod
    def animation(cls, media, *, caption=None, parse_mode=None, **kwargs):
        return cls._make("animation", media, caption=caption, parse_mode=parse_mode, **kwargs)

    @classmethod
    def _make(cls, kind, media, *, caption=None, parse_mode=None, **kwargs):
        payload = {"type": kind, "media": media}
        if caption is not None:
            payload["caption"] = caption
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        return cls(payload)

# ============================================================
# ---- radvinsplus/client.py ----
# ============================================================
"""Dependency-free Soroush Plus Bot API client."""


import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


DEFAULT_API_URL = "https://api.splus.ir"
API_METHODS = (
    "getMe", "logOut", "close", "sendMessage", "forwardMessage", "copyMessage",
    "sendPhoto", "sendAudio", "sendDocument", "sendVideo", "sendAnimation",
    "sendVoice", "sendVideoNote", "sendMediaGroup", "sendLocation", "sendContact",
    "sendChatAction", "getUserProfilePhotos", "getFile", "pinChatMessage",
    "unpinChatMessage", "getChat", "answerCallbackQuery", "setMyCommands",
    "deleteMyCommands", "getMyCommands", "editMessageText", "editMessageCaption",
    "editMessageMedia", "editMessageReplyMarkup", "deleteMessage", "sendSticker",
    "getStickerSet", "getUpdates", "setWebhook", "deleteWebhook", "getWebhookInfo",
)


def _snake_to_api(name: str) -> str:
    if "_" not in name:
        return name
    parts = [part for part in name.split("_") if part]
    if not parts:
        return name
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _jsonable(value):
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    return value


def _encode_form_value(value):
    value = _jsonable(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _collect_uploads(value, path, uploads):
    """Replace nested InputFile values with attach:// references."""
    if isinstance(value, InputFile):
        field_name = path[0] if len(path) == 1 else "_".join(str(p) for p in path)
        filename, content_type, data = value.read()
        uploads[field_name] = (filename, content_type, data)
        # Top-level file parameters are represented by the multipart file field itself.
        return None if len(path) == 1 else f"attach://{field_name}"
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    if isinstance(value, dict):
        return {str(k): _collect_uploads(v, path + [str(k)], uploads) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_collect_uploads(v, path + [str(i)], uploads) for i, v in enumerate(value)]
    return _jsonable(value)


def _multipart_body(params, uploads):
    boundary = "----radvinsplus-" + uuid.uuid4().hex
    chunks = []
    for key, value in params.items():
        if value is None:
            continue
        safe_key = str(key).replace('"', "")
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{safe_key}"\r\n'.encode())
        chunks.append(b"Content-Type: text/plain; charset=utf-8\r\n\r\n")
        if isinstance(value, (dict, list)):
            content = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            content = _encode_form_value(value)
        chunks.append(content.encode("utf-8"))
        chunks.append(b"\r\n")
    for field_name, (filename, content_type, data) in uploads.items():
        safe_field = str(field_name).replace('"', "")
        safe_filename = os.path.basename(str(filename)).replace('"', "")
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{safe_field}"; filename="{safe_filename}"\r\n'.encode())
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(chunks)


class Client:
    """Low-level Bot API client.

    Runtime dependencies: Python standard library only.
    """

    def __init__(self, token, *, api_url=DEFAULT_API_URL, timeout=30, max_retries=2,
                 retry_after=True, user_agent="radvinsplus/1.0.0", default_http_method="POST"):
        if not isinstance(token, str) or not token.strip():
            raise ConfigurationError("A non-empty bot token is required")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ConfigurationError("timeout must be a positive number")
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ConfigurationError("max_retries must be a non-negative integer")
        self._token = token.strip()
        self.api_url = api_url.rstrip("/")
        self.timeout = float(timeout)
        self.max_retries = max_retries
        self.retry_after = bool(retry_after)
        self.user_agent = user_agent
        self.default_http_method = default_http_method.upper()
        self._last_response = None

    def __repr__(self):
        return f"{self.__class__.__name__}(token='***', api_url={self.api_url!r})"

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        api_method = _snake_to_api(name)
        if api_method not in API_METHODS and api_method[:1].islower():
            # Permit forward-compatible API calls, including methods added by Soroush Plus later.
            pass

        def method(*args, **kwargs):
            if args:
                raise TypeError(f"{name} accepts keyword arguments only; use {name}(key=value)")
            return self.call(api_method, **kwargs)
        method.__name__ = name
        method.__doc__ = f"Call the Soroush Plus {api_method} API method."
        return method

    def call(self, method, params=None, *, http_method=None, **kwargs):
        """Call any Bot API method; snake_case and API camelCase are both accepted."""
        if not isinstance(method, str) or not method.strip():
            raise ValueError("method must be a non-empty string")
        api_method = _snake_to_api(method.strip())
        payload = dict(params or {})
        payload.update(kwargs)
        return self._request(api_method, payload, http_method=http_method)

    def _request(self, method, params, *, http_method=None):
        verb = (http_method or self.default_http_method).upper()
        if verb not in ("GET", "POST"):
            raise ValueError("http_method must be GET or POST")

        uploads = {}
        cleaned = {}
        for key, value in params.items():
            cleaned[key] = _collect_uploads(value, [str(key)], uploads)
        cleaned = {k: v for k, v in cleaned.items() if v is not None}
        url = f"{self.api_url}/bot{self._token}/{method}"

        if verb == "GET" and uploads:
            raise ValueError("InputFile uploads require POST")
        if verb == "GET":
            query = {k: _encode_form_value(v) for k, v in cleaned.items()}
            request_url = url + (("?" + urllib.parse.urlencode(query)) if query else "")
            data = None
            headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        elif uploads:
            boundary, data = _multipart_body(cleaned, uploads)
            request_url = url
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            }
        else:
            request_url = url
            data = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            }

        attempts = 0
        request_timeout = max(self.timeout, float(params.get("timeout", 0) or 0) + 5) if method.lower() == "getupdates" else self.timeout
        while True:
            request = urllib.request.Request(request_url, data=data, headers=headers, method=verb)
            try:
                with urllib.request.urlopen(request, timeout=request_timeout) as response:
                    raw = response.read()
                    status = response.status
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                status = exc.code
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise NetworkError(f"Could not connect to Soroush Plus API: {exc}", method=method, cause=exc) from exc

            try:
                decoded = raw.decode("utf-8")
                result = json.loads(decoded) if decoded else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise NetworkError(f"API returned an invalid JSON response (HTTP {status})", method=method, cause=exc) from exc
            self._last_response = result

            if not isinstance(result, dict):
                raise NetworkError("API returned an unexpected response format", method=method)
            ok = result.get("ok", result.get("OK"))
            if ok is True:
                return result.get("result")
            if ok is False or status >= 400:
                parameters = result.get("parameters") or result.get("پارامترها") or {}
                error = APIError(result.get("description") or result.get("Description") or f"Request failed with HTTP {status}",
                                 error_code=result.get("error_code", status), method=method,
                                 parameters=parameters if isinstance(parameters, dict) else {}, response=result)
                if (self.retry_after and error.error_code == 429 and attempts < self.max_retries
                        and isinstance(error.retry_after, (int, float))):
                    attempts += 1
                    time.sleep(max(0, min(float(error.retry_after), 60)) + random.uniform(0, 0.15))
                    continue
                raise error
            raise NetworkError("API response did not contain an 'ok' status", method=method)

    def download_file(self, file_id_or_path, destination=None):
        """Download a file by file_id or file_path.

        Returns bytes when destination is omitted; otherwise writes the file and
        returns the resulting pathlib.Path. The API documentation currently states
        a 20 MB bot download limit.
        """
        value = str(file_id_or_path)
        if "/" not in value and not value.startswith("."):
            file_info = self.get_file(file_id=value)
            file_path = file_info.get("file_path")
            if not file_path:
                raise APIError("getFile response did not include file_path", method="getFile", response=file_info)
        else:
            file_path = value.lstrip("/")
        url = f"{self.api_url}/file/bot{self._token}/{file_path}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read(20 * 1024 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise NetworkError(f"Could not download file: {exc}", method="getFile", cause=exc) from exc
        if len(data) > 20 * 1024 * 1024:
            raise NetworkError("Downloaded file exceeds the documented 20 MB limit", method="getFile")
        if destination is None:
            return data
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def download_file_path(self, file_path, destination=None):
        """Download directly from a previously obtained API ``file_path``."""
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("file_path must be a non-empty string")
        url = f"{self.api_url}/file/bot{self._token}/{file_path.lstrip('/')}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read(20 * 1024 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise NetworkError(f"Could not download file: {exc}", method="getFile", cause=exc) from exc
        if len(data) > 20 * 1024 * 1024:
            raise NetworkError("Downloaded file exceeds the documented 20 MB limit", method="getFile")
        if destination is None:
            return data
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def get_download_url(self, file_id):
        """Get a temporary download URL for a file_id (valid at least one hour per docs)."""
        info = self.get_file(file_id=file_id)
        if not info or not info.get("file_path"):
            raise APIError("getFile response did not include file_path", method="getFile", response=info or {})
        return f"{self.api_url}/file/bot{self._token}/{info['file_path']}"

# ============================================================
# ---- radvinsplus/bot.py ----
# ============================================================
"""High-level event handlers, polling, contexts, and webhook server."""


import json
import logging
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


logger = logging.getLogger("radvinsplus")


@dataclass
class Handler:
    kind: str
    callback: object
    filter: object = None
    commands: frozenset | None = None


class Context:
    """Convenience wrapper passed to every registered handler."""

    def __init__(self, bot, update):
        self.bot = bot
        self.update = update
        self.message = update.get("message") or update.get("edited_message")
        self.edited_message = update.get("edited_message")
        self.callback_query = update.get("callback_query")
        self.callback_message = (self.callback_query or {}).get("message") if self.callback_query else None
        self.effective_message = self.message or self.callback_message or {}
        self.chat = self.effective_message.get("chat") or {}
        self.from_user = ((self.callback_query or {}).get("from") or
                          (self.message or {}).get("from") or
                          (self.edited_message or {}).get("from") or {})
        self.text = self.effective_message.get("text", "") or ""
        self.command = None
        self.args = []
        self._callback_answered = False
        self._parse_command()

    def _parse_command(self):
        if not self.text.startswith("/"):
            return
        first, *rest = self.text.split(maxsplit=1)
        self.command = first[1:].split("@", 1)[0].lower()
        self.args = rest[0].split() if rest else []

    @property
    def chat_id(self):
        return self.chat.get("id")

    @property
    def user_id(self):
        return self.from_user.get("id")

    @property
    def message_id(self):
        return self.effective_message.get("message_id")

    def reply(self, text, **kwargs):
        if self.chat_id is None:
            raise ValueError("This update does not contain a chat_id")
        return self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

    answer = reply

    def reply_photo(self, photo, **kwargs):
        if self.chat_id is None:
            raise ValueError("This update does not contain a chat_id")
        return self.bot.send_photo(chat_id=self.chat_id, photo=photo, **kwargs)

    def reply_document(self, document, **kwargs):
        if self.chat_id is None:
            raise ValueError("This update does not contain a chat_id")
        return self.bot.send_document(chat_id=self.chat_id, document=document, **kwargs)

    def edit_text(self, text, **kwargs):
        if self.chat_id is None or self.message_id is None:
            raise ValueError("This update does not contain an editable message")
        return self.bot.edit_message_text(chat_id=self.chat_id, message_id=self.message_id, text=text, **kwargs)

    def delete(self):
        if self.chat_id is None or self.message_id is None:
            raise ValueError("This update does not contain a deletable message")
        return self.bot.delete_message(chat_id=self.chat_id, message_id=self.message_id)

    def answer_callback(self, text=None, *, show_alert=False, url=None, cache_time=None):
        if not self.callback_query:
            raise ValueError("This update is not a callback query")
        payload = {"callback_query_id": self.callback_query["id"], "show_alert": show_alert}
        if text is not None:
            payload["text"] = text
        if url is not None:
            payload["url"] = url
        if cache_time is not None:
            payload["cache_time"] = cache_time
        result = self.bot.answer_callback_query(**payload)
        self._callback_answered = True
        return result


class Router:
    """Reusable collection of handlers that can be attached to a Bot."""

    def __init__(self, name=None):
        self.name = name or "router"
        self.handlers = []

    def _decorator(self, kind, *, filters=None, commands=None):
        def decorate(function):
            self.handlers.append(Handler(kind, function, as_filter(filters),
                                         frozenset(c.lower().lstrip("/") for c in commands) if commands else None))
            return function
        return decorate

    def message(self, function=None, *, filters=None):
        decorator = self._decorator("message", filters=filters)
        return decorator(function) if function else decorator

    def command(self, *commands, filters=None):
        if len(commands) == 1 and isinstance(commands[0], (list, tuple, set)):
            commands = tuple(commands[0])
        if not commands:
            raise ValueError("at least one command name is required")
        return self._decorator("message", filters=filters, commands=commands)

    def callback_query(self, function=None, *, filters=None):
        decorator = self._decorator("callback_query", filters=filters)
        return decorator(function) if function else decorator

    def edited_message(self, function=None, *, filters=None):
        decorator = self._decorator("edited_message", filters=filters)
        return decorator(function) if function else decorator

    def update(self, function=None, *, filters=None):
        decorator = self._decorator("update", filters=filters)
        return decorator(function) if function else decorator


class Bot(Client):
    """A friendly bot framework built on top of the Soroush Plus Bot API."""

    def __init__(self, token, **kwargs):
        super().__init__(token, **kwargs)
        self.handlers = []
        self.error_handler = None
        self._running = False
        self._offset = None

    def _register(self, kind, function=None, *, filters=None, commands=None):
        def decorate(callback):
            self.handlers.append(Handler(kind, callback, as_filter(filters),
                                         frozenset(c.lower().lstrip("/") for c in commands) if commands else None))
            return callback
        return decorate(function) if function is not None else decorate

    def on_message(self, function=None, *, filters=None):
        return self._register("message", function, filters=filters)

    def command(self, *commands, filters=None):
        if len(commands) == 1 and isinstance(commands[0], (list, tuple, set)):
            commands = tuple(commands[0])
        if not commands:
            raise ValueError("at least one command name is required")
        return self._register("message", filters=filters, commands=commands)

    def on_callback_query(self, function=None, *, filters=None):
        return self._register("callback_query", function, filters=filters)

    def on_edited_message(self, function=None, *, filters=None):
        return self._register("edited_message", function, filters=filters)

    def on_update(self, function=None, *, filters=None):
        return self._register("update", function, filters=filters)

    def on_error(self, function):
        """Register ``function(context, exception)`` as the error callback."""
        if not callable(function):
            raise TypeError("error handler must be callable")
        self.error_handler = function
        return function

    def include_router(self, router):
        if not isinstance(router, Router):
            raise TypeError("include_router expects a Router")
        self.handlers.extend(router.handlers)
        return self

    def process_update(self, update):
        """Dispatch one decoded Update object to all matching handlers."""
        if not isinstance(update, dict):
            raise TypeError("update must be a dict")
        context = Context(self, update)
        for handler in tuple(self.handlers):
            if not self._matches(handler, update, context):
                continue
            try:
                handler.callback(context)
            except Exception as exc:
                if self.error_handler:
                    try:
                        self.error_handler(context, exc)
                    except Exception:
                        logger.exception("The registered error handler also failed")
                else:
                    logger.exception("Handler failed (%s)", handler.callback)
        if context.callback_query and not context._callback_answered:
            try:
                context.answer_callback()
            except Exception:
                logger.debug("Automatic callback acknowledgement failed", exc_info=True)
        return context

    @staticmethod
    def _matches(handler, update, context):
        if handler.kind == "message" and not update.get("message"):
            return False
        if handler.kind == "edited_message" and not update.get("edited_message"):
            return False
        if handler.kind == "callback_query" and not update.get("callback_query"):
            return False
        if handler.kind == "update":
            pass
        if handler.commands is not None:
            if context.command not in handler.commands:
                return False
        return handler.filter(update) if handler.filter else True

    def run_polling(self, *, timeout=25, limit=100, allowed_updates=None,
                    drop_pending_updates=False, delete_webhook=True, poll_interval=1.0):
        """Start long polling. Stop it from another thread with ``bot.stop()``."""
        if not isinstance(timeout, int) or timeout < 0:
            raise ValueError("timeout must be a non-negative integer")
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if delete_webhook:
            self.delete_webhook(drop_pending_updates=bool(drop_pending_updates))
        self._running = True
        logger.info("radvinsplus polling started")
        while self._running:
            try:
                updates = self.get_updates(offset=self._offset, timeout=timeout,
                                           limit=limit, allowed_updates=allowed_updates)
                for update in updates or []:
                    if not self._running:
                        break
                    try:
                        self.process_update(update)
                    finally:
                        update_id = update.get("update_id")
                        if isinstance(update_id, int):
                            self._offset = max(self._offset or 0, update_id + 1)
            except KeyboardInterrupt:
                self.stop()
            except APIError as exc:
                logger.error("Polling API error: %s", exc)
                if exc.error_code == 409:
                    logger.error("Another getUpdates consumer or a webhook may be active")
                    break
                if poll_interval > 0:
                    import time
                    time.sleep(poll_interval)
            except Exception:
                logger.exception("Polling iteration failed")
                if poll_interval > 0:
                    import time
                    time.sleep(poll_interval)
        logger.info("radvinsplus polling stopped")

    polling = run_polling
    run = run_polling

    def stop(self):
        self._running = False

    def serve_webhook(self, *, host="0.0.0.0", port=8080, path="/soroush-webhook",
                      secret=None, max_body_size=2 * 1024 * 1024, block=True):
        """Run a minimal stdlib HTTP webhook receiver.

        Configure the matching public HTTPS URL with ``bot.set_webhook(url=...)``.
        TLS termination is expected to be handled by a reverse proxy when needed.
        """
        if not path.startswith("/"):
            raise ValueError("webhook path must start with '/'")
        if not isinstance(max_body_size, int) or max_body_size <= 0:
            raise ValueError("max_body_size must be a positive integer")
        if secret is not None and (not isinstance(secret, str) or not secret or "/" in secret):
            raise ValueError("secret must be a non-empty path-safe string")
        expected_path = path.rstrip("/")
        if secret is not None:
            expected_path += "/" + secret
        if not expected_path:
            expected_path = "/"
        bot = self

        class RequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path.split("?", 1)[0] != expected_path:
                    self.send_error(404)
                    return
                try:
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                    except (TypeError, ValueError):
                        self.send_error(400)
                        return
                    if length <= 0 or length > max_body_size:
                        self.send_error(413 if length > max_body_size else 400)
                        return
                    raw = self.rfile.read(length)
                    update = json.loads(raw.decode("utf-8"))
                    bot.process_update(update)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"OK")
                except Exception:
                    logger.exception("Webhook update processing failed")
                    self.send_error(500)

            def log_message(self, fmt, *args):
                logger.info("Webhook: " + fmt, *args)

        server = ThreadingHTTPServer((host, port), RequestHandler)
        if block:
            try:
                logger.info("Webhook server listening on %s:%s%s", host, port, expected_path)
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return server
        thread = threading.Thread(target=server.serve_forever, name="radvinsplus-webhook", daemon=True)
        thread.start()
        server.thread = thread
        return server

# ============================================================
# ---- docs_data.py ----
# ============================================================
"""محتوای راهنمای بات RadvinSPlus Docs."""

OWNER = "@Radvinhha"
OWNER_ID = 56597421
LIB_VERSION = "1.0.0"

TOPICS = {
    "install": {
        "title": "📦 نصب و راه‌اندازی",
        "body": """📦 <b>نصب radvinsplus از PyPI</b>

پیش‌نیاز: Python نسخه 3.10 یا جدیدتر.

<b>نصب مستقیم نسخه 1.0.0:</b>
<pre><code>python -m pip install --upgrade radvinsplus==1.0.0</code></pre>

<b>بررسی نصب:</b>
<pre><code>python -c "import radvinsplus; print(radvinsplus.__version__)"</code></pre>

<b>نصب وابستگی‌های همین پروژه:</b>
<pre><code>python -m pip install -r requirements.txt</code></pre>

بسته مستقیماً از مخزن رسمی PyPI دریافت می‌شود و سورس محلی کتابخانه لازم نیست.""",
        "code": 'python -m pip install --upgrade radvinsplus==1.0.0\npython -c "import radvinsplus; print(radvinsplus.__version__)"',
    },
    "firstbot": {
        "title": "🚀 اولین ربات",
        "body": """🚀 <b>ساخت اولین ربات</b>

یک فایل به نام <code>bot.py</code> بساز:

<pre><code class=\"language-python\">import os
from radvinsplus import Bot

bot = Bot(os.environ["SPLUS_BOT_TOKEN"])

@bot.command("start")
def start(ctx):
    ctx.reply("سلام! ربات با radvinsplus فعاله.")

@bot.command("help")
def help_command(ctx):
    ctx.reply("یک پیام متنی بفرست تا دریافتش کنم.")

bot.run_polling()</code></pre>

توکن را در کد قرار نده؛ آن را در متغیر محیطی <code>SPLUS_BOT_TOKEN</code> تنظیم کن.

<b>Windows PowerShell:</b>
<pre><code>$env:SPLUS_BOT_TOKEN="YOUR_TOKEN"
python bot.py</code></pre>

<b>Linux / macOS:</b>
<pre><code>export SPLUS_BOT_TOKEN="YOUR_TOKEN"
python3 bot.py</code></pre>""",
        "code": "import os\nfrom radvinsplus import Bot\n\nbot = Bot(os.environ[\"SPLUS_BOT_TOKEN\"])\n\n@bot.command(\"start\")\ndef start(ctx):\n    ctx.reply(\"سلام! ربات فعاله.\")\n\nbot.run_polling()",
    },
    "context": {
        "title": "🧩 Context و پیام‌ها",
        "body": """🧩 <b>شیء Context</b>

هر هندلر یک شیء <code>ctx</code> دریافت می‌کند.

• <code>ctx.update</code> — کل داده Update
• <code>ctx.message</code> — پیام دریافتی
• <code>ctx.callback_query</code> — داده Callback
• <code>ctx.chat_id</code> — شناسه گفتگو
• <code>ctx.user_id</code> — شناسه فرستنده
• <code>ctx.message_id</code> — شناسه پیام
• <code>ctx.text</code> — متن پیام
• <code>ctx.edited_message</code> — پیام ویرایش‌شده
• <code>ctx.callback_message</code> — پیامی که دکمه روی آن بوده
• <code>ctx.from_user</code> — اطلاعات کامل فرستنده
• <code>ctx.command</code> — نام دستور بدون / و با حروف کوچک، یا None (در <code>/start@BotName</code> بخش @BotName حذف می‌شود)
• <code>ctx.args</code> — آرگومان‌های دستور به‌صورت لیست

<b>متدهای مهم:</b>
<code>ctx.reply()</code>، <code>ctx.answer()</code>، <code>ctx.reply_photo()</code>، <code>ctx.reply_document()</code>، <code>ctx.edit_text()</code>، <code>ctx.delete()</code> و <code>ctx.answer_callback()</code>.

<b>نمونه:</b>
<pre><code>from radvinsplus import Bot
bot = Bot("TOKEN")

@bot.command("id")
def show_id(ctx):
    ctx.reply(f"شناسه شما: {ctx.user_id}")

bot.run_polling()</code></pre>""",
        "code": "@bot.command(\"id\")\ndef show_id(ctx):\n    ctx.reply(f\"شناسه شما: {ctx.user_id}\")",
    },
    "filters": {
        "title": "🔎 فیلترها",
        "body": """🔎 <b>فیلترهای آماده و ترکیبی</b>

فیلترها مشخص می‌کنند کدام Update به هندلر برسد.

فیلترهای آماده نسخه فعلی:
<code>Filters.all</code>، <code>text</code>، <code>photo</code>، <code>video</code>، <code>audio</code>، <code>document</code>، <code>contact</code>، <code>location</code>، <code>sticker</code>، <code>private</code>، <code>group</code>، <code>channel</code>، <code>callback_query</code> و <code>edited</code>.

فیلترهای با پارامتر:
• <code>Filters.regex(r"سلام|درود")</code> — جست‌وجوی regex در متن
• <code>Filters.startswith("!")</code> — شروع متن با پیشوند مشخص

عملگرها:
• <code>&amp;</code> برای AND
• <code>|</code> برای OR
• <code>~</code> برای NOT

<pre><code>from radvinsplus import Bot, Filters
bot = Bot("TOKEN")

@bot.on_message(filters=Filters.text & Filters.private)
def private_text(ctx):
    ctx.reply("پیام متنی خصوصی دریافت شد")

@bot.on_message(filters=Filters.photo | Filters.video)
def media(ctx):
    ctx.reply("رسانه دریافت شد")

bot.run_polling()</code></pre>

فیلتر سفارشی هم می‌تواند یک تابع دریافت‌کننده Update باشد (یک <code>dict</code> که True/False برمی‌گرداند). اگر فیلتر سفارشی خطا بدهد، کتابخانه آن را False در نظر می‌گیرد و هندلر اجرا نمی‌شود.""",
        "code": "@bot.on_message(filters=Filters.text & Filters.private)\ndef private_text(ctx):\n    ctx.reply(\"پیام متنی خصوصی دریافت شد\")",
    },
    "keyboard": {
        "title": "🪄 دکمه‌های شیشه‌ای",
        "body": """🪄 <b>Inline Keyboard و Callback</b>

برای ساخت دکمه شیشه‌ای از <code>InlineKeyboard</code> و <code>InlineButton</code> استفاده کن.

<pre><code>from radvinsplus import Bot, InlineKeyboard, InlineButton
bot = Bot("TOKEN")

@bot.command("start")
def start(ctx):
    menu = (InlineKeyboard()
        .row(InlineButton.callback("وضعیت", "status"),
             InlineButton.callback("راهنما", "help")))
    ctx.reply("یکی را انتخاب کن:", reply_markup=menu)

@bot.on_callback_query
def callbacks(ctx):
    data = ctx.callback_query.get("data")
    if data == "status":
        ctx.answer_callback("ربات فعاله")
    elif data == "help":
        ctx.answer_callback("دستور /help را بفرست")

bot.run_polling()</code></pre>

داده callback حداکثر ۶۴ بایت UTF-8 است؛ بیشتر از آن <code>ValueError</code> می‌دهد. اگر هندلر Callback پاسخی ندهد، کتابخانه بعد از اجرای هندلرها خودکار آن را تأیید می‌کند. برای لینک مستقیم از <code>InlineButton.url(text, url)</code> استفاده کن.""",
        "code": "menu = (InlineKeyboard()\n    .row(InlineButton.callback(\"وضعیت\", \"status\"),\n         InlineButton.callback(\"راهنما\", \"help\")))\nctx.reply(\"انتخاب کن:\", reply_markup=menu)",
    },
    "replykeyboard": {
        "title": "⌨️ کیبورد پاسخ",
        "body": """⌨️ <b>Reply Keyboard</b>

کیبورد پاسخ در محل ورودی پیام نمایش داده می‌شود.

<pre><code>from radvinsplus import ReplyKeyboard, remove_keyboard

keyboard = ReplyKeyboard(resize=True, one_time=False)
keyboard.row("پروفایل", "راهنما")
keyboard.add("ارسال موقعیت", request_location=True)
ctx.reply("از منو استفاده کن:", reply_markup=keyboard)

# حذف کیبورد
ctx.reply("کیبورد حذف شد", reply_markup=remove_keyboard())</code></pre>

در <code>add</code> می‌توان از <code>request_contact=True</code> یا <code>request_location=True</code> استفاده کرد؛ هر دو را هم‌زمان برای یک دکمه فعال نکن.""",
        "code": "keyboard = ReplyKeyboard(resize=True)\nkeyboard.row(\"پروفایل\", \"راهنما\")\nctx.reply(\"انتخاب کن:\", reply_markup=keyboard)",
    },
    "router": {
        "title": "🧭 Router و ساختار پروژه",
        "body": """🧭 <b>تقسیم هندلرها با Router</b>

برای مرتب‌کردن پروژه‌های بزرگ می‌توانی هندلرها را در Router جداگانه ثبت و سپس به Bot متصل کنی.

<pre><code>from radvinsplus import Bot, Router

bot = Bot("TOKEN")
account = Router("account")

@account.command("profile")
def profile(ctx):
    ctx.reply(f"شناسه: {ctx.user_id}")

bot.include_router(account)
bot.run_polling()</code></pre>

Router از message، command، callback_query، edited_message و update پشتیبانی می‌کند.""",
        "code": "account = Router(\"account\")\n\n@account.command(\"profile\")\ndef profile(ctx):\n    ctx.reply(f\"شناسه: {ctx.user_id}\")\n\nbot.include_router(account)",
    },
    "media": {
        "title": "🖼️ فایل و رسانه",
        "body": """🖼️ <b>ارسال رسانه و فایل</b>

در Context متدهای <code>reply_photo</code> و <code>reply_document</code> در دسترس‌اند. در Client نیز متدهای API مثل <code>send_photo</code>، <code>send_video</code>، <code>send_audio</code>، <code>send_document</code> و <code>send_media_group</code> قابل فراخوانی‌اند.

<pre><code>from radvinsplus import Bot, InputFile
bot = Bot("TOKEN")

@bot.command("file")
def send_file(ctx):
    file = InputFile("./sample.pdf")
    ctx.reply_document(file, caption="فایل نمونه")

bot.run_polling()</code></pre>

آلبوم رسانه:
<pre><code>from radvinsplus import InputFile, InputMedia
media = [InputMedia.photo(InputFile("one.jpg"), caption="اول"), InputMedia.photo(InputFile("two.jpg"))]
bot.send_media_group(chat_id=123456, media=media)</code></pre>

دریافت فایل از کاربر:
<pre><code>data = bot.download_file(file_id)                       # bytes
path = bot.download_file(file_id, destination="downloads/f.bin")
url = bot.get_download_url(file_id)                    # یک ساعت اعتبار دارد</code></pre>
سقف دانلود مطابق مستندات ۲۰ مگابایت است.

همچنین <code>InputFile</code> از مسیر فایل، بایت یا file object پشتیبانی می‌کند. برای ارسال مجدد فایل موجود، استفاده از file_id در صورت داشتن آن مناسب است.""",
        "code": "from radvinsplus import InputFile\n\n@bot.command(\"file\")\ndef send_file(ctx):\n    ctx.reply_document(InputFile(\"./sample.pdf\"), caption=\"فایل نمونه\")",
    },
    "errors": {
        "title": "🛡️ خطاها و امنیت",
        "body": """🛡️ <b>مدیریت خطا</b>

می‌توانی با <code>@bot.on_error</code> خطاهای هندلرها را مدیریت کنی.

<pre><code>from radvinsplus import Bot, APIError, NetworkError
bot = Bot("TOKEN")

@bot.on_error
def errors(ctx, error):
    if isinstance(error, APIError):
        print(error.error_code, error.description)
    elif isinstance(error, NetworkError):
        print("مشکل شبکه:", error)

bot.run_polling()</code></pre>

<b>نکات امنیتی:</b>
• توکن را در سورس عمومی، مخزن Git یا لاگ‌ها قرار نده.
• از متغیر محیطی برای نگهداری توکن استفاده کن.
• URL وب‌هوک و مسیر محرمانه آن را عمومی نکن.
• خطاها را ثبت کن، اما اطلاعات محرمانه را لاگ نکن.

استثناهای کتابخانه شامل <code>APIError</code>، <code>NetworkError</code>، <code>ConfigurationError</code> و کلاس پایه <code>RadvinsPlusError</code> است.""",
        "code": "@bot.on_error\ndef errors(ctx, error):\n    print(type(error).__name__, error)",
    },
    "polling": {
        "title": "🌐 Polling و Webhook",
        "body": """🌐 <b>دریافت Update</b>

<b>Long Polling:</b>
<pre><code>bot.run_polling(timeout=25, limit=100)</code></pre>
اگر Polling با خطای 409 متوقف شد، یعنی یک مصرف‌کننده دیگر یا Webhook فعال است.

برای توقف از Thread دیگر می‌توان <code>bot.stop()</code> را فراخوانی کرد. به‌صورت پیش‌فرض، پیش از شروع Polling وب‌هوک قبلی حذف می‌شود؛ برای تغییر رفتار از <code>delete_webhook=False</code> استفاده کن.

<b>Webhook:</b>
<pre><code>secret = "LONG_RANDOM_SECRET"
bot.set_webhook(url="https://example.com/hook/" + secret)
bot.serve_webhook(
    host="127.0.0.1",
    port=8080,
    path="/hook",
    secret=secret,
    block=True,
)</code></pre>

سرور داخلی HTTP است؛ برای دسترسی عمومی HTTPS را با Reverse Proxy فراهم کن. وب‌هوک باید از اینترنت قابل دسترسی باشد.""",
        "code": "bot.run_polling(timeout=25, limit=100)\n\n# یا webhook\nsecret = \"LONG_RANDOM_SECRET\"\nbot.set_webhook(url=\"https://example.com/hook/\" + secret)\nbot.serve_webhook(host=\"127.0.0.1\", port=8080, path=\"/hook\", secret=secret)",
    },
    "api": {
        "title": "⚙️ فراخوانی API و متدها",
        "body": """⚙️ <b>Client و فراخوانی متدهای API</b>

کلاس <code>Bot</code> از <code>Client</code> ارث‌بری می‌کند. می‌توان متدهای شناخته‌شده را با نام snake_case یا نام API صدا زد.

<pre><code>bot.get_me()

# معادل نام API
bot.getMe()

# فراخوانی عمومی
bot.call("sendMessage", chat_id=123, text="سلام")</code></pre>

در Client متدهای API به‌صورت پویا قابل دسترسی‌اند؛ این موضوع امکان فراخوانی متدهای تازه‌تر را نیز فراهم می‌کند. با این حال وجود wrapper تضمین نمی‌کند که سمت سرور آن متد فعال باشد.

<b>GET برای متدهای فقط‌خواندنی:</b>
<pre><code>bot.call("getMe", http_method="GET")</code></pre>

<b>چند متد رایج:</b>
<code>send_message</code>، <code>edit_message_text</code>، <code>delete_message</code>، <code>answer_callback_query</code>، <code>get_updates</code>، <code>set_webhook</code> و <code>get_webhook_info</code>.""",
        "code": "bot.get_me()\nbot.send_message(chat_id=CHAT_ID, text=\"سلام\")\nbot.call(\"sendMessage\", chat_id=CHAT_ID, text=\"سلام\")",
    },
    "limits": {
        "title": "📚 نسخه و محدودیت‌ها",
        "body": """📚 <b>درباره نسخه 1.0.0</b>

• لایسنس MIT
• نیازمند Python 3.10 یا جدیدتر
• هسته بدون وابستگی Runtime ثالث
• پشتیبانی از Long Polling و Webhook
• هندلرهای پیام، Callback Query، پیام ویرایش‌شده و Update عمومی
• Router و فیلترهای آماده/ترکیبی
• سازنده Inline و Reply Keyboard
• ابزارهای InputFile و InputMedia

<b>نکته سازگاری:</b> پیاده‌سازی بر اساس مستندات Bot API سروش‌پلاسِ مبنای پروژه انجام شده است. در سند مبنا بعضی متدها «به‌زودی» معرفی شده‌اند؛ بنابراین وجود متد در کتابخانه به معنی فعال‌بودن قطعی آن در سرور نیست.

برای جزئیات کامل امضاها و پارامترها، مرجع API همراه پروژه را بررسی کن.""",
        "code": "import radvinsplus\nprint(radvinsplus.__version__)  # 1.0.0",
    },
}

FAQ = {
    "نصب": "برای نصب سورس در حالت توسعه: <code>python -m pip install -e .</code> و Python 3.10+ لازم است.",
    "توکن": "توکن را در متغیر محیطی <code>SPLUS_BOT_TOKEN</code> بگذار و در کد عمومی منتشر نکن.",
    "نسخه": "نسخه مستندشده کتابخانه <b>1.0.0</b> است.",
    "فیلتر": "فیلترهای آماده در کلاس <code>Filters</code> هستند و با <code>&amp;</code>، <code>|</code> و <code>~</code> ترکیب می‌شوند.",
    "وبهوک": "برای Webhook از <code>set_webhook</code> و سپس <code>serve_webhook</code> استفاده کن. HTTPS عمومی را با Reverse Proxy فراهم کن.",
    "سازنده": f"سازنده: <b>{OWNER}</b>\nآیدی عددی: <code>{OWNER_ID}</code>",
}

# ============================================================
# ---- docbot.py ----
# ============================================================
"""RadvinSPlus Docs Bot — powered by radvinsplus."""
import logging
import os
import sys


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("radvinsplus.docsbot")
# ⬇️ توکن ربات را اینجا بگذار
TOKEN = "70904751:3Vp6LsxcMELDQDL05qr9Crcpum4GyeBbXaE"
if not TOKEN or TOKEN == "PUT_YOUR_TOKEN_HERE":
    raise SystemExit("توکن را در متغیر TOKEN داخل main.py قرار بده.")

bot = Bot(TOKEN)


def main_menu():
    keyboard = InlineKeyboard()
    entries = list(TOPICS.items())
    for i in range(0, len(entries), 2):
        row = [InlineButton.callback(entries[i][1]["title"], "topic:" + entries[i][0])]
        if i + 1 < len(entries):
            row.append(InlineButton.callback(entries[i + 1][1]["title"], "topic:" + entries[i + 1][0]))
        keyboard.row(*row)
    keyboard.row(InlineButton.callback("❔ پرسش‌های پرتکرار", "faq"),
                 InlineButton.callback("👨‍💻 سازنده", "owner"))
    keyboard.row(InlineButton.callback("🔎 جستجو", "search_help"))
    return keyboard


def home_text():
    return (
        "<b>📘 RadvinSPlus Documentation</b>\n"
        "راهنمای تعاملی کتابخانه <code>radvinsplus</code> برای ساخت ربات‌های سروش‌پلاس.\n\n"
        f"نسخه کتابخانه: <b>{LIB_VERSION}</b>\n"
        "از دکمه‌های زیر یک بخش را انتخاب کن یا از دستور <code>/search عبارت</code> استفاده کن.\n\n"
        f"توسعه‌دهنده: {OWNER}"
    )


def send_home(ctx, edit=False):
    if edit and ctx.message_id:
        return ctx.edit_text(home_text(), reply_markup=main_menu(), parse_mode="HTML")
    return ctx.reply(home_text(), reply_markup=main_menu(), parse_mode="HTML")


def send_topic(ctx, key, edit=False):
    topic = TOPICS.get(key)
    if not topic:
        ctx.reply("این بخش پیدا نشد. /start را بزن.")
        return
    keyboard = InlineKeyboard().row(
        InlineButton.callback("📋 کپی/نمایش نمونه بعدی", "code:" + key),
        InlineButton.callback("🏠 منوی اصلی", "home"),
    )
    text = topic["body"] + "\n\n<i>برای دیدن نمونه کد کوتاه‌تر، دکمه پایین را بزن.</i>"
    if edit and ctx.message_id:
        ctx.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        ctx.reply(text, reply_markup=keyboard, parse_mode="HTML")


@bot.command("start", "menu")
def start(ctx):
    send_home(ctx)


@bot.command("help")
def help_command(ctx):
    ctx.reply(
        "<b>راهنمای بات مستندات</b>\n\n"
        "/start — نمایش فهرست\n"
        "/search کلمه — جستجو در مستندات\n"
        "/about — اطلاعات کتابخانه و سازنده\n"
        "/owner — اطلاعات سازنده\n"
        "/help — همین راهنما",
        parse_mode="HTML",
    )


@bot.command("about")
def about(ctx):
    ctx.reply(
        f"<b>radvinsplus {LIB_VERSION}</b>\n"
        "کتابخانه پایتون برای ساخت ربات‌های سروش‌پلاس.\n"
        "سازنده: " + OWNER + "\n"
        f"آیدی عددی: <code>{OWNER_ID}</code>",
        parse_mode="HTML",
    )


@bot.command("owner")
def owner(ctx):
    ctx.reply(f"👨‍💻 سازنده: <b>{OWNER}</b>\n🆔 آیدی عددی: <code>{OWNER_ID}</code>", parse_mode="HTML")


@bot.command("search")
def search(ctx):
    query = " ".join(ctx.args).strip().lower()
    if not query:
        ctx.reply("عبارت جستجو را بعد از دستور بنویس.\nمثال: <code>/search فیلتر</code>", parse_mode="HTML")
        return
    matches = []
    for key, topic in TOPICS.items():
        haystack = (topic["title"] + " " + topic["body"] + " " + topic["code"]).lower()
        if query in haystack:
            matches.append((key, topic["title"]))
    if not matches:
        ctx.reply("چیزی پیدا نکردم. عبارت دیگری امتحان کن یا /start را بزن.")
        return
    keyboard = InlineKeyboard()
    for key, title in matches[:12]:
        keyboard.row(InlineButton.callback(title, "topic:" + key))
    keyboard.row(InlineButton.callback("🏠 منوی اصلی", "home"))
    ctx.reply(f"🔎 {len(matches)} بخش مرتبط پیدا شد:", reply_markup=keyboard)


@bot.on_callback_query
def callbacks(ctx):
    data = (ctx.callback_query or {}).get("data", "")
    ctx.answer_callback()
    if data == "home":
        send_home(ctx, edit=True)
    elif data.startswith("topic:"):
        send_topic(ctx, data.split(":", 1)[1], edit=True)
    elif data.startswith("code:"):
        key = data.split(":", 1)[1]
        topic = TOPICS.get(key)
        if topic:
            # HTML pre/code to preserve readable formatting in Soroush Plus.
            code = topic["code"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            ctx.reply("<b>نمونه کد</b>\n<pre><code>" + code + "</code></pre>", parse_mode="HTML")
    elif data == "faq":
        keyboard = InlineKeyboard()
        for key in FAQ:
            keyboard.row(InlineButton.callback("❓ " + key, "faq:" + key))
        keyboard.row(InlineButton.callback("🏠 منوی اصلی", "home"))
        ctx.reply("یک پرسش را انتخاب کن:", reply_markup=keyboard)
    elif data.startswith("faq:"):
        key = data.split(":", 1)[1]
        if key in FAQ:
            ctx.reply("<b>" + key + "</b>\n" + FAQ[key], parse_mode="HTML")
    elif data == "owner":
        owner(ctx)
    elif data == "search_help":
        ctx.reply("برای جستجو بنویس:\n<code>/search keyboard</code>\nیا مثلاً <code>/search وبهوک</code>", parse_mode="HTML")


@bot.on_error
def handle_error(ctx, error):
    if isinstance(error, APIError):
        log.error("API error %s: %s", error.error_code, error.description)
    elif isinstance(error, NetworkError):
        log.error("Network error: %s", error)
    else:
        log.exception("Unhandled handler error", exc_info=error)


if __name__ == "__main__":
    log.info("Starting RadvinSPlus Docs Bot (library %s)", LIB_VERSION)
    bot.run_polling(timeout=25, limit=100)
