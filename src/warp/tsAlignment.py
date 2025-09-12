
import os,subprocess,shlex,sys
import numpy as np
import pandas as pd
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
        #if self.st.tsInfo.keepHand==1:
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
              
        if (self.args.alignment_program=="Aretomo3"):

            command=["WarpTools", "ts_aretomo3",
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
           
        if (self.args.alignment_program=="Imod"):
            command=["WarpTools", "ts_etomo_patches",
                    "--settings",self.args.out_dir + "/" + self.tsSettingsName,
                    "--angpix",str(self.args.rescale_angpixs),
                    "--patch_size",str(float(self.args.imod_patch_size_and_overlap.split(":")[0])*10),
                    ]
        
        self.result=run_wrapperCommand(command,tag="run_tsAlignment",relionProj=self.relProj)
        
        
    def updateMetaData(self):
        
        
        multTiltAngle=-1
        #self.st.writeTiltSeries(self.args.out_dir+"/aligned_tilt_series.star")
        os.makedirs(self.args.out_dir+"/tilt_series/", exist_ok=True)
        pixSA=float(self.args.rescale_angpixs)# self.st.tilt_series_df.rlnMicrographOriginalPixelSize[0]
        tsIDAlgFaild=[]
        for stTiltName in self.st.tilt_series_df.rlnTomoTiltSeriesStarFile:
            stTilt=starFileMeta(stTiltName)
            tsID=os.path.basename(stTiltName.replace(".star",""))
            tomoStar=starFileMeta(self.args.out_dir+"/tomostar/"+tsID+".tomostar")
            keysRel = [os.path.basename(path) for path in stTilt.df['rlnMicrographMovieName']]
            if self.args.alignment_program=="Aretomo" or self.args.alignment_program=="Aretomo3":
                if self.args.alignment_program=="Aretomo":
                    AreAlnFile=self.args.out_dir+"warp_tiltseries/tiltstack/" + tsID + os.path.sep + tsID + ".st.aln"
                else:
                    AreAlnFile=self.args.out_dir+"warp_tiltseries/tiltstack/" + tsID + os.path.sep + tsID + ".aln"
                aln=self.readAretomoAlgFile(AreAlnFile)
            else:
                ImodXfFile=self.args.out_dir+"warp_tiltseries/tiltstack/" + tsID + os.path.sep + tsID + ".xf"
                ImodTltFile=self.args.out_dir+"warp_tiltseries/tiltstack/" + tsID + os.path.sep + tsID + ".tlt"
                aln=self.readImodXfAndTiltsFile(ImodXfFile,ImodTltFile)
            if aln is None:
                 tsIDAlgFaild.append(tsID)
            else:                        
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
        
        if len(tsIDAlgFaild)==len(self.st.tilt_series_df.rlnTomoTiltSeriesStarFile):
            print("Error: Alignment failed for all tilt series, check log files")
            print("Check:" + self.args.out_dir + "/warp_tiltseries/logs/")
            raise Exception("Alignment failed for all tilt series, check log files ")
        
            
        stTomo=starFileMeta(self.args.in_mics)
        stTomo.df['rlnTomoSizeX']=int(self.args.tomo_dimensions.split("x")[0])
        stTomo.df['rlnTomoSizeY']=int(self.args.tomo_dimensions.split("x")[1])
        stTomo.df['rlnTomoSizeZ']=int(self.args.tomo_dimensions.split("x")[2])
        stTomo.df['rlnTomoTiltSeriesPixelSize']=float(self.st.tilt_series_df.rlnMicrographOriginalPixelSize.iloc[0])
        stTomo.df = stTomo.df[~stTomo.df['rlnTomoName'].isin(tsIDAlgFaild)]
        tsFold = self.args.out_dir + os.path.sep + "tilt_series" + os.path.sep
        stTomo.df = stTomo.df.copy()
        stTomo.df['rlnTomoTiltSeriesStarFile'] = stTomo.df['rlnTomoTiltSeriesStarFile'].apply(lambda x: os.path.join(tsFold, os.path.basename(x)))
        stTomo.dict=None
        stTomo.writeStar(self.args.out_dir+"/aligned_tilt_series.star")

         
    def checkResults(self):
        #check if important results exists and values are in range
        #set to 1 of something is missing self.result.returncode
        pass
    def readAretomoAlgFile(self,AreAlnFile):
        if os.path.exists(AreAlnFile)==False:
            print("Warning: " + AreAlnFile + " not found removing tiltseries from star")
            return None
        data = []
        with open(AreAlnFile, 'r') as file:
            for line in file:
                if line.startswith('# Local Alignment'):
                    break
                if not line.startswith('#'):  # Skip comment lines
                    try:
                        numbers = [float(x) for x in line.split()]
                        if numbers:  # If line contains numbers
                            data.append(numbers)
                    except ValueError:
                        continue
        data = np.array(data)
        return data
    
    def readImodXfAndTiltsFile(self,pathXF,pathTlt):
        if os.path.exists(pathXF)==False:
            print("Warning: " + pathXF + " not found removing tiltseries from star")
            return None
        
        df1 = pd.read_csv(pathXF, delim_whitespace=True, header=None, 
                        names=['m1', 'm2', 'm3', 'm4', 'tx', 'ty'])

        df2 = pd.read_csv(pathTlt, delim_whitespace=True, header=None, 
                        names=['tilt_angle'])

        combined = pd.concat([df1, df2], axis=1)

        results_x = []
        results_y = []
        titlAng = []
        for index, row in combined.iterrows():
            M = np.array([[row['m1'], row['m2']],
                        [row['m3'], row['m4']]])
            M = np.linalg.inv(M)
            v = np.array([row['tx'], row['ty']])
            v*=-1
            result = np.dot(M, v)
            angle = np.degrees(np.arctan2(M[1,0], M[0,0]))
            results_x.append(result[0])
            results_y.append(result[1])
            titlAng.append(angle)
        combined['Vrot_x'] = results_x
        combined['Vrot_Y'] = results_y
        dataNpArray = np.zeros((index+1,10))
        dataNpArray[:,0] = np.arange(0,index+1)
        dataNpArray[:,1] = titlAng
        dataNpArray[:,3] = results_x
        dataNpArray[:,4]= results_y
        dataNpArray[:,9]= combined['tilt_angle']
        return dataNpArray
    
    # wm=warpMetaData(self.args.out_dir+"/warp_tiltseries/*.xml")
    #     for index, row in self.st.all_tilts_df.iterrows():
    #         key=self.st.all_tilts_df.at[index,'cryoBoostKey']
            #res = wm.data_df.query(f"cryoBoostKey == '{key}'")
            #self.st.all_tilts_df.at[index, 'xxxxxx'] = str(res.iloc[0]['folder']) + "/average/" + key + ".mrc"    