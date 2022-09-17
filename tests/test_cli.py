#!/usr/bin/env python3
"""Test pypass cli test."""
import pytest

from pypass import EX_PARSE
from pypass import main


def test_cli() -> None:
    main(EX_PARSE.parse_args(["-e", "5"]))
