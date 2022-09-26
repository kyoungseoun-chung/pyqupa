#!/usr/bin/env python3
"""Pass information container."""
import json
from dataclasses import dataclass
from difflib import get_close_matches
import pdb
from re import S
from typing import get_args
from typing import get_origin
from typing import Optional
from typing import Union

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import requests
from bs4 import BeautifulSoup as bs
from numpy.typing import NDArray
from tinydb import Query
from tinydb import TinyDB

from .quaeldich import DB_LOC
from .quaeldich import PASS_DB
from .quaeldich import PASS_NAME_DB
from .tools import decompose_digit

PASS_DB_LOC = DB_LOC + PASS_DB
PASS_NAME_DB_LOC = DB_LOC + PASS_NAME_DB


PX = 1 / mpl.rcParams["figure.dpi"]
GRAD_FIG_WIDTH = 720 * PX
GRAD_FIG_HEIGHT = 120 * PX
GRAD_TO_COLOR = np.asarray(
    [
        "#a43074",
        "#80225c",
        "#5f1547",
        "#4e1d52",
        "#2e2048",
        "#102747",
        "#1d406b",
        "#11507c",
        "#34759d",
        "#7db5d5",
        "#aadff7",
        "#79d0f2",
        "#55c0da",
        "#1ab2cc",
        "#14b1b3",
        "#1bb195",
        "#24b065",
        "#20ae50",
        "#49b54e",
        "#78bf4b",
        "#ACE186",
        "#ACE186",
        "#ACE186",
        "#C7E383",
        "#E2F080",
        "#FDFE7B",
        "#FFEA75",
        "#FFD671",
        "#FFBE6D",
        "#FFA668",
        "#FF8B64",
        "#FF7260",
        "#F75B5B",
        "#DB5757",
        "#BA5353",
        "#9A4F4F",
        "#8E4D4D",
        "#824B4B",
        "#774A4A",
        "#6A4848",
        "#5E4747",
    ]
)

GRAD_MAX: float = 30.0
GRAD_MIN: float = -30.0


