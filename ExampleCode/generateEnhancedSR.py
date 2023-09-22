import pydicom as pd
import highdicom as hd
import numpy as np

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid

from highdicom.sr.content import FindingSite
from highdicom.sr.templates import Measurement, TrackingIdentifier

image_dataset = pd.dcmread("../Data/DICOM/CTImage.dcm")

# A measurement derived from an image
depth_item = hd.sr.NumContentItem(
   name=codes.DCM.Depth,
   value=3.4,
   unit=codes.UCUM.cm,
)

# The source image from which the measurement was inferred
source_item = hd.sr.CompositeContentItem(
   name=codes.DCM.SourceImage,
   referenced_sop_class_uid="1.2.840.10008.5.1.4.1.1.2",
   referenced_sop_instance_uid="1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322",
   relationship_type=hd.sr.RelationshipTypeValues.INFERRED_FROM,
)

# A tracking identifier identifying the measurement
tracking_item = hd.sr.UIDRefContentItem(
   name=codes.DCM.TrackingIdentifier,
   value=hd.UID(),  # a newly generated UID
   relationship_type=hd.sr.RelationshipTypeValues.HAS_OBS_CONTEXT,
)

depth_item.ContentSequence = [source_item, tracking_item]

print(depth_item)


sr_dataset = hd.sr.EnhancedSR(
	evidence = [image_dataset],
	content = depth_item,
	series_number = 1,
	series_instance_uid = hd.UID(),
	sop_instance_uid = hd.UID(),
	instance_number = 1,
	manufacturer = "Manufacturer"
)

print(sr_dataset)