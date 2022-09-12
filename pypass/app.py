#!/usr/bin/env python3
"""Display pass data using streamlit library."""
import os
from itertools import cycle
from typing import Any
from typing import Optional

import folium
import numpy as np
import pydeck as pdk
import streamlit as st
from dotenv import dotenv_values
from streamlit_folium import st_folium
from tinydb import TinyDB

from pypass.tools import hex_to_rgb

COLOR_CODE = cycle(
    ["#FF7900", "#F94E5D", "#CA4B8C", "#835698", "#445582", "#2F4858"]
)


try:
    MAPBOX_API_KEY = os.environ.get("MAPBOX_API_KEY")
    if MAPBOX_API_KEY == "":
        raise KeyError()
except KeyError:
    MAPBOX_API_KEY = dotenv_values(".env")["MAPBOX_API_KEY"]

from pypass.passes import search_pass_by_name, Pass
from pypass.quaeldich import PASS_NAME_DB_LOC


def pypass_pass_search() -> Optional[Pass]:

    st.set_page_config(
        layout="centered", page_title="Pass Finder", page_icon="⛰"
    )

    db_names = TinyDB(PASS_NAME_DB_LOC)

    # Find all pass name including alternative name
    all_pass_names = db_names.all()[0]["names"]
    all_pass_names += list(filter(None, db_names.all()[0]["alts"]))

    pass_name = st.selectbox("Search the pass", all_pass_names)
    pass_searched, _ = search_pass_by_name(pass_name)

    return pass_searched


# NOTE: Currently not sure what is the type hint for streamlit app. Therefore, use Any.
def pypass_app_title(pass_searched: Pass) -> Any:

    pass_title = (
        f"**{pass_searched.name}**"
        if pass_searched.alt == ""
        else f"**{pass_searched.name} - {pass_searched.alt}, {pass_searched.height}m**"
    )

    # Display pass name
    st.title(pass_title)
    # Display basic info
    cols = st.columns(len(pass_searched.gpts))
    for idx, (c, n, d, e, g) in enumerate(
        zip(
            cols,
            pass_searched.path_names,
            pass_searched.total_distance,
            pass_searched.total_elevation,
            pass_searched.avg_grad,
        )
    ):
        c.metric(
            f"{idx+1}: {n}",
            value=f"{d/1000: .1f}km",
            delta=f"{e:.1f}m, {g:.1f} %",
        )

    return st


# TODO: test this first and replace folium later if possible
def pypass_app_map_deck(pass_searched: Pass):

    # AWS Open Data Terrain Tiles
    terrain_image = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

    # Define how to parse elevation tiles
    elevation_decoder = {
        "rScaler": 256,
        "gScaler": 1,
        "bScaler": 1 / 256,
        "offset": -32768,
    }

    surface_image = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.png?access_token={MAPBOX_API_KEY}"

    map_layers = []
    # Add terrain
    map_layers.append(
        pdk.Layer(
            "TerrainLayer",
            elevation_decoder=elevation_decoder,
            texture=surface_image,
            elevation_data=terrain_image,
        )
    )

    view_state = pdk.ViewState(
        latitude=pass_searched.coord[0],
        longitude=pass_searched.coord[1],
        zoom=11,
        pitch=45,
    )

    min_elevation = min(elev[:, 2].min() for elev in pass_searched.geo_log)
    max_elevation = pass_searched.height

    # 10% offset
    elevation_offset = (float(max_elevation) - min_elevation) * 0.05

    for path, color in zip(pass_searched.geo_log, COLOR_CODE):

        # Data is in [longitude, latitude, elevation] order
        coord = np.vstack(
            (path[:, 1], path[:, 0], path[:, 2] + elevation_offset)
        ).T
        route = [
            {
                "path": coord.tolist(),
                "color": hex_to_rgb(color, 0.8),
            }
        ]

        map_layers.append(
            pdk.Layer(
                "PathLayer",
                route,
                get_path="path",
                get_color="color",
                get_width=3,
                width_scale=10,
                width_min_pixels=2,
                rouned=True,
            )
        )
    r = pdk.Deck(map_layers, initial_view_state=view_state)
    st.pydeck_chart(r)


def pypass_app_map_folium(pass_searched: Pass) -> None:

    m = folium.Map(location=pass_searched.coord)
    m.fit_bounds(pass_searched.map_bound)
    folium.Marker(
        pass_searched.coord,
        tooltip=f"{pass_searched.name} - {pass_searched.height} [m]",
    ).add_to(m)

    for path, stp, color in zip(
        pass_searched.geo_log, pass_searched.starts_from, COLOR_CODE
    ):

        # Folium only works with font awsome icon v4: https://fontawesome.com/v4/icons/
        icon_start = folium.Icon(
            icon_color="white",
            color="red",
            icon=f"fa-arrow-right",
            prefix="fa",
        )

        folium.Marker(stp, icon=icon_start).add_to(m)

        folium.PolyLine(
            path[:, :2], color=color, weight=4, opacity=0.7
        ).add_to(m)

    st_folium(m, width=725)


def pypass_app_map_selector(pass_searched: Pass) -> None:

    map_type_deck = "Deck.gl (3D)"
    map_type_folium = "Folium (2D)"

    option = st.selectbox("Choose map type", [map_type_deck, map_type_folium])

    if option == map_type_deck:
        pypass_app_map_deck(pass_searched)
    else:
        pypass_app_map_folium(pass_searched)


def pypass_app_gradient_plots(pass_searched: Pass) -> None:

    for idx, path in enumerate(pass_searched.path_names):

        st.subheader(path)
        st.pyplot(pass_searched.plot_gradient(idx))


if __name__ == "__main__":

    pass_searched = pypass_pass_search()

    if pass_searched is not None:
        pypass_app_title(pass_searched)
        pypass_app_map_selector(pass_searched)
        pypass_app_gradient_plots(pass_searched)
