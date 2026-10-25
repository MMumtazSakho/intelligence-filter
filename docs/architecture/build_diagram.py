#!/usr/bin/env python3
"""
High-Level Draw.io Architecture Diagram Builder for Intelligence Filter.

Directly models the clean, minimalist draw.io style from the user's reference sketch:
- Classic draw.io shapes: Actor stickman, Cylinder database, Parallelogram prompt metadata,
  clean black-bordered rectangles, orthogonal black arrows, generous whitespace.
- Equipped with crisp official logos (Cloud Run, Google ADK, FastAPI, SQLite, Python).
- No low-level implementation clutter (no env vars, no init_db, no litellm, no openrouter).
"""

import base64
import html
import math
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(BASE_DIR, "assets", "icons")


def load_icons() -> Dict[str, Tuple[str, str]]:
    icons: Dict[str, Tuple[str, str]] = {}
    for fname in sorted(os.listdir(ICONS_DIR)):
        if not fname.endswith(".svg"):
            continue
        key = fname[:-4]
        path = os.path.join(ICONS_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        compact = re.sub(r"\s+", " ", raw)
        b64 = base64.b64encode(compact.encode("utf-8")).decode("ascii")
        icons[key] = (raw, b64)
    return icons


class CleanDrawioBuilder:
    """
    Produces both native draw.io XML (<mxGraphModel>) and a 1:1 matching standalone SVG
    using authentic draw.io primitives (actor, cylinder3, parallelogram, container, rectangle).
    """

    def __init__(self, page_id: str, page_name: str, width: int, height: int, icons: Dict[str, Tuple[str, str]]):
        self.page_id = page_id
        self.page_name = page_name
        self.width = width
        self.height = height
        self.icons = icons
        self._cid = 2

        self.diagram_el = ET.Element("diagram", id=page_id, name=page_name)
        self.model_el = ET.SubElement(
            self.diagram_el,
            "mxGraphModel",
            dx="1200",
            dy="800",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth=str(width),
            pageHeight=str(height),
            background="#FFFFFF",
            math="0",
            shadow="0",
        )
        self.root_el = ET.SubElement(self.model_el, "root")
        ET.SubElement(self.root_el, "mxCell", id="0")
        ET.SubElement(self.root_el, "mxCell", id="1", parent="0")

        self.svg_bg: List[str] = [
            f'<rect x="-20" y="-20" width="{width + 40}" height="{height + 40}" fill="#FFFFFF"/>'
        ]
        self.svg_shapes: List[str] = []
        self.svg_edges: List[str] = []
        self.svg_labels: List[str] = []

    def _next_id(self, prefix: str = "n") -> str:
        self._cid += 1
        return f"{prefix}_{self._cid}"

    def add_icon(self, icon_name: str, x: int, y: int, size: int = 36):
        if icon_name not in self.icons:
            return
        _, b64 = self.icons[icon_name]
        iid = self._next_id("icon")
        cell = ET.SubElement(
            self.root_el,
            "mxCell",
            id=iid,
            value="",
            style=f"shape=image;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;image=data:image/svg+xml,{b64};",
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            cell, "mxGeometry", x=str(x), y=str(y), width=str(size), height=str(size), attrib={"as": "geometry"}
        )
        self.svg_shapes.append(
            f'<image x="{x}" y="{y}" width="{size}" height="{size}" href="data:image/svg+xml;base64,{b64}"/>'
        )

    def add_actor(self, x: int, y: int, w: int = 50, h: int = 90, label: str = "User"):
        """Classic draw.io stickman Actor (shape=umlActor)."""
        aid = self._next_id("actor")
        cell = ET.SubElement(
            self.root_el,
            "mxCell",
            id=aid,
            value=label,
            style="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;strokeColor=#000000;fillColor=#FFFFFF;strokeWidth=1.5;fontSize=14;fontFamily=Helvetica;fontColor=#000000;",
            vertex="1",
            parent="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})

        cx = x + w / 2
        head_r = w * 0.24
        head_cy = y + head_r + 2
        body_top = head_cy + head_r
        body_bot = y + h * 0.62
        arm_y = y + h * 0.36
        leg_bot = y + h

        self.svg_shapes.append(
            f'<circle cx="{cx}" cy="{head_cy}" r="{head_r}" fill="#FFFFFF" stroke="#000000" stroke-width="1.6"/>'
        )
        self.svg_shapes.append(
            f'<line x1="{cx}" y1="{body_top}" x2="{cx}" y2="{body_bot}" stroke="#000000" stroke-width="1.6"/>'
        )
        self.svg_shapes.append(
            f'<line x1="{x + 4}" y1="{arm_y}" x2="{x + w - 4}" y2="{arm_y}" stroke="#000000" stroke-width="1.6"/>'
        )
        self.svg_shapes.append(
            f'<line x1="{cx}" y1="{body_bot}" x2="{x + 6}" y2="{leg_bot}" stroke="#000000" stroke-width="1.6"/>'
        )
        self.svg_shapes.append(
            f'<line x1="{cx}" y1="{body_bot}" x2="{x + w - 6}" y2="{leg_bot}" stroke="#000000" stroke-width="1.6"/>'
        )
        self.svg_labels.append(
            f'<text x="{cx}" y="{y + h + 22}" font-family="Helvetica, Arial, sans-serif" font-size="14" fill="#000000" text-anchor="middle">{html.escape(label)}</text>'
        )

    def add_cylinder(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        lines: List[str],
        icon: Optional[str] = None,
        stroke: str = "#000000",
        fill: str = "#FFFFFF",
    ):
        """Classic draw.io 3D cylinder (shape=cylinder3) with optional logo."""
        cid = self._next_id("cyl")
        val = "<br>".join(html.escape(line) for line in lines)
        cell = ET.SubElement(
            self.root_el,
            "mxCell",
            id=cid,
            value=val,
            style=f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=16;strokeColor={stroke};fillColor={fill};strokeWidth=1.5;fontSize=13;fontFamily=Helvetica;fontColor=#000000;spacingTop=24;",
            vertex="1",
            parent="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})

        ry = 16
        cx = x + w / 2
        self.svg_shapes.append(
            f'<path d="M {x} {y + ry} L {x} {y + h - ry} A {w / 2} {ry} 0 0 0 {x + w} {y + h - ry} L {x + w} {y + ry} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        self.svg_shapes.append(
            f'<ellipse cx="{cx}" cy="{y + ry}" rx="{w / 2}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

        text_start_y = y + ry * 2 + 28
        if icon:
            self.add_icon(icon, int(cx - 18), int(y + ry * 2 + 8), size=36)
            text_start_y = y + ry * 2 + 64

        for i, line in enumerate(lines):
            weight = "bold" if i == 0 else "normal"
            size = "13.5" if i == 0 else "12.5"
            color = "#000000" if i == 0 else "#333333"
            self.svg_labels.append(
                f'<text x="{cx}" y="{text_start_y + i * 19}" font-family="Helvetica, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="middle">{html.escape(line)}</text>'
            )

    def add_container_box(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        icon: Optional[str] = None,
        stroke: str = "#000000",
        fill: str = "#FFFFFF",
        dashed: bool = False,
        rounded: bool = False,
    ):
        """Large container box (like 'LLM Agent (Google ADK)' or 'Google Cloud Run')."""
        bid = self._next_id("box")
        dash_s = "dashed=1;dashPattern=8 6;" if dashed else ""
        round_s = "rounded=1;arcSize=3;" if rounded else "rounded=0;"
        val = f"<b>{html.escape(title)}</b>"

        cell = ET.SubElement(
            self.root_el,
            "mxCell",
            id=bid,
            value=val,
            style=f"{round_s}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;{dash_s}verticalAlign=top;align=center;spacingTop=14;fontSize=14;fontFamily=Helvetica;fontColor=#000000;",
            vertex="1",
            parent="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})

        rx = 8 if rounded else 0
        dash_svg = 'stroke-dasharray="8,6"' if dashed else ""
        self.svg_shapes.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" {dash_svg}/>'
        )

        cx = x + w / 2
        if icon:
            title_w = len(title) * 8.2
            icon_x = int(cx - title_w / 2 - 40)
            self.add_icon(icon, icon_x, y + 10, size=30)

        self.svg_labels.append(
            f'<text x="{cx}" y="{y + 31}" font-family="Helvetica, Arial, sans-serif" font-size="14.5" font-weight="bold" fill="#000000" text-anchor="middle">{html.escape(title)}</text>'
        )

    def add_rect_node(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        lines: List[str],
        icon: Optional[str] = None,
        icon_pos: str = "left",  # "left" or "top"
        stroke: str = "#000000",
        fill: str = "#FFFFFF",
        rounded: bool = False,
        mono: bool = False,
    ):
        """Clean rectangle node (like 'execute_query(sql_code)' or 'FastAPI + Web UI')."""
        rid = self._next_id("rect")
        round_s = "rounded=1;arcSize=8;" if rounded else "rounded=0;"
        val = "<br>".join(html.escape(l) for l in lines)
        cell = ET.SubElement(
            self.root_el,
            "mxCell",
            id=rid,
            value=val,
            style=f"{round_s}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;align=center;verticalAlign=middle;fontSize=13;fontFamily=Helvetica;fontColor=#000000;",
            vertex="1",
            parent="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})

        rx = 6 if rounded else 0
        self.svg_shapes.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

        font_fam = "'Courier New', Courier, monospace" if mono else "Helvetica, Arial, sans-serif"

        if icon and icon_pos == "left":
            icon_size = 30
            ix = x + 16
            iy = int(y + (h - icon_size) / 2)
            self.add_icon(icon, ix, iy, size=icon_size)
            cx = x + 22 + (w - 22) / 2
            total_h = (len(lines) - 1) * 18
            start_y = int(y + h / 2 - total_h / 2 + 5)
        elif icon and icon_pos == "top":
            icon_size = 34
            cx = x + w / 2
            self.add_icon(icon, int(cx - icon_size / 2), y + 14, size=icon_size)
            start_y = y + 68
        else:
            cx = x + w / 2
            total_h = (len(lines) - 1) * 18
            start_y = int(y + h / 2 - total_h / 2 + 5)

        for i, line in enumerate(lines):
            weight = "bold" if (i == 0 and len(lines) > 1) else "normal"
            fsize = "13" if i == 0 else "12"
            self.svg_labels.append(
                f'<text x="{cx}" y="{start_y + i * 19}" font-family="{font_fam}" font-size="{fsize}" font-weight="{weight}" fill="#000000" text-anchor="middle">{html.escape(line)}</text>'
            )

    def add_parallelogram(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        lines: List[str],
        stroke: str = "#000000",
        fill: str = "#FFFFFF",
    ):
        """Classic draw.io Parallelogram (shape=parallelogram) for Prompt / Metadata schema."""
        pid = self._next_id("para")
        val = "<br>".join(html.escape(line) for line in lines)
        cell = ET.SubElement(
            self.root_el,
            "mxCell",
            id=pid,
            value=val,
            style=f"shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fixedSize=1;size=24;strokeColor={stroke};fillColor={fill};strokeWidth=1.5;fontSize=12.5;fontFamily=Helvetica;fontColor=#000000;",
            vertex="1",
            parent="1",
        )
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})

        dx = 24
        pts = f"{x + dx},{y} {x + w},{y} {x + w - dx},{y + h} {x},{y + h}"
        self.svg_shapes.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

        cx = x + w / 2
        total_h = (len(lines) - 1) * 19
        start_y = int(y + h / 2 - total_h / 2 + 4)
        for i, line in enumerate(lines):
            self.svg_labels.append(
                f'<text x="{cx}" y="{start_y + i * 19}" font-family="Helvetica, Arial, sans-serif" font-size="12.5" fill="#000000" text-anchor="middle">{html.escape(line)}</text>'
            )

    def add_arrow(
        self,
        points: List[Tuple[int, int]],
        label: str = "",
        label_pos: Optional[Tuple[int, int]] = None,
        dashed: bool = False,
        stroke: str = "#000000",
    ):
        eid = self._next_id("edge")
        dash_s = "dashed=1;dashPattern=6 4;" if dashed else ""
        cell = ET.SubElement(
            self.root_el,
            "mxCell",
            id=eid,
            value=label,
            style=f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;strokeColor={stroke};strokeWidth=1.5;{dash_s}endArrow=classic;endFill=1;fontSize=12;fontFamily=Helvetica;fontColor=#000000;labelBackgroundColor=#FFFFFF;",
            edge="1",
            parent="1",
        )
        geom = ET.SubElement(cell, "mxGeometry", relative="1", attrib={"as": "geometry"})
        sx, sy = points[0]
        tx, ty = points[-1]
        ET.SubElement(geom, "mxPoint", x=str(sx), y=str(sy), attrib={"as": "sourcePoint"})
        ET.SubElement(geom, "mxPoint", x=str(tx), y=str(ty), attrib={"as": "targetPoint"})
        if len(points) > 2:
            arr = ET.SubElement(geom, "Array", attrib={"as": "points"})
            for wx, wy in points[1:-1]:
                ET.SubElement(arr, "mxPoint", x=str(wx), y=str(wy))

        pts_str = " ".join(f"{px},{py}" for px, py in points)
        dash_svg = 'stroke-dasharray="6,4"' if dashed else ""
        self.svg_edges.append(
            f'<polyline points="{pts_str}" fill="none" stroke="{stroke}" stroke-width="1.5" {dash_svg}/>'
        )

        p_prev_x, p_prev_y = points[-2]
        angle = math.atan2(ty - p_prev_y, tx - p_prev_x)
        size = 9.0
        a1 = angle + math.pi - 0.42
        a2 = angle + math.pi + 0.42
        p1x = tx + size * math.cos(a1)
        p1y = ty + size * math.sin(a1)
        p2x = tx + size * math.cos(a2)
        p2y = ty + size * math.sin(a2)
        self.svg_edges.append(
            f'<polygon points="{tx},{ty} {p1x:.1f},{p1y:.1f} {p2x:.1f},{p2y:.1f}" fill="{stroke}"/>'
        )

        if label:
            lx, ly = label_pos if label_pos else ((sx + tx) // 2, (sy + ty) // 2 - 8)
            lw = len(label) * 6.8 + 8
            self.svg_edges.append(
                f'<rect x="{lx - lw / 2:.1f}" y="{ly - 13}" width="{lw:.1f}" height="16" fill="#FFFFFF"/>'
            )
            self.svg_labels.append(
                f'<text x="{lx}" y="{ly}" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#000000" text-anchor="middle">{html.escape(label)}</text>'
            )

    def to_svg_string(self) -> str:
        vb_w = self.width + 40
        vb_h = self.height + 40
        out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{vb_w * 2}" height="{vb_h * 2}" viewBox="-20 -20 {vb_w} {vb_h}">'
        ]
        out.extend(self.svg_bg)
        out.extend(self.svg_shapes)
        out.extend(self.svg_edges)
        out.extend(self.svg_labels)
        out.append("</svg>")
        return "\n".join(out)


def build_page_1_high_level(icons: Dict[str, Tuple[str, str]]) -> CleanDrawioBuilder:
    """
    Page 1: High-Level Architecture (1260 x 800)
    Directly completes the user's draw.io sketch with clean geometry & logos.
    """
    b = CleanDrawioBuilder("page-arch", "System Architecture", 1260, 800, icons)

    # Outer Cloud Run boundary
    b.add_container_box(
        x=210,
        y=30,
        w=1010,
        h=730,
        title="Google Cloud Run",
        icon="cloud-run",
        stroke="#777777",
        fill="#FFFFFF",
        dashed=True,
        rounded=True,
    )

    # 1. User Stickman (Left, outside Cloud Run — exactly like user's sketch)
    b.add_actor(x=65, y=450, w=50, h=90, label="User")

    # 2. SQLite (prototype only) Cylinder at top-left (exactly like user's sketch)
    b.add_cylinder(
        x=400,
        y=80,
        w=180,
        h=160,
        lines=["sqlite (prototype", "only)"],
        icon="sqlite",
    )

    # 3. FastAPI / Web UI (Entry & Exit point inside Cloud Run)
    b.add_rect_node(
        x=250,
        y=445,
        w=160,
        h=100,
        lines=["FastAPI + Web UI"],
        icon="fastapi",
        icon_pos="top",
        rounded=True,
    )

    # 4. LLM Agent (Google ADK) main square box (matching user's sketch)
    b.add_container_box(
        x=490,
        y=290,
        w=680,
        h=430,
        title="LLM Agent (Google ADK)",
        icon="google-adk",
        stroke="#000000",
        fill="#FFFFFF",
    )

    # Inside LLM Agent: Tool — run_sql(sql_code)
    b.add_rect_node(
        x=680,
        y=380,
        w=300,
        h=65,
        lines=["run_sql(sql_code)"],
        icon="python",
        icon_pos="left",
        mono=True,
    )

    # Inside LLM Agent: Parallelogram System Prompt / Metadata Schema (matching user's sketch)
    b.add_parallelogram(
        x=535,
        y=500,
        w=590,
        h=175,
        lines=[
            "Disediakan metadata suatu database dengan tabel 'stocks'",
            "yang memiliki kolom, tipe, dan deskripsi sebagai berikut:",
            "1. Kolom - tipe - deskripsi",
            "....",
            "Tugasmu adalah men-generate natural language",
            "ke dalam bentuk SQL query.",
        ],
    )

    # ------------------------------------------------------------------
    # CLEAN ORTHOGONAL ARROWS (Matching user's sketch)
    # ------------------------------------------------------------------
    # User <-> FastAPI Web UI
    b.add_arrow(
        [(125, 480), (250, 480)],
        label="Prompt",
        label_pos=(188, 468),
    )
    b.add_arrow(
        [(250, 515), (125, 515)],
        label="Hasil",
        label_pos=(188, 533),
        dashed=True,
    )

    # FastAPI Web UI <-> LLM Agent
    b.add_arrow(
        [(410, 480), (490, 480)],
    )
    b.add_arrow(
        [(490, 515), (410, 515)],
        dashed=True,
    )

    # Tool (run_sql) -> SQLite cylinder (goes left then up into bottom of cylinder, just like user's sketch!)
    b.add_arrow(
        [(680, 412), (450, 412), (450, 240)],
        label="SQL Query",
        label_pos=(405, 340),
    )

    # SQLite cylinder -> Tool (run_sql) (exits right side of cylinder, goes down then into tool, just like user's sketch!)
    b.add_arrow(
        [(580, 165), (830, 165), (830, 380)],
        label="Data Rows",
        label_pos=(875, 250),
    )

    return b


def build_page_2_modes(icons: Dict[str, Tuple[str, str]]) -> CleanDrawioBuilder:
    """
    Page 2: Perbandingan Mode (One-Shot vs Multistep Agent) (1260 x 800)
    Minimalist high-level flow of the two screening modes without clutter.
    """
    b = CleanDrawioBuilder("page-modes", "One-Shot vs Multistep Flow", 1260, 800, icons)

    # ==================================================================
    # TOP BOX: MODE 1 — ONE-SHOT
    # ==================================================================
    b.add_container_box(
        x=40,
        y=30,
        w=1180,
        h=340,
        title="Mode 1: One-Shot Screening",
        stroke="#000000",
        fill="#FFFFFF",
        rounded=True,
    )

    b.add_actor(x=85, y=155, w=45, h=80, label="User")

    b.add_rect_node(
        x=220,
        y=150,
        w=220,
        h=100,
        lines=["OneShot Agent", "(Google ADK)"],
        icon="google-adk",
        icon_pos="top",
    )

    b.add_rect_node(
        x=530,
        y=168,
        w=240,
        h=65,
        lines=["run_sql(sql_code)"],
        icon="python",
        icon_pos="left",
        mono=True,
    )

    b.add_cylinder(
        x=850,
        y=120,
        w=140,
        h=145,
        lines=["sqlite"],
        icon="sqlite",
    )

    b.add_rect_node(
        x=1050,
        y=150,
        w=140,
        h=100,
        lines=["Web UI", "Tabel & SQL"],
        icon="browser",
        icon_pos="top",
        rounded=True,
    )

    b.add_arrow([(140, 200), (220, 200)], label="Prompt", label_pos=(180, 188))
    b.add_arrow([(440, 200), (530, 200)], label="1x Call", label_pos=(485, 188))
    b.add_arrow([(770, 188), (850, 188)], label="Query", label_pos=(810, 176))
    b.add_arrow([(850, 215), (770, 215)], label="Rows", label_pos=(810, 232), dashed=True)
    b.add_arrow(
        [(650, 233), (650, 320), (1120, 320), (1120, 250)],
        label="Hasil Tabel Saham",
        label_pos=(885, 308),
    )

    # ==================================================================
    # BOTTOM BOX: MODE 2 — MULTISTEP AGENT
    # ==================================================================
    b.add_container_box(
        x=40,
        y=410,
        w=1180,
        h=360,
        title="Mode 2: Multistep Agent (Iteratif + Executive Summary)",
        stroke="#000000",
        fill="#FFFFFF",
        rounded=True,
    )

    b.add_actor(x=85, y=545, w=45, h=80, label="User")

    b.add_rect_node(
        x=220,
        y=540,
        w=220,
        h=100,
        lines=["Multistep Agent", "(Google ADK)"],
        icon="google-adk",
        icon_pos="top",
    )

    b.add_rect_node(
        x=530,
        y=555,
        w=260,
        h=65,
        lines=["run_sql(sql_code)"],
        icon="python",
        icon_pos="left",
        mono=True,
    )

    b.add_cylinder(
        x=860,
        y=515,
        w=140,
        h=145,
        lines=["sqlite"],
        icon="sqlite",
    )

    b.add_rect_node(
        x=1050,
        y=535,
        w=145,
        h=110,
        lines=["Web UI (SSE)", "Tabel & Summary"],
        icon="browser",
        icon_pos="top",
        rounded=True,
    )

    b.add_arrow([(140, 590), (220, 590)], label="Prompt", label_pos=(180, 578))
    b.add_arrow([(440, 588), (530, 588)], label="Iterative Calls", label_pos=(485, 576))
    b.add_arrow([(790, 575), (860, 575)], label="Query", label_pos=(825, 563))
    b.add_arrow([(860, 605), (790, 605)], label="Rows", label_pos=(825, 622), dashed=True)
    b.add_arrow(
        [(330, 640), (330, 725), (1122, 725), (1122, 645)],
        label="Stream Steps + Tabel + Executive Summary (SSE)",
        label_pos=(725, 713),
        dashed=True,
    )

    return b


def main():
    icons = load_icons()
    page1 = build_page_1_high_level(icons)
    page2 = build_page_2_modes(icons)

    mxfile = ET.Element(
        "mxfile",
        host="app.diagrams.net",
        modified="2026-10-25T22:18:00.000Z",
        agent="IntelligenceFilter-CleanDrawio/2.1",
        version="24.7.0",
        type="device",
    )
    mxfile.append(page1.diagram_el)
    mxfile.append(page2.diagram_el)

    ET.indent(mxfile, space="  ")
    drawio_path = os.path.join(BASE_DIR, "intelligence-filter.drawio")
    xml_bytes = ET.tostring(mxfile, encoding="utf-8", xml_declaration=True)
    with open(drawio_path, "wb") as f:
        f.write(xml_bytes)
    print(f"Wrote draw.io file: {drawio_path} ({len(xml_bytes):,} bytes)")

    for builder, basename in [(page1, "system-architecture"), (page2, "agent-request-flow")]:
        svg_path = os.path.join(BASE_DIR, f"{basename}.svg")
        png_path = os.path.join(BASE_DIR, f"{basename}.png")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(builder.to_svg_string())
        subprocess.run(
            ["/usr/bin/sips", "-s", "format", "png", svg_path, "--out", png_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Rendered {png_path}")


if __name__ == "__main__":
    main()
