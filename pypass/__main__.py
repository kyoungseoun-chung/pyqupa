#!/usr/bin/env python3
import os
import sys

from streamlit import config as _config
from streamlit.web import bootstrap

from pypass import __version__
from pypass import EX_PARSE
from pypass import main


if __name__ == "__main__":

    if "--gui" in sys.argv or "-g" in sys.argv:

        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, "app.py")

        _config.set_option("server.headless", True)
        bootstrap.run(filename, "", [], flag_options={})

    else:
        print(f"pypass version {__version__}.")
        main(EX_PARSE.parse_args())
