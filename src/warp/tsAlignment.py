
import os,subprocess,shlex,sys
from src.rw.librw import tiltSeriesMeta,warpMetaData
from src.misc.system import run_wrapperCommand
from src.warp.libWarp import warpWrapperBase

class tsAlignment(warpWrapperBase):
    def __init__(self,args,runFlag=None):
       
        super().__init__(args,runFlag=runFlag)
            
        
    def createSettings(self):
        print("--------------create settings---------------------------")
        sys.stdout.flush()  
        
        command=["WarpTools", "create_settings",
                "--folder_data", self.tomoStarFolderName,
                "--extension" ,"*"+self.tomoStarExt,
                "--folder_processing", self.tsFolderName,
                "--output" , self.args.out_dir + "/" + self.tsSettingsName,
                "--angpix" , str(self.st.tsInfo.framePixS),
                "--exposure",str(self.st.tsInfo.expPerTilt),
                "--tomo_dimensions",self.args.tomo_dimensions,
                ]
        command=self.addGainStringToCommand(self.args,command)
        self.result=run_wrapperCommand(command,tag="tsAlignment-Settings",relionProj=self.relProj)
        
        print("--------------import tiltseries---------------------------")
        sys.stdout.flush()  
        self.importTiltSeries()
      
    def importTiltSeries(self):
        
        dataFold=self.args.out_dir +"/" + self.tomoStarFolderName
        print("generating: ",dataFold)
        sys.stdout.flush()
        os.makedirs(dataFold,exist_ok=True) 
        
        mdocFolder,mdocPattern = os.path.split(self.args.mdocWk)
        mdocPattern="*.mdoc"

        command=["WarpTools", "ts_import",
                    "--mdocs",mdocFolder,
                    "--pattern",mdocPattern,
                    "--frameseries",self.st.tsInfo.warpFrameSeriesFold,
                    "--output" ,dataFold,
                    "--tilt_exposure",str(self.st.tsInfo.expPerTilt), 
                    "--override_axis",str(self.st.tsInfo.tiltAxis),
                ]
        self.result=run_wrapperCommand(command,tag="tsAlignment-ImportTs",relionProj=self.relProj)
            
    def runMainApp(self):    
        
        print("--------------tilt series alignment---------------------------")
        sys.stdout.flush()  
        
        tsFold=self.args.out_dir + "/warp_tiltseries"
        print("generating: ",tsFold)
        sys.stdout.flush()
        os.makedirs(tsFold,exist_ok=True) 
        if (self.args.alignment_program=="Aretomo"):
    
            command=["WarpTools", "ts_aretomo",
                    "--settings",self.args.out_dir+"/"+ self.tsSettingsName,
                    "--angpix",str(self.args.rescale_angpixs),
                    "--alignz",str(int(float(self.args.aretomo_sample_thickness)*10)),
                    "--perdevice",str(self.args.perdevice),
                    ]
            #if args.refine_tilt_axis:
                #-"--patches",str(args.aretomo_patches),
            #    command.append('--axis_iter 3')
            #    command.append('--axis_batch 5')
        else:
            command=["WarpTools", "ts_etomo_patches",
                    "--settings", tsFold + "/" + self.tsSettingsName,
                    "--angpix",str(self.args.rescale_angpixs),
                    ]
        
        self.result=run_wrapperCommand(command,tag="run_tsAlignment",relionProj=self.relProj)
        
        
    def updateMetaData(self):
        wm=warpMetaData(self.args.out_dir+"/warp_tiltseries/*.xml")
        for index, row in self.st.all_tilts_df.iterrows():
            key=self.st.all_tilts_df.at[index,'cryoBoostKey']
            #res = wm.data_df.query(f"cryoBoostKey == '{key}'")
            #self.st.all_tilts_df.at[index, 'xxxxxx'] = str(res.iloc[0]['folder']) + "/average/" + key + ".mrc"
        self.st.writeTiltSeries(self.args.out_dir+"/aligned_tilt_series.star")    
        
         
    def checkResults(self):
        #check if important results exists and values are in range
        #set to 1 of something is missing self.result.returncode
        pass
        