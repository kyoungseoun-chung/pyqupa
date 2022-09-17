#!/usr/bin/env python3
import asyncio
from time import perf_counter
from typing import Any

import pytest

from pypass.passes import PassDB
from pypass.quaeldich import extract_pass_data
from pypass.quaeldich import get_total_pass_count


def test_data_extraction() -> None:
    counts = get_total_pass_count()

    assert counts >= 7794

    data = extract_pass_data(
        db_overwrite=False, db_loc="./tests/test_db/", pass_counts=5
    )

    assert len(data) == 5


def test_pass_data() -> None:

    passdb = PassDB("./tests/test_db/")
    Pass = passdb.search("Mont Ventoux", "name")
    assert Pass[0].name == "Mont Ventoux"

    # Search with alternative anme
    Pass_alt = passdb.search("Passo dello Stelvio", "name")
    assert Pass_alt[0].name == "Stilfser Joch"

    Pass_cou = passdb.search("italien", "country")
    assert len(Pass_cou) == 3
    assert Pass_cou[0].country == "italien"

    Pass_reg = passdb.search("alpen", "region")
    assert len(Pass_reg) == 4
    assert Pass_reg[0].region == "alpen"

    Pass_hei = passdb.search([1800, 2000], "height")
    assert len(Pass_hei) == 1
    assert Pass_hei[0].height == 1909

    Pass_dist = passdb.search([10.0, 15.0], "distance")
    assert len(Pass_dist) == 2
    assert Pass_dist[0].total_distance == [12.5]

    Pass_elev = passdb.search([500, 1000], "elevation")
    assert len(Pass_elev) == 2
    assert Pass_elev[0].total_elevation == [647, 774]

    with pytest.raises(Exception):
        passdb.search("Mont Vento", "name")
