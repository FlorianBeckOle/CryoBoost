import sys,os,subprocess
from distutils.util import strtobool
from src.misc.system import run_wrapperCommand
from src.templateMatching.libTemplateMatching import templateMatchingWrapperBase


class pytomTm(templateMatchingWrapperBase):
    def __init__(self,args,runFlag=None):
       
        super().__init__(args,runFlag=runFlag)
       #pass
        
    def prepareInputs(self):

        print("--------------generate files for pytom---------------------------")
        sys.stdout.flush()  
        #self.generatePytomInputFiles(columnName="rlnTomoNominalStageTiltAngle",tag="tiltAngle",ext=".tlt")
        self.generatePytomInputFiles(columnName="rlnTomoYTilt",tag="tiltAngle",ext=".tlt")
        self.generatePytomInputFiles(columnName="rlnDefocusU",tag="defocus",fact=10000)
        self.generatePytomInputFiles(columnName="rlnMicrographPreExposure",tag="dose")

     
    def runMainApp(self):    
        
        print("--------------run template matching---------------------------")
        sys.stdout.flush()  
        os.makedirs(self.args.out_dir + "tmResults",exist_ok=True)
        
        numGPU,vram,gpuId=self.get_gpu_info()
        
        print("self.args.gpu_ids"+self.args.gpu_ids)
        if self.args.gpu_ids!="auto":
            print("gpu Id overwirte")
            gpuId=self.args.gpu_ids.split(":")
        print("self.args.gpu_ids"+self.args.gpu_ids)
        
        if self.args.split=="auto":    
            if vram>24: #take volume size into account
                volumeSplit=['2','2','1']
            else:
                volumeSplit=['4','4','2']
        else:
             volumeSplit=self.args.split.split(":")
        
        constParams=["-t",self.args.template,
                     "-d",self.args.out_dir + "tmResults",
                     "-m",self.args.templateMask,
                     "--angular-search",self.args.angularSearch,
                     "--voltage",str(self.st.tsInfo.volt),
                     "--spherical-aberration",str(self.st.tsInfo.cs),
                     "--amplitude-contrast",str(self.st.tsInfo.cAmp),
                     "--tomogram-ctf-model",str('phase-flip'),
                     "--per-tilt-weighting",
                     "--log","debug"]
        constParams.extend(["-g"] + gpuId)
        if self.args.split!="None":
            constParams.extend(["-s"] + volumeSplit)
        
        if bool(strtobool(self.args.spectralWhitening)):            
            constParams.extend(["--spectral-whitening"])
        if bool(strtobool(self.args.randomPhaseCorrection)):            
            constParams.extend(["--random-phase-correction"])
        if bool(strtobool(self.args.nonSphericalMask)):            
            constParams.extend(["--non-spherical-mask"])
        if self.args.bandPassFilter!="None":
            constParams.extend(["--low-pass",str(self.args.bandPassFilter).split(":")[0]])
            constParams.extend(["--high-pass",str(self.args.bandPassFilter).split(":")[1]])
            
            
        if self.args.templateSym!="C1":
            if self.args.templateSym[0]!="C":
                raise("Only C symmetry allowed")
            else:
                constParams.extend(["--z-axis-rotational-symmetry", str(self.args.templateSym[1])])
                
        volumes=self.st.tilt_series_df[[self.args.volumeColumn,"rlnTomoName"]]
        print("starting to match " + str(len(volumes)))
        z=0
        for row in volumes.itertuples():
            z+=1
            volumeName=row[1]
            tomoName=row[2]
            print("  --> processing " + tomoName + ": " + str(z) + " of " + str(len(volumes)) + " tomograms", flush=True)
            command=["pytom_match_template.py", 
                    "-v", volumeName, 
                    "--tilt-angles",self.args.out_dir+"/tiltAngleFiles/"+tomoName+".tlt",
                    ]
            if bool(strtobool(self.args.ctfWeight)):            
                    command.extend(["--defocus",self.args.out_dir+"/defocusFiles/"+tomoName+".txt"])
            if bool(strtobool(self.args.doseWeight)):            
                    command.extend(["--dose-accumulation",self.args.out_dir+"/doseFiles/"+tomoName+".txt",])
           
            command.extend(constParams)
            # command = " ".join(command) + " 2> >(crboost_filterOutputStream.sh >&2)"
            self.result=run_wrapperCommand(command,tag="run_template_matching",relionProj=self.relProj,filterOuputFlag="pytomTM")
    
    def get_gpu_info(self):
        try:
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.total', '--format=csv,noheader,nounits'])
            gpu_info = output.decode('utf-8').strip().split('\n')
            num_gpus = len(gpu_info)
            vram = int(gpu_info[0].split(',')[1])  # Get VRAM from first GPU
            vram = round(vram / 1024, 2)
            gpuID = [str(i) for i in range(num_gpus)]
            cuda_visible_devices = os.environ.get('CUDA_VISIBLE_DEVICES')
            if cuda_visible_devices is not None and cuda_visible_devices != '-1':
                print(" ##CUDA_VISIBLE_DEVICE is set ==> gpu ids accordingly")
                gpuID = cuda_visible_devices.split(',')
            print(f" ##Found {num_gpus} GPUs:")
            print(f" ##Available GPU IDs: {gpuID}")
            print(f" ##VRAM per GPU: {vram} GB")
            return num_gpus, vram, gpuID
        except:
            return 0, 0, []
        
    def generatePytomInputFiles(self,columnName,tag,ext=".txt",fact=1):
        
        outFold=self.args.out_dir + os.path.sep + tag + "Files" + os.path.sep
        os.makedirs(outFold,exist_ok=True)
        tomoNames=self.st.tilt_series_df["rlnTomoName"]
        print("  --> generating " + str(len(tomoNames)) + " " + tag + " Files",end="", flush=True)
        for tomoName in tomoNames:
            OneColumnOneTomo=self.st.all_tilts_df.query("rlnTomoName == @tomoName")[columnName]/fact
            OneColumnOneTomo.to_csv(outFold + tomoName + ext, index=False, header=False)
            print(".", end="",flush=True)
        print("done!")     
    
    
    def updateMetaData(self):
        self.st.writeTiltSeries(self.args.out_dir+"/tomograms.star")    
        
    def checkResults(self):
        #check if important results exists and values are in range
        #set to 1 of something is missing self.result.returncode
        pass        
    
    