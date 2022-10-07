#!/usr/bin/env python3
import argparse
from typing import Any

from pypass.quaeldich import extract_pass_data

__version__ = "0.1.0"

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
EX_PARSE.add_argument(
    "-d",
    "--directory",
    metavar="directory",
    help="db directory path to be saved.",
    type=str,
)


def main(argv: Any) -> list[dict]:

    try:
        db_loc = argv.directory
    except AttributeError:
        db_loc = None

    n_pass = argv.extract
    data = extract_pass_data(
        db_loc=db_loc, pass_counts=n_pass if n_pass > 0 else None
    )

    return data
