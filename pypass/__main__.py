#!/usr/bin/env python3
import argparse

from pypass import __version__
from pypass import EX_PARSE
from pypass import main


if __name__ == "__main__":
    print(f"pypass version {__version__}.")
    main(EX_PARSE.parse_args())
