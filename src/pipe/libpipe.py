from src.rw.librw import cbconfig,importFolderBySymlink,schemeMeta,dataImport,starFileMeta   
from src.misc.system import run_command,run_command_async
import shutil
import os,re 
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
    self.importPrefix=args.impPrefix
    self.pathProject=args.proj
    headNode=self.conf.confdata['submission'][0]['HeadNode']
    sshStr=self.conf.confdata['submission'][0]['SshCommand']
    envRel=self.conf.confdata['submission'][0]['Environment']
    schemeName=self.scheme.scheme_star.dict['scheme_general']['rlnSchemeName']
    schemeName=os.path.basename(schemeName.strip(os.path.sep)) #remove path from schemeName
    schemeLockFile=".relion_lock_scheme_" + schemeName + os.path.sep  + "lock_scheme"
    relSchemeStart="export TERM=xterm;(relion_schemer --scheme " + schemeName  + ' --run --verb 2 & pid=\$!; echo \$pid  > Schemes/'+ schemeName + '/scheme.pid)' # working
    #relSchemeStart="export TERM=xterm;{relion_schemer --scheme " + schemeName  + ' --run --verb 2 & pid=\$!; echo \$pid  > Schemes/'+ schemeName + '/scheme.pid}' 
    #relSchemeStart="export TERM=xterm;relion_schemer --scheme " + schemeName  + ' --run --verb 2 & pid=\$!; echo \$pid  > Schemes/'+ schemeName + '/scheme.pid'
    #relSchemeStart = "export TERM=xterm; { relion_schemer --scheme " + schemeName + " --run --verb 2 & pid=$!; echo $pid > Schemes/" + schemeName + "/scheme.pid; }"
    #waitFor=';sleep 2; while ps -p \`cat Schemes/' + schemeName + '/scheme.pid\` > /dev/null 2>&1;do sleep 4;done;sleep 2'
    waitFor=";sleep 259200" #keep the ssh for 3 days in case of manual sorting
   
    self.schemeLockFile=schemeLockFile
    self.schemeName=schemeName
    
    chFold="cd " + os.path.abspath(self.pathProject) + ";"
    #relSchemeAbrot="relion_schemer --scheme " + schemeName  + " --abort; + pkill -f """ + 
    #relSchemeAbrot="pkill -f \'relion_schemer --scheme " + schemeName + "\'" 
    relSchemeAbrot="kill XXXPIDXXX"
    relStopLastJob="scancel XXXJOBIDXXX"
    relSchemeReset="relion_schemer --scheme " + schemeName  + " --reset"
    relSchemeUnlock="rm " + schemeLockFile + ";rmdir "+ os.path.dirname(schemeLockFile)
    relGuiStart="relion --tomo --do_projdir "
    relGuiUpdate="relion_pipeliner --RunJobs "
    envStr=envRel + ";"
    logStr=" > " + schemeName + ".log 2>&1 " 
    logStrAdd=" >> " + schemeName + ".log 2>&1 "
    self.commandSchemeStart=sshStr + " " + headNode + ' "'  + envStr + chFold + relSchemeStart + logStrAdd + waitFor + '"'
    self.commandSchemeAbrot=sshStr + " " + headNode + ' "'  + envStr  + relSchemeAbrot + ";" + logStrAdd + '"'
    self.commandSchemeJobAbrot=sshStr + " " + headNode + ' "' + relStopLastJob + ";" + logStrAdd + '"'
    self.commandSchemeReset=sshStr + " " + headNode + ' "'  + envStr + chFold + relSchemeReset + logStrAdd + '"'
    self.commandGui=sshStr + " " + headNode + ' "'  + envStr + chFold + relGuiStart  + '"'
    self.commandSchemeUnlock=sshStr + " " + headNode + ' "'  + envStr + chFold + relSchemeUnlock + logStrAdd + '"'
    self.commandGuiUpdate=sshStr + " " + headNode + ' "'  + envStr + chFold + relGuiUpdate + '"' 
      
  def initProject(self):
    #importFolderBySymlink(self.pathFrames, self.pathProject)
    #if (self.pathFrames!=self.pathMdoc):
    #    importFolderBySymlink(self.pathMdoc, self.pathProject)
    os.makedirs(self.pathProject,exist_ok=True)
    os.makedirs(self.pathProject + "/" + "Logs",exist_ok=True)
    self.generatCrJobLog("initProject","generting: " + self.pathProject + "\n")
    self.generatCrJobLog("initProject","generting: " + self.pathProject + "/Logs" + "\n")
    self.generatCrJobLog("initProject","copying: " + os.getenv("CRYOBOOST_HOME") + "/config/qsub" + "\n")
    self.writeToLog(" + Project: " + self.pathProject + " --> Logs/initProject" "\n")
    shutil.copytree(os.getenv("CRYOBOOST_HOME") + "/config/qsub", self.pathProject + os.path.sep + "qsub",dirs_exist_ok=True)
    
  def importData(self):#,wkFrames,wkMdoc): 
    self.writeToLog(" + ImportData: --> Logs/importData" "\n")
    self.writeToLog("    " + self.pathFrames + " --> frames" +"\n")
    self.writeToLog("    " + self.pathMdoc + " --> mdoc" +"\n")
    
    logDir=self.pathProject + os.path.sep + "Logs" + os.path.sep + "importData"
    dataImport(self.pathProject,self.pathFrames,self.pathMdoc,self.importPrefix,logDir=logDir)
    print("frames/"+os.path.basename(self.pathFrames))
    self.scheme.update_job_star_dict('importmovies','movie_files',"frames/"+os.path.basename(self.pathFrames))
    self.scheme.update_job_star_dict('importmovies','mdoc_files',"mdoc/"+os.path.basename(self.pathMdoc))
    #import movies and mdoc()  
      
  def writeScheme(self):
     
     self.generatCrJobLog("initProject","writing Scheme to: " + self.pathProject + "/Schemes" + "\n")
     path_scheme = os.path.join(self.pathProject, self.scheme.scheme_star.dict['scheme_general']['rlnSchemeName'])
     nodes = {i: job for i, job in enumerate(self.scheme.jobs_in_scheme)}
     #self.scheme.filterSchemeByNodes(nodes) #to correct for input output mismatch within the scheme
     self.scheme.write_scheme(path_scheme)
     self.scheme.schemeFilePath=path_scheme + "/scheme.star"
  
  def runScheme(self):
    
    self.generatCrJobLog("manageWorkflow","starting workflow:" + "\n")
    self.generatCrJobLog("manageWorkflow","  " + self.commandSchemeStart + "\n")
    p=run_command_async(self.commandSchemeStart)
    #p=run_command(self.commandSchemeStart)
   
    
  def runSchemeSync(self):
    p=run_command(self.commandSchemeStart)
   
  def abortScheme(self):
    lastBatchJobId,lastJobFolder=self.parseSchemeLogFile()
    self.writeToLog(" + Abort Workflow: --> Logs/manageWorkflow" + "\n")
    self.writeToLog("   Name: " + self.schemeName + "\n")
    pidFile=self.pathProject + '/Schemes/'+ self.schemeName + '/scheme.pid'
    try:
      with open(pidFile, 'r') as file:
           pid = int(file.read().strip())
    except FileNotFoundError:
      print(f"PID file {pidFile} does not exist.") 

    cSchemeAbroat=self.commandSchemeAbrot.replace("XXXPIDXXX",str(pid))
    self.generatCrJobLog("manageWorkflow","stopping workflow:" + "\n")
    self.generatCrJobLog("manageWorkflow"," + " + cSchemeAbroat + "\n")
    p=run_command(cSchemeAbroat)
    if lastBatchJobId != None:
      self.generatCrJobLog("manageWorkflow","killing job:" + "\n")
      self.generatCrJobLog("manageWorkflow",self.commandSchemeJobAbrot.replace("XXXJOBIDXXX",lastBatchJobId) +"\n")                     
      p=run_command(self.commandSchemeJobAbrot.replace("XXXJOBIDXXX",lastBatchJobId))
    self.setLastRunningJobToFailed()
    p=run_command(self.commandGuiUpdate)
    self.generatCrJobLog("manageWorkflow","unlocking \n")
    self.generatCrJobLog("manageWorkflow"," + " + self.commandSchemeUnlock + "\n")
    self.writeToLog(" + Workflow aborted !\n")
    self.unlockScheme()
    
  def setLastRunningJobToFailed(self):
      defPipePath=self.pathProject+os.path.sep+"default_pipeline.star"
      
      if os.path.isfile(defPipePath):
        try:
          st=starFileMeta(defPipePath)
          df=st.dict["pipeline_processes"]
          hit=df.rlnPipeLineProcessName[df.index[df['rlnPipeLineProcessStatusLabel'] == 'Running']]
          fold=str(hit.values[0])
          if os.path.isfile(fold + os.path.sep + "RELION_JOB_EXIT_SUCCESS")==False:
            df.loc[df['rlnPipeLineProcessStatusLabel'] == 'Running', 'rlnPipeLineProcessStatusLabel'] = 'Failed'
            print("setting to job to failed")
            st.writeStar(defPipePath)
        except:
          print("error resetting pipe!")
          fold=None
        return fold
      else:
        return None
    
  def checkForLock(self):  
    pathLock=self.pathProject + os.path.sep + self.schemeLockFile
    print(pathLock)
    print(os.path.isfile(pathLock))
    return os.path.isfile(pathLock)
  
  def resetScheme(self):
    self.writeToLog(" + Reset Workflow --> Logs/manageWorkflow \n")
    self.generatCrJobLog("manageWorkflow","  " + self.commandSchemeReset + "\n")
    p=run_command(self.commandSchemeReset)
    self.generatCrJobLog("manageWorkflow",self.commandSchemeReset +"\n")
    self.writeToLog(" + Workflow  reset done !\n")
  
  
  def setCurrentNodeScheme(self,NodeName):
    
    path_scheme = os.path.join(self.pathProject, self.scheme.scheme_star.dict['scheme_general']['rlnSchemeName'])
    self.writeToLog(" + Reset Workflow to node: " + NodeName + " --> Logs/manageWorkflow"  + "\n")
    print(self.scheme.schemeFilePath)
    self.scheme.read_scheme()
    self.scheme.scheme_star.dict["scheme_general"]["rlnSchemeCurrentNodeName"]=NodeName
    print(self.scheme.scheme_star.dict["scheme_jobs"])
    self.writeScheme()
    self.writeToLog(" + Workflow reset done !\n")
    
    
  def getCurrentNodeScheme(self):
   #self.scheme=schemeMeta(self.defaultSchemePath)
   self.scheme.read_scheme()
   return self.scheme.scheme_star.dict["scheme_general"]["rlnSchemeCurrentNodeName"]
        
  def unlockScheme(self):
    pathLock=self.pathProject + os.path.sep + os.path.dirname(self.schemeLockFile)
    if os.path.isdir(pathLock):
      self.writeToLog(" + Unlock Workflow: \n")
      self.generatCrJobLog("manageWorkflow" ," + " + self.commandSchemeUnlock + "\n")
      p=run_command(self.commandSchemeUnlock)
        
  def openRelionGui(self):
    print(self.commandGui)
    p=run_command_async(self.commandGui)
   
  def parseSchemeLogFile(self):
    """
    Parses the scheme log file to extract the last batch job ID and job folder.

    Args:
        self (Pipe): An instance of the Pipe class.

    Returns:
        tuple: A tuple containing the last batch job ID and job folder.

    """
    file_path = self.pathProject + os.path.sep + self.schemeName + ".log"
    if (os.path.isfile(file_path) == False):
        return None, None
    with open(file_path, 'r') as file:
        last_batch_job_id = None
        last_job_folder = None
        for line in file:
            re_res_last_batch_job = re.search("Submitted batch job", line)
            if re_res_last_batch_job:
                last_batch_job_id = re_res_last_batch_job.string.split("job")[1].strip()  # Assuming the format is "Submitted jobid"
            
            #re_res_last_job_folder = re.search("Creating new Job", line) #buggy should be "Executing Job:" but it doesn't work gets only upadted when job is finished
            re_res_last_job_folder = re.search("Executing Job:", line)
            if re_res_last_job_folder:
                last_job_folder = re_res_last_job_folder.string.split("Job:")[1].split(" ")[1].strip() 
            
            re_res_last_job_folder = re.search(' --> Logs/', line)
            if re_res_last_job_folder:
                last_job_folder = re_res_last_job_folder.string.split("-->")[1].split(" ")[1].strip()
            
            
            
    return last_batch_job_id,last_job_folder    
               
  def getLastJobLogs(self):
      lastBatchJobId,lastJobFolderScheme=self.parseSchemeLogFile()
      lastJobFolderPipe=self.getRunningJob()
      if (lastJobFolderPipe is  None):
        lastJobFolder=lastJobFolderScheme
      else:
        lastJobFolder=lastJobFolderPipe
      
      if (lastJobFolder is not None):
        jobOut=self.pathProject+os.path.sep+lastJobFolder+os.path.sep+"run.out"
        jobErr=self.pathProject+os.path.sep+lastJobFolder+os.path.sep+"run.err"
      else:
        print("no Logs found")
        jobOut="No logs found"
        jobErr="No logs found"  
      #TODO: check for ext Log
      return jobOut,jobErr               
  
  def getRunningJob(self):
      defPipePath=self.pathProject+os.path.sep+"default_pipeline.star"
      
      if os.path.isfile(defPipePath):
        try:
            st=starFileMeta(defPipePath)
            df=st.dict["pipeline_processes"]
            hit=df.rlnPipeLineProcessName[df.index[df['rlnPipeLineProcessStatusLabel'] == 'Running']]
            if hit.size > 0:
              fold=str(hit.values[0])
            else:
              hit=df.loc[df['rlnPipeLineProcessStatusLabel'] == 'Failed', 'rlnPipeLineProcessName'].iloc[-1]
              fold=hit
        except:
              fold=None
        return fold
      else:
        return None
        
      
  
  def writeToLog(self,text):
      logFile=self.pathProject+os.path.sep+self.schemeName+".log"
      with open(logFile, "a") as myfile:
          myfile.write(text)
  
  def generatCrJobLog(self,jobName,text,type="out"):
      
      os.makedirs(self.pathProject + "/Logs/" + jobName,exist_ok=True)
      logFile=self.pathProject+ "/Logs/" + jobName+ "/run.out"
     
      with open(logFile, "a") as myfile:
          myfile.write(text)
      
      logFile=self.pathProject+ "/Logs/" + jobName+ "/run.err"
      with open(logFile, "a") as myfile:
        pass            