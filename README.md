# wrangleNPR
# DICOM Structure Reporting
DICOM SR is defined in the standard, and in essence it is possible to story any kind of structured information there – text, containers, waveforms, images. See here: http://www.dclunie.com/pixelmed/DICOMSR.book.pdf

# Solution through DCMTK 
The xml2dsr + dsr2xml tools from DCMTK expect a certain format to the XML files, so that they mirror the SR document type definition. See below from https://support.dcmtk.org/docs/xml2dcm.html.
Not that xml2dcm != xml2dsr. xml2dcm expects a mirrored DICOM key-value tree in the XML, while xml2dsr is a bit more flexible.

# NPR converter tool
In order to convert the XML file type of the NPR reports into a DICOM SR document, it needs to first be converted into the key - value sequence definition expected by the xml2dcm document type definition (see schemas).
It may be that we need to hard code the conversion from the NPR XML into DICOM SR by using e.g. pydicom.

From https://pydicom.github.io/pydicom/stable/tutorials/sr_basics.html:
*Starting in pydicom version 1.4, some support for DICOM Structured Reporting (SR) began to be added, as alpha code; the API for this is subject to change in future pydicom versions. At this point the code is limited to code dictionaries and one class Code as a foundational step for future work.*