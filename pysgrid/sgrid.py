'''
Created on Apr 20, 2015

@author: ayan
'''

from __future__ import (absolute_import, division, print_function)

from netCDF4 import Dataset
import numpy as np

from .read_netcdf import NetCDFDataset, parse_padding, find_grid_topology_var
from .utils import calculate_angle_from_true_east, pair_arrays, points_in_polys
from .variables import SGridVariable


class SGrid(object):

    grid_names = ['node', 'face', 'edge1', 'edge2']
    padding_slices = {'both': (1, -1),
                      'none': (None, None),
                      'low': (1, None),
                      'high': (None, 1)
                      }

    topology_dimension = 2

    def __init__(self,
                 node_lon=None,
                 node_lat=None,
                 center_lon=None,
                 center_lat=None,
                 edge1_lon=None,
                 edge1_lat=None,
                 edge2_lon=None,
                 edge2_lat=None,
                 edges=None,
                 node_padding=None,
                 edge1_padding=None,
                 edge2_padding=None,
                 grid_topology_var=None,
                 variables=None,
                 grid_variables=None,
                 dimensions=None,
                 node_dimensions=None,
                 node_coordinates=None,
                 edge1_coordinates=None,
                 edge2_coordinates=None,
                 angles=None,
                 edge1_dimensions=None,
                 edge2_dimensions=None,
                 faces=None,
                 face_padding=None,
                 face_coordinates=None,
                 face_dimensions=None,
                 vertical_padding=None,
                 vertical_dimensions=None,
                 *args,
                 **kwargs):

        self.node_lon = node_lon
        self.node_lat = node_lat
        self.center_lon = center_lon
        self.center_lat = center_lat
        self.edge1_lon = edge1_lon
        self.edge1_lat = edge1_lat
        self.edge2_lon = edge2_lon
        self.edge2_lat = edge2_lat
        self.edges = edges
        self.node_padding = node_padding
        self.edge1_padding = edge1_padding
        self.edge2_padding = edge2_padding
        self.grid_topology_var = grid_topology_var
        self.variables = variables
        self.grid_variables = grid_variables
        self.dimensions = dimensions
        self.node_dimensions = node_dimensions
        self.node_coordinates = node_coordinates
        self.edge1_coordinates = edge1_coordinates
        self.edge2_coordinates = edge2_coordinates
        self.angles = angles
        self.edge1_dimensions = edge1_dimensions
        self.edge2_dimensions = edge2_dimensions
        self.faces = faces
        self.face_padding = face_padding
        self.face_coordinates = face_coordinates
        self.face_dimensions = face_dimensions
        self.vertical_padding = vertical_padding
        self.vertical_dimensions = vertical_dimensions

    @classmethod
    def load_grid(cls, nc):
        if isinstance(nc, Dataset):
            pass
        else:
            nc = Dataset(nc, 'r')
        topology_var = find_grid_topology_var(nc)
        sa = SGridAttributes(nc, cls.topology_dimension, topology_var)
        dimensions = sa.get_dimensions()
        node_dimensions, node_coordinates = sa.get_node_coordinates()
        grid_topology_var = sa.get_topology_var()
        edge1_dimensions, edge1_padding = sa.get_attr_dimension('edge1_dimensions')  # noqa
        edge2_dimensions, edge2_padding = sa.get_attr_dimension('edge2_dimensions')  # noqa
        edge1_coordinates = sa.get_attr_coordinates('edge1_coordinates')
        edge2_coordinates = sa.get_attr_coordinates('edge2_coordinates')
        angles = sa.get_angles()
        vertical_dimensions, vertical_padding = sa.get_attr_dimension('vertical_dimensions')  # noqa
        node_lon, node_lat = sa.get_cell_node_lat_lon()
        center_lon, center_lat = sa.get_cell_center_lat_lon()
        edge1_lon, edge1_lat = sa.get_cell_edge1_lat_lon()
        edge2_lon, edge2_lat = sa.get_cell_edge2_lat_lon()
        face_dimensions, face_padding = sa.get_attr_dimension('face_dimensions')  # noqa
        face_coordinates = sa.get_attr_coordinates('face_coordinates')
        sgrid = cls(angles=angles,
                    node_lon=node_lon,
                    node_lat=node_lat,
                    center_lon=center_lon,
                    center_lat=center_lat,
                    edge1_lon=edge1_lon,
                    edge1_lat=edge1_lat,
                    edge2_lon=edge2_lon,
                    edge2_lat=edge2_lat,
                    dimensions=dimensions,
                    edge1_coordinates=edge1_coordinates,
                    edge1_dimensions=edge1_dimensions,
                    edge1_padding=edge1_padding,
                    edge2_coordinates=edge2_coordinates,
                    edge2_dimensions=edge2_dimensions,
                    edge2_padding=edge2_padding,
                    edges=None,
                    face_coordinates=face_coordinates,
                    face_dimensions=face_dimensions,
                    face_padding=face_padding,
                    faces=None,
                    grid_topology_var=grid_topology_var,
                    grid_variables=None,
                    node_coordinates=node_coordinates,
                    node_dimensions=node_dimensions,
                    node_padding=None,
                    variables=None,
                    vertical_dimensions=vertical_dimensions,
                    vertical_padding=vertical_padding)
        sa.get_variable_attributes(sgrid)
        return sgrid

    def get_all_face_padding(self):
        if self.face_padding is not None:
            all_face_padding = self.face_padding
        else:
            all_face_padding = []
        return all_face_padding

    def get_all_edge_padding(self):
        all_edge_padding = []
        if self.edge1_padding is not None:
            all_edge_padding += self.edge1_padding
        if self.edge2_padding is not None:
            all_edge_padding += self.edge2_padding
        return all_edge_padding

    def all_padding(self):
        all_padding = self.get_all_face_padding() + self.get_all_edge_padding()
        if self.vertical_padding is not None:
            all_padding += self.vertical_padding
        return all_padding

    def save_as_netcdf(self, filepath):
        with Dataset(filepath, 'w') as nclocal:
            grid_vars = self._save_common_components(nclocal)
            # Add attributes to the grid_topology variable.
            grid_vars.face_dimensions = self.face_dimensions
            if self.vertical_dimensions is not None:
                grid_vars.vertical_dimensions = self.vertical_dimensions
            if self.face_coordinates is not None:
                grid_vars.face_coordinates = ' '.join(self.face_coordinates)

    @property
    def non_grid_variables(self):
        non_grid_variables = [variable for variable in self.variables if
                              variable not in self.grid_variables]
        return non_grid_variables

    def _save_common_components(self, nc_file):
        grid_var = self.grid_topology_var
        # Create dimensions.
        for grid_dim in self.dimensions:
            dim_name, dim_size = grid_dim
            nc_file.createDimension(dim_name, dim_size)
        # Create variables.
        center_lon, center_lat = self.face_coordinates
        center_lon_obj = getattr(self, center_lon)
        center_lat_obj = getattr(self, center_lat)
        center_lon = nc_file.createVariable(center_lon_obj.variable,
                                            center_lon_obj.dtype,
                                            center_lon_obj.dimensions)
        center_lat = nc_file.createVariable(center_lat_obj.variable,
                                            center_lat_obj.dtype,
                                            center_lat_obj.dimensions)
        center_lon[:] = self.center_lon[:]
        center_lat[:] = self.center_lat[:]
        try:
            node_lon, node_lat = self.node_coordinates
        except TypeError:
            pass
        else:
            node_lon_obj = getattr(self, node_lon)
            grid_node_lon = nc_file.createVariable(node_lon_obj.variable,
                                                   node_lon_obj.dtype,
                                                   node_lon_obj.dimensions)
            node_lat_obj = getattr(self, node_lat)
            grid_node_lat = nc_file.createVariable(node_lat_obj.variable,
                                                   node_lat_obj.dtype,
                                                   node_lat_obj.dimensions)
            grid_node_lon[:] = self.node_lon[:]
            grid_node_lat[:] = self.node_lat[:]
        grid_var_obj = getattr(self, grid_var)
        grid_vars = nc_file.createVariable(grid_var_obj.variable,
                                           grid_var_obj.dtype)
        grid_vars.cf_role = 'grid_topology'
        grid_vars.topology_dimension = self.topology_dimension
        grid_vars.node_dimensions = self.node_dimensions
        if self.edge1_dimensions is not None:
            grid_vars.edge1_dimensions = self.edge1_dimensions
        if self.edge2_dimensions is not None:
            grid_vars.edge2_dimensions = self.edge2_dimensions
        if self.node_coordinates is not None:
            grid_vars.node_coordinates = ' '.join(self.node_coordinates)
        if self.edge1_coordinates is not None:
            grid_vars.edge1_coordinates = ' '.join(self.edge1_coordinates)
        if self.edge2_coordinates is not None:
            grid_vars.edge2_coordinates = ' '.join(self.edge2_coordinates)
        if hasattr(self, 'angle'):
            angle_obj = getattr(self, 'angle', None)
            grid_angle = nc_file.createVariable(angle_obj.variable,
                                                angle_obj.dtype,
                                                angle_obj.dimensions
                                                )
            if self.angles is not None:
                grid_angle[:] = self.angles[:]
        for dataset_variable in self.variables:
            dataset_var_obj = getattr(self, dataset_variable)
            try:
                dataset_grid_var = nc_file.createVariable(
                    dataset_var_obj.variable,
                    dataset_var_obj.dtype,
                    dataset_var_obj.dimensions
                )
            except RuntimeError:
                continue
            else:
                axes = []
                if dataset_var_obj.grid is not None:
                    dataset_grid_var.grid = grid_var
                if dataset_var_obj.standard_name is not None:
                    dataset_grid_var.standard_name = dataset_var_obj.standard_name  # noqa
                if dataset_var_obj.coordinates is not None:
                    dataset_grid_var.coordinates = ' '.join(dataset_var_obj.coordinates)  # noqa
                if dataset_var_obj.x_axis is not None:
                    x_axis = 'X: {0}'.format(dataset_var_obj.x_axis)
                    axes.append(x_axis)
                if dataset_var_obj.y_axis is not None:
                    y_axis = 'Y: {0}'.format(dataset_var_obj.y_axis)
                    axes.append(y_axis)
                if dataset_var_obj.z_axis is not None:
                    z_axis = 'Z: {0}'.format(dataset_var_obj.z_axis)
                    axes.append(z_axis)
                if axes:
                    dataset_grid_var.axes = ' '.join(axes)
        return grid_vars

    def _get_grid_vars(self, name):
        if name is 'node':
            return (self.node_lon, self.node_lat)
        elif name is 'center':
            return (self.center_lon, self.center_lat)
        elif name is 'edge1':
            return (self.edge1_lon, self.edge1_lat)
        elif name is 'edge2':
            return (self.edge2_lon, self.edge2_lat)
        else:
            raise ValueError('Invalid grid name')

    def _get_efficient_slice(self, lon_bounds, lat_bounds, name):
        '''
        given minimum and maximum longitudes and latitudes, find
        the most efficient slice for the specified grid that covers the
        entire specified area. 
        '''
        lons, lats = self._get_grid_vars(name)
        t = np.logical_and(lons >= lon_bounds[0], lons <= lon_bounds[1])
        np.logical_and(
            t, np.logical_and(lats >= lat_bounds[0], lats <= lat_bounds[1]), t)
        s = np.where(t)
        x_slice = slice(s[0].min(), s[0].max() + 1)
        y_slice = slice(s[1].min(), s[1].max() + 1)

        return (x_slice, y_slice)

    def get_grid(self, grid='node'):
        if grid not in SGrid.grid_names:
            raise ValueError(
                'Name not recognized. Grid must be in {0}'.format(grid_names))
        lons = getattr(self, grid + '_lon')
        lats = getattr(self, grid + '_lat')
        return np.ma.dstack((lons[:], lats[:]))

    def locate_faces(self, points):
        """
        Returns the node grid indices, one per point.

        Points that are not on the node grid will have an index of -1

        If a single point is passed in, a single index will be returned.
        If a sequence of points is passed in an array of indexes will be returned.

        :param points:  The points that you want to locate -- (lon, lat). If the shape of point
                        is 1D, function will return a scalar index. If it is 2D, it will return
                        a 1D array of indices.
        :type points: array-like containing one or more points: shape (2,) for one point, shape (N, 2)
                     for more than one point.

        This version utilizes the CellTree data structure.

        """
        points = np.asarray(points, dtype=np.float64)
        just_one = (points.ndim == 1)
        points = points.reshape(-1, 2)

        try:
            import cell_tree2d
        except ImportError:
            raise ImportError("the cell_tree2d package must be installed to use the celltree search:\n"
                              "https://github.com/NOAA-ORR-ERD/cell_tree2d/")
        if not hasattr(self, '_tree') or self._tree is None:
            self.build_celltree()
        indices = self._tree.multi_locate(points)
        node_x = indices % (self.node_lat.shape[1] - 1)
        node_y = indices // (self.node_lat.shape[1] - 1)
        node_ind = np.column_stack((node_y, node_x))
        node_ind[node_ind[:, 0] == -1] = [-1, -1]
        if just_one:
            return node_ind[0]
        else:
            return node_ind

    def get_variable_by_index(self, var, index):
        """
        Function to get the node values of a given face index.
        Emulates the 'self.grid.nodes[self.grid.nodes.faces[index]]' paradigm of unstructured grids.
        """

        arr = var[:]
        x = index[:, 0]
        y = index[:, 1]
        return np.ma.column_stack((arr[x, y], arr[x + 1, y], arr[x + 1, y + 1], arr[x, y + 1]))

    def build_celltree(self):
        """
        Tries to build the celltree for grid defined by the node coordinates.

        """
        from cell_tree2d import CellTree
        if self.node_lon is None or self.node_lat is None:
            raise ValueError(
                "node_lon and node_lat must be defined in order to create and use CellTree")
        if not hasattr(self, '_lin_faces') or not hasattr(self, '_lin_nodes') or self._lin_nodes is None or self._lin_faces is None:
            self._lin_nodes = np.ascontiguousarray(
                np.stack((self.node_lon, self.node_lat), axis=-1).reshape(-1, 2))
            y_size = self.node_lon.shape[0]
            x_size = self.node_lon.shape[1]
            self._lin_faces = np.array([np.array([[x, x + 1, x + x_size + 1, x + x_size]
                                                  for x in range(0, x_size - 1, 1)]) + y * x_size for y in range(0, y_size - 1)])
            self._lin_faces = np.ascontiguousarray(
                self._lin_faces.reshape(-1, 4).astype(np.int32))
        self._tree = CellTree(self._lin_nodes, self._lin_faces)

    def interpolate_var_to_points(self, points, variable, indices=None, alphas=None, mask=None):
        """
        Interpolates a variable on one of the grids to an array of points.
        :param points: Array of points to be interpolated to.
        :param variable: Variable data array with the same shape as one of the grids.
        :param indices: If computed already, array of indices can be passed in to increase speed.
        :param alphas: If computed already, array of alphas can be passed in to increase speed.
        :param mask: under development.

        """
        points = points.reshape(-1, 2)
        ind = indices
        if ind is None:
            ind = self.locate_faces(points)
        grid = self.infer_grid(variable)
        ind = self.translate_index(points, ind, grid)

        if alphas is None:
            alphas = self.interpolation_alphas(points, ind, grid)
        vals = self.get_variable_by_index(variable, ind)
        result = np.ma.sum(vals * alphas, axis=1)
        if mask is not None:
            # REVISIT LATER
            result.mask = mask[ind[:, 0], ind[:, 1]]
        off_grids = np.where(ind[:, 0] == -1)
        result[off_grids] = [np.nan, ]
        result.mask[off_grids] = True
        return result

    def infer_grid(self, variable):
        """
        Assuming default is psi grid, check variable dimensions to determine which grid
        it is on.
        """
        shape = np.array(variable.shape)
        difference = (shape - self.node_lon.shape).tolist()
        if difference == [1, 1]:
            return 'center'
        elif difference == [0, 1]:
            return 'edge1'
        elif difference == [1, 0]:
            return 'edge2'
        elif difference == [0, 0]:
            return 'node'
        else:
            return None

    def translate_index(self, points, ind, translation):
        """
        :param points: Array of points on node grid.
        :param ind: Array of x,y indicices of the points on node grid.
        :param translation: string to describe destination grid
        translates indices from one grid to another.
        """

        def s_poly(var, index):
            arr = var[:]
            x = index[:, 0]
            y = index[:, 1]
            x[x < 0] = 0
            y[y < 0] = 0
            x1 = x + 1
            y1 = y + 1
            x1[x1 >= arr.shape[0]] -= 1
            y1[y1 >= arr.shape[1]] -= 1
            return np.ma.column_stack((arr[x, y], arr[x1, y], arr[x1, y1], arr[x, y1]))

        if translation is 'node':
            return np.ma.array(ind, mask=False)

        lons, lats = self._get_grid_vars(translation)
        lons = lons[:]
        lats = lats[:]

        translations = {'center': np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
                        'edge1': np.array([[0, 0], [0, 1], [-1, 0], [-1, 1], [1, 0], [1, 1]]),
                        'edge2': np.array([[0, 0], [1, 0], [0, -1], [0, 1], [1, 1], [1, -1]]),
                        }
        if translation not in translations.keys():
            raise ValueError(
                "Translation must be of: {0}".format(translations.keys()))
        ind = np.ma.array(ind, mask=ind == -1)
        points = np.ma.array(points, mask=ind.mask)
        offsets = translations[translation]
        new_ind = np.ma.copy(ind)
        test_polyx = s_poly(lons, new_ind)
        test_polyy = s_poly(lats, new_ind)
