__author__ = 'alex styler'

import math

import pandas as pd
import numpy as np
import fiona as fio
from matplotlib.collections import PathCollection
from mpl_toolkits.basemap import Basemap
from matplotlib.patches import Path


# haversine function courtesy of https://gist.github.com/rochacbruno/2883505
def haversine(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) \
                                                  * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(
        dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = radius * c

    return d


def create_basemap(ll_lon, ll_lat, ur_lon, ur_lat):
    # Compute width and height in degrees
    w, h = ur_lon - ll_lon, ur_lat - ll_lat
    wpadding = 0.03
    hpadding = 0.04

    # This will work poorly at poles and +179 and -179
    mlon = (ll_lon + ur_lon) / 2.
    mlat = (ll_lat + ur_lat) / 2.

    m = Basemap(
        projection='merc',
        lon_0=mlon,
        lat_0=mlat,
        ellps='WGS84',
        llcrnrlon=ll_lon - wpadding * w,
        llcrnrlat=ll_lat - hpadding * h,
        urcrnrlon=ur_lon + wpadding * w,
        urcrnrlat=ur_lat + hpadding * h,
        lat_ts=0,
        resolution='c',
        suppress_ticks=True)

    return m


class MLMap(object):
    def __init__(self, lower_left_corner, upper_right_corner):
        self.basemap = create_basemap(lower_left_corner[0], lower_left_corner[1], upper_right_corner[0],
                                      upper_right_corner[1])
        self.shapes = pd.DataFrame()
        self.shapes_to_draw = []

    def convert_coordinates(self, coordinates):
        return np.array([self.basemap(lat, lon) for lat, lon in coordinates])

    def load_shape_file(self, file_name):
        shape_file = fio.open(file_name)

        paths = []

        for shape in shape_file:
            if shape['geometry']['type'] == 'Polygon':
                path = Path(self.convert_coordinates(shape['geometry']['coordinates'][0]), readonly=True)
            elif shape['geometry']['type'] == 'LineString':
                path = Path(self.convert_coordinates(shape['geometry']['coordinates']), readonly=True)
            else:
                path = None

            paths.append(path)

        new_shapes = pd.DataFrame(shape['properties'] for shape in shape_file)
        new_shapes['path'] = paths

        new_shapes = new_shapes[new_shapes.path.notnull()]

        self.shapes = self.shapes.append(new_shapes)

    def select_shapes(self, shapes):
        # Shapes are a dictionary structure with the following keys:
        # { 'feature', 'value', 'args' }
        # Shapes where 'feature' == 'value' are selected
        # args are passed to path collection, stuff like linewidth, colors, zorders, etc.
        for shape in shapes:
            self.select_shape(shape['feature'], shape['value'], **shape['args'])

    def select_shape(self, feature, value, **kwargs):
        self.shapes_to_draw.append(
            {'shapes': self.shapes[(self.shapes[feature] == value)]['path'].values,
             'args': kwargs})

    def draw_map(self, ax, **kwargs):
        if 'fill' in kwargs:
            color = kwargs['fill']
        else:
            color = 'white'

        self.basemap.fillcontinents(color, ax=ax, zorder=1)

        for shapec in self.shapes_to_draw:
            ax.add_collection(PathCollection(shapec['shapes'], **shapec['args']))

    def clear_selected_shapes(self):
        self.shapes_to_draw = []

    def clear_loaded_shapefiles(self):
        self.shapes = pd.DataFrame()
