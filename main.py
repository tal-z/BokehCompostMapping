from bokeh.plotting import figure, output_file, show
from bokeh.models import GeoJSONDataSource, WheelZoomTool, HoverTool, LabelSet, CustomJS, Label
from bokeh.tile_providers import CARTODBPOSITRON_RETINA, get_provider
import json
import geopandas as gpd
import pyodbc
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import os
load_dotenv()

today = datetime.today().date()

output_file(r"SitesEligibleForRouting.html")
tile_provider = get_provider(CARTODBPOSITRON_RETINA)

# Prep Community Districts Data for Plotting
districts_gdf = gpd.read_file(r'Data/CommunityDistricts.geojson')
districts_gdf.crs = 'epsg:4326'
districts_gdf = districts_gdf.to_crs('epsg:3857')
districts_gdf['centroid_x'] = districts_gdf['geometry'].apply(lambda x: str(x.centroid.x))
districts_gdf['centroid_y'] = districts_gdf['geometry'].apply(lambda y: str(y.centroid.y))
districts_json = districts_gdf.to_json()
districts_data = json.loads(districts_json)

# Find extents for display
districts_gdf['bounds'] = districts_gdf.geometry.apply(lambda x: x.bounds)
x_values = [val[0] for val in districts_gdf['bounds']] + [val[2] for val in districts_gdf['bounds']]
x_range = (min(x_values), max(x_values))

y_values = [val[1] for val in districts_gdf['bounds']] + [val[3] for val in districts_gdf['bounds']]
y_range = (min(y_values), max(y_values))



# Prep "Eligible for Routing" Data for Plotting
server = os.getenv('server')
database = os.getenv('database')
username = os.getenv('user')
password = os.getenv('password')
cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+ password)
cursor = cnxn.cursor()
query = "SELECT * FROM [CompostingDB].[compost].[vw_CurbsideCompostingEnrollments_EligibleForRouting_ForMapping] ;"
eligible_for_routing_df = pd.read_sql(query, cnxn)
eligible_for_routing_gdf = \
    gpd.GeoDataFrame(data=eligible_for_routing_df,
                     geometry=gpd.points_from_xy(
                         eligible_for_routing_df.AddressPointLongitude, 
                         eligible_for_routing_df.AddressPointLatitude)
                     )
eligible_for_routing_gdf.crs = 'epsg:4326'
eligible_for_routing_gdf = eligible_for_routing_gdf.to_crs('epsg:3857')
eligible_for_routing_gdf['EnrollmentDateCreated'] = eligible_for_routing_gdf['EnrollmentDateCreated'].astype(str)
eligible_for_routing_gdf['EnrollmentDateLastUpdated'] = eligible_for_routing_gdf['EnrollmentDateLastUpdated'].astype(str)
eligible_for_routing_gdf['DateLastUpdatedServiceStatus'] = eligible_for_routing_gdf['DateLastUpdatedServiceStatus'].astype(str)
count_of_enrollments = eligible_for_routing_gdf[['AddressPointId','Id']].groupby('AddressPointId').count()
count_of_enrollments.columns = ['count_of_enrollments']
eligible_for_routing_gdf.drop_duplicates(subset=['AddressPointId'], inplace=True)
eligible_for_routing_gdf = eligible_for_routing_gdf.merge(count_of_enrollments, on='AddressPointId')

eligible_sites_json = eligible_for_routing_gdf.to_json()
eligible_sites_data = json.loads(eligible_sites_json)


# Plot the data
districts_geo_source = GeoJSONDataSource(geojson=json.dumps(districts_data))
eligible_sites_geo_source = GeoJSONDataSource(geojson=json.dumps(eligible_sites_data))
tooltips = [("Site Name", "@AccountName"),
            ("Address", "@HouseNumber" + " " + "@StreetName" + " " + "@City" + ", " + "@Zip"),
            ("Number of Enrollments", "@count_of_enrollments")
            ]


hover = HoverTool(names=["sites"], tooltips=tooltips)

p = figure(x_range=x_range, y_range=y_range)
p.toolbar.active_scroll = p.select_one(WheelZoomTool)
p.add_tools(hover)
p.sizing_mode = 'stretch_both'
p.add_tile(tile_provider)
p.patches(xs='xs', ys='ys', color='lightgreen', alpha=.2, source=districts_geo_source, )
p.circle(x='x', y='y', color='orangered', alpha=.2, size=6, source=eligible_sites_geo_source, name='sites')

labels = LabelSet(x='centroid_x', y='centroid_y', text='boro_cd',
              x_offset=0, y_offset=0, source=districts_geo_source, render_mode='canvas', text_font_size='10pt')
p.add_layout(labels)



code= '''if (cb_data.index.indices.length > 2) {
            document.getElementsByClassName('bk-tooltip')[0].style.display = 'none'; 
        }'''
p.hover.callback = CustomJS(code=code)

citation1 = Label(x=70, y=70, x_units='screen', y_units='screen',
                 text=f'Last Updated: {today}', render_mode='css',
                 border_line_color='black', border_line_alpha=1.0,
                 background_fill_color='white', background_fill_alpha=1.0)
citation2 = Label(x=70, y=48, x_units='screen', y_units='screen',
                 text=f'Made by Tal Zaken', render_mode='css',
                 border_line_color='black', border_line_alpha=1.0,
                 background_fill_color='white', background_fill_alpha=1.0)

p.add_layout(citation1)
p.add_layout(citation2)

p.title.text = "Sites Eligible for Routing"
p.title.align = "center"
p.title.text_font_size = "25px"

p.axis.visible = False

show(p)
