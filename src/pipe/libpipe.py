from src.rw.librw import cbconfig,importFolderBySymlink,schemeMeta
from src.misc.system import run_command,run_command_async
import shutil
import os 
import subprocess

class pipe:
  """_summary_

  Raises:if (type(args.scheme) == str and os.path.exists(file_path)):
      self.defaultSchemePath=args.scheme
      Exception: _description_

  Returns:
      _type_: _description_
  """
  def __init__(self,args):
    CRYOBOOST_HOME=os.getenv("CRYOBOOST_HOME")
    if (type(args.scheme) == str and os.path.exists(args.scheme)==False):
      self.defaultSchemePath=CRYOBOOST_HOME + "/config/Schemes/" + args.scheme
    if (type(args.scheme) == str and os.path.exists(args.scheme)):
      self.defaultSchemePath=args.scheme
    if type(args.scheme)==schemeMeta:  
      self.scheme=args.scheme
    else:
      self.scheme=schemeMeta(self.defaultSchemePath)
    
    self.confPath=CRYOBOOST_HOME + "/config/conf.yaml"
    self.conf=cbconfig(self.confPath)     
    self.args=args
    self.pathMdoc=args.mdocs
    self.pathFrames=args.movies
    self.pathProject=args.proj
    headNode=self.conf.confdata['submission'][0]['HeadNode']
    sshStr=sub=self.conf.confdata['submission'][0]['SshCommand']
    schemeName=self.scheme.scheme_star.dict['scheme_general']['rlnSchemeName']
    schemeName=os.path.basename(schemeName.strip(os.path.sep)) #remove path from schemeName
    relSchemeStart="relion_schemer --scheme " + schemeName  + " --run"
    relGuiStart="relion --tomo --do_projdir "
    chFold="cd " + os.path.abspath(self.pathProject) + ";"
    envStr="module load RELION/5.0-beta-3;"
    logStr=" > " + schemeName + ".log 2>&1 " 
    self.commandScheme=sshStr + " " + headNode + ' "'  + envStr + chFold + relSchemeStart + logStr + '"'
    self.commandGui=sshStr + " " + headNode + ' "'  + envStr + chFold + relGuiStart  + '"'
    
      
  def initProject(self):
    importFolderBySymlink(self.pathFrames, self.pathProject)
    if (self.pathFrames!=self.pathMdoc):
        importFolderBySymlink(self.pathMdoc, self.pathProject)
    self.scheme.update_job_star_dict('importmovies','movie_files',os.path.basename(self.pathFrames.strip(os.path.sep)) + os.path.sep + "*.eer")
    self.scheme.update_job_star_dict('importmovies','mdoc_files',os.path.basename(self.pathMdoc.strip(os.path.sep)) + os.path.sep + "*.mdoc")
    shutil.copytree(os.getenv("CRYOBOOST_HOME") + "/config/qsub", self.pathProject + os.path.sep + "qsub",dirs_exist_ok=True)
    
      
  def writeScheme(self):
     path_scheme = os.path.join(self.pathProject, self.scheme.scheme_star.dict['scheme_general']['rlnSchemeName'])
     nodes = {i: job for i, job in enumerate(self.scheme.jobs_in_scheme)}
     self.scheme.filterSchemeByNodes(nodes) #to correct for input output mismatch within the scheme
     self.scheme.write_scheme(path_scheme)
  
  def runScheme(self):
    print("-----------------------------------------")
    print(self.commandScheme)
    p=run_command_async(self.commandScheme)
    print("-----------------------------------------")
 
  def runSchemeSync(self):
    print("-----------------------------------------")
    print(self.commandScheme)
    p=run_command(self.commandScheme)
    print("-----------------------------------------")
 
 
  def openRelionGui(self):
    print("-----------------------------------------")
    print(self.commandGui)
    p=run_command_async(self.commandGui)
    print("-----------------------------------------")        