#         not_found = np.logical_and(
#             ~ind.mask[:, 0], ~points_in_polys(points, test_polyx, test_polyy))
        not_found = np.where(~ind.mask[:, 0])[0]
#         not_found = np.where(not_in_polys)[0]
        for offset in offsets:
            # for every not found, update the cell to be checked
            test_polyx[not_found] = s_poly(lons, new_ind[not_found] + offset)
            test_polyy[not_found] = s_poly(lats, new_ind[not_found] + offset)
            # retest the missing points. Some might be found, and will not appear
            # in still_not_found
#             found = np.where(points_in_polys(points, test_polyx, test_polyy))[0]

            found = points_in_polys(
                points[not_found], test_polyx[not_found], test_polyy[not_found])
            found = not_found[found]

#             still_not_found = np.logical_and(
#                 ~ind.mask[:, 0][not_found], ~points_in_polys(points[not_found], test_polyx[not_found], test_polyy[not_found]))
#             still_not_found = np.where(still_not_found)[0]
            # therefore the points that were found is the intersection of the
            # two
            not_found = np.setdiff1d(not_found, found)
            # update the indices of the ones that were found
            new_ind[found] += offset
            if len(not_found) == 0:
                break

        # There aren't any boundary issues thanks to numpy's indexing
        new_ind.mask[not_found] = True
        new_ind[not_found] = [-1, -1]
        return new_ind

    def interpolation_alphas(self, points, indices=None, location='center'):
        """
        Given an array of points, this function will return the bilinear interpolation alphas
        for each of the four nodes of the face that the point is located in. If the point is
        not located on the grid, the alphas are set to 0
        :param points: Nx2 numpy array of lat/lon coordinates.

        :param indices: If the face indices of the points is already known, it can be passed in to save
        repeating the effort.

        :return: Nx4 numpy array of interpolation factors.

        TODO: mask the indices that aren't on the grid properly.
        """

        def compute_coeffs(px, py):
            '''
            Params:
            px, py: x, y coordinates of the polygon. Order matters(?) (br, tr, tl, bl
            '''
            px = np.matrix(px)
            py = np.matrix(py)
            A = np.array(
                ([1, 0, 0, 0], [1, 0, 1, 0], [1, 1, 1, 1], [1, 1, 0, 0]))
            AI = np.linalg.inv(A)
            a = np.dot(AI, px.getH())
            b = np.dot(AI, py.getH())
            return (np.array(a), np.array(b))

        def x_to_l(x, y, a, b):
            """
            Params:
            a: x coefficients
            b: y coefficients
            x: x coordinate of point
            y: y coordinate of point

            Returns:
            (l,m) - coordinate in logical space to use for interpolation

            Eqns:
            m = (-bb +- sqrt(bb^2 - 4*aa*cc))/(2*aa)
            l = (l-a1 - a3*m)/(a2 + a4*m)
            """
            def lin_eqn(l, m, ind_arr, aa, bb, cc):
                '''
                AB is parallel to CD...need to solve linear equation instead.
                m = -cc/bb
                bb = Ei*Fj - Ej*Fi + Hi*Gj - Hj*Gi
                k0 = Hi*Ej - Hj*Ei
                '''
                m[ind_arr] = -cc / bb
                l[ind_arr] = (x - a[0] - a[2] * m) / (a[1] + a[3] * m)

            def quad_eqn(l, m, ind_arr, aa, bb, cc):
                '''

                '''
                if len(aa) is 0:
                    return
                k = bb * bb - 4 * aa * cc
                k = np.ma.array(k, mask=(k < 0))

                det = np.ma.sqrt(k)
                m1 = (-bb - det) / (2 * aa)
                l1 = (x - a[0] - a[2] * m1) / (a[1] + a[3] * m1)

                m2 = (-bb + det) / (2 * aa)
                l2 = (x - a[0] - a[2] * m2) / (a[1] + a[3] * m2)

                m[ind_arr] = m1
                l[ind_arr] = l1

                t1 = np.logical_and(l >= 0, m >= 0)
                t2 = np.logical_and(l <= 1, m <= 1)
                t3 = np.logical_and(t1, t2)

                m[~t3[ind_arr]] = m2[ind_arr]
                l[~t3[ind_arr]] = l2[ind_arr]

            aa = a[3] * b[2] - a[2] * b[3]
            bb = a[3] * b[0] - a[0] * b[3] + a[1] * \
                b[2] - a[2] * b[1] + x * b[3] - y * a[3]
            cc = a[1] * b[0] - a[0] * b[1] + x * b[1] - y * a[1]

            m = np.zeros(bb.shape)
            l = np.zeros(bb.shape)
            t = aa[:] == 0
            lin_eqn(l, m, np.where(t)[0], aa[t], bb[t], cc[t])
            quad_eqn(l, m, np.where(~t)[0], aa[~t], bb[~t], cc[~t])

            return (l, m)

        lons, lats = self._get_grid_vars(location)
        lons = lons[:]
        lats = lats[:]

        if indices is None:
            indices = self.locate_faces(points)
            indices = self.translate_index(points, indices, location)
