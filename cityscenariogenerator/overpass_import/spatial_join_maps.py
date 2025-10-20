"""
Can plot maps of various spatial joins of OSM data, BUILDA data, and custom POIs.
"""

import geopandas as gpd  # type: ignore
import pandas as pd
import folium

from cityscenariogenerator.plots.building_map_interactive import MARKER_COLORS
import cityscenariogenerator.plots.unmapped_building_map as buil_map
from cityscenariogenerator import builda_client_import, geoutils
from cityscenariogenerator.overpass_import import overpass_query
from cityscenariogenerator.overpass_import import osm_data_join
from cityscenariogenerator.geoutils import GeoDFColumns


def add_popup_column(df: pd.DataFrame, id: str = GeoDFColumns.BUILDA_ID):
    df["popup"] = df[id] + "\n" + df[GeoDFColumns.CATEGORY]


def add_markers_for_df(df: pd.DataFrame, m, color: str, geometry_col: str):
    for _, row in df.iterrows():
        folium.Marker(
            location=[row[geometry_col].y, row[geometry_col].x],
            popup=row.get("popup"),
            icon=folium.Icon(color=color),
        ).add_to(m)


def plot_map(dataframes: list[gpd.GeoDataFrame], name: str):
    # create a new column with coordinates in the correct format
    geo_col = "geometry_4326"
    for df in dataframes:
        df.loc[:, geo_col] = df.geometry.to_crs("EPSG:4326")
    # use the first non-empty dataframe to determine centre coordinates
    map_center = next(
        [
            df[geo_col].y.mean(),
            df[geo_col].x.mean(),
        ]
        for df in dataframes
        if len(df) > 0
    )
    # create a Folium map centered on the average coordinates
    map_1 = folium.Map(
        location=map_center,
        zoom_start=12,
    )
    # marker_cluster = folium.plugins.MarkerCluster().add_to(map_1)
    # create markers for each dataframe
    for i, df in enumerate(dataframes):
        color = MARKER_COLORS[i % len(MARKER_COLORS)]
        add_markers_for_df(df, map_1, color, geo_col)

    # Save map to an HTML file and display
    map_1.save(name)
    map_1.show_in_browser()


def show_osm_builda_join_on_map():
    city = "Jülich"
    # load overpass building data
    overpass_df = gpd.read_file(f"scenario_inputs/{city}/osm_nonres_nodes.geojson")
    # determine the LPG location type for each OSM node ID
    keys = overpass_query.get_osm_keys_for_mapping()
    osm_node_locations = osm_data_join.map_osm_nodes_to_locations(overpass_df, keys)
    overpass_df[GeoDFColumns.CATEGORY] = overpass_df[GeoDFColumns.EXT_ID].map(
        lambda id: next(iter(osm_node_locations[id].non_work_locations))
    )

    # load custom POIs
    poi_path = f"scenario_inputs/{city}/custom_pois_dasörtliche.json"
    poi_df_oe = osm_data_join.load_custom_poi_geodf(poi_path)
    poi_path = f"scenario_inputs/{city}/custom_pois_dastelefonbuch.json"
    poi_df_tb = osm_data_join.load_custom_poi_geodf(poi_path)

    # load BUILDA data
    builda_query = {
        "city": city,
        # "postcode": "52066",
        # "street": "Eupener Straße",
    }
    nonres_buildings = builda_client_import.get_nonresidential_buildings(builda_query)
    res_buildings = builda_client_import.get_residential_buildings(builda_query)
    # convert BUILDA objects to GeoDataFrames and add a category column
    builda_nonres_df = geoutils.builda_to_geodf(nonres_buildings)
    builda_nonres_df[GeoDFColumns.CATEGORY] = [
        buil_map.get_building_category_alkis(b) for b in nonres_buildings
    ]
    builda_res_df = geoutils.builda_to_geodf(res_buildings)
    builda_res_df.loc[:, GeoDFColumns.CATEGORY] = ["residential"] * len(builda_res_df)
    builda_df = osm_data_join.concat_builda_dfs(builda_nonres_df, builda_res_df)

    # add a column for the popup text
    add_popup_column(builda_res_df)
    add_popup_column(builda_nonres_df)
    add_popup_column(builda_df)
    add_popup_column(poi_df_oe, GeoDFColumns.EXT_ID)
    add_popup_column(poi_df_tb, GeoDFColumns.EXT_ID)
    add_popup_column(overpass_df, GeoDFColumns.EXT_ID)

    # convert to Web Mercator projection to get correct distances
    overpass_df.to_crs("EPSG:3857", inplace=True)
    builda_df.to_crs("EPSG:3857", inplace=True)
    poi_df_oe.to_crs("EPSG:3857", inplace=True)
    poi_df_tb.to_crs("EPSG:3857", inplace=True)

    # filter for testing
    overpass_df = overpass_df[overpass_df[GeoDFColumns.CATEGORY] == "Doctors Office"]

    poi_dfs = [overpass_df, poi_df_oe, poi_df_tb]
    combined_df = osm_data_join.combine_poi_dfs(poi_dfs, 30)

    # spatial join
    joined_df = gpd.sjoin_nearest(
        combined_df,
        builda_df,
        distance_col=GeoDFColumns.DISTANCE,
        exclusive=False,
        max_distance=30,
    )
    # joined_df = osm_data_join.remove_duplicate_matches(joined_df)
    # set popup column for the map plot
    joined_df["popup"] = (
        joined_df[GeoDFColumns.EXT_ID]
        + " - "
        + joined_df[GeoDFColumns.BUILDA_ID]
        + "\n"
        + joined_df["category_left"]
        + "\n"
        + joined_df[GeoDFColumns.DISTANCE].round(1).astype(str)
        + " m"
    )

    print(
        f"OSM: {len(overpass_df)}, DasÖrtliche POIs: {len(poi_df_oe)}, DasTelefonbuch POIS: {len(poi_df_tb)}"
    )
    print(f"Matches: {len(joined_df)}")

    # determine the BUILDA buildings that were matched
    builda_res_matched = osm_data_join.filter_matched(builda_res_df, joined_df)
    builda_nonres_matched = osm_data_join.filter_matched(builda_nonres_df, joined_df)

    plot_map(
        [builda_res_matched, builda_nonres_matched, combined_df, joined_df],
        "health_map.html",
    )


if __name__ == "__main__":
    show_osm_builda_join_on_map()
