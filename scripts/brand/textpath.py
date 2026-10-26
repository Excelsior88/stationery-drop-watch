"""Shape text with HarfBuzz and emit SVG path data (font-independent wordmark)."""
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

def text_path(fontfile, text, size, x=0.0, y=0.0, variations=None, features=None, tracking=0.0):
    blob = hb.Blob.from_file_path(fontfile)
    face = hb.Face(blob)
    font = hb.Font(face)
    upem = face.upem
    if variations:
        font.set_variations(variations)
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf, features or {"kern": True, "liga": True})
    s = size / upem
    pen = SVGPathPen(None)
    cx = 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        tp = TransformPen(pen, (s, 0, 0, -s, x + (cx + pos.x_offset) * s, y - pos.y_offset * s))
        font.draw_glyph_with_pen(info.codepoint, tp)
        cx += pos.x_advance + tracking * upem
    return pen.getCommands(), cx * s

def metrics(fontfile, variations=None):
    face = hb.Face(hb.Blob.from_file_path(fontfile)); font = hb.Font(face)
    if variations: font.set_variations(variations)
    ext = font.get_font_extents("ltr")
    return face.upem, ext
