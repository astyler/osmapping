__author__ = 'alex styler'

import math

import pandas as pd
import numpy as np
import fiona as fio
from matplotlib.figure import Figure
from matplotlib.collections import PathCollection
from mpl_toolkits.basemap import Basemap
from matplotlib.patches import Path
from matplotlib.transforms import Bbox



# haversine function code courtesy of https://gist.github.com/rochacbruno/2883505
def haversine(origin, destination):
    """ haversine formula to get distance in meters
    :param origin: (lat, lon) pair
    :param destination:  (lat, lon) pair
    :return: distance in meters
    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = radius * c

    return d


# TODO fix for poles and 180 degrees longitude


class MLMap(object):
    def __init__(self, lower_left_corner, upper_right_corner, projection='merc'):
        """ Create a map view over the specified projection
        :param lower_left_corner: (lon, lat) coordinates in degrees
        :param upper_right_corner: (lon, lat) coordinates in degrees
        :param projection: which projection to use, legal list from mpl_toolkits.basemap
        :return:
        """
        self.basemap = MLMap.__create_basemap(lower_left_corner[0], lower_left_corner[1], upper_right_corner[0],
                                              upper_right_corner[1], projection=projection)
        self.shapes = pd.DataFrame()
        self.shapes_to_draw = []
        llc = self.basemap(lower_left_corner[0], lower_left_corner[1])
        urc = self.basemap(upper_right_corner[0], upper_right_corner[1])

        #self.bbox = Bbox([llc, urc])
        self.bbox = (lower_left_corner[0], lower_left_corner[1], upper_right_corner[0], upper_right_corner[1])

    @staticmethod
    def __create_basemap(ll_lon, ll_lat, ur_lon, ur_lat, wpadding=0.03, hpadding=0.04, projection='merc'):
        # Compute width and height in degrees
        w, h = ur_lon - ll_lon, ur_lat - ll_lat

        # This will work poorly at poles and +179 and -179
        mlon = (ll_lon + ur_lon) / 2.
        mlat = (ll_lat + ur_lat) / 2.

        m = Basemap(
            projection=projection,
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

    def convert_coordinates(self, coordinates):
        """ Converts coordinates to plot x,y coordinates
        :param coordinates: List of coordinates pairs to convert [(lon1, lat1)...(lon9, lat9)]
        :return: list of plot coordinates, [(x1,y1)...(x9,y9)]
        """
        return np.array(zip(*self.basemap(*zip(*coordinates))))

    # use osmapi to import a selected node into the map
    def import_osm_node(self, node_id, server='defaultserveraddress'):
        """ Not implemented, signature may change
        :param node_id:
        :param server:
        :return:
        """
        raise NotImplementedError('Not implemented, only Mapzen shapefiles at the moment')

    # use osm turbo query library to import shapes into the database
    def import_turbo_query(self, query, server='defaultserveraddress'):
        """ Not implemented, signature may change
        :param query:
        :param server:
        :return:
        """
        raise NotImplementedError('Not implemented, only Mapzen shapefiles at the moment')

    # may need to define a unifying shape/data class that can be used by Mapzen, osmapi,
    # and turbo queries.  something that is easily selectable

    # can load polygons or line shapefiles.  does not yet support points.  only loads in paths
    # for drawing, but not text or labels of any kind.  will need to expand upon inspecting the
    # properties of polys, lines, and points.   also does not support Multipolygons yet, but that
    # should be an easy fix.
    def load_shape_file(self, file_name, clip_to_view=True):
        """ Loads in a shapefile to the map, from OpenStreetMaps or other services
        :param file_name: Filename of .shp file to be imported
        :param clip_to_view: if true, only loads shapes in the specified view window
        :return: None
        """

        shape_paths = []
        properties = []

        # convert shape_paths to x,y of map view and remove all shapes outside the view window
        # consider moving bbox check to lat/lon and checking before conversion to save computation

        with fio.open(file_name) as shape_file:
            if clip_to_view:
                shape_file = shape_file.filter(bbox=self.bbox)

            for shape in shape_file:

                clist = []
                shape_type = shape['geometry']['type']
                coords = shape['geometry']['coordinates']
                if shape_type == 'Polygon':
                    clist.append(coords[0])
                elif shape_type == 'LineString':
                    clist.append(coords)
                elif shape_type == 'MultiPolygon':
                    clist.extend(poly[0] for poly in coords)

                for coords in clist:
                    path = Path(self.convert_coordinates(coords), readonly=True)

                    if path is not None:
                        properties.append(shape['properties'])
                        shape_paths.append(path)

        new_shapes = pd.DataFrame(properties)
        new_shapes['path'] = shape_paths

        new_shapes = new_shapes[new_shapes.path.notnull()]

        self.shapes = self.shapes.append(new_shapes)

    def select_shape(self, feature, value, **kwargs):
        """ Selects shapes for plotting where shape[feature] == value
        :param feature: Feature string to match value on such as 'highway'
        :param value: Value to select, such as 'motorway'
        :param kwargs: arguments for the drawing
        :return:
        """
        self.shapes_to_draw.append(
            {'shapes': self.shapes[(self.shapes[feature] == value)]['path'].values,
             'args': kwargs})

    def select_shapes(self, select_function, **kwargs):
        """ Selects shapes based on an arbitrary function such as: lambda shape: shape['highway'] == 'motorway'
        :param select_function: boolean function to include a shape or not
        :param kwargs: arguments for the drawing
        :return:
        """
        self.shapes_to_draw.append(
            {'shapes': self.shapes[self.shapes.apply(select_function, axis=1)]['path'].values,
             'args': kwargs}
        )

    def draw_map(self, ax=None, map_fill='white'):
        """
        :param ax: Matplotlib axes on which to draw this map
        :param map_fill: base color of continents on the map
        :return: handle to axes
        """
        if ax is None:
            fig = Figure()
            ax = fig.add_subplot(111)

        # is there some option to fill in oceans?  maybe as background color to the fig/ax
        self.basemap.fillcontinents(map_fill, ax=ax, zorder=1)

        for shapec in self.shapes_to_draw:
            ax.add_collection(PathCollection(shapec['shapes'], **shapec['args']))

        return ax

    def clear_selected_shapes(self):
        """ Clears selected shapes for next draw
        :return: None
        """
        self.shapes_to_draw = []

    def clear_loaded_shapefiles(self):
        """ Clears the loaded shape database
        :return: None
        """
        self.shapes = pd.DataFrame()
