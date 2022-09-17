#!/usr/bin/env python3
import argparse
from typing import Any

from pypass.quaeldich import extract_pass_data

__version__ = "0.0.1"

EX_PARSE = argparse.ArgumentParser(
    prog="pypass",
    description="Python interface to access data in quaeldich.de",
)
EX_PARSE.add_argument(
    "-e",
    "--extract",
    metavar="value",
    help="extract n number of data from quaeldich.de.",
    type=int,
)


def main(argv: Any) -> None:

    n_pass = argv.extract
    extract_pass_data(pass_counts=n_pass if n_pass > 0 else None)