#         indices = indices.data

        polyx = self.get_variable_by_index(lons, indices)
        polyy = self.get_variable_by_index(lats, indices)

        (a, b) = compute_coeffs(polyx, polyy)

        reflats = points[:, 1]
        reflons = points[:, 0]

        (l, m) = x_to_l(reflons, reflats, a, b)

        aa = 1 - l - m + l * m
        ab = m - l * m
        ac = l * m
        ad = l - l * m
        return np.array((aa, ab, ac, ad)).T


class SGridAttributes(object):
    """
    Class containing methods to help with getting the
    attributes for either SGrid.

    """

    def __init__(self, nc, topology_dim, topology_variable):
        self.nc = nc
        self.ncd = NetCDFDataset(self.nc)
        self.topology_dim = topology_dim
        self.topology_variable = topology_variable
        self.topology_var = self.nc.variables[self.topology_variable]

    def get_dimensions(self):
        ds_dims = self.nc.dimensions
        grid_dims = [(ds_dim, len(ds_dims[ds_dim])) for ds_dim in ds_dims]
        return grid_dims

    def get_topology_var(self):
        grid_topology_var = find_grid_topology_var(self.nc)
        return grid_topology_var

    def get_attr_dimension(self, attr_name):
        try:
            attr_dim = getattr(self.topology_var, attr_name)
        except AttributeError:
            attr_dim = None
            attr_padding = None
        else:
            attr_dim_padding = parse_padding(attr_dim, self.topology_variable)
            attr_padding = attr_dim_padding
        return attr_dim, attr_padding

    def get_attr_coordinates(self, attr_name):
        try:
            attr_coordinates_raw = getattr(self.topology_var, attr_name)
        except AttributeError:
            location_name = attr_name.split('_')[0]
            attr_coordinates = self.ncd.find_coordinates_by_location(location_name, self.topology_dim)  # noqa
        else:
            attr_coordinates_val = attr_coordinates_raw.split(' ')
            attr_coordinates = tuple(attr_coordinates_val)
        return attr_coordinates

    def get_node_coordinates(self):
        node_dims = self.topology_var.node_dimensions
        node_dimensions = node_dims
        try:
            node_coordinates = self.topology_var.node_coordinates
        except AttributeError:
            grid_cell_node_vars = self.ncd.find_node_coordinates(node_dimensions)  # noqa
            node_coordinates = grid_cell_node_vars
        else:
            node_coordinate_val = node_coordinates.split(' ')
            node_coordinates = tuple(node_coordinate_val)
        return node_dimensions, node_coordinates

    def get_variable_attributes(self, sgrid):
        dataset_variables = []
        grid_variables = []
        nc_variables = self.nc.variables
        for nc_variable in nc_variables:
            nc_var = nc_variables[nc_variable]
            sgrid_var = SGridVariable.create_variable(nc_var, sgrid)
            setattr(sgrid, sgrid_var.variable, sgrid_var)
            dataset_variables.append(nc_var.name)
            if hasattr(nc_var, 'grid'):
                grid_variables.append(nc_var.name)
        sgrid.variables = dataset_variables
        sgrid.grid_variables = grid_variables

    def get_angles(self):
        angles = self.nc.variables.get('angle')
        if not angles:
            # FIXME: Get rid of pair_arrays.
            center_lon, center_lat = self.get_cell_center_lat_lon()
            cell_centers = pair_arrays(center_lon, center_lat)
            centers_start = cell_centers[..., :-1, :]
            centers_end = cell_centers[..., 1:, :]
            angles = calculate_angle_from_true_east(centers_start, centers_end)
        return angles

    def get_cell_center_lat_lon(self):
        grid_cell_center_lon_var, grid_cell_center_lat_var = self.get_attr_coordinates('face_coordinates')  # noqa
        center_lat = self.nc[grid_cell_center_lat_var]
        center_lon = self.nc[grid_cell_center_lon_var]
        return center_lon, center_lat

    def get_cell_node_lat_lon(self):
        try:
            node_lon_var, node_lat_var = self.get_node_coordinates()[1]
        except TypeError:
            node_lon, node_lat = None, None
        else:
            node_lat = self.nc[node_lat_var]
            node_lon = self.nc[node_lon_var]
        return node_lon, node_lat

    def get_cell_edge1_lat_lon(self):
        edge1_lon_var, edge1_lat_var = self.get_attr_coordinates(
            'edge1_coordinates')
        edge1_lon = self.nc[edge1_lon_var]
        edge1_lat = self.nc[edge1_lat_var]
        return edge1_lon, edge1_lat

    def get_cell_edge2_lat_lon(self):
        edge2_lon_var, edge2_lat_var = self.get_attr_coordinates(
            'edge2_coordinates')
        edge2_lon = self.nc[edge2_lon_var]
        edge2_lat = self.nc[edge2_lat_var]
        return edge2_lon, edge2_lat


def load_grid(nc):
    """
    Get a SGrid object from a netCDF4.Dataset or file/URL.

    :param str or netCDF4.Dataset nc: a netCDF4 Dataset or URL/filepath
                                       to the netCDF file
    :return: SGrid object
    :rtype: sgrid.SGrid

    """
    if isinstance(nc, Dataset):
        pass
    else:
        nc = Dataset(nc, 'r')

    return SGrid.load_grid(nc)