@dataclass
class Pass:

    name: str
    """Name of pass."""
    coord: list[float]
    """coordinate of pass."""
    alt: str
    """Alternative name if exists"""
    country: str
    """Pass country"""
    region: str
    """Pass region."""
    height: int
    """Height of the pass in meter."""
    total_distance: list[float]
    """Total distance of each paths."""
    total_elevation: list[int]
    """Total elevation of each paths."""
    avg_grad: list[float]
    """Average gradient of each paths."""
    max_distance: float
    """Max distance among the paths"""
    min_distance: float
    """Min distance among the paths"""
    max_elevation: int
    """Max elevation among the paths"""
    min_elevation: int
    """Min elevation among the paths"""
    url: str
    """URL of the pass"""
    gpts: dict
    """Geographical coordinate information. Latitude, Longitude, Elevation, Distance."""

    def __post_init__(self):

        if len(self.gpts) > 0:

            self.geo_log = get_gpt_data(self.gpts)

            # Process gradients
            self.grad_process()

    @property
    def is_valid(self) -> bool:
        """Check whether Pass information contains valid path data."""

        return self.max_distance > 0

    @property
    def map_bound(self) -> list[float]:

        sf = np.asarray(self.starts_from, dtype=np.float64)
        pass_coord = np.asarray(self.coord, dtype=np.float64)

        if len(sf) == 1:
            coord_delta = pass_coord - sf[0]
            return [
                (pass_coord - coord_delta).tolist(),
                (pass_coord + coord_delta).tolist(),
            ]
        else:
            coord_delta_dist = np.sqrt(((pass_coord - sf) ** 2).sum(axis=1))
            path_idx = np.argmax(coord_delta_dist)
            coord_delta = pass_coord - sf[path_idx]

            return [
                (pass_coord - coord_delta).tolist(),
                (pass_coord + coord_delta).tolist(),
            ]

    @property
    def num_pathes(self) -> int:
        """Number pathes to the top."""
        return len(self.total_distance)

    @property
    def starts_from(self) -> list[list[float]]:

        return [geo[0, :2].tolist() for geo in self.geo_log if geo is not None]

    @property
    def path_names(self) -> list[str]:

        return [self.gpts[pid]["name"] for pid in self.gpts]

    @property
    def grad_max(self) -> list[float]:
        """Maximum gradient measured."""
        return self._grad_max

    @property
    def grad_min(self) -> list[float]:
        """Minimum gradient measured."""
        return self._grad_min

    @property
    def flat(self) -> list[float]:
        """Measured flat section in km. If the gradient is +- 2%, it is regarded as the flat section."""
        return self._flat

    @property
    def descend(self) -> list[float]:
        """Measured descending section in km."""
        return self._descend

    @property
    def gradient(self) -> list[NDArray[np.float64]]:
        """Computed gradient. Interpolated every 100 meter from 50 meter."""
        return self._grad

    @property
    def grad_interp(self) -> list[NDArray[np.float64]]:
        """Interpolated gradient."""
        return self._grad_interp

    @property
    def grad_bin(self) -> list[NDArray[np.float64]]:
        """Coordinate for the gradients."""
        return self._grad_bin

    @property
    def grad_color(self) -> list[NDArray[np.unicode_]]:
        """Converted gradient to color code."""
        return self._grad_color

    @property
    def distance(self) -> list[NDArray[np.float64]]:
        """Distance to the top of the Pass in km."""

        return self._distance

    @property
    def elevation(self) -> list[NDArray[np.float64]]:
        """Elevation of the Pass in meter."""

        return self._elevation

    @property
    def elev_interp(self) -> list[NDArray[np.float64]]:
        """Elevlation interpolated to grad_bin."""
        return self._elev_interp

    @property
    def elev_lower(self) -> list[float]:
        """Lower limit of the elevation."""
        return self._elev_lower

    @property
    def elev_upper(self) -> list[float]:
        """Upper limit of the elevation."""
        return self._elev_upper

    def grad_process(self) -> None:
        """Compute average gradient of every 100m."""

        self._grad_max = []
        self._grad_min = []
        self._flat = []
        self._descend = []
        self._grad = []
        self._grad_interp = []
        self._grad_color = []
        self._distance = []
        self._elevation = []
        self._elev_interp = []
        self._grad_bin = []

        # For plot bounds
        self._elev_lower = []
        self._elev_upper = []

        for geo in self.geo_log:

            if geo is not None:

                dist = geo[:, 3] * 1000  # in meter
                self._distance.append(dist / 1000)
                height = geo[:, 2]  # in meter
                # Altitude cannot be zero?
                dist = dist[height > 0.0]
                height = height[height > 0.0]  # remove zero
                self._elevation.append(height)

                self._elev_lower.append(decompose_digit(height[0], -2)[0])
                self._elev_upper.append(decompose_digit(height[-1], 2)[0])

                # Compute gradient
                mask = np.diff(dist) > 1
                grad = np.zeros_like(np.diff(dist))
                grad[mask] = (
                    np.diff(height)[mask] / np.diff(dist)[mask] * 100
                )  # in %
                # Starting point will be zero gradient
                self._grad.append(np.append([0.0], grad))

                # Min-max gradient measured
                self._grad_max.append(min(np.max(grad), GRAD_MAX))
                self._grad_min.append(max(np.min(grad), GRAD_MIN))

                flat_mask = np.logical_and(grad >= -2, grad < 2)
                descend_mask = grad < -2
                # Sum all flat section
                self._flat.append(np.diff(dist)[flat_mask].sum() / 1000)
                # Sum all descend section
                self._descend.append(np.diff(dist)[descend_mask].sum() / 1000)

                # Gradients are binned at the mid-points
                mid_pt = dist[:-1] + np.diff(dist)[0] / 2

                # Interpolate every 100 meter and the start at 50 meter not 0.
                # TODO: it should be average over 100m not the interpolation.
                xp = np.arange(50, dist[-1] + 50, 100)
                self._grad_bin.append(xp / 1000)
                grad_interp = np.interp(xp, mid_pt, grad)
                self._grad_interp.append(grad_interp)
                elev_interp = np.interp(xp / 1000, dist / 1000, height)
                self._elev_interp.append(elev_interp)
                self._grad_color.append(grad_to_color(grad_interp))

    # NOTE: type for plt.Figure is ambigous. Therefore, type: ignore
    def plot_gradient(
        self, idx: int, show: bool = False, tool: str = "pyplot"
    ) -> Optional[plt.Figure]:  # type: ignore
        """Plot gradient profile."""

        if tool == "pyplot":
            fig, ax = plt.subplots(figsize=(GRAD_FIG_WIDTH, GRAD_FIG_HEIGHT))

            ax.bar(
                self.grad_bin[idx],
                self.elev_interp[idx],
                color=self.grad_color[idx],
                width=0.1,
            )
            ax.set_yticks(np.arange(0, 3000, 500))
            ax.set_xticks(np.arange(0, 40, 5))
            ax.set_ylim(self.elev_lower[idx], self.elev_upper[idx])
            ax.set_xlim(0, self.total_distance[idx])
            ax.set_xlabel("distance [km]")
            ax.set_ylabel("elevation [m]")

            if show:
                plt.show()
        elif tool == "plotly":
            # WIP
            fig = None
        else:
            fig = None

        return fig


