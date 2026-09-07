"""
Terrain support for city layout generation.

Provides an ElevationModel interface with two implementations:

- SyntheticTerrain: deterministic, seeded rolling-hill field. Used when no
  DEM is supplied, so every terrain-aware rule in layout.py (seed-point
  siting, civic-building siting, road-cost weighting) works identically
  in "demo mode" and "real DEM mode" -- only the elevation() call changes.
- DemTerrain: real elevation sampled (bilinear) from a user-supplied
  GeoTIFF DEM via rasterio.

DEPENDENCIES: rasterio is only imported inside DemTerrain.__init__, so
importing this module -- and using SyntheticTerrain -- never requires
rasterio to be installed. Only pass dem_path to load_terrain() if
rasterio is available.
"""
import math


class ElevationModel:
    """
    Common interface. Subclasses implement elevation(x, y) in local city
    coordinates (meters, city center at (0, 0)); slope() is derived from
    elevation() for both subclasses via central finite differences, so it
    doesn't need to be reimplemented per terrain source.
    """

    def elevation(self, x, y):
        raise NotImplementedError

    def slope(self, x, y, h=1.0):
        """
        Magnitude of the elevation gradient at (x, y): how many meters of
        rise per meter of horizontal travel, in the steepest direction.

        dz/dx and dz/dy are each estimated with a central difference
        (sample h meters either side and divide by the 2h span -- this is
        more accurate than a one-sided difference and cancels first-order
        error). The two partials are then combined the same way you'd get
        speed from x- and y-velocity components: slope = sqrt(dzdx^2 + dzdy^2),
        i.e. math.hypot(dzdx, dzdy). A slope of 0.20 means "20cm of rise
        for every 1m walked in the steepest direction" -- roughly an 11-12
        degree grade.
        """
        dzdx = (self.elevation(x + h, y) - self.elevation(x - h, y)) / (2 * h)
        dzdy = (self.elevation(x, y + h) - self.elevation(x, y - h)) / (2 * h)
        return math.hypot(dzdx, dzdy)


class SyntheticTerrain(ElevationModel):
    """
    Deterministic pseudo-terrain: a small sum of sine waves at different
    frequencies and phases derived from `seed`, so the same seed always
    gives the same hills (needed for generate_city_layout's reproducibility
    guarantee) while different seeds give visibly different terrain.
    Not physically meaningful -- it exists purely so terrain-aware rules
    have *something* to react to when the caller has no real DEM.
    """

    def __init__(self, seed=0, amplitude=15.0, scale=0.01):
        self.seed = seed
        self.amplitude = amplitude
        self.scale = scale

    def elevation(self, x, y):
        s = self.scale
        a = self.amplitude
        phase = (self.seed % 97) * 0.37
        z = (
            math.sin(x * s + phase) * math.cos(y * s * 1.3 + phase)
            + 0.5 * math.sin(x * s * 2.1 - phase) * math.cos(y * s * 1.7)
            + 0.25 * math.sin((x + y) * s * 3.3 + phase)
        )
        return z * a


class DemTerrain(ElevationModel):
    """
    Real elevation from a GeoTIFF DEM (SRTM, USGS 3DEP, etc.), bilinear-
    sampled at arbitrary (x, y) so it can be queried at the same continuous
    coordinates as seed points, road ridges, and block centroids.

    `origin` is where the layout's local (0, 0) sits in the DEM's own
    world/projected coordinates (e.g. UTM meters) -- set this to the
    real-world coordinates of your intended city center. If the DEM's CRS
    is geographic (degrees, not meters) reproject it to a local UTM zone
    first; this class does not reproject, and mixing degrees with the
    layout's meter-based rules (block length, slope thresholds) will give
    nonsense results.
    """

    def __init__(self, path, origin=(0.0, 0.0)):
        import numpy as np
        import rasterio

        self._np = np
        self.origin = origin
        with rasterio.open(path) as src:
            band = src.read(1).astype(float)
            self._transform = src.transform
            self._inv_transform = ~src.transform
            nodata = src.nodata
        if nodata is not None:
            band = np.where(band == nodata, np.nan, band)
        self._elev = band
        self._rows, self._cols = band.shape

    def elevation(self, x, y):
        world_x, world_y = x + self.origin[0], y + self.origin[1]
        col_f, row_f = self._inv_transform * (world_x, world_y)
        row_f = min(max(row_f, 0.0), self._rows - 1.001)
        col_f = min(max(col_f, 0.0), self._cols - 1.001)
        r0, c0 = int(row_f), int(col_f)
        r1, c1 = r0 + 1, c0 + 1
        fr, fc = row_f - r0, col_f - c0
        e = self._elev
        # bilinear blend of the 4 surrounding DEM pixels
        z = (
            e[r0, c0] * (1 - fr) * (1 - fc)
            + e[r0, c1] * (1 - fr) * fc
            + e[r1, c0] * fr * (1 - fc)
            + e[r1, c1] * fr * fc
        )
        if self._np.isnan(z):
            return 0.0
        return float(z)


def load_terrain(dem_path=None, seed=0, dem_origin=(0.0, 0.0)):
    """
    Single decision point used by layout.py: a real DEM if the caller gave
    one, otherwise deterministic synthetic terrain. Every downstream rule
    (seed-point rejection, civic siting, road-cost weighting) calls the
    same .elevation()/.slope() interface either way.
    """
    if dem_path:
        return DemTerrain(dem_path, origin=dem_origin)
    return SyntheticTerrain(seed=seed)
