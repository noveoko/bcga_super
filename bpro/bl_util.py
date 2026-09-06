import bpy
import bmesh
newObjectName = "BCGA"


def create_footprint_from_points(blenderContext, points, offset=(0, 0)):
    """
    Like create_rectangle(), but builds an arbitrary N-gon footprint from a
    plain list of (x, y) points (in meters, local planar coordinates),
    optionally offset (e.g. to position a city block at its centroid).
    """
    if blenderContext.object:
        bpy.ops.object.select_all(action="DESELECT")
    scene = blenderContext.scene
    ox, oy = offset
    mesh = bpy.data.meshes.new(newObjectName)
    mesh.from_pydata(
        [(x - ox, y - oy, 0) for x, y in points], [], [tuple(range(len(points)))]
    )
    obj = bpy.data.objects.new(newObjectName, mesh)
    obj.location = scene.cursor.location
    obj.location.x += ox
    obj.location.y += oy
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    mesh.update()
    return obj


def create_footprint_from_geojson(blenderContext, geojsonPathOrData):
    """
    Like create_rectangle(), but builds an arbitrary N-gon footprint from a
    GeoJSON Polygon (see pro.geojson_import.load_footprint()) instead of a
    fixed rectangle. Returns the loaded metadata dict (origin lon/lat,
    point count) so callers can report it.
    """
    from pro.geojson_import import load_footprint
    points, metadata = load_footprint(geojsonPathOrData)
    create_footprint_from_points(blenderContext, points)
    return metadata


def get_roof_shape(shape):
    """
    Returns the Shape2d to apply a roof to, given the current shape, which
    might be:
      - a Shape2d already (has .face directly) -- the common case when
        called after decompose(top >> ...), or on a fresh footprint.
      - a Shape3d (e.g. right after extrude(), before any decompose()) --
        in this case, pick the constituent face whose normal points most
        upward (+Z), the natural "roof goes on the top face" reading.
    Callers can use the returned Shape2d's .face and .getNormal().
    """
    if hasattr(shape, "face"):
        return shape
    faces = getattr(shape, "shapes", None)
    if not faces:
        raise ValueError("Can't find a face to apply a roof to on this shape")
    return max(faces, key=lambda s: s.face.normal.z)


def create_rectangle(blenderContext, sizeX, sizeY):
    sizeX /= 2
    sizeY /= 2
    if blenderContext.object:
        bpy.ops.object.select_all(action="DESELECT")
    scene = blenderContext.scene
    mesh = bpy.data.meshes.new(newObjectName)
    mesh.from_pydata(
        ((-sizeX, -sizeY, 0), (sizeX, -sizeY, 0),
         (sizeX, sizeY, 0), (-sizeX, sizeY, 0)), [], ((0, 1, 2, 3),)
    )
    obj = bpy.data.objects.new(newObjectName, mesh)
    obj.location = scene.cursor.location
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    mesh.update()


def align_view(obj):
    obj.select_set(True)
    bpy.ops.view3d.view_selected()


def first_edge_ymin(blenderContext):
    """
    Rearranges vertices in a face so the first edge contains the vertex with minimal Y coordinate
    """
    if not blenderContext.object:
        return
    bpy.ops.object.mode_set(mode="EDIT")
    mesh = blenderContext.object.data
    # setting bmesh instance
    bm = bmesh.from_edit_mesh(blenderContext.object.data)
    if hasattr(bm.faces, "ensure_lookup_table"):
        bm.faces.ensure_lookup_table()

    face = bm.faces[0]
    loops = face.loops
    # find the loop with minimal Y coord
    minY = float("inf")
    loop = loops[0]
    startLoop = loop
    firstLoop = loop
    while True:
        y = loop.vert.co[1]
        if y < minY:
            firstLoop = loop
            minY = y
        loop = loop.link_loop_next
        if loop == startLoop:
            break

    # Now the problem: which of the two edges containing loop.vert
    # shall we select as the first edge
    # Solution: select the edge with the smallest length as the first edge
    len1 = firstLoop.edge.calc_length()
    len2 = firstLoop.link_loop_prev.edge.calc_length()
    if len2 > len1:
        firstLoop = firstLoop.link_loop_prev

    if firstLoop != startLoop:
        # rearrange vertices
        startLoop = firstLoop
        loop = startLoop
        verts = []
        while True:
            verts.append(loop.vert)
            loop = loop.link_loop_next
            if loop == startLoop:
                break
        bmesh.ops.delete(bm, geom=(face,), context=3)
        bm.faces.new(verts)
        # update mesh
        bmesh.update_edit_mesh(mesh)

    bpy.ops.object.mode_set(mode="OBJECT")
