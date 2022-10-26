#!/usr/bin/env python3
"""Test pyqupa cli test."""
from pyqupa import EX_PARSE
from pyqupa import main
from pyqupa.passes import Pass


def test_cli() -> None:

    data = main(EX_PARSE.parse_args(["-e", "6", "-d", "./tests/test_db/"]))

    assert len(data) == 6

    pass_list = [Pass(**d) for d in data]

    assert len(pass_list) == 6
