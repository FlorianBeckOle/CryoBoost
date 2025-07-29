
# %%

import yaml
import os,pathlib
import starfile
import subprocess
import glob
import tempfile
import pandas as pd
import xml.etree.ElementTree as ET
import mrcfile
from collections import namedtuple

class warpMetaData:
  
  def __init__(self,dataPath):
    
    self.data_df=pd.DataFrame()
    self.parseXMLdata(dataPath)
  
  def parseXMLdata(self,wk):
    for name in glob.glob(wk):
      if self.checkXMLFileType(name)== 'fs':
        df=self.__parseXMLFileFrameSeries(name) 
      else:
        df=self.__parseXMLFileTiltSeries(name)
      self.data_df =pd.concat([self.data_df, df], ignore_index=True)
       
  def checkXMLFileType(self,pathXML):
    tree = ET.parse(pathXML)
    root = tree.getroot()
    grid_ctf = root.find('MoviePath')
    if grid_ctf is None:
      xmlType='fs'
    else:
      xmlType='ts'
    #print(xmlType)
    return xmlType  
          
  def __parseXMLFileFrameSeries(self,pathXML):
    data_df=pd.DataFrame()
    tree = ET.parse(pathXML)
    root = tree.getroot()
    ctf = root.find(".//CTF")
    data={}
    data = {
       "cryoBoostKey":pathlib.Path(pathXML).name.replace(".xml",""),
       "name": pathXML,
       "folder": str(pathlib.Path(pathXML).parent.as_posix()),
       "defocus_value": ctf.find(".//Param[@Name='Defocus']").get('Value'),
       "defocus_angle": ctf.find(".//Param[@Name='DefocusAngle']").get('Value'),
       "defocus_delta": ctf.find(".//Param[@Name='DefocusDelta']").get('Value'),
         }
    data_df = pd.DataFrame([data])
    return data_df

  def __parseXMLFileTiltSeries(self, pathXML):
    tree = ET.parse(pathXML)
    root = tree.getroot()
    
    # Parse GridCTF (Defocus)
    grid_ctf = root.find('GridCTF')
    defocus_values = []
    z_values = []
    for node in grid_ctf.findall('Node'):
        value = float(node.get('Value'))
        z = int(node.get('Z'))
        defocus_values.append(value)
        z_values.append(z)
        
    # Parse GridCTFDefocusDelta
    grid_delta = root.find('GridCTFDefocusDelta')
    delta_values = []
    for node in grid_delta.findall('Node'):
        value = float(node.get('Value'))
        delta_values.append(value)
        
    # Parse GridCTFDefocusAngle
    grid_angle = root.find('GridCTFDefocusAngle')
    angle_values = []
    for node in grid_angle.findall('Node'):
        value = float(node.get('Value'))
        angle_values.append(value)
        
    # Parse MoviePath
    movie_paths = []
    for path in root.find('MoviePath').text.split('\n'):
        if path.strip():  # Skip empty lines
            # Get basename and remove .eer extension
            movie_name = os.path.basename(path).replace('_EER.eer', '')
            movie_name = movie_name.replace(".tif","")
            movie_name = movie_name.replace(".eer","")
            movie_paths.append(movie_name)
            
    # Create DataFramemdoc.all_df.mdocFileName[0] in mdoc.all_df.SubFramePath 
    df = pd.DataFrame({
        'Z': z_values,
        'defocus_value': defocus_values,
        'defocus_delta': delta_values,
        'defocus_angle': angle_values,
        'cryoBoostKey': movie_paths
    })
    
    return df

      
#from lib.functions import calculate_dose_rate_per_pixel, extract_eer_from_header
class cbconfig:
  def __init__(self,configPath=None):
    if configPath is None:
        self.CRYOBOOST_HOME=os.getenv("CRYOBOOST_HOME")
        configPath=self.CRYOBOOST_HOME + "/config/conf.yaml"
    self.configPath = configPath
    self.read_config()
    self.get_microscopePreSetNames()

  def read_config(self):
    """
    reads a configuration file in yaml format.
    
    Args:
      filename (str): name of the .yaml file.
    
    Returns: 
      dict: dictioanry with paramName and data.
    """
    with open(self.configPath) as f:
      self.confdata = yaml.load(f, Loader=yaml.FullLoader)
  def getEnvSting(self,typeE):
   
    if typeE=="local":
        envString=self.confdata["local"]['Environment']
    if typeE=="submission":
        self.conf.confdata['submission'][0]['Environment']
    
    return envString
  
  def getJobComputingParams(self,comReq,doNodeSharing):    
       
        self.confdata["computing"]["JOBTypesCompute"]
        confComp=self.confdata["computing"]
        jobType=None
        for entry in confComp["JOBTypesCompute"]:
          for job in confComp["JOBTypesCompute"][entry]:
              if job == comReq[0]:
                jobType=entry
                break
        
        if (jobType == None):
          compParams=None
          return compParams 
        
        partionSetup= self.confdata["computing"][comReq[2]]
        kMPIperNode=self.get_alias_reverse(comReq[0],"MPIperNode")
        kNrGPU=self.get_alias_reverse(comReq[0],"NrGPU")
        kNrNodes=self.get_alias_reverse(comReq[0],"NrNodes")
        kPartName=self.get_alias_reverse(comReq[0],"PartionName")
        kMemory=self.get_alias_reverse(comReq[0],"MemoryRAM")
        compParams={}
        compParams[kPartName]=comReq[2]
        compParams[kMemory]=partionSetup["RAM"]
        NodeSharing= self.confdata["computing"]["NODE-Sharing"]
        if (doNodeSharing and (comReq[2] in NodeSharing["ApplyTo"])):
          compParams[kMemory]=str(round(int(partionSetup["RAM"][:-1])/2))+"G"
        gpuIDString=":".join(str(i) for i in range(0,partionSetup["NrGPU"]))
        maxNodes= self.confdata["computing"]["JOBMaxNodes"]
        
        
        if (comReq[0] in maxNodes.keys()):  
            if (comReq[1]>maxNodes[comReq[0]][0]):
                comReq[1]=maxNodes[comReq[0]][0]
        
        if (jobType == "CPU-MPI"):
          compParams[kMPIperNode]=partionSetup["NrCPU"]
          compParams["nr_mpi"]=partionSetup["NrCPU"]*comReq[1]  
          compParams[kNrGPU]=0
          compParams[kNrNodes]=comReq[1] 
          compParams["nr_threads"]=1
          if (doNodeSharing and comReq[2] in NodeSharing["ApplyTo"]):
              compParams[kMPIperNode]=partionSetup["NrCPU"]-(partionSetup["NrGPU"]*NodeSharing["CPU-PerGPU"]) 
              compParams["nr_mpi"]=compParams[kMPIperNode]*comReq[1]
              
        if (jobType == "CPU-2MPIThreads"):
          compParams[kMPIperNode]=2
          compParams["nr_mpi"]=compParams[kMPIperNode]*comReq[1]  
          compParams[kNrGPU]=0
          compParams[kNrNodes]=comReq[1] 
          compParams["nr_threads"]=round(partionSetup["NrCPU"]/2)
          if (doNodeSharing and comReq[2] in NodeSharing["ApplyTo"]):
              compParams["nr_threads"]=compParams["nr_threads"]-round(partionSetup["NrGPU"]*NodeSharing["CPU-PerGPU"]/2)
        
        if (jobType == "GPU-OneProcess") or (jobType == "GPU-OneProcessOneGPU"):
          compParams[kMPIperNode]=1
          compParams["nr_mpi"]=1  
          compParams[kNrGPU]=partionSetup["NrGPU"]
          compParams[kNrNodes]=1
          compParams["nr_threads"]=partionSetup["NrGPU"]
          compParams["gpu_ids"]=gpuIDString
        
        if (jobType == "GPU-OneProcessOneGPU"):
          compParams["gpu_ids"]=0
          compParams[kNrGPU]=1
        
        if (jobType == "GPU-ThreadsOneNode"):
          compParams[kMPIperNode]=1
          compParams["nr_mpi"]=1  
          compParams[kNrGPU]=partionSetup["NrGPU"]
          compParams[kNrNodes]=1 
          compParams["nr_threads"]=round(partionSetup["NrCPU"]/1)
          if (doNodeSharing and comReq[2] in NodeSharing["ApplyTo"]):
              compParams["nr_threads"]=compParams["nr_threads"]-round(partionSetup["NrGPU"]*NodeSharing["CPU-PerGPU"])
        
        if (jobType == "GPU-MultProcess"):
          compParams[kMPIperNode]=partionSetup["NrGPU"]
          compParams[kNrGPU]=partionSetup["NrGPU"]
          compParams["nr_mpi"]=partionSetup["NrGPU"]*comReq[1]  
          compParams["nr_threads"]=1
          compParams["gpu_ids"]= ":".join([gpuIDString] * comReq[1]) 
          compParams[kNrNodes]=comReq[1]
              
        if comReq[0] in confComp['JOBsPerDevice'].keys():
            compParams["param10_value"]=confComp['JOBsPerDevice'][comReq[0]][comReq[2]]
          
        return compParams 
        
  def get_alias(self,job, parameter):
    """
    some inputs used by Relion are not self-explanatory (eg. qsub_extra2) so a yaml list was created to change the 
    respective name that is displayed while still keeping the original name for writing the data.

    Args:
      job (str): job name the parameter is used for.
      parameter (str): parameter name.

    Returns:
      alias (str): alias displayed instead of the parameter name.

    Example:
      job
    """
    
    for entry in self.confdata["aliases"]:
      # if the entry Job of one of the lists equals the given job or all and the entry Parameter contains the given 
      # parameter name, return the entry Alias
      if (entry["Job"] == job or entry["Job"] == "all") and entry["Parameter"] == parameter:
        return entry["Alias"]
    return None
  
  def getJobOutput(self, jobName):
    return self.confdata["star_file"][jobName]
  
  def get_microscopePreSet(self,microscope):
      mic_data= self.confdata['microscopes']
      for entry in mic_data:
          if entry == microscope:
              microscope_parameters_list_of_dicts= mic_data[entry]
      microscope_parameters = {}
      for dicts in microscope_parameters_list_of_dicts:
          microscope_parameters.update(dicts)
      
      return microscope_parameters    
  
  def get_microscopePreSetNames(self):
      mic_data = self.confdata['microscopes']
      microscope_presets = {}  # Initialize an empty dictionary
      for i, entry in enumerate(mic_data):  # Use enumerate to get both index and entry
        microscope_presets[i] = entry
      self.microscope_presets=microscope_presets
      
      return microscope_presets
      
  
  def get_alias_reverse(self,job, alias,):
    """
    reverse of the get alias function, i.e. returns the parameter name as used in the .star file when entering the 
    alias. Kept seperate to keep reading and writing clearly separated to avoid errors. 

    Args:
      job (str): job name the parameter is used for.
      alias (str): alias displayed instead of the parameter name.

    Returns:
      parameter (str): parameter name as displayed in the job.star file.

    Example:mdoc.all_df.mdocFileName[0] in mdoc.all_df.SubFramePath 
      job
    """
    
    # go through entries in the aliases dict
    for entry in self.confdata["aliases"]:
      # if the entry Job of one of the lists equals the given job or all and the entry Alias contains the given 
      # parameter name, return the entry Parameter
      if (entry["Job"] == job or entry["Job"] == "all") and entry["Alias"] == alias:
        return entry["Parameter"]
    return None

