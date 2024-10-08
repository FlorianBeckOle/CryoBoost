from src.rw.librw import starFileMeta,tiltSeriesMeta
from src.rw.librw import warpMetaData
import shlex,os,subprocess,select,sys,threading
import shutil,glob

def read_stream(stream, callback):
    print("above loop")
    while True:
        #print("reading stream")
        output = stream.read()
        if output:
            #callback(output.replace('\r', '\n'))
            callback(output)
        else:
            print("breaking")
            break

def tsReconstruct(args):
    relProj=os.path.dirname(os.path.dirname(os.path.dirname(args.in_mics)))
    if relProj != "" and relProj is not None:
        relProj=relProj+"/"
    st=tiltSeriesMeta(args.in_mics,relProj)
    outputFolder=args.out_dir    
    warpTiltSeriesFoldSource=os.path.split(args.in_mics)[0]+"/warp_tiltseries"
    warpTiltSeriesFoldTarget=outputFolder+"/warp_tiltseries"
    
    print("generating: ",warpTiltSeriesFoldTarget)
    os.makedirs(warpTiltSeriesFoldTarget,exist_ok=True) 
    print("copying data: ",warpTiltSeriesFoldSource + "/*.xml to" + warpTiltSeriesFoldTarget)
    for f in glob.glob(warpTiltSeriesFoldSource + "/*.xml"):
        shutil.copy(f,warpTiltSeriesFoldTarget)
    print("copying data: ", os.path.split(args.in_mics)[0] + "/warp_tiltseries.settings to " + warpTiltSeriesFoldTarget)
    shutil.copy(os.path.split(args.in_mics)[0] + "/warp_tiltseries.settings",outputFolder)
    print("copying data: ", os.path.split(args.in_mics)[0] + "/tomostar to " + outputFolder)
    shutil.copytree(os.path.split(args.in_mics)[0] + "/tomostar",outputFolder+"/tomostar",dirs_exist_ok=True)

    # command=["WarpTools", "ts_reconstruct",
    #         "--settings", outputFolder + "/warp_tiltseries.settings",
    #         "--angpix" ,str(args.rescale_angpixs),
    #         "--halfmap_frames" ,str(args.halfmap_frames),
    #         "--deconv" ,str(args.deconv),
    #         "--perdevice",str(args.perdevice),
    #         ]
    
    command=["WarpTools", "ts_reconstruct",
            "--settings", outputFolder + "/warp_tiltseries.settings",
            "--angpix" ,str(args.rescale_angpixs),
            "--halfmap_frames" ,str(args.halfmap_frames),
            "--deconv" ,str(args.deconv),
            "--perdevice" ,str(args.perdevice),
            ]
    
    
    command_string = shlex.join(command)
    print(command_string)  

    try:
        #print("launching via subprocess")
        result = subprocess.run(command, check=True) #,capture_output=True, text=True) #, capture_output=True, text=True)          
    except subprocess.CalledProcessError as e:
        print("Error output:", e.stderr, file=sys.stderr)
        
    
    if result.returncode == 0:
        #adapt values here
        print("transfer from tsReconstruct still missing...not needed to proceed in warp")
        for index, row in st.all_tilts_df.iterrows():
            key=st.all_tilts_df.at[index,'cryoBoostKey']
            #st.all_tilts_df.at[index, 'cryoBoostXfPath'] = str(res.iloc[0]['folder']) + "/average/" + key + ".mrc" 
            # st.all_tilts_df.at[index, '_rlnTomoXTilt']= 
            # _rlnTomoYTilt #26
            # _rlnTomoZRot #27
            # _rlnTomoXShiftAngst #28
            # _rlnTomoYShiftAngst #29
        st.writeTiltSeries(outputFolder+"/tomograms.star")
        return 0
    else:
        return 1        