def grad_to_color(grad: NDArray[np.float64]) -> NDArray[np.unicode_]:
    """Convert gradient to the color code. Min-max cut-off is [-20, 20] %."""

    idx = np.round(grad).astype(np.int64) + 20
    idx[idx < 0] = 0
    idx[idx > 40] = 40

    return GRAD_TO_COLOR[idx]


def latlng2m(
    latlng1: NDArray[np.float64], latlng2: NDArray[np.float64]
) -> float:
    """Convert latitude, longitude data to distance. Compute using the Haversine formula.

    Args:
        latlng1 (NDArray[np.float64]): the first point
        latlng2 (NDArray[np.float64]): the second point

    Returns:
        float: distance to be computed
    """

    radius = 6371e3  # Earch radius in meter
    dlat = deg2rad(latlng2[0] - latlng1[0])
    dlng = deg2rad(latlng2[1] - latlng1[1])

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(deg2rad(latlng1[0]))
        * np.cos(deg2rad(latlng2[0]))
        * np.sin(dlng / 2) ** 2
    )

    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return radius * c


def deg2rad(deg: float) -> float:
    """Convert degree to radian."""
    return deg * np.pi / 180


def search_pass_by_distance(distance: list[float], db_loc: str) -> list[Pass]:

    pass_db_loc = db_loc + PASS_DB
    db = TinyDB(pass_db_loc)

    # Sanity check
    _sanity_check_list_input(distance)

    from_db = db.search(
        (
            (Query().min_distance >= distance[0])
            & (Query().min_distance <= distance[1])
        )
        | (
            (Query().max_distance >= distance[0])
            & (Query().max_distance <= distance[1])  # type: ignore
        )
    )

    searched_pass = []

    for data in from_db:
        dist_list = np.asarray(data["total_distance"])
        indicies = np.argwhere(
            np.logical_and(dist_list > distance[0], dist_list < distance[1])
        )

        searched_pass.append(Pass(**_update_list_data(data, indicies)))

    if len(searched_pass) == 0:
        raise RuntimeError(
            f"Pass: No pass data searched matching distance range: {distance}"
        )

    return searched_pass