def importFolderBySymlink(sourceFold, targetFold):
    """
    creates a symlink from sourceFold to targetFold

    Args:
        path_frames (str): absolute path to the imported frames.
        targetFold (str): path where the symlink will be created

    Returns:
        -

    Example:
        path_frames = /fs/pool/pool-plitzko3/Michael/01-Data/relion/frames
        path_out_dir = /fs/pool/pool-plitzko3/Michael/01-Data/project

        importFolderBySymlink(path_frames, path_out_dir)
        
    """
    import warnings
    
    if not os.path.exists(targetFold):
        os.makedirs(targetFold)      
    
    command_frames = f"ln -s {os.path.abspath(sourceFold)} {targetFold}" + os.path.sep
    
    foldFrames=targetFold + os.path.sep + os.path.basename(sourceFold.rstrip("/")) 
    if os.path.exists(foldFrames):
        warnings.warn("Path to folder already exists." + f" {foldFrames} ")
        #os.unlink(foldFrames)
    else:
        os.system(command_frames)
    
   
    



def read_header(path_to_frames):
  """
  reads header of a file to fetch the nr of eer's to calculate the optimal split using the calculate_dose_rate_per_pixel function.

  Args:
    path_to_frames (str): path to the respective frames.

  Returns:
    eer_split (dict): best possible eer split per frame as value so it can be added to the dict when transferring
                      information from the file path to the input data.
  Example:

  """
  # so it only fetches the first instance of *.eer, not all of them
  eer_file = glob.glob(f"{path_to_frames}/*.eer")[0]
  command = f"header {eer_file}"
  result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
  header = str(result)
  #eers = extract_eer_from_header(header)
  #print(eers)
  #eer_split = calculate_dose_rate_per_pixel(eers)
  #header = frame.read()
  #print(result.stdout)
  
