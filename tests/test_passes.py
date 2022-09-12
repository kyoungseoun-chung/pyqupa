#!/usr/bin/env python3
from tinydb import TinyDB

from pypass.passes import search_pass_by_distance
from pypass.passes import search_pass_by_height
from pypass.passes import search_pass_by_name
from pypass.passes import search_pass_by_region
from pypass.quaeldich import extract_pass_data
from pypass.quaeldich import get_total_pass_count
from pypass.quaeldich import PASS_NAME_DB_LOC


def test_pass_data() -> None:

    counts = get_total_pass_count()
    res = extract_pass_data(db_overwrite=False, pass_counts=5)
    Pass, _ = search_pass_by_name("Mont Ventoux")
    Pass_elv = search_pass_by_height([1800, 2000])
    Pass_dist = search_pass_by_distance([10.0, 15.0])

    Pass_alt, _ = search_pass_by_name("Passo dello Stelvio")
    Pass_wrong, suggested = search_pass_by_name("passo Stelvio")

    print(Pass)


if __name__ == "__main__":
    test_pass_data()
