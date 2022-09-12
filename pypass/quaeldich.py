#!/usr/bin/env python3
"""Retrieve pass data from https://www.quaeldich.de/. """
from pathlib import Path
from typing import Optional
from unicodedata import combining
from unicodedata import normalize

import requests
from bs4 import BeautifulSoup as bs
from rich.progress import Progress
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.progress import track
from tinydb import Query
from tinydb import TinyDB

PASS_DB_LOC = "./pypass/db/passes.json"
PASS_NAME_DB_LOC = "./pypass/db/pass_names.json"

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

    total_counts = int(soup.find(id=html_id).text)

    return total_counts


def extract_pass_data(
    db_overwrite: bool = False,
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

    html_id = "qd_list_template_paesse_list"

    if pass_counts is None:
        pass_counts = get_total_pass_count()

    if not db_overwrite:
        # Remove all databases
        if Path(PASS_NAME_DB_LOC).exists():
            Path(PASS_NAME_DB_LOC).unlink()

        if Path(PASS_DB_LOC).exists():
            Path(PASS_DB_LOC).unlink()

    with Progress(TEXT_COLUMN, TIME_COLUMN) as progress:

        progress.add_task("[cyan]Etracting html elements...")
        r = requests.get(BASE_PASS_URL + f"?n={pass_counts}")
        soup = bs(r.text, "lxml")
        ul = soup.find(id=html_id)
        html_pass_list = ul.findAll("li")

        # Sanity check.
        assert (
            len(html_pass_list) == pass_counts
        ), f"Pass: There is mismatch in number of passes - get {len(html_pass_list)} but registed {pass_counts}."

    all_passes = []
    all_names = []
    all_alts = []

    for li in track(
        html_pass_list,
        description=f"[cyan]Processing {len(html_pass_list)} pass data...",
    ):
        row = li.find("div", {"class": "row"})
        all_divs = row.findAll("div")
        all_links = [href["href"] for href in row.findAll("a", href=True)]
        pass_url = BASE_URL + all_links[0]

        # Get geotraphical region of the pass
        pass_region = []
        for link in all_links:
            if link.find("regionen") >= 0:
                pass_region.append(
                    link.replace(BASE_URL + "/regionen/", "")
                    .replace("/paesse/", "")
                    .capitalize()
                )
        pass_region = " ".join(pass_region)

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
        pass_coord, pass_url = _get_pass_coord(data[0])
        path_urls = _get_path_url(pass_url)
        path_info = _get_path_info(pass_url)
        path_ids = _get_path_ids(path_urls)
        path_gpt_js = _get_gpt_data_js(path_ids)

        # Store data in the dictionary
        gpt_dict = {}
        for i, (gjs, ft, purl) in enumerate(
            zip(path_gpt_js, all_from_to, path_urls)
        ):
            gpt_dict.update({i: {"name": ft, "url": purl, "gpt": gjs}})

        pass_data = {
            "name": data[0],
            "coord": pass_coord,
            "alt": data[3],
            "region": pass_region,
            "height": int(data[2].strip(" m")),
            "url": pass_url,
            "gpts": gpt_dict,
            "total_distance": path_info["distance"],
            "total_elevation": path_info["elevation"],
            "avg_grad": path_info["gradient"],
            "max_distance": max(path_info["distance"]),
            "min_distance": min(path_info["distance"]),
            "max_elevation": max(path_info["elevation"]),
            "min_elevation": min(path_info["elevation"]),
        }

        db = TinyDB(PASS_DB_LOC)
        if db_overwrite:
            searched = db.search(Query().name == data[0])
            if len(searched) > 0:
                db.update(pass_data)
            else:
                db.insert(pass_data)
        else:
            # Remove and save
            db.insert(pass_data)

        all_alts.append(data[3])
        all_names.append(data[0])
        all_passes.append(pass_data)

    db = TinyDB(PASS_NAME_DB_LOC)
    if db_overwrite:
        db.update({"names": all_names, "alts": all_alts})
    else:
        db.insert({"names": all_names, "alts": all_alts})

    return all_passes


def _get_pass_coord(pass_name: str) -> tuple[list[float], str]:

    url_pass_name = pass_name.lower().replace(" ", "-")

    url_pass_name = remove_diacritics(url_pass_name)

    # for gv, ev in GERMAN_SPECIAL_CHARACTOR_CONVERTER.items():
    #     url_pass_name = url_pass_name.replace(gv, ev)

    url = BASE_PASS_URL + url_pass_name

    coord_string = (
        bs(requests.get(url).text, "lxml")
        .find("div", {"class": "coords"})
        .find("a", {"class": "external"})
        .text
    ).split(",")

    return [float(coord) for coord in coord_string], url


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
    all_url_links = (
        bs(requests.get(pass_url).text, "lxml")
        .find("div", {"class": "panel-group"})
        .find_all("a", href=True)
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
    all_info = (
        bs(requests.get(pass_url).text, "lxml")
        .find("div", {"class": "panel-group"})
        .find_all("small")
    )

    distance = []
    elevation = []
    gradient = []

    for info in all_info:
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
