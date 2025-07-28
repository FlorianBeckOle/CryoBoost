from src.rw.librw import tiltSeriesMeta
from src.rw.librw import mdocMeta
import numpy as np
import os,shutil,copy

#TODO This has to an object !


def filterTitls(tilseriesStar,relionProj='',pramRuleFilter=None,model=None,plot=None,outputFolder=None,probThr=0.1,probAction="assingToGood",threads=24,mdocWk=None):
    ts=tiltSeriesMeta(tilseriesStar,relionProj)
    lenUnfilterd=len(ts.all_tilts_df)
    
    if os.path.exists(outputFolder+"tiltseries_labeled.star"):
         tsExist=tiltSeriesMeta(outputFolder+"tiltseries_labeled.star")
         ts.reduceToNonOverlab(tsExist)
         if len(ts.tilt_series_df)==0:
             return
         print(ts.tilt_series_df.rlnTomoName)
    
    #plotTiltStat(ts,outputFolder)
    threads=int(threads)
    if pramRuleFilter!=None:
        from src.filterTilts.filterTiltsRule import filterTiltsRule
        ts=filterTiltsRule(ts,pramRuleFilter,plot)

    if model!=None:
        from src.filterTilts.filterTiltsDL import filterTiltsDL
        ts=filterTiltsDL(ts,model,'binary',outputFolder,plot,probThr,probAction,threads)
    
    if os.path.exists(outputFolder+"tiltseries_labeled.star"):
        tsExist.mergeTiltSeries(ts)
        ts=tsExist
    meanProb=ts.all_tilts_df.cryoBoostDlProbability.mean()
    meanAngBad=ts.all_tilts_df[ts.all_tilts_df.cryoBoostDlLabel == "bad"].rlnTomoNominalStageTiltAngle.abs().mean()
    bad_count = (ts.all_tilts_df.cryoBoostDlLabel == "bad").sum()
    meanAngGood=ts.all_tilts_df[ts.all_tilts_df.cryoBoostDlLabel == "good"].rlnTomoNominalStageTiltAngle.abs().mean()
    if np.isnan(meanAngBad):
        meanAngBad=float(180)
    badFract=round((bad_count/lenUnfilterd)*100,1)
        
    ts.writeTiltSeries(outputFolder+"tiltseries_labeled.star","tilt_seriesLabel")
    
    filterParams = {"cryoBoostDlLabel": ("good")}
    ts.filterTilts(filterParams)
    ts.writeTiltSeries(outputFolder+"tiltseries_filtered.star")
    preExpFolder=os.path.dirname(tilseriesStar)
    
    if os.path.exists(preExpFolder+"/warp_frameseries.settings"):
        print("Warp frame alignment detected ...getting data from: " + preExpFolder)
        getDataFromPreExperiment(preExpFolder,outputFolder)
        os.makedirs(outputFolder+"/mdoc", exist_ok=True)    
        if (len(ts.tilt_series_df)>0):
            print("  filtering mdocs: " + mdocWk)
            mdocWk=os.path.dirname(mdocWk) + os.path.sep + "*.mdoc"
            mdoc=mdocMeta(mdocWk)
            mdoc.filterByTiltSeriesStarFile(outputFolder+"tiltseries_filtered.star")
            print("  filtered mdoc has " + str(len(mdoc.all_df)) + " tilts")
            mdoc.writeAllMdoc(outputFolder+"/mdoc")    
        else:
            badFract=100
            print("All tilts are bad, no output written")
            print("Maual sortinign will be started")

    if (meanProb<0.95) or (meanAngGood>(meanAngBad-2)) or (badFract>50):
        print("WARNINIG data out of distribution you should sort manual")
        with open(outputFolder+'DATA_OUT_OF_DISTRIBUTION', 'w') as f:
            pass
    else:
        print("Removal of bad tilts successful")
        with open(outputFolder+'DATA_IN_DISTRIBUTION', 'w') as f:
            pass
            
    print("  Average Prediction Probability: " + str(round(meanProb,2)) + " (should be > 0.95)")
    print("  Percentage of bad tilts: " + str(badFract) + "%")
    meanAngBad="n.d" if int(meanAngBad) == 180 else str(round(meanAngBad,1))
    print("  Mean Angle of good tilts: " + str(round(meanAngGood,1)) + " Mean Angle of bad tilts: " + meanAngBad)
        


    
