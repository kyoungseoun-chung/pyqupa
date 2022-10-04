#!/usr/bin/env python3
"""Retrieve pass data from https://www.quaeldich.de/.

Note: Not all data are stored correctly. This code will exclude any incomplete Pass data.
"""
import os
import sys
import warnings
from http import HTTPStatus
from pathlib import Path
from typing import Any
from typing import Optional
from unicodedata import combining
from unicodedata import normalize

import bs4
import requests
from bs4 import BeautifulSoup as bs
from rich.progress import Progress
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.progress import TimeRemainingColumn
from tinydb import Query
from tinydb import TinyDB

from pypass.tools import system_logger

DB_LOC = os.path.dirname(__file__) + "/db/"
PASS_DB = "passes.json"
PASS_NAME_DB = "pass_names.json"

BASE_URL = "https://www.quaeldich.de"
BASE_PASS_URL = "https://www.quaeldich.de/paesse/"
GERMAN_COMPASS_CONVERTER = {
    "nord": "North",
    "süd": "South",
    "west": "West",
    "ost": "East",
}
GERMAN_ROAD_TYPE_CONVERTER = {
    "rampe": " Side",
    "anfahrt": " Side",
    "auffahrt": " Side",
}
GERMAN_PREP_CONVERTER = {"von": "from", "ab": "from", "über": "via"}
GERMAN_SPECIAL_CHARACTOR_CONVERTER = {
    "ü": "ue",
    "ö": "oe",
    "ä": "ae",
    "ß": "ss",
}


LATIN = "ä  æ  ǽ  đ ð ƒ ħ ı ł ø ǿ ö  œ  ß  ŧ ü ß"
ASCII = "ae ae ae d d f h i l o o oe oe ss t ue ss"


TIME_REMAIN_COLUMN = TimeRemainingColumn()
TIME_COLUMN = TimeElapsedColumn()
TEXT_COLUMN = TextColumn("{task.description}")


def remove_diacritics(
    s: str,
    outliers=str.maketrans(dict(zip(LATIN.split(), ASCII.split()))),
):
    return "".join(
        c
        for c in normalize("NFD", s.lower().translate(outliers))
        if not combining(c)
    )


def get_total_pass_count() -> int:
    """Obtain total number of passes listed in quaeldich website.

    Returns:
        int: Number of total passes.
    """

    html_id = "qd_list_template_paesse_total_count"

    r = requests.get(BASE_PASS_URL)
    soup = bs(r.text, "lxml")

    total_counts = soup.find(id=html_id)

    if total_counts is not None:
        total_counts = int(total_counts.text)
    else:
        raise RuntimeError(f"Quaeldich: Total pass count is not found!")

    return total_counts


def extract_pass_data(
    db_overwrite: bool = False,
    db_loc: Optional[str] = DB_LOC,
    pass_counts: Optional[int] = None,
) -> list[dict]:
    """Get pass data from quaeldich website.

    Data contains:
        - Pass name and alternative name if exists.
        - Pass region.
        - Pathes to the peak.
        - Altitude at the peak.

    Note:
        - If `pass_counts` is given, first `pass_counts` number of the pass list in "www.quaeldich.de/passes/".
          Therefore, this parameter is mainly used for debugging purpose.

    Args:
        pass_counts (int, optional): Number of pass to be extracted. Defaults to None.

    Returns:
        list[dict]: Return pass data extracted.
    """

    if db_loc is None:
        db_loc = DB_LOC

    if pass_counts is None:
        pass_counts = get_total_pass_count()

    db_loc_full = Path(db_loc) / Path(PASS_DB)
    name_db_loc_full = Path(db_loc) / Path(PASS_NAME_DB)

    if not db_overwrite:
        # Remove all databases
        if Path(name_db_loc_full).exists():
            Path(name_db_loc_full).unlink()

        if Path(db_loc_full).exists():
            Path(db_loc_full).unlink()

    system_logger("QUAELDICH", "start data extraction!")
    with Progress(TEXT_COLUMN, TIME_COLUMN) as progress:

        progress.add_task("[cyan]Etracting html elements...")
        html_pass_list = get_html_components(pass_counts)

        # Sanity check.
        assert (
            len(html_pass_list) == pass_counts
        ), f"Pass: There is mismatch in number of passes - get {len(html_pass_list)} but registed {pass_counts}."

    all_passes = []
    all_names = []
    all_alts = []

    total_list = len(html_pass_list)
    with Progress(TEXT_COLUMN, TIME_COLUMN, TIME_REMAIN_COLUMN) as progress:

        task = progress.add_task(
            f"[cyan]Processing data... # 0/{total_list}", total=total_list
        )

        for idx, li in enumerate(html_pass_list):

            pass_data = get_pass_data(li)

            if pass_data["status"] == HTTPStatus.NOT_FOUND:
                continue
            else:
                del pass_data["status"]

            db = TinyDB(db_loc_full)
            if db_overwrite:
                searched = db.search(Query().name == pass_data["name"])
                if len(searched) > 0:
                    db.update(pass_data, Query().name == pass_data["name"])
                else:
                    db.insert(pass_data)
            else:
                # Remove and save
                db.insert(pass_data)

            all_alts.append(pass_data["alt"])
            all_names.append(pass_data["name"])
            all_passes.append(pass_data)

            progress.update(
                task,
                description=f"[cyan]Processing data... # {idx+1}/{total_list}",
                advance=1,
            )

    db = TinyDB(name_db_loc_full)
    if db_overwrite:
        db.update({"names": all_names, "alts": all_alts})
    else:
        db.insert({"names": all_names, "alts": all_alts})
    system_logger("QUAELDICH", "finished!")

    return all_passes