class mdocMeta:
  def __init__(self,mdocWk=None):
      
    if (mdocWk is not None):
      self.mdocWk = mdocWk
      self.readAllMdoc(mdocWk)

  
  def filterByTiltSeriesStarFile(self,tiltSeriesFileName):
    
    ts=tiltSeriesMeta(tiltSeriesFileName)
    dfMdoc=self.all_df['cryoBoostKey']
    dfTs=ts.all_tilts_df['rlnMicrographMovieName'].apply(os.path.basename)
    
    mask=dfMdoc.isin(dfTs)
    self.all_df=self.all_df[mask]

  def readAllMdoc(self,wkMdoc):
    mdoc_files = glob.glob(wkMdoc)
    self.all_df=pd.DataFrame()
    for mdoc in mdoc_files:
      header,data,orgPath = self.readMdoc(mdoc)
      df = pd.DataFrame(data)
      df['mdocHeader']=header
      df['mdocFileName']=os.path.basename(mdoc)
      if orgPath is not None:
        df['mdocOrgPath']=orgPath
      else:
        df['mdocOrgPath']=mdoc
      
      self.all_df = pd.concat([self.all_df, df], ignore_index=True) 
      if 'SubFramePath' in self.all_df:
        k = self.all_df['SubFramePath'].apply(lambda x: os.path.basename(x.replace("\\","/").replace("\\","")))
      else:
        raise Exception("SubFramePath entry missing check your mdoc's: "+ mdoc)
      if (k.is_unique):
        self.all_df['cryoBoostKey']=k
      else:
        raise Exception("SubFramePath is not unique !!") 

    self.param4Processing={}
    if self.all_df.mdocHeader[0].find("SerialEM:")==-1:
      self.acqApp="Tomo5"
      #self.param4Processing["TiltAxisAngle"]=-round(-(-1*float(self.all_df.RotationAngle.unique()[0]))+180,1)
      self.param4Processing["TiltAxisAngle"]=abs(round(float(self.all_df.RotationAngle.unique()[0]),1))
    else: #+180
      self.acqApp="SerialEM"
      self.param4Processing["TiltAxisAngle"]=round(float(self.all_df.mdocHeader[0].split("Tilt axis angle =")[1].split(",")[0]),2) #+180
    self.param4Processing["DosePerTilt"]=round(float(self.all_df.ExposureDose[0])*1.5,2)
    self.param4Processing["PixelSize"]= round(float(self.all_df.mdocHeader[0].split("PixelSpacing = ")[1].split('\n')[0]),2)
    self.param4Processing["ImageSize"]=self.all_df.mdocHeader[0].split("ImageSize = ")[1].split('\n')[0].replace(" ","x")
    self.param4Processing["NumMdoc"]=len(mdoc_files)
  def addPrefixToFileName(self,prefix):

    self.all_df['SubFramePath']=self.all_df['SubFramePath'].apply(lambda x: prefix+os.path.basename(x))
    self.all_df['mdocFileName']=self.all_df['mdocFileName'].apply(lambda x: prefix+os.path.basename(x))
         
          
  def writeAllMdoc(self,folder,appendMdocRootPath=False):   
    
    for mdoc in self.all_df['mdocFileName'].unique():
      df = self.all_df[self.all_df['mdocFileName']==mdoc]
      header=df['mdocHeader'].unique()[0]
      mdocPath=os.path.join(folder,mdoc)       
      self.writeMdoc(mdocPath,header,df,appendMdocRootPath)
      del df,header
    
    
  def readMdoc(self,file_path):
      """
      Parses an .mdoc file into a header and a pandas DataFrame containing ZValue sections.

      Args:
          file_path (str): Path to the .mdoc file.

      Returns:
          tuple: A tuple containing the header string and a DataFrame with ZValue section data.
      """
      header = []
      data = []
      current_row = {}
      in_zvalue_section = False
      orgPath=None
      
      with open(file_path, 'r') as file:
          lines = file.readlines()

      for line in lines:
          line = line.strip()
          
          # Check if we're entering ZValue section
          if line.startswith('[ZValue'):
              in_zvalue_section = True
              if current_row:
                  data.append(current_row)
                  current_row = {}
              current_row['ZValue'] = line.split('=')[1].strip().strip(']')
              continue
          
          # Check if we're leaving ZValue section
          if in_zvalue_section and line.startswith('[') and not line.startswith('[ZValue'):
              in_zvalue_section = False
              data.append(current_row)
              current_row = {}
          
          if in_zvalue_section:
              # Process each line within ZValue section
              if line.startswith('TiltAngle'):
                  current_row['TiltAngle'] = line.split('=')[1].strip()
              elif line.startswith('StagePosition'):
                  current_row['StagePosition'] = line.split('=')[1].strip()
              elif line.startswith('StageZ'):
                  current_row['StageZ'] = line.split('=')[1].strip()
              elif line.startswith('Magnification'):
                  current_row['Magnification'] = line.split('=')[1].strip()
              elif line.startswith('Intensity'):
                  current_row['Intensity'] = line.split('=')[1].strip()
              elif line.startswith('ExposureDose'):
                  current_row['ExposureDose'] = line.split('=')[1].strip()
              elif line.startswith('PixelSpacing'):
                  current_row['PixelSpacing'] = line.split('=')[1].strip()
              elif line.startswith('SpotSize'):
                  current_row['SpotSize'] = line.split('=')[1].strip()
              elif line.startswith('Defocus'):
                  current_row['Defocus'] = line.split('=')[1].strip()
              elif line.startswith('ImageShift'):
                  current_row['ImageShift'] = line.split('=')[1].strip()
              elif line.startswith('RotationAngle'):
                  current_row['RotationAngle'] = line.split('=')[1].strip()
              elif line.startswith('ExposureTime'):
                  current_row['ExposureTime'] = line.split('=')[1].strip()
              elif line.startswith('Binning'):
                  current_row['Binning'] = line.split('=')[1].strip()
              elif line.startswith('MagIndex'):
                  current_row['MagIndex'] = line.split('=')[1].strip()
              elif line.startswith('CountsPerElectron'):
                  current_row['CountsPerElectron'] = line.split('=')[1].strip()
              elif line.startswith('MinMaxMean'):
                  current_row['MinMaxMean'] = line.split('=')[1].strip()
              elif line.startswith('TargetDefocus'):
                  current_row['TargetDefocus'] = line.split('=')[1].strip()
              elif line.startswith('PriorRecordDose'):
                  current_row['PriorRecordDose'] = line.split('=')[1].strip()
              elif line.startswith('SubFramePath'):
                  current_row['SubFramePath'] = line.split('=')[1].strip()
              elif line.startswith('NumSubFrames'):
                  current_row['NumSubFrames'] = line.split('=')[1].strip()
              elif line.startswith('FrameDosesAndNumber'):
                  current_row['FrameDosesAndNumber'] = line.split('=')[1].strip()
              elif line.startswith('DateTime'):
                  current_row['DateTime'] = line.split('=')[1].strip()
              elif line.startswith('FilterSlitAndLoss'):
                  current_row['FilterSlitAndLoss'] = line.split('=')[1].strip()
              elif line.startswith('ChannelName'):
                  current_row['ChannelName'] = line.split('=')[1].strip()
              elif line.startswith('CameraLength'):
                  current_row['CameraLength'] = line.split('=')[1].strip()
          else:
              # Collect header information
              header.append(line)
          if line.startswith('CryoBoost_RootMdocPath'):
              orgPath=line.split('=')[1].strip()
              
              
      # Append the last row if it exists
      if current_row:
          data.append(current_row)

      # Convert header list to a single string
      header_str = "\n".join(header)

      # Create DataFrame for ZValue sections
      df = pd.DataFrame(data)
      
      
      return header_str,df,orgPath

  def writeMdoc(self,output_path, header_str, df,appendMdocRootPath=False):
      """
      Writes the modified .mdoc data to a file.

      Args:
          file_path (str): Path to the output .mdoc file.
          header_str (str): Header string of the .mdoc file.
          df (DataFrame): DataFrame containing the ZValue sections.
      """
     
      #df=df.drop(columns=["mdocHeader","mdocFilePath","cryoBoostKey"])   
      # Define the format for each line in the ZValue sections
      # def format_row(row):
      #     return (
      #         f'[ZValue = {row.get("ZValue", "")}]\n'
      #         f'TiltAngle = {row.get("TiltAngle", "")}\n'
      #         f'StagePosition = {row.get("StagePosition", "")}\n'
      #         f'StageZ = {row.get("StageZ", "")}\n'
      #         f'Magnification = {row.get("Magnification", "")}\n'
      #         f'Intensity = {row.get("Intensity", "")}\n'
      #         f'ExposureDose = {row.get("ExposureDose", "")}\n'
      #         f'PixelSpacing = {row.get("PixelSpacing", "")}\n'
      #         f'SpotSize = {row.get("SpotSize", "")}\n'
      #         f'Defocus = {row.get("Defocus", "")}\n'
      #         f'ImageShift = {row.get("ImageShift", "")}\n'
      #         f'RotationAngle = {row.get("RotationAngle", "")}\n'
      #         f'ExposureTime = {row.get("ExposureTime", "")}\n'
      #         f'Binning = {row.get("Binning", "")}\n'
      #         f'MagIndex = {row.get("MagIndex", "")}\n'
      #         f'CountsPerElectron = {row.get("CountsPerElectron", "")}\n'
      #         f'MinMaxMean = {row.get("MinMaxMean", "")}\n'
      #         f'TargetDefocus = {row.get("TargetDefocus", "")}\n'
      #         f'PriorRecordDose = {row.get("PriorRecordDose", "")}\n'
      #         f'SubFramePath = {row.get("SubFramePath", "")}\n'
      #         f'NumSubFrames = {row.get("NumSubFrames", "")}\n'
      #         f'FrameDosesAndNumber = {row.get("FrameDosesAndNumber", "")}\n'
      #         f'DateTime = {row.get("DateTime", "")}\n'
      #         f'FilterSlitAndLoss = {row.get("FilterSlitAndLoss", "")}\n'
      #         f'ChannelName = {row.get("ChannelName", "")}\n'
      #         f'CameraLength = {row.get("CameraLength", "")}\n'
      #     )
      def format_row(row):
          output = [f'[ZValue = {row.get("ZValue", "")}]']  # ZValue is required
          
          # List of possible fields
          fields = [
              "TiltAngle", "StagePosition", "StageZ", "Magnification", 
              "Intensity", "ExposureDose", "PixelSpacing", "SpotSize",
              "Defocus", "ImageShift", "RotationAngle", "ExposureTime",
              "Binning", "MagIndex", "CountsPerElectron", "MinMaxMean",
              "TargetDefocus", "PriorRecordDose", "SubFramePath", 
              "NumSubFrames", "FrameDosesAndNumber", "DateTime",
              "FilterSlitAndLoss", "ChannelName", "CameraLength"
          ]
          
          # Only add fields that exist in the row and have non-null values
          for field in fields:
              if field in row and pd.notna(row[field]):
                  output.append(f'{field} = {row[field]}')
          
          return '\n'.join(output) + '\n'
      

      # Open the file for writing
      with open(output_path, 'w') as file:
          # Write the header
          file.write(header_str + '\n')
          
          # Write each ZValue section using DataFrame
          df.apply(lambda row: file.write(format_row(row) + '\n'), axis=1)
          
          if appendMdocRootPath:
            file.write("CryoBoost_RootMdocPath = " + os.path.abspath(df["mdocOrgPath"].unique()[0]) + "\n")
          

  # def move_files_to_trash(missing_files, tilts_folder, ext):
  #     """
  #     Move the excluded .mrc and .eer files to a 'Trash' folder.

  #     Args:
  #         missing_files (set): Set of filenames of missing files.
  #         tilts_folder (str): Directory containing the files.
  #         extension (str): extension of the file, either mrc or eer
  #     """
  #     trash_folder = os.path.join(tilts_folder, 'Trash')
  #     os.makedirs(trash_folder, exist_ok=True)

  #     for file in missing_files:
  #         src = os.path.join(tilts_folder, f'{file}.{ext}')
  #         dst = os.path.join(trash_folder, f'{file}.{ext}')
  #         if os.path.exists(src):
  #             shutil.move(src, dst)
  #             print(f'Moved {file} to Trash')
  #         else:
  #             print(f'{file} not found in {tilts_folder}')

    
  
