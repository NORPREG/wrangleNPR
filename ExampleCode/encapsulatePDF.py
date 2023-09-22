# Example from Dr. Cuauhtémoc Rossell @ https://groups.google.com/g/fo-dicom/c/L36L5fu2QPs

public static string uploadReport(Study estudio, string cPathPDF)
  {
    string sRes = "";
    DicomDataset dataset = fillDataset(estudio);
    byte[] fileData = readBytesFromFile(cPathPDF);
    dataset.Add(DicomTag.EncapsulatedDocument, fileData);
    DicomFile dcmFile = new DicomFile(dataset);
    try
    {
      DicomClient client = new DicomClient();
      client.AddRequest(new DicomCStoreRequest(dcmFile));
      //client.SendAsync(Funcs.opt.dicomAddress, Funcs.opt.dicomPort, false, Funcs.opt.callingAET, Funcs.opt.calledAET);
      client.Send(Funcs.opt.dicomAddress, Funcs.opt.dicomPort, false, Funcs.opt.callingAET, Funcs.opt.calledAET);
    }
    catch (Exception ex)
    {
      sRes = ex.Message;
    }
    return sRes;
  }

public static DicomDataset fillDataset(Study estudio)
  {
    DicomDataset dataset = new DicomDataset();
    // type 1 attributes
    dataset.Add(DicomTag.SOPClassUID, DicomUID.EncapsulatedPDFStorage);
    dataset.Add(DicomTag.StudyInstanceUID, estudio.StudyInstanceUID);
    dataset.Add(DicomTag.SeriesInstanceUID, generateUID());
    dataset.Add(DicomTag.SOPInstanceUID, generateUID());
    dataset.Add(DicomTag.SpecificCharacterSet, "ISO_IR 100");      // nuevo
    // type 2 attributes
    dataset.Add(DicomTag.PatientID, estudio.PatientID);
    dataset.Add(DicomTag.PatientName, estudio.PatientName);
    dataset.Add(DicomTag.PatientBirthDate, estudio.PatientBirthDate);
    dataset.Add(DicomTag.PatientSex, estudio.PatientSex);
    dataset.Add(DicomTag.StudyDate, estudio.StudyDate);
    dataset.Add(DicomTag.StudyTime, estudio.StudyTime);
    DateTime hoy = DateTime.Now;
    dataset.Add(DicomTag.InstanceCreationDate, Funcs.dateToDICOM(hoy));
    dataset.Add(DicomTag.InstanceCreationTime, Funcs.timeToDICOM(hoy));
    dataset.Add(DicomTag.ContentDate, Funcs.dateToDICOM(hoy));
    dataset.Add(DicomTag.ContentTime, Funcs.timeToDICOM(hoy));
    dataset.Add(DicomTag.AccessionNumber, estudio.AccessionNumber);
    dataset.Add(DicomTag.ReferringPhysicianName, estudio.MedRef);
    dataset.Add(DicomTag.StudyID, estudio.StudyID);
    dataset.Add(DicomTag.SeriesNumber, "9");
    dataset.Add(DicomTag.SeriesDescription, estudio.StudyDescription);
    dataset.Add(DicomTag.ModalitiesInStudy, "SR");
    dataset.Add(DicomTag.Modality, "SR");
    dataset.Add(DicomTag.Manufacturer, "ServicesinIT");
    dataset.Add(DicomTag.ManufacturerModelName, "WordPACSClient");
    dataset.Add(DicomTag.SoftwareVersions, "1.0");
    return dataset;
  }

private static DicomUID generateUID()
  {
    StringBuilder uid = new StringBuilder("1.08.1982.10121984.2.0.07.");
    uid.Append(DateTime.UtcNow.Ticks);
    return new DicomUID(uid.ToString(), "SOP Instance UID", DicomUidType.SOPInstance);
  }

  private static byte[] readBytesFromFile(string fileName)
  {
    FileStream fs = File.OpenRead(fileName);
    try
    {
      byte[] bytes = new byte[fs.Length];
      fs.Read(bytes, 0, Convert.ToInt32(fs.Length));
      fs.Close();
      return bytes;
    }
    finally
    {
      fs.Close();
    }
  }

public class Study
{
  public string StudyDateTime { get; set; }
  public string StudyDate { get; set; }
  public string StudyTime { get; set; }
  public string PatientID { get; set; }
  public string PatientName { get; set; }
  public string PatientSex { get; set; }
  public string PatientBirthDate { get; set; }
  public string StudyInstanceUID { get; set; }
  public string StudyID { get; set; }
  public string ModalitiesInStudy { get; set; }
  public string AccessionNumber { get; set; }
  public string StudyDescription { get; set; }
  public string Images { get; set; }
  public string MedRef { get; set; }
  public string Reporte { get; set; }
}