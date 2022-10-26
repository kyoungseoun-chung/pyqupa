#!/usr/bin/env python3
"""Display pass data using streamlit library."""
from itertools import cycle
from typing import Any
from typing import Optional

import folium
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from dotenv import dotenv_values
from streamlit_folium import st_folium
from tinydb import TinyDB

from pyqupa.tools import hex_to_rgb

COLOR_CODE = cycle(
    ["#FF7900", "#F94E5D", "#CA4B8C", "#835698", "#445582", "#2F4858"]
)

try:
    MAPBOX_API_KEY = dotenv_values(".env")["MAPBOX_API_KEY"]
except KeyError:
    MAPBOX_API_KEY = st.secrets["MAPBOX_API_KEY"]

from pyqupa.passes import PassDB, Pass
from pyqupa.quaeldich import DB_LOC, PASS_NAME_DB

st.set_page_config(layout="centered", page_title="Pass Finder", page_icon="⛰")


def pyqupa_pass_search(attr: str) -> list[Pass]:

    db_names = TinyDB(DB_LOC + PASS_NAME_DB)

    # Find all pass name including alternative name
    if attr == "name":
        all_names = db_names.all()[0][attr + "s"]
        all_names += list(filter(None, db_names.all()[0]["alts"]))
    else:
        all_names = db_names.all()[0][attr]

    all_names.sort()
    target = st.selectbox("Search the pass", all_names)
    pass_searched = PassDB().search(target, attr)

    return pass_searched


def pyqupa_pass_search_by_bounds(
    bounds: list[float], search_type: str
) -> list[Pass]:

    pass_searched = PassDB().search(bounds, search_type)

    return pass_searched


# NOTE: Currently not sure what is the type hint for streamlit app. Therefore, use Any.
def pyqupa_app_title(pass_searched: Pass) -> Any:

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
            value=f"{d: .1f}km",
            delta=f"{e:.1f}m, {g:.1f} %",
        )

    return st


# TODO: test this first and replace folium later if possible
def pyqupa_app_map_deck(pass_searched: Pass):

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


def pyqupa_app_map_folium(pass_searched: Pass) -> None:

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

    st_folium(m)


def pyqupa_app_map_selector(pass_searched: Pass) -> None:

    map_type_deck = "Deck.gl (3D)"
    map_type_folium = "Folium (2D)"

    option = st.selectbox("Choose map type", [map_type_deck, map_type_folium])

    if option == map_type_deck:
        pyqupa_app_map_deck(pass_searched)
    else:
        pyqupa_app_map_folium(pass_searched)


def pyqupa_app_gradient_plots(pass_searched: Pass) -> None:

    for idx, path in enumerate(pass_searched.path_names):

        st.write(f"Elevation profile: {path}")
        st.plotly_chart(pass_searched.plot_gradient(idx))

    st.plotly_chart(pass_searched.plot_heatmap())


def from_pass_to_pd(pass_searched: list[Pass]) -> pd.DataFrame:
    info = dict()
    for data in pass_searched:
        info.update(
            {
                data.name: {
                    "alt": data.alt,
                    "coord": data.coord,
                    "country": data.country,
                    "region": data.region,
                    "height [m]": data.height,
                    "link": data.url,
                }
            }
        )

    return pd.DataFrame(info).T


def from_path_to_pd(
    pass_searched: list[Pass],
) -> tuple[pd.DataFrame, int]:

    info = dict()
    num_paths = 0
    for data in pass_searched:

        for i in range(data.num_pathes):
            info.update(
                {
                    f"{data.name} - {i+1}": {
                        "path direction": data.path_names[i],
                        "distance [km]": f"{data.total_distance[i]:.1f}",
                        "elevation [m]": f"{data.total_elevation[i]}",
                        "avg_grad [%]": f"{data.avg_grad[i]:.1f}",
                        "link": data.gpts[str(i)]["url"],
                    }
                }
            )
            num_paths += 1

    return pd.DataFrame(info).T, num_paths