#TODO lagacy will be removed by mdoc object
def read_mdoc(path_to_mdoc_dir, path_to_yaml = "../src/read_write/config_reading_meta.yaml"):
  """
  reads mdoc file and fetches the relevant parameters to automatically set the respective values.

  Args:
    path_to_mdoc (str): path to the directory containing the mdoc files.
  
  Returns:
    return_mdoc_data (dict): values set in the config_reading_meta.yaml file for the respective meta-data type.

  Example:
    path_to_mdoc_dir = [path to mdoc file]

    returns a dict with the respective "x/z dimension", "Pixel size in A", and "Voltage of Microscope"
    (names must be set in the config_reading_meta.yaml file and be the same as in the config_aliases.yaml 
    file). This can subsequently be used to update the respective fields in the table.  
  """
  return_mdoc_data = {}
  # using the dir, access the first mdoc file in the folder
  path_to_mdoc = glob.glob(f"{path_to_mdoc_dir}")[0]
  # get respective mdoc file
  with open(path_to_mdoc, "r") as mdoc_file:
    # store the lines in that mdoc file in a list to iterate over
    mdoc_list = [line.strip() for line in mdoc_file if line.strip()]
    # get entries to look for in the mdoc file (based on the config_reading_meta.yaml file)
    # when only accessing the config_reading_meta.yaml file here, it's only accessed once a valid file-path is 
    # entered, not everytime there is a change to the QLine field
    with open(path_to_yaml, "r") as yaml_file:
      yaml_data = yaml.safe_load(yaml_file)
      print("mdoc file found")
      # access the respective list in the config_reading_meta.yaml file (parameter to look for in mdoc and respective alias)
      yaml_mdoc = yaml_data["meta_data"].get("mdoc", [])
      # access the list of dicts
      for yaml_entry in yaml_mdoc:
        # iterate through the meta data yaml to get the parameters which should be found (and the associated alias as key)
        for yaml_param_name, yaml_alias in yaml_entry.items():
          # iterate through the lines in the mdoc file until the respective entry is found
          for mdoc_current_line in mdoc_list:
            # remove spaces ect that might be in front/after the parameter name
            mdoc_current_line = mdoc_current_line.strip()
            # Skip empty lines
            if not mdoc_current_line:
              continue
            else:
              # data in the mdoc file is in this format: "PixelSpacing = 2.93" --> separate into key and value
              mdoc_key_value = mdoc_current_line.split("=")
              mdoc_current_line_key = mdoc_key_value[0].strip()
              mdoc_current_line_value = mdoc_key_value[1].strip()
              # if the current line holds the information we want as specified in the yaml), add it to the data dict
              # (keys = alias; value = value in meta data)
              if yaml_param_name == mdoc_current_line_key:
                # ImageSize contains both xdim and ydim in the mdoc file, have to split it up
                if mdoc_current_line_key == "ImageSize" and len(mdoc_current_line_value.split()) == 2:
                  xdim, ydim = mdoc_current_line_value.split()
                  # Add entries for both x and y dimensions
                  yaml_alias = "x dimensions"
                  return_mdoc_data[yaml_alias] = xdim
                  yaml_alias = "y dimensions"
                  return_mdoc_data[yaml_alias] = ydim
                else:      
                  return_mdoc_data[yaml_alias] = mdoc_current_line_value
  return(return_mdoc_data) 


# %%
# create Sphinx documentation: sphinx-build -M html docs/ docs/
# remove everything in the _build: make clean
# update Sphinx documentation: make html
import pandas as pd
from pathlib import Path
from starfile import read as starread
from starfile import write as starwrite
import copy
import os
from datetime import datetime
import time

class starFileMeta:
  """_summary_

  Raises:
      Exception: _description_

  Returns:
      _type_: _description_
  """
  def __init__(self, starfile,always_dict = True):
    
    self.always_dict = always_dict
    if isinstance(starfile, str):
      self.starfilePath = starfile
      self.readStar()
    if isinstance(starfile, pd.DataFrame):
      self.df = starfile
      self.dict = None  
    if isinstance(starfile, dict):
      self.dict = starfile
      self.df = None  
    
    
  def readStar(self):
    #Hack to avoid caching
    
    file_path = Path(self.starfilePath)
    if not file_path.exists():
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    tmpTargetPath=tempfile.gettempdir() + os.path.sep + "tmpPointer.tmp" + str(time.time())
    os.symlink(os.path.abspath(self.starfilePath),tmpTargetPath)
    #self.dict = starread(self.starfilePath, always_dict = self.always_dict)
    self.dict = starread(tmpTargetPath,always_dict = self.always_dict)
    os.remove(tmpTargetPath)
    if (len(self.dict.keys())==1):
      self.df=self.dict[next(iter(self.dict.keys()))]
    else:
      self.df=None
    
  def writeStar(self,starfilePath):
    
    if isinstance(self.dict, dict):
       starwrite(self.dict,starfilePath)
       return
    if isinstance(self.df, pd.DataFrame):
        starwrite(self.df,starfilePath)
        return
    
