#!/usr/bin/env python3
"""Test pypass cli test."""
from pypass import EX_PARSE
from pypass import main


def test_cli() -> None:

    data = main(EX_PARSE.parse_args(["-e", "5", "-d", "./tests/test_db/"]))

    assert len(data) == 5