def getDataFromPreExperiment(sourceFolder,targetFolder):
    fsFolderSource=os.path.abspath(sourceFolder+os.path.sep+"warp_frameseries")
    fsFolderTarget=os.path.abspath(targetFolder+os.path.sep+"warp_frameseries")
    if os.path.exists(fsFolderTarget):
        print(fsFolderTarget+" already exists")
    else:
        print(" generating symlink:")
        print("   ln -s "+ fsFolderSource+ " " +  fsFolderTarget)
        os.symlink(fsFolderSource,fsFolderTarget)
    fsSettingsSource=sourceFolder+os.path.sep+"warp_frameseries.settings"
    fsSettingsTarget=targetFolder+os.path.sep+"warp_frameseries.settings"
    print(" copy settings file")
    print("   cp "+ fsSettingsSource + " " + fsSettingsTarget)
    shutil.copyfile(fsSettingsSource,fsSettingsTarget)
    
    
def plotTiltStat(ts,outputFolder,plot=None):
    import matplotlib.pyplot as plt
    import os
    if (plot==None):
        return
    #dummy plot replaced by michael's code
    ts.all_tilts_df.reset_index().plot(kind='scatter', x='rlnTomoNominalStageTiltAngle', y='rlnCtfMaxResolution', title='Scatter Plot using Pandas')
    plt.savefig(outputFolder+ os.path.sep +'tiltseriesStatistic.pdf')
    pass
    
    
def plotFilterTiltsResults(ts,outputFolder,classLabelName=None,predScoreLabelName=None,titlNameLabel=None,plot=False,threads=24):
    
    if (plot==False):
        return
    
    from src.deepLearning.predictTilts_Binary import mrcFilesToPilImageStackParallel
    print("generting:" + outputFolder + "/logfile.pdf")
       
    
    pred_lables=ts.all_tilts_df[classLabelName]
    if (predScoreLabelName is not None):
        pred_probs=ts.all_tilts_df.cryoBoostDlProbability
    
    
    if (titlNameLabel is not None):
        pred_Name=ts.all_tilts_df[titlNameLabel]    
    
    titlspath=ts.getMicrographMovieNameFull()
   
    from matplotlib import pyplot as plt
    import numpy as np
    maxRows=100
    num_images = len(pred_lables)
    num_cols = 4  # Number of columns in the matrix
    num_rows = (num_images // num_cols)  # Calculate number of rows needed
    if (num_rows>maxRows):
        num_rows=maxRows
    
    print("plotting " + str(num_rows) )
    titlspathCut=titlspath[0:(maxRows*num_cols)]
    pil_images=mrcFilesToPilImageStackParallel(titlspathCut,128,threads,ignoreNonSquare=1)
   
    fig, axs = plt.subplots(num_rows, num_cols, figsize=(20, 5*num_rows))
    perm = np.random.permutation(num_images)
    for i, ax in enumerate(axs.flat):
        if i < num_images:
            try:
                ind=i ##ind=perm[i]
                img = pil_images[ind]
                ax.imshow(img,cmap='gray')
                if (predScoreLabelName is not None and  titlNameLabel is not None):
                    axTitleStr=f'{pred_Name[ind]}\n Pred: {pred_lables[ind]}, Prob: {pred_probs[ind]:.2f}'
                if (predScoreLabelName is not None and titlNameLabel is None):
                    axTitleStr=f'Pred: {pred_lables[ind]}, Prob: {pred_probs[ind]:.2f}'
                if (predScoreLabelName is None and titlNameLabel is None):
                    axTitleStr=f'Pred: {pred_lables[ind]}'    
                
                ax.set_title(axTitleStr,fontsize=9) 
                
                img_size = img.shape[-2:]  
                rect_width = img_size[1] * 0.98  
                rect_height = img_size[0] * 0.98
                rect_x = (img_size[1] - rect_width) / 2  
                rect_y = (img_size[0] - rect_height) / 2 
                
                if pred_lables[ind] == 'good':
                    color = 'g'  # Green for correct prediction
                else:
                    color = 'r'  # Red for incorrect prediction """
                rect = plt.Rectangle((rect_x, rect_y), rect_width, rect_height, linewidth=5, edgecolor=color, facecolor='none')
                ax.add_patch(rect)
                ax.axis('off')
            except Exception as exc:
                print("error: skipping img:"+titlspath[ind])
                print(exc)    

        else:
            ax.axis('off')  # Hide empty subplots
    plt.tight_layout()
    fig.savefig(f'{outputFolder}/logfile.pdf')
    #plt.show()   
    