def get_table(
    pass_searched: list[Pass], search_type: str
) -> Optional[pd.DataFrame]:

    with st.spinner("Retrieving data ..."):

        with st.spinner("Processing ..."):
            if search_type == "height":
                pass_df = from_pass_to_pd(pass_searched)
                st.write(f"A total of {len(pass_searched)} Passes are found.")
            else:
                pass_df, num_paths = from_path_to_pd(pass_searched)
                st.write(f"A total of {num_paths} climb paths are found.")

    return pass_df


def display_table(df: pd.DataFrame) -> None:
    st.write("List of searched Passes:")
    st.dataframe(df)


def display_hist(
    df: pd.DataFrame, attr: str, bounds: Optional[list[float]]
) -> None:
    import plotly.express as px

    data = df[attr].to_numpy(dtype=np.float64)

    if data.size > 10:
        # Only plot data if searched results return more than 10 data

        if bounds is None:
            bin_size = int((data.max() - data.min()) / 20)
            counts, bins = np.histogram(
                data, bins=range(int(data.min()), int(data.max()), bin_size)
            )
        else:
            bin_size = int((bounds[1] - bounds[0]) / 20)

            counts, bins = np.histogram(
                data, bins=range(bounds[0], bounds[1], bin_size)
            )

        bins = 0.5 * (bins[:-1] + bins[1:])

        fig = px.bar(x=bins, y=counts, labels={"x": f"{attr}", "y": "counts"})

        st.write("Statistics of searched Passes:")
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Name", "Distance", "Height", "Elevation", "Region", "Country"]
    )

    with tab1:
        st.header("Search Passes by name")

        pass_searched = pyqupa_pass_search("name")
        if pass_searched is not None:
            pyqupa_app_title(pass_searched[0])
            pyqupa_app_map_selector(pass_searched[0])
            pyqupa_app_gradient_plots(pass_searched[0])

    with tab2:
        st.header("Search Passes by distance")

        bounds = st.slider("Select search range.", 0, 40, (10, 30))
        st.write(
            f"Searching Pass's path distance from {bounds[0]} km to {bounds[1]} km ..."
        )

        pass_searched = pyqupa_pass_search_by_bounds(bounds, "distance")
        df = get_table(pass_searched, "distance")
        if df is not None:
            display_hist(df, "distance [km]", bounds)
            display_table(df)

    with tab3:
        st.header("Search Passes by altitude")

        bounds = st.slider("Select search range.", 0, 3000, (1000, 2000))
        st.write(
            f"Searching Pass elevation from {bounds[0]} m to {bounds[1]} m ..."
        )

        pass_searched = pyqupa_pass_search_by_bounds(bounds, "height")
        df = get_table(pass_searched, "height")
        if df is not None:
            display_hist(df, "height [m]", bounds)
            display_table(df)

    with tab4:
        st.header("Search Passes by elevation gain")

        bounds = st.slider("Select search range.", 0, 2500, (500, 2000))
        st.write(
            f"Searching Pass elevation gain from {bounds[0]} m to {bounds[1]} m ..."
        )

        pass_searched = pyqupa_pass_search_by_bounds(bounds, "elevation")
        df = get_table(pass_searched, "elevation")
        if df is not None:
            display_hist(df, "elevation [m]", bounds)
            display_table(df)

    with tab5:
        st.header("Search Passes by region")
        pass_searched = pyqupa_pass_search("region")
        df = get_table(pass_searched, "region")

        if df is not None:
            display_hist(df, "elevation [m]", None)
            display_hist(df, "distance [km]", None)
            display_table(df)

    with tab6:
        st.header("Search Passes by country")
        pass_searched = pyqupa_pass_search("country")
        df = get_table(pass_searched, "country")

        if df is not None:
            display_hist(df, "elevation [m]", None)
            display_hist(df, "distance [km]", None)
            display_table(df)
