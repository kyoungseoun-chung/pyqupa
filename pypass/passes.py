#!/usr/bin/env python3
"""Pass information container."""
from bs4 import BeautifulSoup as bs
from difflib import get_close_matches
import matplotlib.pyplot as plt

import json
from typing import Optional
import requests
import numpy as np
from dataclasses import dataclass
from numpy.typing import NDArray
from .tools import hex_to_rgb, decompose_digit

from .quaeldich import PASS_DB_LOC, PASS_NAME_DB_LOC

from tinydb import TinyDB, Query

PX = 1 / plt.rcParams["figure.dpi"]
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
    coord: list[float, float]
    """coordinate of pass."""
    alt: str
    """Alternative name if exists"""
    region: str
    """Pass region."""
    height: int
    """Height of the pass in meter."""
    url: str
    """URL of the pass"""
    gpts: dict
    """Geographical coordinate information. Latitude, Longitude, Elevation, Distance."""

    def __post_init__(self):

        self.geo_log = get_gpt_data(self.gpts)

        self.loc = self.geo_log[0][-1]

        # Process gradients
        self.grad_process()

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
        return len(self.geo_log)

    @property
    def starts_from(self) -> list[float, float]:

        return [geo[0, :2] for geo in self.geo_log]

    @property
    def path_names(self) -> list[str]:

        return [self.gpts[pid]["name"] for pid in self.gpts]

    @property
    def total_distance(self) -> list[float]:
        return [(geo[-1, -1] - geo[0, -1]) * 1000 for geo in self.geo_log]

    @property
    def total_elevation(self) -> list[float]:
        return [geo[-1, -2] - geo[0, -2] for geo in self.geo_log]

    @property
    def avg_grad(self) -> list[float]:
        """Compute average gradient from start to finish."""

        return [
            e / d * 100
            for d, e in zip(self.total_distance, self.total_elevation)
        ]

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

            dist = geo[:, 3] * 1000  # in meter
            self._distance.append(dist / 1000)
            height = geo[:, 2]  # in meter
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

    def plot_gradient(self, idx: int, show: bool = False) -> plt.Figure:

        fig, ax = plt.subplots(figsize=(GRAD_FIG_WIDTH, GRAD_FIG_HEIGHT))

        ax.bar(
            self.grad_bin[idx],
            self.elev_interp[idx],
            color=self.grad_color[idx],
            width=0.1,
        )
        ax.set_yticks(np.arange(0, 3000, 500))
        ax.set_xticks(np.arange(0, 40, 5))
        ax.set_ylim([self.elev_lower[idx], self.elev_upper[idx]])
        ax.set_xlim([0, self.total_distance[idx] / 1000])
        ax.set_xlabel("distance [km]")
        ax.set_ylabel("elevation [m]")

        if show:
            plt.show()

        return fig

    def plot_gradients(self, show: bool = False) -> plt.Figure:

        fig, axes = plt.subplots(
            self.num_pathes,
            1,
            figsize=(GRAD_FIG_WIDTH, GRAD_FIG_HEIGHT * self.num_pathes),
        )

        for ax, gb, ei, gc in zip(
            axes, self.grad_bin, self.elev_interp, self.grad_color
        ):
            ax.bar(gb, ei, color=gc, width=0.1)

        if show:
            plt.show()

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


def search_pass_by_distance(distance: list[float]) -> list[Pass]:

    # Sanity check
    _sanity_check_list_input(distance)


def search_pass_by_height(elevation: list[int]) -> list[Pass]:
    """Search pass by its height (heightest point).

    Args:
        elevation (list[int]): lower and upper bound of passes to be searched.

    Returns:
        list[Pass]: list of searched passes.
    """

    db = TinyDB(PASS_DB_LOC)

    _sanity_check_list_input(elevation)
    from_db = db.search(
        (Query().height > elevation[0]) & (Query().height < elevation[1])
    )

    return [Pass(**data) for data in from_db]


def _sanity_check_list_input(inputs: list[float]) -> None:

    # Sanity check
    assert (
        len(inputs) == 2
    ), "Pass: length of the input should be 2 -> [lower, upper]."

    assert (
        inputs[1] > inputs[0]
    ), "Pass: bounds should be increasing order -> [lower, upper]."


def search_pass_by_region(region: str) -> list[Pass]:
    pass


def search_pass_by_name(name: str) -> tuple[Optional[Pass], Optional[str]]:

    db = TinyDB(PASS_DB_LOC)
    db_names = TinyDB(PASS_NAME_DB_LOC)

    # There should be only one pass corresponding to the given name.
    from_db = db.get(Query().name == name)

    if from_db is None:

        # Try with alternative name
        from_db = db.get(Query().alt == name)

        if from_db is None:
            # Check levenstein distance of pass names
            all_names = db_names.all()[0]["alts"] + db_names.all()[0]["names"]
            suggested = get_close_matches(name, all_names)

            print(
                f"The given name ({name}) is not in our database. Did you mean {suggested}?"
            )
            pass_searched = None
        else:
            pass_searched = Pass(**from_db)
            suggested = None

    else:
        pass_searched = Pass(**from_db)
        suggested = None

    return pass_searched, suggested


def get_gpt_data(gpts: dict[str, str]) -> list[NDArray[np.float64]]:
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

        gpt_data.append(
            np.asarray(
                [np.array(line.split(","), dtype=np.float64) for line in gpt],
                dtype=np.float64,
            )
        )

    return gpt_data
