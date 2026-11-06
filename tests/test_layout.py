"""Plate packing."""
from __future__ import annotations

import pytest

from ziptag.layout import LayoutError, Rect, pack

USABLE = Rect(5, 5, 251, 251)
TOWER = Rect(190, 205, 250, 250)


def _boxes_overlap(a, b, sizes):
    (la, wa), (lb, wb) = sizes[a.index], sizes[b.index]
    return a.x < b.x + lb and b.x < a.x + la and a.y < b.y + wb and b.y < a.y + wa


@pytest.mark.parametrize("count,size", [(1, (72, 16)), (16, (72, 16)), (40, (72, 16)), (40, (105, 24)),
                                        (40, (50, 8))])
def test_no_overlap_inside_plate_and_order_kept(count, size):
    sizes = [size] * count
    plates = pack(sizes, USABLE, (TOWER,))
    placed = [p for plate in plates for p in plate]
    assert [p.index for p in placed] == list(range(count))
    for plate in plates:
        for i, a in enumerate(plate):
            assert a.x >= USABLE.x0 and a.y >= USABLE.y0
            assert a.x + size[0] <= USABLE.x1 + 1e-9 and a.y + size[1] <= USABLE.y1 + 1e-9
            assert not Rect(a.x, a.y, a.x + size[0], a.y + size[1]).overlaps(TOWER)
            assert not any(_boxes_overlap(a, b, sizes) for b in plate[i + 1:])


def test_many_big_tags_use_several_plates():
    assert len(pack([(105, 24)] * 40, USABLE, ())) >= 3


def test_tag_larger_than_plate_is_an_error():
    with pytest.raises(LayoutError):
        pack([(300, 16)], USABLE, ())
