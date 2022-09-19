#!/usr/bin/env python3
"""Retrieve pass data from https://www.quaeldich.de/. """
import os
import warnings
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

    db_loc_full = db_loc + PASS_DB
    name_db_loc_full = db_loc + PASS_NAME_DB
    if not db_overwrite:
        # Remove all databases
        if Path(name_db_loc_full).exists():
            Path(name_db_loc_full).unlink()

        if Path(db_loc_full).exists():
            Path(db_loc_full).unlink()

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

    return all_passes


def get_html_components(pass_counts: int) -> bs4.ResultSet:
    """Extract all html component for `pass_counts` number of listed Passes in quaeldich.de."""

    html_id = "qd_list_template_paesse_list"

    r = requests.get(BASE_PASS_URL + f"?n={pass_counts}")
    html_pass_list = bs(r.text, "lxml").find(id=html_id).findAll("li")

    return html_pass_list


def get_pass_data(li: Any) -> dict[str, Any]:

    row = li.find("div", {"class": "row"})
    all_divs = row.findAll("div")
    all_links = [href["href"] for href in row.findAll("a", href=True)]
    pass_url = BASE_URL + all_links[0]

    country, region = _get_pass_region(all_links, pass_url)

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

    # Obtain URLs for each path and path ids used in quaeldich website
    path_info = _get_path_info(pass_url)
    pass_coord = _get_pass_coord(pass_url)
    path_urls = _get_path_url(pass_url)

    gpt_dict = {}
    if len(path_urls) > 0:
        path_ids = _get_path_ids(path_urls)
        path_gpt_js = _get_gpt_data_js(path_ids)
        # Store data in the dictionary
        for i, (gjs, ft, purl) in enumerate(
            zip(path_gpt_js, all_from_to, path_urls)
        ):
            gpt_dict.update({i: {"name": ft, "url": purl, "gpt": gjs}})
    else:
        # If there is no path info stored, save wrong values. Here, negative values.
        warnings.warn(
            f"Quaeldich: Path path url cannot be found in {pass_url}. Data left as empty list.",
            UserWarning,
        )

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
    }


def _get_pass_region(all_links: list[str], pass_url: str) -> tuple[str, str]:

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
        warnings.warn(
            f"Quaeldich: country and region information cannot be found in {pass_url}",
            RuntimeWarning,
        )

    return country, region


def _get_pass_coord(pass_url: str) -> list[float]:

    try:
        coord_string = (
            bs(requests.get(pass_url).text, "lxml")
            .find("div", {"class": "coords"})
            .find("a", {"class": "external"})
            .text
        ).split(",")
    except AttributeError:
        # Store wrong data
        coord_string = ["-1.0", "-1.0"]
        warnings.warn(
            f"Quaeldich: No coordinate information found in {pass_url}!"
        )

    return [float(coord) for coord in coord_string]


def _get_gpt_data_js(path_ids) -> list[str]:
    """In quaeldich website, all gpt data are written in .js file. From
    `path_ids`, get the url of js files.

    Args:
        path_ids (list[str]): path ids

    Returns:
        list[str]: js file url
    """
    # Get gpt js file
    gpt_js = [f"{BASE_URL}/qdtp/anfahrten/{ids}.json" for ids in path_ids]

    return gpt_js


def _get_path_ids(path_urls: list[str]) -> list[str]:
    """Extract path ids. There is no obvious way to extract GPT data or data-id from
    quaeldich website. Only way that I found was, find the image for the pass's graident
    and remove unnecessary string part.

    Args:
        path_urls (list[str]): list of urls for pathes

    Returns:
        list[str]: path ids
    """

    path_ids_container = [
        bs(requests.get(url).text, "lxml").findAll("img") for url in path_urls
    ]

    path_ids = [
        img["src"].replace("/qdtp/anfahrten/", "").replace("_gradient.gif", "")
        for path in path_ids_container
        for img in path
        if img["src"].find("gradient") >= 0
    ]

    return path_ids


def _get_path_url(pass_url: str) -> list[str]:
    """From pass name, obtain path url.

    Args:
        pass_name (str): name of the pass, in German.

    Returns:
        list[str]: list of urls of the pass
    """
    all_url_links = bs(requests.get(pass_url).text, "lxml").find_all(
        "a", href=True
    )

    path_urls = [
        link["href"]
        for link in all_url_links
        if link["href"].find("/profile/") >= 0
    ]

    return path_urls


def _get_path_info(pass_url: str) -> dict:
    """From pass name, obtain basic path information.

    Args:
        pass_name (str): name of the pass, in German.

    Returns:
        list[str]: list of urls of the pass
    """
    all_info = bs(requests.get(pass_url).text, "lxml").find_all("small")

    distance = []
    elevation = []
    gradient = []

    for info in all_info:

        if "km" in info.text and "Hm" in info.text and "%" in info.text:
            data_extracted = info.text.replace(" ", "").split("|")
            distance.append(
                float(data_extracted[0].replace(",", ".").replace("km", ""))
            )
            elevation.append(
                int(data_extracted[1].replace(",", ".").replace("Hm", ""))
            )
            gradient.append(
                float(data_extracted[2].replace(",", ".").replace("%", ""))
            )

    if len(distance) == 0 or len(elevation) == 0 or len(gradient) == 0:

        distance.append([-1.0])
        elevation.append([-1])
        gradient.append([-1.0])

        warnings.warn(
            f"Quaeldich: Basic information (km, Hm, and %) cannot be found! Check input pass_url:\n{pass_url}",
            RuntimeWarning,
        )

    return {
        "distance": distance,
        "elevation": elevation,
        "gradient": gradient,
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