def get_html_components(pass_counts: int) -> bs4.ResultSet:
    """Extract all html component for `pass_counts` number of listed Passes in quaeldich.de."""

    html_id = "qd_list_template_paesse_list"

    r = requests.get(BASE_PASS_URL + f"?n={pass_counts}")
    html_pass_list = bs(r.text, "lxml").find(id=html_id).findAll("li")

    return html_pass_list


def get_pass_data(li: Any) -> dict[str, Any]:

    status = HTTPStatus.OK

    row = li.find("div", {"class": "row"})
    all_divs = row.findAll("div")
    all_links = [href["href"] for href in row.findAll("a", href=True)]
    pass_url = BASE_URL + all_links[0]

    region_info = _get_pass_region(all_links, pass_url)

    if region_info["status"] == HTTPStatus.NOT_FOUND:
        warnings.warn(region_info["msg"], RuntimeWarning)
        return {"status": HTTPStatus.NOT_FOUND}
    else:
        country = region_info["country"]
        region = region_info["region"]

    # Clean up extracted text
    data = [
        (div.get_text())
        .replace("\n", "")
        .replace("\r", "")
        .replace("quaeldich-Reise", "")
        .strip()
        for div in all_divs
    ]

    # Extract brief path info and translate german to english
    all_from_to = []
    for ft in data[6::3]:
        _, ft = _convert_german(ft)
        all_from_to.append(ft)

    coord_info = _get_pass_coord(pass_url)
    if coord_info["status"] == HTTPStatus.NOT_FOUND:
        warnings.warn(coord_info["msg"], RuntimeWarning)
        return {"status": HTTPStatus.NOT_FOUND}
    else:
        pass_coord = coord_info["coord"]

    # Extract all path data
    path_info = _get_path_info(pass_url)
    if path_info["status"] == HTTPStatus.NOT_FOUND:
        warnings.warn(path_info["msg"], RuntimeWarning)
        return {"status": HTTPStatus.NOT_FOUND}
    else:
        path_urls = path_info["path_urls"]
        path_gpt_js = path_info["path_gpt_js"]
        gpt_dict = {}
        for i, (gjs, ft, purl) in enumerate(
            zip(path_gpt_js, all_from_to, path_urls)
        ):
            gpt_dict.update({i: {"name": ft, "url": purl, "gpt": gjs}})

    return {
        "name": data[0],
        "coord": pass_coord,
        "alt": data[3],
        "country": country,
        "region": region,
        "height": int(data[2].strip(" m")),
        "total_distance": path_info["distance"],
        "total_elevation": path_info["elevation"],
        "avg_grad": path_info["gradient"],
        "max_distance": max(path_info["distance"]),
        "min_distance": min(path_info["distance"]),
        "max_elevation": max(path_info["elevation"]),
        "min_elevation": min(path_info["elevation"]),
        "url": pass_url,
        "gpts": gpt_dict,
        "status": status,
    }


def _get_pass_region(all_links: list[str], pass_url: str) -> dict[str, Any]:

    status = HTTPStatus.OK
    msg = ""

    try:
        country = (
            all_links[1]
            .replace(BASE_URL + "/regionen/", "")
            .replace("/paesse/", "")
            .lower()
        )

        region = (
            all_links[2]
            .replace(BASE_URL + "/regionen/", "")
            .replace("/paesse/", "")
            .lower()
        )

    except IndexError:
        country = ""
        region = ""

        status = HTTPStatus.NOT_FOUND
        msg = f"Quaeldich: country and region information cannot be found in {pass_url}!"

    return {"country": country, "region": region, "status": status, "msg": msg}


