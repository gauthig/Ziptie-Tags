"""Tag geometry, text fitting and fonts."""
from __future__ import annotations

import pytest
from manifold3d import Error

from ziptag import constants as c
from ziptag.fonts import load_font
from ziptag.geometry import Align, FitStatus, TagSpec, build_tag, dimensions, fit_text


def test_ten_fonts_are_bundled(fonts):
    assert len(fonts) == 10


@pytest.mark.parametrize("name", ["Roboto", "Open Sans", "Lato", "Montserrat", "Oswald", "Source Sans 3",
                                  "Noto Sans", "Roboto Condensed", "Poppins", "Inter"])
def test_every_font_builds_a_valid_tag(fonts, name):
    tag = build_tag(load_font(fonts[name]), TagSpec("Cable 12 & Ant-3/B #4 aeiou"))
    assert not tag.body.is_empty() and tag.inlay is not None
    assert tag.body.status() == Error.NoError
    assert tag.inlay.status() == Error.NoError


def test_inlay_fills_recess_exactly(roboto):
    plain = build_tag(roboto, TagSpec(""))
    tag = build_tag(roboto, TagSpec("HEX BEAM"))
    assert tag.body.volume() + tag.inlay.volume() == pytest.approx(plain.body.volume(), rel=1e-3)


@pytest.mark.parametrize("pct", [50, 100, 150])
def test_slider_scales_footprint_but_not_thickness_or_slot(roboto, pct):
    tag = build_tag(roboto, TagSpec("TAG", size_pct=pct))
    box = tag.body.bounding_box()            # (xmin, ymin, zmin, xmax, ymax, zmax)
    assert box[3] == pytest.approx(c.ZIP_SECTION + c.BASE_LABEL_LENGTH * pct / 100)
    assert box[4] == pytest.approx(c.BASE_WIDTH * pct / 100)
    assert box[5] == pytest.approx(c.THICKNESS)
    d = dimensions(pct)
    assert d.thickness == c.THICKNESS
    # the slot removed is constant in X and Z: body = full block - slot - text recess
    block = d.length * d.width * d.thickness
    slot = (c.SLOT_X1 - c.SLOT_X0) * d.width * (c.SLOT_Z1 - c.SLOT_Z0)
    assert tag.body.volume() == pytest.approx(block - slot - tag.inlay.volume(), rel=1e-3)


def test_default_tags_fit_at_standard_size(roboto):
    for text in ("HEX BEAM", "VERTICAL"):
        fit = fit_text(roboto, TagSpec(text))
        assert fit.status is FitStatus.OK and fit.pct == pytest.approx(100)


def test_auto_fit_shrinks_long_text(roboto):
    fit = fit_text(roboto, TagSpec("A LONGER TAG NAME HERE"))
    assert fit.status in (FitStatus.SHRUNK, FitStatus.TOO_SMALL) and fit.pct < 100


def test_overflow_is_reported_per_tag_and_clipped(roboto):
    spec = TagSpec("THIS TEXT IS FAR TOO LONG FOR ANY TAG", text_pct=100)
    fit = fit_text(roboto, spec)
    assert fit.status is FitStatus.OVERFLOW and fit.overflow_mm > 5
    box = build_tag(roboto, spec).inlay.bounding_box()
    assert box[0] >= c.ZIP_SECTION + c.WALL - 1e-6
    assert box[3] <= dimensions(100).length - c.WALL + 1e-6


def test_manual_size_overrides_auto(roboto):
    assert fit_text(roboto, TagSpec("AB", text_pct=60)).pct == pytest.approx(60)


def test_tiny_text_warns(roboto):
    fit = fit_text(roboto, TagSpec("AB", size_pct=50, text_pct=50))
    assert fit.status is FitStatus.TOO_SMALL


@pytest.mark.parametrize("align", list(Align))
def test_alignment_positions_text(roboto, align):
    box = build_tag(roboto, TagSpec("AB", align=align)).inlay.bounding_box()
    left, right = c.ZIP_SECTION + c.MARGIN_X, dimensions(100).length - c.MARGIN_X
    if align is Align.LEFT:
        assert box[0] == pytest.approx(left, abs=0.3)
    elif align is Align.RIGHT:
        assert box[3] == pytest.approx(right, abs=0.3)
    else:
        assert (box[0] + box[3]) / 2 == pytest.approx((left + right) / 2, abs=0.3)


def test_empty_text_makes_plain_tag(roboto):
    assert build_tag(roboto, TagSpec("   ")).inlay is None


def test_unknown_characters_fall_back(roboto):
    assert build_tag(roboto, TagSpec("☃ snow")).inlay is not None