def tsCtf(args):
    relProj=os.path.dirname(os.path.dirname(os.path.dirname(args.in_mics)))
    if relProj != "" and relProj is not None:
        relProj=relProj+"/"
    st=tiltSeriesMeta(args.in_mics,relProj)
    framePixS=st.all_tilts_df["rlnMicrographOriginalPixelSize"][0]
    tiltAxis=st.all_tilts_df["rlnTomoNominalTiltAxisAngle"][0]
    volt=st.tilt_series_df.rlnVoltage[0]
    cs=st.tilt_series_df.rlnSphericalAberration[0]
    cAmp=st.tilt_series_df.rlnAmplitudeContrast[0]  
    outputFolder=args.out_dir    
    dataFold=outputFolder+"/tomostar"
    expPerTilt=st.all_tilts_df["rlnMicrographPreExposure"].sort_values().iloc[1]
    warpTiltSeriesFoldSource=os.path.split(args.in_mics)[0]+"/warp_tiltseries"
    warpTiltSeriesFoldTarget=outputFolder+"/warp_tiltseries"
    nrTilt=st.tilt_series_df.shape[0]
    if (int(args.auto_hand)>int(nrTilt)):
        nrAutoHand=nrTilt
    else:
        nrAutoHand=int(args.auto_hand)
    nrAutoHand=1
        
    print("generating: ",warpTiltSeriesFoldTarget)
    os.makedirs(warpTiltSeriesFoldTarget,exist_ok=True) 
    print("copying data: ",warpTiltSeriesFoldSource + "/*.xml to" + warpTiltSeriesFoldTarget)
    for f in glob.glob(warpTiltSeriesFoldSource + "/*.xml"):
        shutil.copy(f,warpTiltSeriesFoldTarget)
    print("copying data: ", os.path.split(args.in_mics)[0] + "/warp_tiltseries.settings to " + warpTiltSeriesFoldTarget)
    shutil.copy(os.path.split(args.in_mics)[0] + "/warp_tiltseries.settings",outputFolder)
    print("copying data: ", os.path.split(args.in_mics)[0] + "/tomostar to " + outputFolder)
    shutil.copytree(os.path.split(args.in_mics)[0] + "/tomostar",outputFolder+"/tomostar",dirs_exist_ok=True)
    # command=["WarpTools", "ts_ctf",
    #          "--settings", outputFolder + "/warp_tiltseries.settings",
    #          "--range_high","6",
    #          "--defocus_max", "8"]
    
    command=["WarpTools", "ts_ctf",
            "--settings", outputFolder + "/warp_tiltseries.settings",
            "--window" ,str(args.window),
            "--range_low" ,args.range_min_max.split(":")[0],
            "--range_high" ,args.range_min_max.split(":")[1],
            "--defocus_min" ,args.defocus_min_max.split(":")[0],
            "--defocus_max" ,args.defocus_min_max.split(":")[1],
            "--voltage" ,str(round(volt)),
            "--cs" ,str(cs),
            "--amplitude" ,str(cAmp),
            "--perdevice",str(args.perdevice),
            #"--auto_hand" ,str(nrAutoHand),
            ]
    
    command_string = shlex.join(command)
    print(command_string)  
    #os.system(command_string)
    
    try:
        #print("launching via subprocess")
        result = subprocess.run(command, check=True) #,capture_output=True, text=True) #, capture_output=True, text=True)          
    except subprocess.CalledProcessError as e:
        print("Error output:", e.stderr, file=sys.stderr)
        
    
    if result.returncode == 0:
        #adapt values here
        print("transfer from tsCTF still missing...not needed to proceed in warp")
        for index, row in st.all_tilts_df.iterrows():
            key=st.all_tilts_df.at[index,'cryoBoostKey']
            #st.all_tilts_df.at[index, 'cryoBoostXfPath'] = str(res.iloc[0]['folder']) + "/average/" + key + ".mrc" 
            # st.all_tilts_df.at[index, '_rlnTomoXTilt']= 
            # _rlnTomoYTilt #26
            # _rlnTomoZRot #27
            # _rlnTomoXShiftAngst #28
            # _rlnTomoYShiftAngst #29
        st.writeTiltSeries(outputFolder+"/ts_ctf_tilt_series.star")
        return 0
    else:
        return 1        
    