def search_pass_by_elevation(elevation: list[float], db_loc: str) -> list[Pass]:

    pass_db_loc = db_loc + PASS_DB
    db = TinyDB(pass_db_loc)

    # Sanity check
    _sanity_check_list_input(elevation)

    from_db = db.search(
        (
            (Query().min_elevation >= elevation[0])
            & (Query().min_elevation <= elevation[1])
        )
        | (
            (Query().max_elevation >= elevation[0])
            & (Query().max_elevation <= elevation[1])  # type: ignore
        )
    )

    searched_pass = []

    for data in from_db:
        dist_list = np.asarray(data["total_elevation"])
        indicies = np.argwhere(
            np.logical_and(dist_list > elevation[0], dist_list < elevation[1])
        )

        searched_pass.append(Pass(**_update_list_data(data, indicies)))

    if len(searched_pass) == 0:
        raise RuntimeError(
            f"Pass: No pass data searched matching elevation range: {elevation}"
        )

    return searched_pass


def search_pass_by_height(height: list[float], db_loc: str) -> list[Pass]:
    """Search pass by its height (heightest point).

    Args:
        elevation (list[int]): lower and upper bound of passes to be searched.

    Returns:
        list[Pass]: list of searched passes.
    """

    pass_db_loc = db_loc + PASS_DB
    db = TinyDB(pass_db_loc)

    _sanity_check_list_input(height)

    from_db = db.search(
        (Query().height > height[0]) & (Query().height < height[1])
    )

    searched_pass = [Pass(**data) for data in from_db]

    if len(searched_pass) == 0:
        raise RuntimeError(
            f"Pass: No pass data searched matching height range: {height}"
        )

    return searched_pass


def search_pass_by_region(region: str, db_loc: str) -> list[Pass]:

    region = region.lower()

    pass_db_loc = db_loc + PASS_DB
    db = TinyDB(pass_db_loc)

    from_db = db.search(Query().region == region)

    searched_pass = [Pass(**data) for data in from_db]

    if len(searched_pass) == 0:

        raise RuntimeError(
            f"Pass: No pass data searched matching region: {region}"
        )

    return searched_pass


def search_pass_by_country(country: str, db_loc: str) -> list[Pass]:

    country = country.lower()

    pass_db_loc = db_loc + PASS_DB
    db = TinyDB(pass_db_loc)

    from_db = db.search(Query().country == country)

    searched_pass = [Pass(**data) for data in from_db]

    if len(searched_pass) == 0:

        raise RuntimeError(
            f"Pass: No pass data searched matching country: {country}"
        )

    return searched_pass


def search_pass_by_name(name: str, db_loc: str) -> list[Pass]:
    """Search pass by its name. First, it searches `db.names`. In the case of no matching name is found, check `db.alts` instead. Also, if there is a typo in the given name input, this function will return non-empty list contains name suggestions. Suggestion is made by using `difflib.get_close_mathces`.

    Args:
        name (str): name of a pass

    Returns:
        list[Pass]: searched pass. If there is no matching name, return None and non-empty name suggestion.
    """

    pass_db_loc = db_loc + PASS_DB
    pass_name_db_loc = db_loc + PASS_NAME_DB

    db = TinyDB(pass_db_loc)
    db_names = TinyDB(pass_name_db_loc)

    # There should be only one pass corresponding to the given name.
    from_db = db.get(Query().name == name)

    if from_db is None:

        # Try with alternative name
        from_db = db.get(Query().alt == name)

        if from_db is None:
            # Check levenstein distance of pass names
            all_names = db_names.all()[0]["alts"] + db_names.all()[0]["names"]
            suggested = get_close_matches(name, all_names)

            raise NameError(
                f"The given name ({name}) is not in our database. Did you mean {suggested}?"
            )

        else:
            pass_searched = [Pass(**from_db)]

    else:
        pass_searched = [Pass(**from_db)]

    return pass_searched


