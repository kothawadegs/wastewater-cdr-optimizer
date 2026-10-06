import pandas as pd
import geopandas as gpd
from typing import Tuple

class WAESpatialOptimizer:
    def __init__(self, epsg_code: int = 3310):
        """Initializes pipeline with standard California Albers projection."""
        self.epsg_code = epsg_code
        self.co2_yield_per_mgd = 60

    def load_and_project(self, epa_path: str, usgs_path: str) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Loads CSVs and projects to local CRS."""
        epa_df = pd.read_csv(epa_path)
        usgs_df = pd.read_csv(usgs_path)

        epa_gdf = gpd.GeoDataFrame(
            epa_df, geometry=gpd.points_from_xy(epa_df.Longitude, epa_df.Latitude), crs="EPSG:4326"
        )
        usgs_gdf = gpd.GeoDataFrame(
            usgs_df, geometry=gpd.points_from_xy(usgs_df.Longitude, usgs_df.Latitude), crs="EPSG:4326"
        )
        return epa_gdf.to_crs(epsg=self.epsg_code), usgs_gdf.to_crs(epsg=self.epsg_code)

    def compute_logistics_join(self, epa_gdf: gpd.GeoDataFrame, usgs_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Executes vectorized nearest-neighbor spatial join."""
        joined = gpd.sjoin_nearest(epa_gdf, usgs_gdf, how="left", distance_col="haul_distance_meters")
        joined['haul_distance_miles'] = joined['haul_distance_meters'] * 0.000621371
        return joined

    def calculate_viability(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Calculates yields and Viability Index."""
        gdf['est_co2_t_yr'] = gdf['flow_mgd'] * self.co2_yield_per_mgd
        gdf['viability_index'] = gdf['flow_mgd'] / (gdf['haul_distance_miles'] + 0.1)
        return gdf.sort_values(by='viability_index', ascending=False)

    def export_pipeline(self, epa_path: str, usgs_path: str, out_path: str):
        """Orchestrates pipeline and exports GeoJSON."""
        epa_gdf, usgs_gdf = self.load_and_project(epa_path, usgs_path)
        logistics_gdf = self.compute_logistics_join(epa_gdf, usgs_gdf)
        final_gdf = self.calculate_viability(logistics_gdf)
        
        final_gdf.to_crs(epsg=4326).to_file(out_path, driver="GeoJSON")
        print(f"Pipeline executed. Artifact saved to {out_path}")