def _get_pass_coord(pass_url: str) -> dict[str, Any]:

    status = HTTPStatus.OK
    msg = ""

    try:
        coord_string = (
            bs(requests.get(pass_url).text, "lxml")
            .find("div", {"class": "coords"})
            .find("a", {"class": "external"})
            .text
        ).split(",")
        coord = [float(coord) for coord in coord_string]
    except AttributeError:
        # Store wrong data
        coord = []
        status = HTTPStatus.NOT_FOUND
        msg = f"Quaeldich: No coordinate information found in {pass_url}!"

    return {"coord": coord, "status": status, "msg": msg}


def _get_path_info(pass_url) -> dict[str, Any]:
    # Extract path urls
    # Get path id
    # Obtain path gpt

    path_divs = bs(requests.get(pass_url).text, "lxml").find_all(
        "div", {"class": "panel panel-default"}
    )

    path_urls: list[str] = []
    distance: list[float] = []
    elevation: list[int] = []
    gradient: list[float] = []
    path_gpt_js: list[str] = []
    msg: str = ""

    for pdiv in path_divs:
        # Extract path urls
        links = pdiv.find_all("a", href=True)

        has_profile = False
        for li in links:
            if li["href"].find("/profile/") >= 0:
                path_urls.append(li["href"])
                has_profile = True

        # Get path ids
        if has_profile:
            infos = pdiv.find_all("small")

            for info in infos:
                if "km" in info.text and "Hm" in info.text and "%" in info.text:
                    data_extracted = info.text.replace(" ", "").split("|")
                    distance.append(
                        float(
                            data_extracted[0]
                            .replace(",", ".")
                            .replace("km", "")
                        )
                    )
                    elevation.append(
                        int(
                            data_extracted[1]
                            .replace(",", ".")
                            .replace("Hm", "")
                        )
                    )
                    gradient.append(
                        float(
                            data_extracted[2].replace(",", ".").replace("%", "")
                        )
                    )
            path_ids_container = pdiv.find_all("img")

            for img in path_ids_container:
                if img["src"].find("gradient") >= 0:
                    path_id = (
                        img["src"]
                        .replace("/qdtp/anfahrten/", "")
                        .replace("_gradient_600_50.gif", "")
                    )
                    path_gpt_js.append(
                        f"{BASE_URL}/qdtp/anfahrten/{path_id}.json"
                    )
    if len(path_urls) == 0:
        msg = f"Quaeldich: path urls cannot be found! Check input pass_url:\n{pass_url}"
        return {"status": HTTPStatus.NOT_FOUND, "msg": msg}

    if len(distance) == 0 or len(elevation) == 0 or len(gradient) == 0:
        msg = f"Quaeldich: Basic information (km, Hm, and %) cannot be found! Check input pass_url:\n{pass_url}"
        return {"status": HTTPStatus.NOT_FOUND, "msg": msg}

    if len(path_gpt_js) == 0:
        msg = f"Quaeldich: path gpt data cannot be found! Check input pass_url:\n{pass_url}"
        return {"status": HTTPStatus.NOT_FOUND, "msg": msg}

    if (
        not len(path_urls)
        == len(distance)
        == len(elevation)
        == len(gradient)
        == len(path_gpt_js)
    ):
        msg = (
            f"Quaeldich: path data mismatch! Check input pass_url:\n{pass_url}"
        )
        return {"status": HTTPStatus.NOT_FOUND, "msg": msg}

    return {
        "path_urls": path_urls,
        "distance": distance,
        "elevation": elevation,
        "gradient": gradient,
        "path_gpt_js": path_gpt_js,
        "status": HTTPStatus.OK,
        "msg": msg,
    }


def _convert_german(ft: str) -> tuple[str, str]:
    """Convert german specific characters to english one. This is for
    obtaining URLs of pathes of the pass and also labeling of the gpt data.

    Args:
        ft (str): pass's path name. In the form of "compass side" "starting point" "intermediate stop"

    Returns:
        tuple[str, str]: all lower case with dash (for the URL), english conversion with whitespace.
    """

    # Get orginal name in lower case. Replace Umlaut using "e"
    # This is necessary to get URL of individual path of the pass.
    ft_lower = ft.lower().replace(" ", "-")
    ft_lower = remove_diacritics(ft_lower)
    # for gv, ev in GERMAN_SPECIAL_CHARACTOR_CONVERTER.items():
    #     ft_lower = ft_lower.replace(gv, ev)

    # Preposition
    for gp, ep in GERMAN_PREP_CONVERTER.items():
        ft = ft.replace(gp, ep)

    # Compass points
    for gc, ec in GERMAN_COMPASS_CONVERTER.items():
        ft = ft.replace(gc, ec).replace(gc.capitalize(), ec)

    # Different expression for the slope
    for grt, ert in GERMAN_ROAD_TYPE_CONVERTER.items():
        ft = ft.replace(grt, ert)

    return ft_lower, ft