class dataImport():
  
  def __init__(self,targetPath,wkFrames,wkMdoc=None,prefix="auto",logDir=None,invTiltAngle=False):  
    self.targetPath=targetPath
    self.wkFrames=wkFrames
    self.wkMdoc=wkMdoc
    if prefix == "auto":
      current_datetime = datetime.now()
      self.prefix=current_datetime.strftime("%Y-%m-%d-%H-%M-%S_")
    else:
      self.prefix=prefix
    self.mdocLocalFold="mdoc/"
    self.framesLocalFold="frames/"
    frameTargetPattern=self.targetPath + "/" + self.framesLocalFold + os.path.basename(self.wkFrames)
    self.existingFramesSource=[os.path.realpath(file) for file in glob.glob(frameTargetPattern)]
    self.existingMdocSource=self.__getexistingMdoc()
    self.logDir=logDir
    self.logToConsole=False
    self.invTiltAngle=invTiltAngle
    print("import TiltAngle Inv data Import Ini:" + str(self.invTiltAngle))
    if logDir is not None:  
      os.makedirs(logDir, exist_ok=True)
      self.logErrorFile=open(os.path.join(logDir,"run.err"),'a')
      self.logInfoFile=open(os.path.join(logDir,"run.out"),'a')
    importOk=self.checkImport()  
    if importOk:
      self.runImport()
      
  
  def checkImport(self):
    importOk=True
    #duplicates=self.__checkDuplicates(self.wkMdoc, self.existingMdocSource)
    if (not glob.glob(self.wkMdoc)):
       self.__writeLog("error", "no mdocs found check wildcard")
       self.__writeLog("error", self.wkMdoc)
       importOk=False
   
    if (not glob.glob(self.wkFrames)):
       self.__writeLog("error", "no frames found check wildcard")
       self.__writeLog("error", self.wkFrames)
       importOk=False
    duplicateFiles=self.__checkDuplicates(self.wkMdoc, self.existingMdocSource)
    if duplicateFiles:
      importOk=False
      for mdocName in duplicateFiles:
        self.__writeLog("error",str(mdocName) + " name already exists")
      self.__writeLog("error","importing files use prefix to import")
    return importOk
  
  def __del__(self):
    if self.logDir is not None:
      self.logErrorFile.close()
      self.logInfoFile.close()

  def __getexistingMdoc(self):
    
    existingMdoc=[]
    mdocTargetPattern=self.targetPath + "/" + self.mdocLocalFold + os.path.basename(self.wkMdoc)
    print("mdocTargetPattern: " + mdocTargetPattern)
    for fileName in glob.glob(mdocTargetPattern):
      with open(fileName, 'r') as file:
        lines = file.readlines()
        for i, line in enumerate(lines):
          if 'CryoBoost_RootMdocPath' in line:
            existingMdoc.append(line.replace("CryoBoost_RootMdocPath = ",""))
    
    return existingMdoc  
  
  def runImport(self):   
    from src.rw.librw import mdocMeta
    self.mdoc=mdocMeta(self.wkMdoc)
    base_filename = os.path.splitext(self.mdoc.all_df.mdocFileName[0])[0]
    path_to_search = os.path.splitext(self.mdoc.all_df.SubFramePath[0])[0]
    base_filename in path_to_search
    if base_filename in path_to_search:
      self.relcompPrefix=False
    else:   
      self.relcompPrefix=True
    
    os.makedirs(self.targetPath, exist_ok=True)
    framesFold=os.path.join(self.targetPath,self.framesLocalFold)
    os.makedirs(framesFold, exist_ok=True)
    
    self.__genLinks(self.wkFrames,framesFold,self.existingFramesSource)
    
    if self.wkMdoc is not None:
      mdocFold=os.path.join(self.targetPath,self.mdocLocalFold)
      os.makedirs(mdocFold, exist_ok=True)  
      self.__writeAdaptedMdoc(self.wkMdoc,mdocFold,self.existingMdocSource,self.invTiltAngle)
      #self.__genLinks(self.wkMdoc,mdocFold,self.existingMdoc)
  
  def __writeAdaptedMdoc(self,inputPattern,targetFold,existingFiles,invTiltAngle=False):
    
    nrFilesAlreadyImported=len(glob.glob(targetFold + "/*" + os.path.splitext(inputPattern)[1])); 
    for file_path in glob.glob(inputPattern):
        file_name = os.path.basename(file_path)
        tragetFileName = os.path.join(targetFold,self.prefix+file_name)
        print("targetFileName:"+tragetFileName)
        print("inputPatter:"+inputPattern)
        if self.__chkFileExists(file_path,existingFiles)==False:
            if self.relcompPrefix:
                file_nameBase=os.path.splitext(os.path.splitext(file_name)[0])[0]+".mdoc"
                tragetFileName=os.path.join(targetFold,self.prefix+file_nameBase)
            self.__adaptMdoc(self.prefix,file_path,tragetFileName,invTiltAngle)
    
    nrFilesTotalImported=len(glob.glob(targetFold + "/*" + os.path.splitext(inputPattern)[1]));
    nrFilesNewImported=nrFilesTotalImported-nrFilesAlreadyImported
    self.__writeLog("info","Total number of mdocs imported: " + str(nrFilesTotalImported) )
    self.__writeLog("info","Number of new mdoc imported: " + str(nrFilesNewImported) )        
          
  def __adaptMdoc(self,prefix,inputMdoc,outputMdoc,invTiltAngle=False):
    
    with open(inputMdoc, 'r') as file:
      lines = file.readlines()
      for i, line in enumerate(lines):
        if 'SubFramePath' in line:
            lineTmp=line.replace("SubFramePath = \\","")
            lineTmp=line.replace("SubFramePath =","")
            lineTmp=os.path.basename(lineTmp.replace('\\',"/"))
            lineTmp=lineTmp.replace(" ","")
            if self.relcompPrefix:
              baseName=os.path.splitext(os.path.splitext(inputMdoc)[0])[0]
              baseName=os.path.basename(baseName)
              lines[i] = "SubFramePath = " + prefix + baseName  + lineTmp
            else:
              lines[i] = "SubFramePath = " + prefix + lineTmp
        if ('TiltAngle =' in line) and invTiltAngle:  
            key,angle=line.split("=")
            lines[i] = key.replace(" ","") + " = " + str(-1*float(angle)) + "\n"
          
      lines.append("CryoBoost_RootMdocPath = " + os.path.abspath(inputMdoc) + "\n")       
      with open(outputMdoc, 'w') as file:
        file.writelines(lines)
  
  def __genLinks(self,inputPattern,targetFold,existingFiles):  
    
    #print("targetWk:" + targetFold + "/*." + os.path.splitext(inputPattern)[1])
    nrFilesAlreadyImported=len(glob.glob(targetFold + "/*" + os.path.splitext(inputPattern)[1]));
    dftmp = self.mdoc.all_df['SubFramePath'].apply(lambda x: x.replace('\\', '/'))
    framesFromMdoc = [os.path.join(os.path.dirname(inputPattern), os.path.basename(x)) for x in dftmp]
   
    #for file_path in glob.glob(inputPattern):
    for file_path in framesFromMdoc:
        file_name = os.path.basename(file_path)
        tragetFileName = os.path.join(targetFold,self.prefix+file_name)
        if self.relcompPrefix:
            mdoc_file = self.mdoc.all_df[self.mdoc.all_df['SubFramePath'].str.contains(file_name, case=False)]['mdocFileName'].iloc[0]
            mdoc_file = os.path.splitext(os.path.splitext(str(mdoc_file))[0])[0]
            tragetFileName = os.path.join(targetFold,self.prefix+mdoc_file+file_name)
        if self.__chkFileExists(os.path.abspath(file_path),existingFiles)==False:
          try:
             os.symlink(os.path.abspath(file_path),tragetFileName)
             self.__writeLog("info","Created symlink: " + tragetFileName + " -> " + file_path)
          except FileExistsError:
             self.__writeLog("info","Symlink already exists: " + tragetFileName + " -> " + file_path)
          except OSError as e:
             self.__writeLog("error","Error creating symlink for " + tragetFileName + ": " + str(e))
    nrFilesTotalImported=len(glob.glob(targetFold + "/*" + os.path.splitext(inputPattern)[1]));
    nrFilesNewImported=nrFilesTotalImported-nrFilesAlreadyImported
    
    self.__writeLog("info","Total number of tilts imported: " + str(nrFilesTotalImported) )
    self.__writeLog("info","Number of new tilts imported: " + str(nrFilesNewImported) )
    
              
  def __writeLog(self,type,message):
    
    if self.logDir is not None:
      if type=="error":
        self.logErrorFile.write("Error: " + message + "\n")
      elif type=="info":
        self.logInfoFile.write(message + "\n")
      
      if (self.logToConsole): 
        print(message)            
    
    
  def __chkFileExists(self,inputPattern,existingFiles):
    
    if inputPattern in existingFiles:
        return True
    
    return False
  def __checkDuplicates(self, inputPattern, existingFiles):

    name_duplicates=[]
    filePathsSource = [file_path for file_path in glob.glob(inputPattern)]
    filePathsSourceAbs = [os.path.abspath(file_path) for file_path in glob.glob(inputPattern)]
    baseNamesSource = [self.prefix+os.path.basename(file).replace('\n', '') for file in filePathsSource]
    baseNamesExisting = [os.path.basename(file).replace('\n', '') for file in existingFiles]
    mdocExistingAbs=self.__getexistingMdoc()
    mdocExistingAbs=[file.replace('\n', '') for file in mdocExistingAbs]
    
    name_sourceConflict = set(mdocExistingAbs).intersection(set(filePathsSourceAbs))
    name_sourceConflict = set([os.path.basename(file).replace('\n', '') for file in name_sourceConflict])
    name_targetConflict = set(baseNamesExisting).intersection(set(baseNamesSource))

    if  name_sourceConflict>=name_targetConflict:
        name_duplicates=[]
    else:    
        name_duplicates=name_targetConflict
    
    return name_duplicates
        
       

