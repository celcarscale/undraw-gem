from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


DEFAULT_COLOR = "#6c63ff"
UNDRAW_DIR = Path(__file__).resolve().parent.parent / "undraw"


class PictureRequest(BaseModel):
    name: str


def normalize_key(raw: str) -> str:
    """
    Normalize an input name so both `a_whole_year` and `A whole year` match.
    """

    s = raw.strip()
    if s.lower().endswith(".svg"):
        s = s[: -len(".svg")]

    # Plan requirement: only `_` becomes a space.
    s = s.replace("_", " ")
    # Collapse multiple spaces to a single space.
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def display_name_from_stem(stem: str) -> str:
    # Plan requirement: `a_whole_year` -> `A whole year`
    return stem.replace("_", " ").title()


def normalize_color(raw: str) -> str:
    """
    Validate `raw` as a hex color and return lowercase `#rrggbb`.
    """

    s = raw.strip()
    if not s.startswith("#"):
        s = f"#{s}"

    if not re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        raise ValueError("color must be a hex value like #RRGGBB")

    return s.lower()


def build_index() -> tuple[Dict[str, Path], list[str]]:
    if not UNDRAW_DIR.exists():
        raise RuntimeError(f"undraw folder not found at: {UNDRAW_DIR}")

    key_to_path: Dict[str, Path] = {}
    display_names: set[str] = set()

    for svg_path in sorted(UNDRAW_DIR.glob("*.svg")):
        stem = svg_path.stem
        key = normalize_key(stem)
        # If this happens, it means two different filenames normalize to the same key.
        key_to_path.setdefault(key, svg_path)
        display_names.add(display_name_from_stem(stem))

    return key_to_path, sorted(display_names)


app = FastAPI()
key_to_path: Dict[str, Path] = {}
all_display_names: list[str] = []


@app.on_event("startup")
def _startup() -> None:
    global key_to_path, all_display_names
    key_to_path, all_display_names = build_index()


@app.get("/get-list")
def get_list() -> list[str]:
    return all_display_names


@app.post("/get-picture/")
def get_picture(req: PictureRequest, color: Optional[str] = Query(default=None)) -> dict:
    key = normalize_key(req.name)
    svg_path = key_to_path.get(key)
    if svg_path is None:
        raise HTTPException(status_code=404, detail="Unknown picture name")

    try:
        svg_text = svg_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Be explicit: these are expected to be UTF-8 SVGs.
        raise HTTPException(status_code=500, detail="Failed to decode SVG as UTF-8")

    if color is not None:
        try:
            user_color = normalize_color(color)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        svg_text = svg_text.replace(DEFAULT_COLOR, user_color)

    return {"svg": svg_text}


if __name__ == "__main__":
    # Allow running locally for manual verification.
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
