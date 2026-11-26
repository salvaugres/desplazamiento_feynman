#!/usr/bin/env python3
"""
tex2pptx_mathtype_v2.py
-----------------------
Convierte una presentación Beamer (.tex) en un archivo PowerPoint (.pptx)
extrayendo las fórmulas en formato de texto limpio (sin delimitadores \\[...\\]
ni $...$), conservando el diseño, los bloques y las figuras.

Uso:
    python tex2pptx_mathtype_v2.py transparencias.tex
    python tex2pptx_mathtype_v2.py transparencias.tex -o salida.pptx --pdf transparencias.pdf

Requisitos:
    pip install python-pptx
    pip install pymupdf   # opcional, para extraer diagramas TikZ desde el PDF
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


def strip_latex_comments(text: str) -> str:
    """Elimina comentarios % de LaTeX respetando \\% escapados."""
    lines = []
    for line in text.splitlines():
        out = []
        i = 0
        while i < len(line):
            if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
                break
            out.append(line[i])
            i += 1
        lines.append("".join(out))
    return "\n".join(lines)


def extract_braced(text: str, pos: int) -> Tuple[Optional[str], int]:
    """Extrae el contenido de {...} empezando en pos (tras saltar espacios)."""
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    if pos >= n or text[pos] != "{":
        return None, pos
    depth = 0
    start = pos + 1
    i = pos
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return None, pos


def extract_bracketed(text: str, pos: int) -> Tuple[Optional[str], int]:
    """Extrae el contenido opcional [...] empezando en pos."""
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    if pos >= n or text[pos] != "[":
        return None, pos
    depth = 0
    start = pos + 1
    i = pos
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return None, pos


def clean_latex_math_spacing(text: str) -> str:
    """Limpia macros cosméticas fuera de matemáticas y normaliza espacios."""
    text = text.replace("---", "—").replace("--", "–")
    text = text.replace("``", "«").replace("''", "»")
    text = text.replace("{,}", ",")
    text = re.sub(r"\\\\(\[[^\]]*\])?", "\n", text)
    text = re.sub(r"\\vspace\*?\{[^}]*\}", "", text)
    text = re.sub(r"\\hspace\*?\{[^}]*\}", " ", text)
    text = re.sub(
        r"\\(centering|small|scriptsize|footnotesize|normalsize|large|Large|tiny|hfill|vfill|noindent)\b",
        "",
        text,
    )
    text = re.sub(r"\\color\{[^}]*\}", "", text)
    return text.strip()


def format_formula_plain(expr: str) -> str:
    """Limpia una expresión matemática y le quita los delimitadores $...$ o \\[...\\]."""
    s = expr.strip()
    if s.startswith(r"\[") and s.endswith(r"\]"):
        s = s[2:-2].strip()
    elif s.startswith("$") and s.endswith("$") and len(s) >= 2:
        s = s[1:-1].strip()
    else:
        m = re.match(r"\\begin\{[^}]+\}(.*)\\end\{[^}]+\}", s, re.S)
        if m:
            s = m.group(1).strip()

    s = s.replace("{,}", ",")
    # Quitar comandos de espaciado matemático explícito
    s = re.sub(r"\\(quad|qquad)\b", "  ", s)
    s = re.sub(r"\\[,:;!]|\\!", " ", s)
    s = re.sub(r"\\left\s*|\\right\s*", "", s)
    s = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\mathsf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\mathcal\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    # Quitar llaves agrupadoras sobrantes que no sean subíndices/superíndices simples
    s = re.sub(r"\{([^{}]+)\}", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_inline_runs(text: str) -> List[Tuple[str, str]]:
    """
    Convierte un fragmento de texto LaTeX en una lista de (segmento, estilo),
    donde estilo in {'normal', 'bold', 'italic', 'alert', 'url', 'math', 'accent'}.
    Extrae el contenido de $...$ sin los signos $.
    """
    text = clean_latex_math_spacing(text)
    runs: List[Tuple[str, str]] = []
    i = 0
    n = len(text)
    buf: List[str] = []

    def flush(style: str = "normal"):
        if buf:
            s = "".join(buf)
            s = re.sub(r"[ \t]+", " ", s)
            if s:
                runs.append((s, style))
            buf.clear()

    while i < n:
        ch = text[i]

        # Matemáticas en línea $...$ -> sin signos $
        if ch == "$" and (i == 0 or text[i - 1] != "\\"):
            flush("normal")
            j = i + 1
            while j < n:
                if text[j] == "$" and text[j - 1] != "\\":
                    j += 1
                    break
                j += 1
            math_str = format_formula_plain(text[i:j].replace("\n", " "))
            if math_str:
                runs.append((math_str, "math"))
            i = j
            continue

        # Macros con argumento
        if ch == "\\":
            m = re.match(r"\\(textbf|emph|textit|alert|url|texttt|textcolor)\b", text[i:])
            if m:
                cmd = m.group(1)
                flush("normal")
                pos = i + len(m.group(0))
                if cmd == "textcolor":
                    _color, pos = extract_braced(text, pos)
                    arg, pos = extract_braced(text, pos)
                    style = "accent"
                else:
                    arg, pos = extract_braced(text, pos)
                    style = {
                        "textbf": "bold",
                        "emph": "italic",
                        "textit": "italic",
                        "alert": "alert",
                        "url": "url",
                        "texttt": "normal",
                    }[cmd]
                if arg is not None:
                    if r"\color{accentblue}" in arg:
                        style = "accent_bold"
                    arg_clean = re.sub(r"\\color\{[^}]*\}", "", arg).strip()
                    sub_runs = parse_inline_runs(arg_clean) if cmd != "url" else [(arg_clean, "url")]
                    for seg, sub_st in sub_runs:
                        final_st = sub_st if sub_st in ("alert", "url") else (
                            "bold_math" if (style == "bold" and sub_st == "math") else style
                        )
                        runs.append((seg, final_st))
                    i = pos
                    continue

            if i + 1 < n and text[i + 1] in (",", ";", ":", "!", " "):
                buf.append(" ")
                i += 2
                continue
            if i + 1 < n and text[i + 1] in ("_", "%", "&", "#", "{", "}"):
                buf.append(text[i + 1])
                i += 2
                continue

        if ch == "{":
            arg, pos = extract_braced(text, i)
            if arg is not None:
                flush("normal")
                for seg, st in parse_inline_runs(arg):
                    runs.append((seg, st))
                i = pos
                continue

        if ch == "~":
            buf.append(" ")
            i += 1
            continue

        buf.append(ch)
        i += 1

    flush("normal")
    if runs:
        runs[0] = (runs[0][0].lstrip(), runs[0][1])
        runs[-1] = (runs[-1][0].rstrip(), runs[-1][1])
    return [(s, st) for s, st in runs if s]


@dataclass
class SlideElement:
    kind: str  # 'heading', 'paragraph', 'caption', 'equation', 'itemize', 'enumerate', 'block', 'image', 'tikz'
    content: object
    title: str = ""


@dataclass
class ParsedFrame:
    index: int
    title: str
    elements: List[SlideElement]


@dataclass
class BeamerTheme:
    aspect_ratio: str = "43"
    accent_blue: RGBColor = RGBColor(24, 78, 119)
    soft_blue: RGBColor = RGBColor(234, 242, 250)
    accent_red: RGBColor = RGBColor(192, 57, 43)
    muted_gray: RGBColor = RGBColor(90, 100, 110)
    footline: str = ""
    font_name: str = "Noto Sans"


def parse_preamble(tex: str) -> BeamerTheme:
    theme = BeamerTheme()

    m_ar = re.search(r"\\documentclass\[[^\]]*aspectratio\s*=\s*(\d+)", tex)
    if m_ar:
        theme.aspect_ratio = m_ar.group(1)

    colors = {}
    for m in re.finditer(
        r"\\definecolor\{([^}]+)\}\{RGB\}\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}", tex
    ):
        colors[m.group(1)] = RGBColor(int(m.group(2)), int(m.group(3)), int(m.group(4)))

    if "accentblue" in colors:
        theme.accent_blue = colors["accentblue"]
    if "softblue" in colors:
        theme.soft_blue = colors["softblue"]
    if "accentred" in colors:
        theme.accent_red = colors["accentred"]
    if "mutedgray" in colors:
        theme.muted_gray = colors["mutedgray"]

    m_font = re.search(r"\\babelfont\{(?:sf|rm)\}\{([^}]+)\}", tex)
    if m_font:
        theme.font_name = m_font.group(1).strip()

    m_foot = re.search(r"\\setbeamertemplate\{footline\}\{(.*?)\n\}", tex, re.S)
    if m_foot:
        foot_block = m_foot.group(1)
        m_txt = re.search(r"\\scriptsize\s+([^\n\\{}]+)", foot_block)
        if m_txt:
            theme.footline = m_txt.group(1).replace("---", "—").strip()

    return theme


def parse_list_items(list_body: str) -> List[List[SlideElement]]:
    parts = re.split(r"\\item(?:\[[^\]]*\])?\s*", list_body)
    items: List[List[SlideElement]] = []
    for part in parts[1:]:
        part = part.strip()
        if not part:
            continue
        sub_elems: List[SlideElement] = []
        pattern = re.compile(
            r"(\\\[.*?\\\]|\\begin\{(?:equation\*?|align\*?)\}.*?\\end\{(?:equation\*?|align\*?)\})",
            re.S,
        )
        tokens = pattern.split(part)
        for tok in tokens:
            tok = tok.strip()
            if not tok:
                continue
            if tok.startswith(r"\[") or tok.startswith(r"\begin{"):
                sub_elems.append(SlideElement("equation", format_formula_plain(tok)))
            else:
                runs = parse_inline_runs(tok)
                if runs:
                    sub_elems.append(SlideElement("paragraph", runs))
        if sub_elems:
            items.append(sub_elems)
    return items


def parse_frame_elements(body: str) -> List[SlideElement]:
    elements: List[SlideElement] = []
    pos = 0
    n = len(body)

    token_re = re.compile(
        r"\\begin\{(equation\*?|align\*?|tikzpicture|itemize|enumerate|block|alertblock|exampleblock)\}"
        r"|\\\["
        r"|\\IfFileExists\b"
        r"|\\includegraphics\b",
        re.S,
    )

    def push_text_chunk(chunk: str):
        is_caption = bool(re.search(r"\\scriptsize|\\footnotesize", chunk)) and r"\textbf" not in chunk
        is_heading = bool(re.match(r"^\s*\\textbf\{\\color\{accentblue\}", chunk))
        cleaned = clean_latex_math_spacing(chunk)
        if not cleaned:
            return
        for para in re.split(r"\n\s*\n", cleaned):
            para = para.strip()
            if not para:
                continue
            runs = parse_inline_runs(para)
            if not runs:
                continue
            if is_caption:
                elements.append(SlideElement("caption", runs))
            elif is_heading:
                elements.append(SlideElement("heading", runs))
                is_heading = False
            else:
                elements.append(SlideElement("paragraph", runs))

    while pos < n:
        m = token_re.search(body, pos)
        if not m:
            push_text_chunk(body[pos:])
            break

        if m.start() > pos:
            push_text_chunk(body[pos:m.start()])

        tok = m.group(0)

        if tok == r"\[":
            end = body.find(r"\]", m.end())
            if end == -1:
                pos = m.end()
                continue
            eq_raw = body[m.start():end + 2]
            elements.append(SlideElement("equation", format_formula_plain(eq_raw)))
            pos = end + 2
            continue

        if tok == r"\IfFileExists":
            img_path, p1 = extract_braced(body, m.end())
            _true_branch, p2 = extract_braced(body, p1)
            _false_branch, p3 = extract_braced(body, p2)
            if img_path:
                elements.append(SlideElement("image", img_path.strip()))
            pos = p3
            continue

        if tok == r"\includegraphics":
            _opts, p1 = extract_bracketed(body, m.end())
            img_path, p2 = extract_braced(body, p1)
            if img_path:
                elements.append(SlideElement("image", img_path.strip()))
            pos = p2
            continue

        env = m.group(1)
        end_tag = rf"\end{{{env}}}"
        end = body.find(end_tag, m.end())
        if end == -1:
            pos = m.end()
            continue
        inner = body[m.end():end]
        pos = end + len(end_tag)

        if env in ("equation", "equation*", "align", "align*"):
            elements.append(SlideElement("equation", format_formula_plain(inner)))
        elif env == "tikzpicture":
            elements.append(SlideElement("tikz", inner))
        elif env in ("itemize", "enumerate"):
            items = parse_list_items(inner)
            if items:
                elements.append(SlideElement(env, items))
        elif env in ("block", "alertblock", "exampleblock"):
            btitle, rest_pos = extract_braced(inner, 0)
            bbody = inner[rest_pos:].strip() if btitle is not None else inner.strip()
            elements.append(
                SlideElement("block", parse_inline_runs(bbody), title=(btitle or "").strip())
            )

    return elements


def parse_beamer_tex(tex_path: Path) -> Tuple[BeamerTheme, List[ParsedFrame]]:
    raw = tex_path.read_text(encoding="utf-8")
    tex = strip_latex_comments(raw)
    theme = parse_preamble(tex)

    m_doc = re.search(r"\\begin\{document\}(.*)\\end\{document\}", tex, re.S)
    doc_body = m_doc.group(1) if m_doc else tex

    frames: List[ParsedFrame] = []
    pos = 0
    idx = 0
    while True:
        start = doc_body.find(r"\begin{frame}", pos)
        if start == -1:
            break
        end = doc_body.find(r"\end{frame}", start)
        if end == -1:
            break

        idx += 1
        cur = start + len(r"\begin{frame}")
        _opts, cur = extract_bracketed(doc_body, cur)
        title, cur = extract_braced(doc_body, cur)
        frame_body = doc_body[cur:end]

        if not title:
            m_ft = re.search(r"\\frametitle\{", frame_body)
            if m_ft:
                title, ft_end = extract_braced(frame_body, m_ft.end() - 1)
                frame_body = frame_body[:m_ft.start()] + frame_body[ft_end:]
            else:
                title = f"Diapositiva {idx}"

        title_runs = parse_inline_runs(title)
        title_clean = "".join(seg for seg, _ in title_runs)
        elements = parse_frame_elements(frame_body)
        frames.append(ParsedFrame(index=idx, title=title_clean, elements=elements))
        pos = end + len(r"\end{frame}")

    return theme, frames


def extract_tikz_from_pdf(pdf_path: Optional[Path], slide_index: int, out_dir: Path) -> Optional[Path]:
    if not pdf_path or not pdf_path.exists():
        return None
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    doc = fitz.open(pdf_path)
    if slide_index - 1 >= len(doc):
        doc.close()
        return None

    page = doc[slide_index - 1]
    rect = page.rect
    clip = fitz.Rect(
        rect.width * 0.12,
        rect.height * 0.32,
        rect.width * 0.88,
        rect.height * 0.91,
    )
    out_png = out_dir / f"_tikz_slide_{slide_index}.png"
    pix = page.get_pixmap(clip=clip, dpi=300)
    pix.save(str(out_png))
    doc.close()
    return out_png


def apply_runs_to_paragraph(p, runs: List[Tuple[str, str]], theme: BeamerTheme, base_size: float):
    for seg, style in runs:
        r = p.add_run()
        r.text = seg
        r.font.size = Pt(base_size)
        if style in ("math", "bold_math"):
            r.font.name = "Cambria Math"
            r.font.bold = style == "bold_math"
            r.font.color.rgb = RGBColor(20, 20, 20)
        elif style == "bold":
            r.font.name = theme.font_name
            r.font.bold = True
            r.font.color.rgb = RGBColor(20, 20, 20)
        elif style == "accent_bold":
            r.font.name = theme.font_name
            r.font.bold = True
            r.font.color.rgb = theme.accent_blue
        elif style == "accent":
            r.font.name = theme.font_name
            r.font.color.rgb = theme.accent_blue
        elif style == "italic":
            r.font.name = theme.font_name
            r.font.italic = True
            r.font.color.rgb = RGBColor(20, 20, 20)
        elif style == "alert":
            r.font.name = theme.font_name
            r.font.bold = True
            r.font.color.rgb = theme.accent_red
        elif style == "url":
            r.font.name = theme.font_name
            r.font.size = Pt(max(base_size - 2, 11))
            r.font.color.rgb = theme.accent_blue
        else:
            r.font.name = theme.font_name
            r.font.color.rgb = RGBColor(20, 20, 20)


def estimate_text_height(runs: List[Tuple[str, str]], width_in: float, font_pt: float) -> float:
    total_chars = sum(len(s) for s, _ in runs)
    newlines = sum(s.count("\n") for s, _ in runs)
    chars_per_line = max(int((width_in * 72.0) / (font_pt * 0.56)), 20)
    lines = max(1, math.ceil(total_chars / chars_per_line)) + newlines
    return lines * (font_pt / 72.0) * 1.42 + 0.16


def build_pptx(
    theme: BeamerTheme,
    frames: List[ParsedFrame],
    tex_dir: Path,
    pdf_path: Optional[Path],
    out_pptx: Path,
) -> None:
    prs = Presentation()
    if theme.aspect_ratio == "169":
        slide_w, slide_h = 13.333, 7.5
    else:
        slide_w, slide_h = 10.0, 7.5

    prs.slide_width = Inches(slide_w)
    prs.slide_height = Inches(slide_h)

    total_slides = len(frames)
    margin_x = 0.55
    content_w = slide_w - 2 * margin_x
    header_h = 0.86
    footer_y = slide_h - 0.42
    usable_bottom = footer_y - 0.18

    for frame in frames:
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        hdr = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(slide_w), Inches(header_h)
        )
        hdr.fill.solid()
        hdr.fill.fore_color.rgb = theme.accent_blue
        hdr.line.fill.background()
        tf_h = hdr.text_frame
        tf_h.word_wrap = True
        tf_h.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf_h.margin_left = Inches(0.4)
        tf_h.margin_right = Inches(0.4)
        p_h = tf_h.paragraphs[0]
        p_h.text = frame.title
        p_h.font.name = theme.font_name
        p_h.font.size = Pt(20)
        p_h.font.bold = True
        p_h.font.color.rgb = RGBColor(255, 255, 255)

        if theme.footline:
            fl = slide.shapes.add_textbox(Inches(0.35), Inches(footer_y), Inches(slide_w - 2.0), Inches(0.32))
            p_fl = fl.text_frame.paragraphs[0]
            p_fl.text = theme.footline
            p_fl.font.name = theme.font_name
            p_fl.font.size = Pt(10)
            p_fl.font.color.rgb = theme.muted_gray

        fr = slide.shapes.add_textbox(Inches(slide_w - 1.55), Inches(footer_y), Inches(1.2), Inches(0.32))
        p_fr = fr.text_frame.paragraphs[0]
        p_fr.alignment = PP_ALIGN.RIGHT
        p_fr.text = f"{frame.index} / {total_slides}"
        p_fr.font.name = theme.font_name
        p_fr.font.size = Pt(10)
        p_fr.font.bold = True
        p_fr.font.color.rgb = theme.accent_blue

        cur_y = header_h + 0.28

        for el_idx, el in enumerate(frame.elements):
            remaining_h = max(usable_bottom - cur_y, 0.8)

            if el.kind == "heading":
                h = estimate_text_height(el.content, content_w, 17)
                box = slide.shapes.add_textbox(Inches(margin_x), Inches(cur_y), Inches(content_w), Inches(h))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                apply_runs_to_paragraph(p, el.content, theme, 17)
                cur_y += h + 0.06

            elif el.kind == "paragraph":
                h = estimate_text_height(el.content, content_w, 16)
                box = slide.shapes.add_textbox(Inches(margin_x), Inches(cur_y), Inches(content_w), Inches(h))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.line_spacing = 1.2
                apply_runs_to_paragraph(p, el.content, theme, 16)
                cur_y += h + 0.08

            elif el.kind == "caption":
                h = estimate_text_height(el.content, content_w, 12)
                box = slide.shapes.add_textbox(Inches(margin_x), Inches(cur_y), Inches(content_w), Inches(h))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER
                apply_runs_to_paragraph(p, el.content, theme, 12)
                for r in p.runs:
                    r.font.color.rgb = theme.muted_gray
                cur_y += h + 0.06

            elif el.kind == "equation":
                eq_str = str(el.content)
                eq_size = 16 if len(eq_str) > 95 else 18
                h = 0.88 if r"\frac" in eq_str or r"\iint" in eq_str or r"\underbrace" in eq_str else 0.65
                box = slide.shapes.add_textbox(Inches(margin_x), Inches(cur_y), Inches(content_w), Inches(h))
                tf = box.text_frame
                tf.word_wrap = True
                tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                p = tf.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER
                p.text = eq_str
                p.font.name = "Cambria Math"
                p.font.size = Pt(eq_size)
                p.font.color.rgb = RGBColor(20, 20, 20)
                cur_y += h + 0.14

            elif el.kind in ("itemize", "enumerate"):
                for item_idx, sub_elems in enumerate(el.content, start=1):
                    bullet_prefix = "•  " if el.kind == "itemize" else f"{item_idx}. "
                    first_para = True
                    for sub in sub_elems:
                        if sub.kind == "paragraph":
                            h = estimate_text_height(sub.content, content_w - 0.15, 16)
                            box = slide.shapes.add_textbox(
                                Inches(margin_x + 0.05), Inches(cur_y), Inches(content_w - 0.1), Inches(h)
                            )
                            tf = box.text_frame
                            tf.word_wrap = True
                            p = tf.paragraphs[0]
                            p.line_spacing = 1.2
                            if first_para:
                                rb = p.add_run()
                                rb.text = bullet_prefix
                                rb.font.name = theme.font_name
                                rb.font.size = Pt(16)
                                rb.font.bold = True
                                rb.font.color.rgb = theme.accent_blue
                                first_para = False
                            apply_runs_to_paragraph(p, sub.content, theme, 16)
                            cur_y += h + 0.08
                        elif sub.kind == "equation":
                            eq_str = str(sub.content)
                            h = 0.88 if r"\frac" in eq_str or r"\underbrace" in eq_str else 0.65
                            box = slide.shapes.add_textbox(
                                Inches(margin_x + 0.2), Inches(cur_y), Inches(content_w - 0.4), Inches(h)
                            )
                            tf = box.text_frame
                            tf.word_wrap = True
                            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                            p = tf.paragraphs[0]
                            p.alignment = PP_ALIGN.CENTER
                            p.text = eq_str
                            p.font.name = "Cambria Math"
                            p.font.size = Pt(17)
                            p.font.color.rgb = RGBColor(20, 20, 20)
                            cur_y += h + 0.14

            elif el.kind == "block":
                body_h = estimate_text_height(el.content, content_w - 0.4, 15) + 0.28
                hdr_bh = 0.46
                if len(frame.elements) == 1:
                    cur_y = max(cur_y, header_h + (usable_bottom - header_h - (hdr_bh + body_h)) / 2)

                bhdr = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE, Inches(margin_x), Inches(cur_y), Inches(content_w), Inches(hdr_bh)
                )
                bhdr.fill.solid()
                bhdr.fill.fore_color.rgb = theme.accent_blue
                bhdr.line.fill.background()
                tf_bh = bhdr.text_frame
                tf_bh.vertical_anchor = MSO_ANCHOR.MIDDLE
                tf_bh.margin_left = Inches(0.18)
                p_bh = tf_bh.paragraphs[0]
                p_bh.text = el.title
                p_bh.font.name = theme.font_name
                p_bh.font.size = Pt(15)
                p_bh.font.bold = True
                p_bh.font.color.rgb = RGBColor(255, 255, 255)

                bbody = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE,
                    Inches(margin_x),
                    Inches(cur_y + hdr_bh),
                    Inches(content_w),
                    Inches(body_h),
                )
                bbody.fill.solid()
                bbody.fill.fore_color.rgb = theme.soft_blue
                bbody.line.fill.background()
                tf_bb = bbody.text_frame
                tf_bb.word_wrap = True
                tf_bb.margin_left = Inches(0.22)
                tf_bb.margin_right = Inches(0.22)
                tf_bb.margin_top = Inches(0.14)
                p_bb = tf_bb.paragraphs[0]
                p_bb.line_spacing = 1.25
                apply_runs_to_paragraph(p_bb, el.content, theme, 15)
                cur_y += hdr_bh + body_h + 0.16

            elif el.kind in ("image", "tikz"):
                has_next_caption = (
                    el_idx + 1 < len(frame.elements) and frame.elements[el_idx + 1].kind == "caption"
                )
                max_h = max(remaining_h - (0.65 if has_next_caption else 0.15), 1.5)
                max_w = content_w

                if el.kind == "image":
                    img_path = (tex_dir / str(el.content)).resolve()
                    placeholder_msg = f"[Imagen no encontrada: {el.content}]"
                else:
                    img_path = extract_tikz_from_pdf(pdf_path, frame.index, tex_dir)
                    placeholder_msg = (
                        f"[Diagrama TikZ — Slide {frame.index}]\n"
                        "Instala PyMuPDF (pip install pymupdf) y coloca el PDF compilado "
                        "en la misma carpeta para insertarlo automáticamente."
                    )

                if img_path and img_path.exists():
                    pic = slide.shapes.add_picture(str(img_path), Inches(margin_x), Inches(cur_y))
                    ratio = min(Inches(max_w) / pic.width, Inches(max_h) / pic.height)
                    pic.width = int(pic.width * ratio)
                    pic.height = int(pic.height * ratio)
                    pic.left = int(Inches(margin_x) + (Inches(max_w) - pic.width) / 2)
                    pic.top = int(Inches(cur_y) + (Inches(max_h) - pic.height) / 2)
                else:
                    ph = slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE, Inches(margin_x), Inches(cur_y), Inches(max_w), Inches(max_h)
                    )
                    ph.fill.solid()
                    ph.fill.fore_color.rgb = theme.soft_blue
                    ph.line.color.rgb = theme.muted_gray
                    tf_p = ph.text_frame
                    tf_p.word_wrap = True
                    tf_p.vertical_anchor = MSO_ANCHOR.MIDDLE
                    p_p = tf_p.paragraphs[0]
                    p_p.alignment = PP_ALIGN.CENTER
                    p_p.text = placeholder_msg
                    p_p.font.name = theme.font_name
                    p_p.font.size = Pt(13)
                    p_p.font.color.rgb = theme.muted_gray

                cur_y += max_h + 0.12

    prs.save(str(out_pptx))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convierte un archivo Beamer (.tex) en PowerPoint (.pptx) sin delimitadores de fórmula."
    )
    parser.add_argument("tex_file", type=Path, help="Ruta al archivo .tex de Beamer.")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Ruta de salida .pptx.")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="PDF compilado opcional para extraer automáticamente los diagramas TikZ.",
    )
    args = parser.parse_args()

    tex_path: Path = args.tex_file.resolve()
    if not tex_path.exists():
        print(f"Error: no se encuentra {tex_path}", file=sys.stderr)
        return 1

    out_pptx = args.output.resolve() if args.output else tex_path.with_suffix(".pptx")
    pdf_path = args.pdf.resolve() if args.pdf else tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        pdf_path = None

    theme, frames = parse_beamer_tex(tex_path)
    print(f"Parseadas {len(frames)} diapositivas (aspectratio={theme.aspect_ratio}) desde {tex_path.name}")
    build_pptx(theme, frames, tex_path.parent, pdf_path, out_pptx)
    print(f"Presentación generada -> {out_pptx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
