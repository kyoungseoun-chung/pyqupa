#!/usr/bin/env python3

from pypass.quaeldich import (
    get_total_pass_count,
    extract_pass_data,
    PASS_NAME_DB_LOC,
)
from pypass.passes import (
    search_pass_by_name,
    search_pass_by_distance,
    search_pass_by_height,
    search_pass_by_region,
)

from tinydb import TinyDB


def test_pass_data() -> None:

    counts = get_total_pass_count()
    res = extract_pass_data(db_overwrite=True, pass_counts=10)
    Pass, _ = search_pass_by_name("Mont Ventoux")
    Pass_elv = search_pass_by_height([1800, 2000])

    Pass_alt, _ = search_pass_by_name("Passo dello Stelvio")
    Pass_wrong, suggested = search_pass_by_name("passo Stelvio")

    print(Pass)


if __name__ == "__main__":
    test_pass_data()