class schemeMeta:
  """
  """
  def __init__(self, schemeFolderPath):
    self.CRYOBOOST_HOME=os.getenv("CRYOBOOST_HOME")
    self.conf=cbconfig(self.CRYOBOOST_HOME + "/config/conf.yaml")
    self.schemeFilePath=schemeFolderPath+os.path.sep+"scheme.star"
    self.schemeFolderPath=schemeFolderPath
    self.read_scheme()
    
  def read_scheme(self):
    self.scheme_star=starFileMeta(self.schemeFilePath)
    self.jobs_in_scheme = self.scheme_star.dict["scheme_edges"].rlnSchemeEdgeOutputNodeName.iloc[1:-1]
    self.job_star = {
    f"{job}": starFileMeta(os.path.join(self.schemeFolderPath, f"{job}/job.star"))
    for job in self.jobs_in_scheme}
    #self.scheme_star_dict = starFileMeta(self.schemeFilePath)
    self.nrJobs = len(self.jobs_in_scheme)
  
  def getJobOptions(self, jobName):
    return self.job_star[jobName].dict["joboptions_values"]   
  
  def jobListToNodeList(self,jobList,tag=None):
    
    Node = namedtuple('Node', ['type', 'tag', 'inputType', 'inputTag'])
    nodes = []
    intag=None
    all_types=[]
    for job in jobList:
      inputType=self.getInputJobType(job)
      if inputType is not None and inputType not in all_types and len(all_types)>0:
          inputType =all_types[-1]
      oneNode = Node(type=job, tag=tag, inputType=inputType, inputTag=intag)
      nodes.append(oneNode)
      all_types.append(job)
      intag=tag
    nodes_dict = {i: node for i, node in enumerate(nodes)}   
    #nodes_dict = {i: row.to_dict() for i, row in nodes.iterrows()}
    nodes_df = pd.DataFrame.from_dict(nodes_dict, orient='index')
    
    return nodes,nodes_df
  
  def addNoiseToNoiseFilter(self):
    pass
  def removeNoiseToNoiseFilter(self):
    nFilterJobs=self.conf.confdata['computing']['JOBTypesApplication']['Noise2NoiseFilterJobs']
    nonFilterJobs=[job for job in self.jobs_in_scheme if job not in set(nFilterJobs)]
    nodes,nodes_df=self.jobListToNodeList(nonFilterJobs)
    schemeAdapted=self.filterSchemeByNodes(nodes_df)
    return schemeAdapted
  
  def getMajorInputParamNameFromJob(self, jobName):
    """
    Returns the input type for a given job name.
    
    Args:
        jobName (str): The name of the job.
        
    Returns:
        str: The input type for the job.
        
    Raises:
        Exception: If no input type is found for the job.
    """
    df = self.job_star[jobName].dict['joboptions_values']
    ind=df.rlnJobOptionVariable=="input_star_mics"
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_tiltseries" 
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_mic"
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_tomoset"
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_optimisation"
    if not any(ind):
        raise Exception("nether input_star_mics nor in_tiltseries found")
    row_index = df.index[ind]
    # inputType=os.path.basename(os.path.dirname(df.loc[row_index, "rlnJobOptionValue"].item()))
    inputParamName=df.loc[row_index, "rlnJobOptionVariable"].item()
    inputParamValue=df.loc[row_index, "rlnJobOptionValue"].item()
    scName=self.scheme_star.dict['scheme_general']['rlnSchemeName']
    inutJobType=os.path.dirname(inputParamValue.split(scName)[1])
    return inputParamName,inputParamValue,inutJobType
  
  def removeParticleJobs(self):
    """
    Removes particle jobs from the scheme.
    
    Returns:
        schemeAdapted (schemeMeta): A new schemeMeta object with particle jobs removed.
    """
    particleJobs=self.conf.confdata['computing']['JOBTypesApplication']['ParticleJobs']
    nonParticleJobs=[job for job in self.jobs_in_scheme if job not in set(particleJobs)]
    nodes,nodes_df=self.jobListToNodeList(nonParticleJobs)
    
    schemeAdapted=self.filterSchemeByNodes(nodes_df)
    return schemeAdapted
  
  def removefilterTiltsJobs(self):
    """
    Removes filter jobs from the scheme.
    
    Returns:
        schemeAdapted (schemeMeta): A new schemeMeta object with filter jobs removed.
    """
    filterJobs=self.conf.confdata['computing']['JOBTypesApplication']['FilterTiltsJobs']
    nonFilterJobs=[job for job in self.jobs_in_scheme if job not in set(filterJobs)]
    nodes,nodes_df=self.jobListToNodeList(nonFilterJobs)
    
    schemeAdapted=self.filterSchemeByNodes(nodes_df)
    return schemeAdapted
  
  def addParticleJobs(self,tags):
    particleJobs=self.conf.confdata['computing']['JOBTypesApplication']['ParticleJobs']
    nonParticleJobs=[job for job in self.jobs_in_scheme if job not in set(particleJobs)]
    nodes,nodes_df=self.jobListToNodeList(nonParticleJobs)
    for tag in tags:
      ndf,nodesPlTag_df=self.jobListToNodeList(particleJobs,tag)
      nodes_df = pd.concat([nodes_df, nodesPlTag_df], ignore_index=True)
      
    #nodes_dict = {i: node for i, node in enumerate(nodes)}   
    #nodes_dict = {i: row.to_dict() for i, row in nodes.iterrows()}
    #nodes_df = pd.DataFrame.from_dict(nodes_dict, orient='index')
    schemeAdapted=self.filterSchemeByNodes(nodes_df)
    return schemeAdapted
    
  def getInputJobType(self, jobName):

    if jobName=="importmovies": #first job for every pipeline
      return None
    
    df = self.job_star[jobName].dict['joboptions_values']
    ind=df.rlnJobOptionVariable=="input_star_mics"
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_tiltseries" 
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_mic"
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_tomoset"
    if not any(ind):
        ind=df.rlnJobOptionVariable=="in_optimisation"
    if not any(ind):
        raise Exception("nether input_star_mics nor in_tiltseries found")
    row_index = df.index[ind]
    inputType=os.path.basename(os.path.dirname(df.loc[row_index, "rlnJobOptionValue"].item()))
    
    return inputType
    
  def filterSchemeByNodes(self, nodes_df,filterMode="TypeOnly"):
    
   
    filtEdges_df=self.filterEdgesByNodes(self.scheme_star.dict["scheme_edges"], nodes_df)
    jobStar_dict=self.job_star
    jobStar_dictFilt=self.filterjobStarByNodes(jobStar_dict,nodes_df,filterMode)
    schemeJobs_dfFilt=self._filterSchemeJobsByNodes(self.scheme_star.dict["scheme_jobs"],nodes_df)
    
    scFilt=copy.deepcopy(self)
    scFilt.scheme_star.dict["scheme_edges"]=filtEdges_df
    scFilt.scheme_star.dict["scheme_jobs"]=schemeJobs_dfFilt
    scFilt.job_star=jobStar_dictFilt
    scFilt.nrJobs =len(scFilt.job_star)
    scFilt.jobs_in_scheme = scFilt.scheme_star.dict["scheme_edges"].rlnSchemeEdgeOutputNodeName.iloc[1:-1]
    #scFilt.jobTypes_in_scheme = nodes_df["type"].iloc[:]
    
    return scFilt   
  
  def _filterSchemeJobsByNodes(self,schemJobs,nodes_df):
    
    schemeJobs_dfFilt = pd.DataFrame(columns=schemJobs.columns)
    for index, row in nodes_df.iterrows():
        new_row=copy.deepcopy(schemJobs.head(1))
        new_row['rlnSchemeJobNameOriginal']=row['type'] + ('_' + row['tag'] if row['tag'] != None else '')
        new_row['rlnSchemeJobName']=row['type'] + ('_' + row['tag'] if row['tag'] != None else '')
        schemeJobs_dfFilt=pd.concat([schemeJobs_dfFilt,new_row])
    return schemeJobs_dfFilt
    
  def filterjobStarByNodes(self,jobStarDict,nodes_df, filterMode="TypeOnly"): 
    
    schemeJobs_dfFilt={}
    schemeName=self.scheme_star.dict["scheme_general"]["rlnSchemeName"]
    #for nodeid, node in nodes.items():
    for index, row in nodes_df.iterrows():
      jobNameWithTag=jobNameWithTag = row['type'] + ('_' + row['tag'] if row['tag'] != None else '')
      jobName=row['type']
      if filterMode=="TypeOnly":
        key= jobName
      else:
        key=jobNameWithTag
      schemeJobs_dfFilt[jobNameWithTag]=copy.deepcopy(jobStarDict[key])
      df=schemeJobs_dfFilt[jobNameWithTag].dict["joboptions_values"]
      ## adapt input
      if row['inputType'] is not None:
        #input=schemeName+row['inputType'] + ('_' + row['inputTag'] if row['inputTag'] != 'None' else '')
          input=schemeName+row['inputType'] + ('_' + str(row['inputTag']) if row['inputTag'] not in [None, 'None'] else '')
          input=input+os.path.sep+os.path.basename(self.conf.getJobOutput(row['inputType']))
          ind=df.rlnJobOptionVariable=="input_star_mics"
          if not any(ind):
              ind=df.rlnJobOptionVariable=="in_tiltseries" 
          if not any(ind):
              ind=df.rlnJobOptionVariable=="in_mic"
          if not any(ind):
              ind=df.rlnJobOptionVariable=="in_tomoset"
          if not any(ind):
              ind=df.rlnJobOptionVariable=="in_optimisation"
          if not any(ind):
              raise Exception("nether input_star_mics nor in_tiltseries found")
          
          row_index = schemeJobs_dfFilt[jobNameWithTag].dict["joboptions_values"].index[ind]
          schemeJobs_dfFilt[jobNameWithTag].dict["joboptions_values"].loc[row_index, "rlnJobOptionValue"] = input
          
    return schemeJobs_dfFilt 
  
  
  
  def filterEdgesByNodes(self,edge_df, nodes_df):     
    
    firstEdge=edge_df.loc[0:0].copy(deep=True)
    jobNameWithTagOld=firstEdge["rlnSchemeEdgeOutputNodeName"].item()
    #for nodeid, node in nodes.items(): 
    schemeEdge_df=firstEdge
    for index, row in nodes_df.iterrows():
        jobNameWithTag=jobNameWithTag = row['type'] + ('_' + row['tag'] if row['tag'] != None else '')
        dfOneEdge=firstEdge.copy(deep=True)
        dfOneEdge["rlnSchemeEdgeInputNodeName"]=jobNameWithTagOld
        dfOneEdge["rlnSchemeEdgeOutputNodeName"]=jobNameWithTag
        schemeEdge_df=pd.concat([schemeEdge_df,dfOneEdge],ignore_index=True) 
        jobNameWithTagOld=jobNameWithTag
   
    dfOneEdge=firstEdge.copy(deep=True)
    dfOneEdge["rlnSchemeEdgeInputNodeName"]=jobNameWithTag
    dfOneEdge["rlnSchemeEdgeOutputNodeName"]="EXIT"
    schemeEdge_df=pd.concat([schemeEdge_df,dfOneEdge],ignore_index=True) 
    
    return schemeEdge_df
      
  def locate_val(self,job_name:str,var:str):
    """
    locates the value defined of the dict defined in the job_star_dict dictionary so it can be displayed and edited.

    Args:
      job_name (str): job name as str as it's stated in the job_star_dict ("importmovies", "motioncorr", "ctffind", "aligntilts", "reconstruction").
      var (str): name of variable/parameter that should be changed (parameters as defined in the job.star files).
      job_dict (str): dataframe that should be accessed inside the job defined in job_name (standard input is the df containing the parameters).
      column_variable (str): column in the dataframe containing the parameters (standard input is the correct name).
      column_value (str): column in the dataframe containing the values assigned to each parameter (standard input is the correct name).

    Returns:
      str: value that is currently assigned to the defined parameter of the defined job.
    """
    job_dict = "joboptions_values", 
    column_variable = "rlnJobOptionVariable" 
    column_value = "rlnJobOptionValue"
    val = self.job_star[job_name].dict[job_dict].loc[self.job_star[job_name].dict[job_dict][column_variable] == var, column_value].values[0]
    return val
  
  def update_job_star_dict(self,job_name, param, value):
      """
      updates the job_star_dict dictionary (containing all .star files of the repective jobs) with the values provided.

      Args:
        job_name (str): job name as str as it's stated in the job_star_dict ("importmovies", "motioncorr", "ctffind", "aligntilts", "reconstruction").
        param (str): parameter that should be updated as str as it's called in the respective job.star file.
        value (str): new value that should be placed in the job.star file for the set parameter.

      Returns:
        job_star_dict with updated value for respective parameter.
      """
      index = self.job_star[job_name].dict["joboptions_values"].index[self.job_star[job_name].dict["joboptions_values"]["rlnJobOptionVariable"] == param]
      self.job_star[job_name].dict["joboptions_values"].iloc[index, 1] = value
      
      return self.job_star[job_name].dict


  
  def write_scheme(self,schemeFolderPath):
     self.schemeFilePath =  schemeFolderPath+os.path.sep+"scheme.star"
     self.schemeFolderPath =  schemeFolderPath
     os.makedirs(schemeFolderPath, exist_ok=True)
     self.scheme_star.writeStar(schemeFolderPath+os.path.sep+"scheme.star")

    
    # repeat for all jobs, creating a job.star file in these directories
     for job in self.jobs_in_scheme:
        jobFold = schemeFolderPath+os.path.sep+job 
        os.makedirs(jobFold, exist_ok=True)
        job_star = self.job_star[job]
        job_star.writeStar(jobFold+os.path.sep+"job.star")
        