PASS_SEARCH_TYPE = [
    "name",
    "height",
    "elevation",
    "distance",
    "region",
    "country",
]

SEARCH_FACTORIES = {
    "name": {"func": search_pass_by_name, "key_type": str},
    "height": {"func": search_pass_by_height, "key_type": Union[list, tuple]},
    "distance": {
        "func": search_pass_by_distance,
        "key_type": Union[list, tuple],
    },
    "elevation": {
        "func": search_pass_by_elevation,
        "key_type": Union[list, tuple],
    },
    "region": {"func": search_pass_by_region, "key_type": str},
    "country": {"func": search_pass_by_country, "key_type": str},
}


@dataclass
class PassDB:

    db_loc: str = DB_LOC
    """Database location"""

    def search(
        self, key: Union[str, list[int], list[float]], search_type: str
    ) -> list[Pass]:

        search_type = search_type.lower()

        if search_type in PASS_SEARCH_TYPE:

            search_func = SEARCH_FACTORIES[search_type]["func"]
            input_type = SEARCH_FACTORIES[search_type]["key_type"]

            if (
                isinstance(key, get_args(input_type))
                and get_origin(input_type) is Union
            ) or isinstance(key, input_type):

                pass_searched = search_func(key, self.db_loc)

            else:
                raise TypeError(
                    f"PassDB: Non-supporting input type: {type(key)}. Should be {input_type}."
                )

        else:

            raise TypeError(
                f"PassDB: Non-supporting search type: {search_type}. Should be one of {PASS_SEARCH_TYPE}."
            )

        return pass_searched


def _update_list_data(data: dict, indicies: NDArray[np.int64]) -> dict:

    gpts = dict()
    total_distance: list[float] = []
    total_elevation: list[int] = []
    avg_grad: list[float] = []

    # Indices is 2D array. Therefore need to be accessed with zero index.
    for i, idx in enumerate(indicies):
        gpts.update({str(i): data["gpts"][str(idx[0])]})
        total_distance.append(data["total_distance"][idx[0]])
        total_elevation.append(data["total_elevation"][idx[0]])
        avg_grad.append(data["avg_grad"][idx[0]])

    max_distance = max(total_distance)
    min_distance = min(total_distance)
    max_elevation = max(total_elevation)
    min_elevation = min(total_elevation)

    data["gpts"] = gpts
    data["total_distance"] = total_distance
    data["total_elevation"] = total_elevation
    data["max_distance"] = max_distance
    data["min_distance"] = min_distance
    data["max_elevation"] = max_elevation
    data["min_elevation"] = min_elevation
    data["avg_grad"] = avg_grad

    return data


def _sanity_check_list_input(inputs: Union[list[float], list[int]]) -> None:

    # Sanity check
    assert (
        len(inputs) == 2
    ), "Pass: length of the input should be 2 -> [lower, upper]."

    assert (
        inputs[1] > inputs[0]
    ), "Pass: bounds should be increasing order -> [lower, upper]."


def get_gpt_data(
    gpts: dict[str, dict[str, str]]
) -> list[Optional[NDArray[np.float64]]]:
    """Obtain latitude, longitude, height, and distance information (GPT data) from the path ids.

    Args:
        path_ids (list[str]): path ids

    Returns:
        list[NDarray[np.float64]]: resulting gpt data
    """
    gpt_data_string = [
        json.loads(
            bs(requests.get(gpts[pid]["gpt"]).text, "lxml").text.replace(
                ";", ","
            )
        )
        for pid in gpts
    ]

    # Convert string to number
    # Since json cannot serialize numpy ndarray, convert to list.
    gpt_data = []
    for gpt in gpt_data_string:

        try:
            gpt_data.append(
                np.asarray(
                    [
                        np.array(line.split(","), dtype=np.float64)
                        for line in gpt
                    ],
                    dtype=np.float64,
                )
            )
        except ValueError:
            gpt_data.append(None)

    return gpt_data
