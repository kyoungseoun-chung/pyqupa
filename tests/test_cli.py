#!/usr/bin/env python3
"""Test pypass cli test."""
from pypass import EX_PARSE
from pypass import main
from pypass.passes import Pass


def test_cli() -> None:

    data = main(EX_PARSE.parse_args(["-e", "6", "-d", "./tests/test_db/"]))

    assert len(data) == 6

    pass_list = [Pass(**d) for d in data]

    assert len(pass_list) == 6
