import arcpy
import os
import uuid


def _msg(text):
    """Send messages to ArcGIS Pro when available."""
    try:
        arcpy.AddMessage(text)
    except Exception:
        print(text)


def _tmp_name(workspace, prefix):
    """Create a unique temporary feature class name."""
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    return os.path.join(workspace, name)


def _field_exists(fc, field_name):
    return any(
        f.name.lower() == field_name.lower()
        for f in arcpy.ListFields(fc)
    )


def _check_inputs(admin1_fc, admin2_fc, admin1_id, admin2_parent_id):
    """Basic validation before processing."""

    if not arcpy.Exists(admin1_fc):
        raise ValueError(f"Admin1 dataset does not exist: {admin1_fc}")

    if not arcpy.Exists(admin2_fc):
        raise ValueError(f"Admin2 dataset does not exist: {admin2_fc}")

    if not _field_exists(admin1_fc, admin1_id):
        raise ValueError(
            f"Field '{admin1_id}' was not found in the Admin1 dataset."
        )

    if not _field_exists(admin2_fc, admin2_parent_id):
        raise ValueError(
            f"Field '{admin2_parent_id}' was not found in the Admin2 dataset."
        )

    sr1 = arcpy.Describe(admin1_fc).spatialReference
    sr2 = arcpy.Describe(admin2_fc).spatialReference

    if sr1.factoryCode != sr2.factoryCode:
        raise ValueError(
            "Admin1 and Admin2 must use the same coordinate system."
        )


def _get_admin1_values(admin1_fc, admin1_id):
    """Return unique Admin1 IDs."""
    values = set()

    with arcpy.da.SearchCursor(admin1_fc, [admin1_id]) as cursor:
        for row in cursor:
            if row[0] is not None:
                values.add(row[0])

    return sorted(values, key=str)


def _where_clause(fc, field_name, value):
    """Build a SQL where clause safely."""

    fields = {
        f.name.lower(): f
        for f in arcpy.ListFields(fc)
    }

    field_obj = fields.get(field_name.lower())

    if field_obj is None:
        available = ", ".join(f.name for f in arcpy.ListFields(fc))
        raise ValueError(
            f"Field '{field_name}' was not found in {fc}. "
            f"Available fields: {available}"
        )

    field = arcpy.AddFieldDelimiters(
        fc,
        field_obj.name
    )

    numeric_types = {
        "SmallInteger",
        "Integer",
        "Single",
        "Double",
        "BigInteger"
    }

    if field_obj.type in numeric_types:
        return f"{field} = {value}"

    value = str(value).replace("'", "''")
    return f"{field} = '{value}'"


def _process_admin1(
    admin1_layer,
    admin2_layer,
    admin1_fc,
    admin2_fc,
    admin1_id,
    admin2_parent_id,
    admin1_value,
    workspace
):
    """
    Process one Admin1 unit.

    Returns:
        clipped Admin2 feature class
        gap feature class
    """

    _msg(f"Processing Admin1: {admin1_value}")

    # ---------------------------------------------------------
    # Select authoritative Admin1
    # ---------------------------------------------------------

    expression = _where_clause(
    admin1_layer,
    admin1_id,
    admin1_value
    )


    arcpy.management.SelectLayerByAttribute(
        admin1_layer,
        "NEW_SELECTION",
        expression
    )

    # ---------------------------------------------------------
    # Select its corresponding Admin2 units
    # ---------------------------------------------------------

    expression = _where_clause(
        admin2_layer,
        admin2_parent_id,
        admin1_value
    )

    arcpy.management.SelectLayerByAttribute(
        admin2_layer,
        "NEW_SELECTION",
        expression
    )

    count = int(arcpy.management.GetCount(admin2_layer)[0])

    if count == 0:
        _msg(
            f"WARNING: No Admin2 features found for Admin1 "
            f"{admin1_value}."
        )
        return None, None

    _msg(f"  Admin2 features: {count}")

    # ---------------------------------------------------------
    # Clip Admin2 to authoritative Admin1
    # ---------------------------------------------------------

    clipped = _tmp_name(
        workspace,
        "admin2_clip"
    )

    arcpy.analysis.PairwiseClip(
        admin2_layer,
        admin1_layer,
        clipped
    )

    # ---------------------------------------------------------
    # Dissolve Admin2 coverage
    # ---------------------------------------------------------

    coverage = _tmp_name(
        workspace,
        "admin2_coverage"
    )

    arcpy.management.Dissolve(
        clipped,
        coverage
    )

    # ---------------------------------------------------------
    # Identify uncovered portions of Admin1
    # ---------------------------------------------------------

    gaps = _tmp_name(
        workspace,
        "admin2_gaps"
    )

    arcpy.analysis.PairwiseErase(
        admin1_layer,
        coverage,
        gaps
    )

    gap_count = int(arcpy.management.GetCount(gaps)[0])

    _msg(f"  Gap polygons: {gap_count}")

    return clipped, gaps


