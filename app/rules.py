"""Business rules for the report app.

This module is the backend source of truth. The frontend may still pre-check
inputs for a nicer UX, but every durable decision must pass through here.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


DEFAULT_TYPES = [
    "akb", "triton", "izi", "navo", "xabib", "jet", "jon", "top", "uztez", "mandarin",
    "oneway", "x637", "x517", "redwing",
]
DEFAULT_TYPE_SET = {t.lower() for t in DEFAULT_TYPES}

MAX_REPORTS = 25
MAX_REPORT_NAME_LEN = 60
MAX_TYPE_NAME_LEN = 40

MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 12 * 1024 * 1024
MAX_TOTAL_BYTES = 60 * 1024 * 1024
MAX_BODY_BYTES = MAX_TOTAL_BYTES + 2 * 1024 * 1024

COEFFICIENT_MODES = {"none", "box", "fixed", "custom"}
OBSHIY_ACTIONS = {"top", "topchiqgan", "bizda", "chiqgan"}
OBSHIY_SECTIONS = {
    "top": {"title": "Top", "code_required": True},
    "topchiqgan": {"title": "Topdan chiqgan", "code_required": False},
    "bizda": {"title": "Bizda qoladigan", "code_required": False},
    "chiqgan": {"title": "Bizdan chiqgan", "code_required": False},
}

_TYPE_RE = re.compile(r"^[0-9a-zA-Z_\-\s]+$")
_EPS = 1e-9


class RuleError(ValueError):
    """Validation error that can be returned to API clients."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


@dataclass(frozen=True)
class ReysPayload:
    tovar_turi: str
    weight: float
    coefficient: float
    coefficient_mode: str
    box_weight: float
    net: float


@dataclass(frozen=True)
class AdjustPayload:
    from_type: str
    to_type: str
    weight: float


@dataclass(frozen=True)
class ObshiyPayload:
    section: str
    code: str
    weight: float
    coefficient: float
    coefficient_mode: str
    box_weight: float
    net: float


def clean_decimal(value: Any, field_name: str = "qiymat") -> float:
    """Parse user-entered decimal values, accepting comma decimal separators."""
    if value is None:
        raise RuleError(f"{field_name} noto'g'ri")
    raw = str(value).strip().replace(",", ".")
    if not raw:
        raise RuleError(f"{field_name} noto'g'ri")
    try:
        out = float(raw)
    except ValueError:
        raise RuleError(f"{field_name} noto'g'ri")
    if not math.isfinite(out):
        raise RuleError(f"{field_name} noto'g'ri")
    return out


def same_num(a: Any, b: Any, eps: float = 0.0001) -> bool:
    return abs(float(a or 0) - float(b or 0)) <= eps


def clean_report_name(name: Any) -> str:
    name = str(name or "").strip()
    if not name:
        raise RuleError("hisobotga nom bering")
    if len(name) > MAX_REPORT_NAME_LEN:
        raise RuleError("nom juda uzun")
    return name


def clean_type_name(name: Any, *, allow_empty: bool = False) -> str:
    name = str(name or "").strip().lower()
    if not name:
        if allow_empty:
            return ""
        raise RuleError("tovar turini kiriting")
    if len(name) > MAX_TYPE_NAME_LEN:
        raise RuleError("tovar turi juda uzun")
    if not _TYPE_RE.match(name):
        raise RuleError("tovar turi noto'g'ri")
    return name


def is_default_type(name: str) -> bool:
    return clean_type_name(name, allow_empty=True) in DEFAULT_TYPE_SET


def entry_action(kind: Any) -> str:
    kind = str(kind or "reys")
    if kind in OBSHIY_ACTIONS:
        return kind
    if kind == "adjust":
        return "adjust"
    return "reys"


def clean_coefficient_mode(mode: Any) -> str:
    mode = str(mode or "none").strip().lower()
    if mode not in COEFFICIENT_MODES:
        raise RuleError("koeffitsient rejimi noto'g'ri")
    return mode


def validate_photo_count(count: int, *, required: bool, label: str = "rasm") -> None:
    if required and count <= 0:
        raise RuleError(f"kamida 1 ta {label} qo'shing")
    if count > MAX_PHOTOS:
        raise RuleError(f"Maksimal {MAX_PHOTOS} ta rasm yuklash mumkin", status_code=413)


def reys_payload(
    *,
    tovar_turi: Any,
    weight: Any,
    coefficient: Any,
    coefficient_mode: Any,
    box_weight: Any = 0,
    photo_count: int | None = None,
    creating: bool = True,
) -> ReysPayload:
    t = clean_type_name(tovar_turi)
    w = clean_decimal(weight, "og'irlik")
    coef = clean_decimal(coefficient, "koeffitsient")
    box = clean_decimal(box_weight, "karobka og'irligi")
    mode = clean_coefficient_mode(coefficient_mode)

    if w <= 0:
        raise RuleError("og'irlik noto'g'ri")
    if coef < 0 or box < 0:
        raise RuleError("koeffitsient noto'g'ri")
    if mode == "none":
        coef = 0
        box = 0
    elif mode == "box":
        coef = 0
        if box <= 0:
            raise RuleError("karobka og'irligini tanlang")
    elif mode in {"fixed", "custom"}:
        if coef <= 0:
            raise RuleError("koeffitsientni kiriting")
        box = 0

    net = round(w - coef, 4)
    if net < -_EPS:
        raise RuleError("koeffitsient og'irlikdan katta")
    net = max(0, net)
    if photo_count is not None:
        validate_photo_count(photo_count, required=creating, label="rasm")
    return ReysPayload(t, w, coef, mode, box, net)


def adjust_payload(*, from_type: Any, to_type: Any, weight: Any) -> AdjustPayload:
    src = clean_type_name(from_type)
    dst = clean_type_name(to_type)
    w = clean_decimal(weight, "og'irlik")
    if src == dst:
        raise RuleError("tovar turlari bir xil bo'lmasin")
    if w <= 0:
        raise RuleError("og'irlik noto'g'ri")
    return AdjustPayload(src, dst, w)


def obshiy_payload(
    *,
    section: Any,
    code: Any,
    weight: Any,
    coefficient: Any = 0,
    coefficient_mode: Any = "none",
    box_weight: Any = 0,
    photo_count: int | None = None,
    creating: bool = True,
) -> ObshiyPayload:
    action = str(section or "").strip()
    if action not in OBSHIY_ACTIONS:
        raise RuleError("bo'lim noto'g'ri")
    code_clean = str(code or "").strip()
    if OBSHIY_SECTIONS[action]["code_required"] and not code_clean:
        raise RuleError("karobka kodini kiriting")

    w = clean_decimal(weight, "og'irlik")
    coef = clean_decimal(coefficient, "karobka og'irligi")
    box = clean_decimal(box_weight, "karobka og'irligi")
    mode = clean_coefficient_mode(coefficient_mode)
    if w <= 0:
        raise RuleError("og'irlik noto'g'ri")
    if coef < 0 or box < 0:
        raise RuleError("karobka og'irligi noto'g'ri")

    if box <= 0 and coef > 0:
        box = coef
    if action == "top":
        coef = 0
        mode = "none" if box <= 0 else "fixed"
    elif mode == "custom" and box <= 0:
        raise RuleError("karobka og'irligini kiriting")
    elif box > 0 and mode == "none":
        mode = "fixed"

    coef = 0
    net = round(w, 4)
    if photo_count is not None:
        validate_photo_count(photo_count, required=creating, label="rasm")
    return ObshiyPayload(action, code_clean, w, coef, mode, box, net)