class tiltSeriesMeta:
    """
    Class for handling tilt series metadata.

    Args:
        tiltseriesStarFile (str): Path to the tilt series star file.
        relProjPath (str): Path to the relative project directory.

    Attributes:
        tilt_series_df (pd.DataFrame): DataFrame containing the tilt series information.
        tiltseriesStarFile (str): Path to the tilt series star file.
        relProjPath (str): Path to the relative project directory.

    Methods:
        __init__(self, tiltseriesStarFile, relProjPath): Initializes the tiltSeriesMeta class.
        readTiltSeries(self): Reads the tilt series star file and its associated tilt series files.
        filterTilts(self, fitlterParams): Filters the tilt series based on the provided parameters.
        filterTiltSeries(self, fitlterParams): Filters the tilt series based on the provided parameters.
        writeTiltSeries(self, tiltseriesStarFile, tiltSeriesStarFolder='tilt_series'): Writes the tilt series star file and its associated tilt series files.
    """

    def __init__(self, tiltseriesStarFile, relProjPath=''):
        """
        Initializes the tiltSeriesMeta class.

        Args:
            tiltseriesStarFile (str): Path to the tilt series star file.
            relProjPath (str): Path to the relative project directory.

        Attributes:
            tilt_series_df (pd.DataFrame): DataFrame containing the tilt series information.
            tiltseriesStarFile (str): Path to the tilt series star file.
            relProjPath (str): Path to the relative project directory.
        """
        self.tilt_series_df = None
        self.tiltseriesStarFile = tiltseriesStarFile
        self.relProjPath = relProjPath
        self.readTiltSeries()

    def readTiltSeries(self):
        
        print("Reading: " + self.tiltseriesStarFile)
        tilt_series=starFileMeta(self.tiltseriesStarFile)
        #tilt_series_df =tilt_series.dict[next(iter(tilt_series.dict.keys()))] 
        self.nrTomo=tilt_series.df.shape[0]
        all_tilts_df = pd.DataFrame()
        tilt_series_tmp = pd.DataFrame()
        
        i = 0
        for tilt_seriesName in tilt_series.df["rlnTomoTiltSeriesStarFile"]:
           # tilt_star_df = read_star(self.relProjPath + tilt_series)
            tilt_star=starFileMeta(self.relProjPath + tilt_seriesName)
            all_tilts_df = pd.concat([all_tilts_df, tilt_star.df], ignore_index=True)
            tmp_df = pd.concat([tilt_series.df.iloc[[i]]] * tilt_star.df.shape[0], ignore_index=True)
            tilt_series_tmp = pd.concat([tilt_series_tmp, tmp_df], ignore_index=True)
            i += 1

        #all_tilts_df = pd.concat([all_tilts_df, tilt_series_tmp], axis=1)
        if "rlnTomoZRot" in tilt_series_tmp.columns:
           tilt_series_tmp = tilt_series_tmp.rename(columns={"rlnTomoZRot": "rlnTomoZRotTs"})
        all_tilts_df = pd.concat([tilt_series_tmp,all_tilts_df], axis=1)

        columns_to_check = [col for col in all_tilts_df.columns if col not in ['rlnCtfScalefactor']]
        all_tilts_df.dropna(subset=columns_to_check,inplace=True)  # check !!
        #generte key to merge later on  
        if 'rlnMicrographName' in all_tilts_df.columns:
          k=all_tilts_df['rlnMicrographName'].apply(os.path.basename)
        else:
          k=all_tilts_df['rlnMicrographMovieName'].apply(os.path.basename)
        
        if (k.is_unique):
          all_tilts_df['cryoBoostKey']=k
        else:
          raise Exception("rlnMicrographName is not unique !!")        

        # duplicate_cols = all_tilts_df.columns[all_tilts_df.columns.duplicated()]
        # if not duplicate_cols.empty:
        #   all_tilts_df= all_tilts_df.loc[:, ~all_tilts_df.columns.duplicated()]
        
        self.all_tilts_df = all_tilts_df
        self.tilt_series_df = tilt_series.df
        self.__extractInformation()
        # Store the key values
        key_values = self.all_tilts_df['cryoBoostKey']
        # Remove the column
        self.all_tilts_df = self.all_tilts_df.drop('cryoBoostKey', axis=1)
        # Add it back (it will be added as the last column)
        self.all_tilts_df['cryoBoostKey'] = key_values
        
    def writeTiltSeries(self, tiltseriesStarFile, tiltSeriesStarFolder='tilt_series'):
        """
        Writes the tilt series star file and its associated tilt series files.

        Args:
            self (tiltSeriesMeta): An instance of the tiltSeriesMeta class.
            tiltseriesStarFile (str): Path to the tilt series star file.
            tiltSeriesStarFolder (str): Folder name for the tilt series star files.

        Example:
            >>> ts = tiltSeriesMeta("/path/to/tilt_series_star_file", "/path/to/rel_proj_path")
            >>> ts.writeTiltSeries("/tmp/fbeck/test8/tiltseries.star")
        """
        print("Writing: " + tiltseriesStarFile)
        #generate tiltseries star from all dataframe ...more generic if filter removes all tilts of one series
        #ts_df = self.all_tilts_df[self.tilt_series_df.columns].copy()
        #indStart=self.all_tilts_df.shape[1]-self.tilt_series_df.shape[1]
        ts_df = self.all_tilts_df.iloc[:,0:self.tilt_series_df.shape[1]].copy()
        ts_df=ts_df.drop("cryoBoostKey",axis=1,errors='ignore')
        
        ts_df.drop_duplicates(inplace=True)
        tsFold = os.path.dirname(tiltseriesStarFile) + os.path.sep + tiltSeriesStarFolder + os.path.sep
        ts_df['rlnTomoTiltSeriesStarFile'] = ts_df['rlnTomoTiltSeriesStarFile'].apply(lambda x: os.path.join(tsFold, os.path.basename(x)))
        os.makedirs(tsFold,exist_ok=True)
        ts_dict={}
        if "rlnTomoZRotTs" in ts_df.columns:
           ts_df = ts_df.rename(columns={"rlnTomoZRotTs": "rlnTomoZRot"})
        ts_dict['global']=ts_df
        
        stTs=starFileMeta(ts_dict)
        stTs.writeStar(tiltseriesStarFile)
       
        fold = os.path.dirname(tiltseriesStarFile)
        Path(fold + os.sep + tiltSeriesStarFolder).mkdir(exist_ok=True)
        for tilt_series in self.tilt_series_df["rlnTomoTiltSeriesStarFile"]:
            oneTs_df = self.all_tilts_df[self.all_tilts_df['rlnTomoTiltSeriesStarFile'] == tilt_series].copy()
            #oneTs_df.drop(self.tilt_series_df.columns, axis=1, inplace=True)
            #oneTs_df=test=self.all_tilts_df.iloc[:,0:indStart-1]
            oneTs_df=oneTs_df.iloc[:,self.tilt_series_df.shape[1]:]
            tomoName = self.all_tilts_df.loc[self.all_tilts_df['rlnTomoTiltSeriesStarFile'] == tilt_series, 'rlnTomoName'].unique()[0]
            oneTS_dict={}
            oneTS_dict[tomoName]=oneTs_df
            stOneTs=starFileMeta(oneTS_dict)
            stOneTs.writeStar(fold + os.sep + tiltSeriesStarFolder + os.sep + os.path.basename(tilt_series))
           
            
    def filterTilts(self, fitlterParams):
      """
      Filters the tilt series based on the provided parameters.

      Args:
          self (tiltSeriesMeta): An instance of the tiltSeriesMeta class.
          fitlterParams (dict): A dictionary containing the parameters and their respective thresholds for filtering the tilt series.

      Raises:
          ValueError: If any of the required star files are not found.

      Returns:
          None: This method modifies the tiltSeriesMeta object in-place.

      Example:
          >>> ts = tiltSeriesMeta("/path/to/tilt_series_star_file", "/path/to/rel_proj_path")
          >>> ts.filterTilts({"rlnCtfMaxResolution": (7.5, 30,-35,35), "rlnDefocusU": (1, 80000,-60,60)})
      """
      pTilt = "rlnTomoNominalStageTiltAngle"  # fieldName for tiltRange
      dfTmp = self.all_tilts_df

      for param, thresholds in fitlterParams.items():
          
          if isinstance(thresholds, set):
              v = dfTmp[param].isin(thresholds)
          else:    
              if isinstance(thresholds[0], str):
                  v = dfTmp[param] == thresholds
              else:
                  vParamRange = (dfTmp[param] > thresholds[0]) & (dfTmp[param] < thresholds[1])
                  vTiltRange = (dfTmp[pTilt] > thresholds[2]) & (dfTmp[pTilt] < thresholds[3])
                  # Tiltrange defines for which tilts the filter gets applied
                  v = vParamRange | (vTiltRange == False)

          dfTmp = dfTmp[v]

      dfTmp.reset_index(drop=True, inplace=True)
      self.all_tilts_df = dfTmp
      
      ts_df = self.all_tilts_df[self.tilt_series_df.columns].copy()
      ts_df.drop_duplicates(inplace=True)
      self.tilt_series_df=ts_df
      self.nrTomo=len(self.tilt_series_df)
      
    def reduceToNonOverlab(self,tsSubset):
      tomoNamesSub=set(tsSubset.tilt_series_df["rlnTomoName"])
      tomoNamesFull=set(self.tilt_series_df["rlnTomoName"])
      tomoNamesDiff=tomoNamesFull-tomoNamesSub
      self.filterTilts({"rlnTomoName": tomoNamesDiff})
    
    def mergeTiltSeries(self,tsToAdd):
      
      self.all_tilts_df=pd.concat([self.all_tilts_df,tsToAdd.all_tilts_df],axis=0)
      self.all_tilts_df.reset_index(drop=True, inplace=True)
      ts_df = self.all_tilts_df[self.tilt_series_df.columns].copy()
      ts_df.drop_duplicates(inplace=True)
      self.tilt_series_df=ts_df
      self.nrTomo=len(self.tilt_series_df) 
      
    def filterTiltSeries(self,minNumTilts,fitlterParams):
      pass 
    
    def getMicrographMovieNameFull(self):
      return self.relProjPath+self.all_tilts_df['rlnMicrographName'] 
    
    def addColumns(self,columns_df):  
      """
      Adds new columns to the DataFrame stored in the instance variable `all_tilts_df`.

      This method takes a DataFrame `columns_df` containing new columns to be added to `all_tilts_df`. 
      The merge is performed on the 'rlnMicrographMovieName' column, using a left join. This means that all 
      entries in `all_tilts_df` will be retained, and matching entries from `columns_df` will be added based 
      on the 'cryoBoostKey' column. If there are no matching entries in `columns_df`, the new 
      columns will contain NaN values for those rows.

      Args:
      - columns_df (DataFrame): A pandas DataFrame containing the columns to be added to `all_tilts_df`. 
         It must include a 'cryoBoostKey' column for the merge operation.

      Returns:
      - None. The method updates `all_tilts_df` in place by adding the new columns from `columns_df`.

      """ 
      k=columns_df['cryoBoostKey'].apply(os.path.basename)
      if (k.is_unique):
        columns_df['cryoBoostKey']=k
      
      self.all_tilts_df=self.all_tilts_df.merge(columns_df,on='cryoBoostKey',how='left') 
    
    def __extractInformation(self):        
      self.tsInfo=type('', (), {})()
      self.tsInfo.allUnique=1
      
      directories = self.all_tilts_df["rlnMicrographMovieName"].apply(lambda x: os.path.dirname(x))
      extensions = self.all_tilts_df["rlnMicrographMovieName"].apply(lambda x: os.path.splitext(x)[1])

      unique_directories = directories.unique()
      unique_extensions = extensions.unique()
      self.tsInfo.allUnique=self.tsInfo.allUnique and len(unique_directories)==1 and len(unique_extensions)==1
      self.tsInfo.frameFold=unique_directories[0]
      self.tsInfo.frameExt=unique_extensions[0]
      
      if len(self.all_tilts_df["rlnMicrographPreExposure"].drop_duplicates())>1:
        self.tsInfo.expPerTilt=self.all_tilts_df["rlnMicrographPreExposure"].drop_duplicates().sort_values().iloc[1]
      else:
        self.tsInfo.expPerTilt=self.all_tilts_df["rlnMicrographPreExposure"].drop_duplicates().sort_values().iloc[0]
      
      self.tsInfo.numTiltSeries=self.tilt_series_df.shape[0]
      
      df_attr="rlnMicrographName"
      #print(self.all_tilts_df.columns)
      if df_attr in self.all_tilts_df.columns:
          warpFrameSeriesFold=self.all_tilts_df[df_attr].sort_values().iloc[0]
          self.tsInfo.warpFrameSeriesFold=os.path.split(warpFrameSeriesFold)[0].replace("average","")
      else:
          print(f"Warning: {df_attr} not found in tilt_series_df")
      
      attributes = {  
                  'volt': 'rlnVoltage',
                  'cs': 'rlnSphericalAberration',
                  'cAmp': 'rlnAmplitudeContrast',
                  'framePixS': 'rlnMicrographOriginalPixelSize',
                  'tiltAxis': 'rlnTomoNominalTiltAxisAngle',
                  'keepHand': 'rlnTomoHand'
                  }

      for attr, df_attr in attributes.items():
          if df_attr in self.all_tilts_df.columns:
              unique_values = self.all_tilts_df[df_attr].unique()
              setattr(self.tsInfo, attr, unique_values)
              self.tsInfo.allUnique = self.tsInfo.allUnique and len(unique_values) == 1
              if len(unique_values) > 0:
                  setattr(self.tsInfo, attr, unique_values[0])
          else:
              print(f"Warning: {df_attr} not found in tilt_series_df")
            
      self.tsInfo.tomoSize = None
      if "rlnTomoReconstructedTomogram" in self.all_tilts_df.columns:
        tomoName = self.all_tilts_df["rlnTomoReconstructedTomogram"].iloc[0]
        if os.path.exists(tomoName):
            with mrcfile.open(tomoName, header_only=True) as mrc:
                self.tsInfo.tomoSize = [mrc.header.nx, mrc.header.ny, mrc.header.nz]
        else:
            print(f"Warning: Tomogram file {tomoName} does not exist.")
            
        
      
      