
import os,subprocess,shlex,sys
import numpy as np
from src.rw.librw import tiltSeriesMeta,warpMetaData,starFileMeta
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
        
        if os.path.exists(self.preJobFolder + "/mdoc"):
            print("local mdoc folder detected=>proj. filtering")
            mdocFolder=self.preJobFolder + "/mdoc"
            print("new mdoc folder: " + mdocFolder)
            sys.stdout.flush()
        else:
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
        if self.st.tsInfo.keepHand==1:
            command.append("--dont_invert")
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
            if self.args.aretomo_patches!="0x0":
                command.extend(["--patches",str(self.args.aretomo_patches)])
             
            if self.args.refineTiltAxis_iter_and_batch!="0:0":
                tsIter=self.args.refineTiltAxis_iter_and_batch.split(":")[0]
                batchSz=self.args.refineTiltAxis_iter_and_batch.split(":")[1]
                if int(batchSz)>int(self.st.nrTomo):
                    batchSz=self.st.nrTomo
                command.extend(["--axis_iter",str(tsIter)])
                command.extend(["--axis_batch",str(batchSz)])
                #-"--patches",str(args.aretomo_patches),
            #    command.append('--axis_iter 3')
            #    command.append('--axis_batch 5')
           
        else:
            command=["WarpTools", "ts_etomo_patches",
                    "--settings", tsFold + "/" + self.tsSettingsName,
                    "--angpix",str(self.args.rescale_angpixs),
                    "--patch_size",str(self.args.imod_patch_size_and_overlap.split(":")[0]),
                    ]
        
        self.result=run_wrapperCommand(command,tag="run_tsAlignment",relionProj=self.relProj)
        
        
    def updateMetaData(self):
        
        
        multTiltAngle=-1
        self.st.writeTiltSeries(self.args.out_dir+"/aligned_tilt_series.star")
        pixSA=float(self.args.rescale_angpixs)# self.st.tilt_series_df.rlnMicrographOriginalPixelSize[0]
        for stTiltName in self.st.tilt_series_df.rlnTomoTiltSeriesStarFile:
            stTilt=starFileMeta(stTiltName)
            tsID=os.path.basename(stTiltName.replace(".star",""))
            tomoStar=starFileMeta(self.args.out_dir+"/tomostar/"+tsID+".tomostar")
            keysRel = [os.path.basename(path) for path in stTilt.df['rlnMicrographMovieName']]
            if self.args.alignment_program=="Aretomo":
                AreAlnFile=self.args.out_dir+"warp_tiltseries/tiltstack/" + tsID + os.path.sep + tsID + ".st.aln"
                aln=np.loadtxt(AreAlnFile)
                aln = aln[aln[:, 0].argsort()]
                for index, row in tomoStar.df.iterrows():
                    keyTomo=os.path.basename(row['wrpMovieName'])
                    position = keysRel.index(keyTomo)
                    stTilt.df.at[position,'rlnTomoXTilt']=0
                    stTilt.df.at[position,'rlnTomoYTilt']=multTiltAngle*aln[index,9]
                    stTilt.df.at[position,'rlnTomoZRot']=aln[index,1]        
                    stTilt.df.at[position,'rlnTomoXShiftAngst']=aln[index,3]*pixSA
                    stTilt.df.at[position,'rlnTomoYShiftAngst']=aln[index,4]*pixSA
                stTilt.writeStar(self.args.out_dir+"/tilt_series/"+tsID+".star")
            
        stTomo=starFileMeta(self.args.out_dir+"/aligned_tilt_series.star")
        stTomo.df['rlnTomoSizeX']=int(self.args.tomo_dimensions.split("x")[0])
        stTomo.df['rlnTomoSizeY']=int(self.args.tomo_dimensions.split("x")[1])
        stTomo.df['rlnTomoSizeZ']=int(self.args.tomo_dimensions.split("x")[2])
        stTomo.df['rlnTomoTiltSeriesPixelSize']=float(self.st.tilt_series_df.rlnMicrographOriginalPixelSize.iloc[0])
        stTomo.writeStar(self.args.out_dir+"/aligned_tilt_series.star")

        
        # self.st.writeTiltSeries(self.args.out_dir+"/aligned_tilt_series.star")
        # for tsStarName in self.st.tilt_series_df.rlnTomoTiltSeriesStarFile:
        #     tsStar=starFileMeta(tsStarName)
        
        # stTomo=starFileMeta(self.args.out_dir+"/aligned_tilt_series.star")
        # stTomo.df['rlnTomoSizeX']=int(self.args.tomo_dimensions.split("x")[0])
        # stTomo.df['rlnTomoSizeY']=int(self.args.tomo_dimensions.split("x")[1])
        # stTomo.df['rlnTomoSizeZ']=int(self.args.tomo_dimensions.split("x")[2])
        # stTomo.df['rlnTomoTiltSeriesPixelSize']=float(self.st.tilt_series_df.rlnMicrographOriginalPixelSize)
        # stTomo.writeStar(self.args.out_dir+"/aligned_tilt_series.star")
         
    def checkResults(self):
        #check if important results exists and values are in range
        #set to 1 of something is missing self.result.returncode
        pass
    
    # wm=warpMetaData(self.args.out_dir+"/warp_tiltseries/*.xml")
    #     for index, row in self.st.all_tilts_df.iterrows():
    #         key=self.st.all_tilts_df.at[index,'cryoBoostKey']
            #res = wm.data_df.query(f"cryoBoostKey == '{key}'")
            #self.st.all_tilts_df.at[index, 'xxxxxx'] = str(res.iloc[0]['folder']) + "/average/" + key + ".mrc"    