from maya.api.OpenMaya import MMatrix, MPoint
import maya.cmds as cmds


def get_min_max(objs, tr_matrix=MMatrix()):
    """Returns the absolute minimum and maximum points occupied by objs based on the given coordinate system.

    Args:
        objs (list[str]): List of objs to establish a bounding box.
        tr_matrix (maya.api.OpenMaya.MMatrix): Matrix to derive a coordinate system.  Defaults to world matrix.

    Returns:
        list[maya.api.OpenMaya.MPoint]: List of min and max points, i.e. [(xmin, ymin, zmin), (xmax, ymax, zmax)]
    """
    min_all = None
    max_all = None
    for obj in objs:
        node_bb = node_get_bounding_box(obj, tr_matrix)
        v_min = node_bb[0]
        v_max = node_bb[1]
        if min_all is None:
            min_all = v_min
            max_all = v_max
        else:
            if v_min.x < min_all.x:
                min_all.x = v_min.x
            if v_max.x > max_all.x:
                max_all.x = v_max.x
            if v_min.y < min_all.y:
                min_all.y = v_min.y
            if v_max.y > max_all.y:
                max_all.y = v_max.y
            if v_min.z < min_all.z:
                min_all.z = v_min.z
            if v_max.z > max_all.z:
                max_all.z = v_max.z
    if min_all is None:
        return None
    else:
        return [min_all, max_all]


def node_get_bounding_box(obj_nm, mtrx_coord=MMatrix()):
    """Returns a list of min and max points of bounding box relative to the given matrix coordinate system.

    Args:
        obj_nm (str): Name of object.
        mtrx_coord (maya.api.OpenMaya.MMatrix): Matrix whose coordinate system to use to orient the bounding box.
            Default is world matrix.

    Returns:
        list[maya.api.OpenMaya.MPoint]: Min and max points of bounding box relative to the given matrix
            coordinate system.
    """
    mtrx_obj_orig = MMatrix(cmds.xform(obj_nm, query=True, worldSpace=True, matrix=True))

    # If camera were at the origin, this matrix transforms the object to
    # the same orientation relative to the camera.
    mtrx_obj_coord_relative = mtrx_obj_orig * mtrx_coord.inverse()
    # Move object relative to camera if camera were at the origin.
    cmds.xform(obj_nm, worldSpace=True, matrix=mtrx_obj_coord_relative)

    obj_copy_name = cmds.duplicate(obj_nm, name="{}_copy_delete_me".format(obj_nm))[0]
    # Freeze Transformations, thus aligning the local bbox with world space.
    cmds.makeIdentity(obj_copy_name, apply=True, translate=True, rotate=True, scale=True)
    # Get Bounding box in world space.
    xmin, ymin, zmin, xmax, ymax, zmax = cmds.exactWorldBoundingBox(obj_copy_name)
    cmds.delete(obj_copy_name)
    # Put object back into original position.
    cmds.xform(obj_nm, worldSpace=True, matrix=mtrx_obj_orig)

    return [MPoint(xmin, ymin, zmin), MPoint(xmax, ymax, zmax)]
