import arcpy
import os
import sys
import importlib


class Toolbox(object):

    def __init__(self):
        self.label = "Administrative Boundary Tools"
        self.alias = "AdministrativeBoundaryTools"

        self.tools = [AlignAdministrativeBoundaries]


class AlignAdministrativeBoundaries(object):

    def __init__(self):
        self.label = "Align Administrative Boundaries"
        self.description = (
            "Aligns lower-level administrative boundaries to an "
            "authoritative higher-level administrative boundary."
        )

        self.canRunInBackground = False


    def getParameterInfo(self):

        # -----------------------------------------------------
        # Authoritative Admin1
        # -----------------------------------------------------

        admin1 = arcpy.Parameter(
            displayName="Authoritative Admin1 Features",
            name="admin1_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        admin1.filter.list = ["Polygon"]


        # -----------------------------------------------------
        # Admin1 ID
        # -----------------------------------------------------

        admin1_id = arcpy.Parameter(
            displayName="Admin1 ID Field",
            name="admin1_id_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )

        admin1_id.parameterDependencies = [
            admin1.name
        ]


        # -----------------------------------------------------
        # Source Admin2
        # -----------------------------------------------------

        admin2 = arcpy.Parameter(
            displayName="Source Admin2 Features",
            name="admin2_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        admin2.filter.list = ["Polygon"]


        # -----------------------------------------------------
        # Admin2 parent Admin1 ID
        # -----------------------------------------------------

        admin2_parent = arcpy.Parameter(
            displayName="Admin2 Parent Admin1 Field",
            name="admin2_parent_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )

        admin2_parent.parameterDependencies = [
            admin2.name
        ]


        # -----------------------------------------------------
        # Output
        # -----------------------------------------------------

        output_fc = arcpy.Parameter(
            displayName="Output Admin2 Features",
            name="output_admin2",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output"
        )


        return [
            admin1,
            admin1_id,
            admin2,
            admin2_parent,
            output_fc
        ]


    def isLicensed(self):
        return True


    def updateParameters(self, parameters):
        return


    def updateMessages(self, parameters):
        return


    def execute(self, parameters, messages):

        admin1 = parameters[0].valueAsText
        admin1_id = parameters[1].valueAsText

        admin2 = parameters[2].valueAsText
        admin2_parent = parameters[3].valueAsText

        output_fc = parameters[4].valueAsText


        # -----------------------------------------------------
        # Import source module
        # -----------------------------------------------------

        toolbox_dir = os.path.dirname(__file__)

        if toolbox_dir not in sys.path:
            sys.path.insert(0, toolbox_dir)

        import boundary_alignment
        importlib.reload(boundary_alignment)


        # -----------------------------------------------------
        # Run
        # -----------------------------------------------------

        result = boundary_alignment.main(
            admin1_fc=admin1,
            admin2_fc=admin2,
            admin1_id=admin1_id,
            admin2_parent_id=admin2_parent,
            output_fc=output_fc
        )


        # -----------------------------------------------------
        # Set output
        # -----------------------------------------------------

        arcpy.SetParameterAsText(
            4,
            result
        )