def main(
    admin1_fc,
    admin2_fc,
    admin1_id,
    admin2_parent_id,
    output_fc,
    scratch_workspace=None
):
    """
    Align lower administrative boundaries to an authoritative
    higher-level administrative boundary.

    Parameters
    ----------
    admin1_fc : str
        Authoritative Admin1 feature class.

    admin2_fc : str
        Source Admin2 feature class.

    admin1_id : str
        Unique identifier for Admin1.

    admin2_parent_id : str
        Admin2 field identifying the corresponding Admin1.

    output_fc : str
        Final Admin2 output feature class.

    scratch_workspace : str, optional
        Workspace used for intermediate processing.
        Defaults to ArcGIS scratchGDB.
    """

    arcpy.env.overwriteOutput = True

    if scratch_workspace is None:
        scratch_workspace = arcpy.env.scratchGDB

    _msg("Starting administrative boundary conflation.")

    # ---------------------------------------------------------
    # Validate
    # ---------------------------------------------------------

    _check_inputs(
        admin1_fc,
        admin2_fc,
        admin1_id,
        admin2_parent_id
    )

    # ---------------------------------------------------------
    # Repair source geometries
    #
    # We copy first because the input datasets should never
    # be modified by the tool.
    # ---------------------------------------------------------

    admin1_work = _tmp_name(
        scratch_workspace,
        "admin1_work"
    )

    admin2_work = _tmp_name(
        scratch_workspace,
        "admin2_work"
    )

    arcpy.management.CopyFeatures(
        admin1_fc,
        admin1_work
    )

    arcpy.management.CopyFeatures(
        admin2_fc,
        admin2_work
    )

    arcpy.management.RepairGeometry(admin1_work)
    arcpy.management.RepairGeometry(admin2_work)

    # ---------------------------------------------------------
    # Layers
    # ---------------------------------------------------------

    admin1_layer = arcpy.management.MakeFeatureLayer(
        admin1_work,
        "admin1_layer"
    )[0]

    admin2_layer = arcpy.management.MakeFeatureLayer(
        admin2_work,
        "admin2_layer"
    )[0]

    # ---------------------------------------------------------
    # Admin1 units
    # ---------------------------------------------------------

    admin1_values = _get_admin1_values(
        admin1_work,
        admin1_id
    )

    _msg(
        f"Admin1 units to process: {len(admin1_values)}"
    )

    clipped_outputs = []
    gap_outputs = []

    # ---------------------------------------------------------
    # Process each Admin1 independently
    # ---------------------------------------------------------

    for admin1_value in admin1_values:

        clipped, gaps = _process_admin1(
            admin1_layer,
            admin2_layer,
            admin1_work,
            admin2_work,
            admin1_id,
            admin2_parent_id,
            admin1_value,
            scratch_workspace
        )

        if clipped:
            clipped_outputs.append(clipped)

        if gaps:
            gap_outputs.append(gaps)

    if not clipped_outputs:
        raise RuntimeError(
            "No matching Admin2 features were processed."
        )

    # ---------------------------------------------------------
    # Consolidate clipped Admin2
    # ---------------------------------------------------------

    _msg("Combining processed Admin2 features.")

    clipped_merged = _tmp_name(
        scratch_workspace,
        "admin2_clipped_all"
    )

    arcpy.management.Merge(
        clipped_outputs,
        clipped_merged
    )

    # ---------------------------------------------------------
    # TEMPORARY OUTPUT
    #
    # At this stage we deliberately return the clipped Admin2.
    # Gap assignment will be added in the next processing step.
    # ---------------------------------------------------------

    arcpy.management.CopyFeatures(
        clipped_merged,
        output_fc
    )

    # ---------------------------------------------------------
    # Final cleanup
    # ---------------------------------------------------------

    arcpy.management.RepairGeometry(output_fc)

    _msg("Boundary processing complete.")

    return output_fc


if __name__ == "__main__":
    pass