def tsAlignment(args):
    relProj=os.path.dirname(os.path.dirname(os.path.dirname(args.in_mics)))
    if relProj != "" and relProj is not None:
        relProj=relProj+"/"
    st=tiltSeriesMeta(args.in_mics,relProj)
    framePixS=st.all_tilts_df["rlnMicrographOriginalPixelSize"][0]
    tiltAxis=st.all_tilts_df["rlnTomoNominalTiltAxisAngle"][0]
    outputFolder=args.out_dir    
    dataFold=outputFolder+"/tomostar"
    expPerTilt=st.all_tilts_df["rlnMicrographPreExposure"].drop_duplicates().sort_values().iloc[1]
    warpFrameSeriesFold=st.all_tilts_df["rlnMicrographName"].sort_values().iloc[0]
    warpFrameSeriesFold=os.path.split(warpFrameSeriesFold)[0].replace("average","")
    
    print("generating: ",dataFold)
    os.makedirs(dataFold,exist_ok=True) 
    
    command=["WarpTools", "create_settings",
             "--folder_data", "tomostar",
             "--extension" ,"*.tomostar",
             "--folder_processing", "warp_tiltseries",
             "--output" , outputFolder + "/warp_tiltseries.settings",
             "--angpix" , str(framePixS),
             "--exposure",str(expPerTilt),
             "--tomo_dimensions",args.tomo_dimensions,
             ]
    if args.gain_path!="None":
        command.extend(["--gain_path",args.gain_path])
    
    if args.gain_operations is not None:
        if args.gain_operations.find("flip_x") != -1:
            command.append("--gain_flip_x")
        if args.gain_operations.find("flip_y") != -1:
            command.append("--gain_flip_y")
        if args.gain_operations.find("gain_transpose") != -1:
            command.append("--gain_gain_transpose")
    command_string = shlex.join(command)
    print(command_string)  
    try:
        result = subprocess.run(command, check=True) #, capture_output=True, text=True)          
    except subprocess.CalledProcessError as e:
        print("Error output:", e.stderr, file=sys.stderr)
    
    print("++++++++++settings done++++++++++++++++")
    print("modoc pattern:",args.mdocWk)
    mdocFolder,mdocPattern = os.path.split(args.mdocWk)
    mdocPattern="*.mdoc"
    
    command=["WarpTools", "ts_import",
             "--mdocs",mdocFolder,
             "--pattern",mdocPattern,
             "--frameseries",warpFrameSeriesFold,
             "--output" ,dataFold,
             "--tilt_exposure",str(expPerTilt), 
             "--override_axis",str(tiltAxis),
            ]
    
    command_string = shlex.join(command)
    print(command_string)  
    try:
        result = subprocess.run(command, check=True) #, capture_output=True, text=True)          
    except subprocess.CalledProcessError as e:
        print("Error output:", e.stderr, file=sys.stderr) 
    
    print("generating: ",outputFolder + "/warp_tiltseries")
    os.makedirs(outputFolder + "/warp_tiltseries",exist_ok=True) 
    print("++++++++++Tiltseries import done++++++++++++++++")
    
    if (args.alignment_program=="Aretomo"):
    
        command=["WarpTools", "ts_aretomo",
                "--settings", outputFolder + "/warp_tiltseries.settings",
                "--angpix",str(args.rescale_angpixs),
                "--alignz",str(int(float(args.aretomo_sample_thickness)*10)),
                "--perdevice",str(args.perdevice),
                ]
        #if args.refine_tilt_axis:
            #-"--patches",str(args.aretomo_patches),
        #    command.append('--axis_iter 3')
        #    command.append('--axis_batch 5')
        
    else:
        command=["WarpTools", "ts_etomo_patches",
                "--settings", outputFolder + "/warp_tiltseries.settings",
                "--angpix",str(args.rescale_angpixs),
                ]
    command_string = shlex.join(command)
    print(command_string)  
    try:
        result = subprocess.run(command, check=True) #, capture_output=True, text=True)          
    except subprocess.CalledProcessError as e:
        print("Error output:", e.stderr, file=sys.stderr)     
    
    if result.returncode == 0:
        #adapt values here
        print("transfer from xf still missing ...not needed to proceed in warp")
        for index, row in st.all_tilts_df.iterrows():
            key=st.all_tilts_df.at[index,'cryoBoostKey']
            #st.all_tilts_df.at[index, 'cryoBoostXfPath'] = str(res.iloc[0]['folder']) + "/average/" + key + ".mrc" 
            # st.all_tilts_df.at[index, '_rlnTomoXTilt']= 
            # _rlnTomoYTilt #26
            # _rlnTomoZRot #27
            # _rlnTomoXShiftAngst #28
            # _rlnTomoYShiftAngst #29
        st.writeTiltSeries(outputFolder+"/aligned_tilt_series.star")
        
        return 0
    else:
        return 1        
               

