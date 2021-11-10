# Standard Python
from math import atan, cos, radians, tan

# Package library
from xform_utils import get_min_max

# App-specific Libraries
from maya.api.OpenMaya import MMatrix, MPoint, MTransformationMatrix, MVector
import maya.cmds as cmds


def frame_camera_to_objects(cam, objs, padding):
    """Frame given objects with given padding.
    Derived from:
    .../dvs-3dsmax-qc-tool/QC-Tool/QC-Tool/_Core/Generic_Methods.ms
    fn frameCameraToObjects

    Args:
        cam (str): Name of camera node to move.
            The camera's film back aspect ratio and the resolution aspect ratio should be equal.
        objs (list[str]): Objects to frame.
        padding (float): Padding around the frame in decimal percentage.  Valid range: 0.0 - 0.5.

    Returns:
        MPoint: New Position of camera.
    """
    # vars

    # Camera transform matrix.
    cam_tr = MMatrix(cmds.xform(cam, query=True, worldSpace=True, matrix=True))
    cam_fov = cmds.camera(cam, query=True, horizontalFieldOfView=True)
    render_height = cmds.getAttr("defaultResolution.height")
    render_width = cmds.getAttr("defaultResolution.width")
    frame_ar = 1.0 * render_height/render_width  # frame aspect ratio.

    # Padding
    if padding < 0:
        # No negative padding.
        padding = 0.0
    # No 100% padding.
    if padding * 2 > 0.998:
        padding = 0.499

    # Tangents: Used to find the edge of FOV (minus padding).
    ang_ht = tan(radians(cam_fov/2))
    ang_vt = ang_ht * frame_ar

    # Lens Tilt
    if is_vray_cam(cam):
        horizontal_tilt = cmds.getAttr("{}.vrayCameraPhysicalHorizLensShift".format(cam))
        vertical_tilt = cmds.getAttr("{}.vrayCameraPhysicalLensShift".format(cam))
        if vertical_tilt != 0:
            # Vector representing x-axis of camera transformation matrix.
            cam_tr_x_axis = MVector(*[cam_tr.getElement(0, c) for c in range(3)])
            # Modified camera transformation matrix rotated about the x-axis by the vertical tilt angle.
            c_tr_tilt_mtx = (
                    cam_tr * MTransformationMatrix().setToRotationAxis(cam_tr_x_axis, -atan(vertical_tilt)).asMatrix())
            # Copy the y-axis vector values (row 1) of the tilt matrix to the camera transformation matrix.
            for c in range(4):
                cam_tr.setElement(1, c, c_tr_tilt_mtx.getElement(1, c))

        if horizontal_tilt != 0:
            # Vector representing y-axis of camera transformation matrix.
            cam_tr_y_axis = MVector(*[cam_tr.getElement(1, c) for c in range(3)])
            # Modified camera transformation matrix rotated about the y-axis by the horizontal tilt angle.
            c_tr_hor_tilt_mtx = (
                    cam_tr * MTransformationMatrix().setToRotationAxis(cam_tr_y_axis, atan(horizontal_tilt)).asMatrix())
            # Copy the x-axis vector values (row 0) of the tilt matrix to the camera transformation matrix.
            for c in range(4):
                cam_tr.setElement(0, c, c_tr_hor_tilt_mtx.getElement(0, c))

    # Lens shifting
    hfa = cmds.camera(cam, query=True, horizontalFilmAperture=True)  # Film back width
    vfo = cmds.camera(cam, query=True, verticalFilmOffset=True)  # Vertical Shift (in inches).
    vfa = hfa * frame_ar
    # Vertical Lens Shift.
    if vfo != 0.0:
        # Vector representing x-axis of camera transformation matrix.
        cam_tr_x_axis = MVector(*[cam_tr.getElement(0, c) for c in range(3)])
        vertical_shift = vfo/vfa  # Vertical offset percentage.
        c_tr_shift_x_ang = atan(ang_vt * 2 * vertical_shift)  # Shift angle (in radians).
        # Modified camera matrix rotated about the x-axis by vertical shift angle.
        c_tr_shift_x_mtx = (
                cam_tr * MTransformationMatrix().setToRotationAxis(cam_tr_x_axis, c_tr_shift_x_ang).asMatrix())
        # Copy the z-axis vector values (row 2) from the shift matrix to the camera matrix.
        # Moving only the z-axis causes the view of the camera to zoom in by a factor of the cosine of the shift angle.
        # Compensate for this by dividing each value of the z-axis vector by the cosine of the shift angle.
        for c in range(4):
            cam_tr.setElement(2, c, c_tr_shift_x_mtx.getElement(2, c)/cos(c_tr_shift_x_ang))
    hfo = cmds.camera(cam, query=True, horizontalFilmOffset=True)  # Horizontal Shift (in inches).
    # Horizontal Lens Shift.
    if hfo != 0.0:
        # Vector representing y-axis of camera transformation matrix.
        cam_tr_y_axis = MVector(*[cam_tr.getElement(1, c) for c in range(3)])
        horizontal_shift = hfo/hfa  # Horizontal offset percentage.
        c_tr_shift_y_ang = atan(ang_ht * 2 * horizontal_shift)  # Shift angle (in radians).
        # Modified camera matrix rotated about the y-axis by horizontal shift angle.
        c_tr_shift_y_mtx = (
                cam_tr * MTransformationMatrix().setToRotationAxis(cam_tr_y_axis, -c_tr_shift_y_ang).asMatrix())
        # Copy the z-axis vector values (row 2) from the shift matrix to the camera matrix.
        # Moving only the z-axis causes the view of the camera to zoom in by a factor of the cosine of the shift angle.
        # Compensate for this by dividing each value of the z-axis vector by the cosine of the shift angle.
        for c in range(4):
            cam_tr.setElement(2, c, c_tr_shift_y_mtx.getElement(2, c)/cos(c_tr_shift_y_ang))

    # Padding Vectors: Vectors representing edge of FOV (minus padding).
    # The object(s) being framed must fit within these vectors.
    vec_r = MVector(ang_ht * (1.0 - padding * 2), 0, -1).normalize()  # Right
    vec_l = MVector(-ang_ht * (1.0 - padding * 2), 0, -1).normalize()  # Left
    vec_b = MVector(0, -ang_vt * (1.0 - padding * 2), -1).normalize()  # Bottom
    vec_t = MVector(0, ang_vt * (1.0 - padding * 2), -1).normalize()  # Top

    # Make a FOV matrix where the x and y axes are aligned with the right and left FOV (minus padding) vectors on the
    # camera in world-space.
    c_tr_h_mtrx = MMatrix()  # Identity matrix.
    # Build orientation matrix.  X and Y axes will be at FOV (minus padding) angle and might not be at right angle.
    # Results will be sheared.
    c_tr_h_mtrx_data = [(vec_r.x, vec_r.y, vec_r.z),  # x-axis: right
                        (vec_l.x, vec_l.y, vec_l.z),  # y-axis: left
                        (0, 1, 0),                    # z-axis: cam y-axis
                        (0, 0, 0)]
    for r in range(3):
        for c in range(3):
            c_tr_h_mtrx.setElement(r, c, c_tr_h_mtrx_data[r][c])
    c_tr_h = c_tr_h_mtrx * cam_tr  # Orientation matrix in camera-space

    # Make a FOV matrix where the x and y axes are aligned with the bottom and top FOV (minus padding) vectors on the
    # camera in world-space.
    c_tr_v_mtrx = MMatrix()  # Identity matrix.
    # Build orientation matrix.  X and Y axes will be at FOV (minus padding) angle and might not be at right angle.
    # Results will be sheared.
    c_tr_v_mtrx_data = [(vec_b.x, vec_b.y, vec_b.z),  # x-axis: bottom
                        (vec_t.x, vec_t.y, vec_t.z),  # y-axis: top
                        (1, 0, 0),                    # z-axis: cam x-axis
                        (0, 0, 0)]
    for r in range(3):
        for c in range(3):
            c_tr_v_mtrx.setElement(r, c, c_tr_v_mtrx_data[r][c])
    c_tr_v = c_tr_v_mtrx * cam_tr  # Orientation matrix in camera-space

    # Min and max points of object bounding box in relation to each horizontal and vertical FOV (minus padding) matrix.
    min_max_h = get_min_max(objs, c_tr_h)
    min_max_v = get_min_max(objs, c_tr_v)

    # Minimum Horizontal point in camera-space, converted from FOV matrix space.
    min_pos_h = MPoint(MPoint(min_max_h[0].x, min_max_h[0].y, 0) * c_tr_h * cam_tr.inverse())
    # Minimum Vertical point in camera-space, converted from FOV matrix space.
    min_pos_v = MPoint(MPoint(min_max_v[0].x, min_max_v[0].y, 0) * c_tr_v * cam_tr.inverse())

    # New Position in camera-space.
    new_pos = MPoint(min_pos_h.x, min_pos_v.y, min_pos_h.z if min_pos_h.z > min_pos_v.z else min_pos_v.z)

    # New Position in world-space.
    new_pos *= cam_tr

    cmds.xform(cam, worldSpace=True, translation=[new_pos.x, new_pos.y, new_pos.z])

    return new_pos


def is_vray_cam(cam):
    """Is the given camera a V-Ray camera?

    Args:
        cam (str): Name of camera.

    Returns:
        bool: Is the given camera a V-Ray camera?
    """
    return cmds.objExists("{}.vrayCameraPhysicalFOV".format(cam))
