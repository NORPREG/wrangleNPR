import pydicom as pd
import highdicom as hd
import numpy as np

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid

from highdicom.sr.content import FindingSite
from highdicom.sr.templates import Measurement, TrackingIdentifier

# A code content item expressing that the severity is mild
mild_item = hd.sr.CodeContentItem(
   name=codes.SCT.Severity,
   value=codes.SCT.Mild,
)

# A num content item expressing that the depth is 3.4cm
depth_item = hd.sr.NumContentItem(
   name=codes.DCM.Depth,
   value=3.4,
   unit=codes.UCUM.cm,
)

# A scoord content item expressing a point in 3D space of a particular
# frame of reference
region_item = hd.sr.Scoord3DContentItem(
   name=codes.DCM.ImageRegion,
   graphic_type=hd.sr.GraphicTypeValues3D.POINT,
   graphic_data=np.array([[10.6, 2.3, -9.6]]),
   frame_of_reference_uid="1.2.826.0.1.3680043.10.511.3.88131829333631241913772141475338566",
)

# A composite content item referencing another image as the source for a
# segmentation
source_item = hd.sr.CompositeContentItem(
   name=codes.DCM.SourceImageForSegmentation,
   referenced_sop_class_uid="1.2.840.10008.5.1.4.1.1.2",
   referenced_sop_instance_uid="1.2.826.0.1.3680043.10.511.3.21429265101044966075687084803549517",
)

print(codes.DCM.dir("Text"))

print(source_item)