def fsMotionAndCtf(args):
    
    
    relProj=os.path.dirname(os.path.dirname(os.path.dirname(args.in_mics)))
    if relProj != "" and relProj is not None:
        relProj=relProj+"/"
    st=tiltSeriesMeta(args.in_mics,relProj)
    frameFold="../../"+os.path.dirname(st.all_tilts_df["rlnMicrographMovieName"][0])
    _,frameExt=os.path.splitext(st.all_tilts_df["rlnMicrographMovieName"][0])
    frameExt="*"+frameExt
    framePixS=st.all_tilts_df["rlnMicrographOriginalPixelSize"][0]
    volt=st.tilt_series_df.rlnVoltage[0]
    cs=st.tilt_series_df.rlnSphericalAberration[0]
    cAmp=st.tilt_series_df.rlnAmplitudeContrast[0]    

    
    outputFolder=args.out_dir    
    
    command=["WarpTools", "create_settings",
             "--folder_data", frameFold,
             "--extension" ,frameExt,
             "--folder_processing", "warp_frameseries",
             "--output" , outputFolder + "/warp_frameseries.settings",
             "--angpix" , str(framePixS)
             ]
    if frameExt=="*.eer":
        command.extend(["--eer_ngroups", str(args.eer_ngroups)])
    
    if args.gain_path!="None":
        command.extend(["--gain_path",args.gain_path])
    
    if args.gain_operations is not None:
        if args.gain_operations.find("flip_x") != -1:
            command.append("--gain_flip_x")
        if args.gain_operations.find("flip_y") != -1:
            command.append("--gain_flip_y")
        if args.gain_operations.find("gain_transpose") != -1:
            command.append("--gain_gain_transpose")
        
    command_string = shlex.join(command)
    print(command_string)  
    try:
        result = subprocess.run(command, check=True) #, capture_output=True, text=True)          
    except subprocess.CalledProcessError as e:
        print("Error output:", e.stderr, file=sys.stderr)
    
    
    print("generating: ",outputFolder + "/warp_frameseries")
    os.makedirs(outputFolder + "/warp_frameseries",exist_ok=True)
    
    command=["WarpTools", "fs_motion_and_ctf",
             "--settings", outputFolder + "/warp_frameseries.settings",
             "--m_grid" ,args.m_grid,
             "--m_range_min" ,args.m_range_min_max.split(":")[0],
             "--m_range_max" ,args.m_range_min_max.split(":")[1],
             "--m_bfac" ,str(args.m_bfac),
             "--c_grid",args.c_grid,
             "--c_window" ,str(args.c_window),
             "--c_range_min" ,args.c_range_min_max.split(":")[0],
             "--c_range_max" ,args.c_range_min_max.split(":")[1],
             "--c_defocus_min" ,args.c_defocus_min_max.split(":")[0],
             "--c_defocus_max" ,args.c_defocus_min_max.split(":")[1],
             "--c_voltage" ,str(round(volt)),
             "--c_cs" ,str(cs),
             "--c_amplitude" ,str(cAmp),
             "--out_averages",
             "--out_skip_first", str(args.out_skip_first),
             "--out_skip_last", str(args.out_skip_last),
             "--perdevice", str(args.perdevice),
             ]
    
    if args.out_average_halves!=False:
        command.append("--out_average_halves")
    
    if args.c_use_sum!=False:
        command.append("--c_use_sum")
    
    command_string = shlex.join(command)
    print(command_string)
    
    try:
        result = subprocess.run(command, check=True)#, capture_output=True, text=True)
    except:
        print("Error output:", e.stderr, file=sys.stderr)
    
    if result.returncode == 0:
        wm=warpMetaData(outputFolder+"/warp_frameseries/*.xml")
        for index, row in st.all_tilts_df.iterrows():
            key=st.all_tilts_df.at[index,'cryoBoostKey']
            res = wm.data_df.query(f"cryoBoostKey == '{key}'")
            st.all_tilts_df.at[index, 'rlnMicrographName'] = str(res.iloc[0]['folder']) + "/average/" + key + ".mrc"
            st.all_tilts_df.at[index, 'rlnMicrographNameEven'] = str(res.iloc[0]['folder']) + "/average/even/" + key + ".mrc"
            st.all_tilts_df.at[index, 'rlnMicrographNameOdd'] = str(res.iloc[0]['folder']) + "/average/odd/" + key + ".mrc"
            st.all_tilts_df.at[index, 'rlnMicrographMetadata']="None"
            st.all_tilts_df.at[index, 'rlnAccumMotionTotal']=-1
            st.all_tilts_df.at[index, 'rlnAccumMotionEarly']=-1
            st.all_tilts_df.at[index, 'rlnAccumMotionLate']=-1
            st.all_tilts_df.at[index, 'rlnCtfImage'] = str(res.iloc[0]['folder']) + "/powerspectrum/" + key + ".mrc"
            st.all_tilts_df.at[index, 'rlnDefocusU'] = str(res.iloc[0]['defocus_value']) 
            st.all_tilts_df.at[index, 'rlnDefocusV'] = str(res.iloc[0]['defocus_value'])
            st.all_tilts_df.at[index, 'rlnCtfAstigmatism'] = str(res.iloc[0]['defocus_delta'])
            st.all_tilts_df.at[index, 'rlnDefocusAngle'] = str(res.iloc[0]['defocus_angle'])
            st.all_tilts_df.at[index, 'rlnCtfFigureOfMerit']="None"
            st.all_tilts_df.at[index, 'rlnCtfMaxResolution']="None"
            st.all_tilts_df.at[index, 'rlnMicrographMetadata']="None"
        st.writeTiltSeries(outputFolder+"/fs_motion_and_ctf.star")
        return 0
    else:
        return 1
    