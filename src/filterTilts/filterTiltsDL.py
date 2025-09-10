import os
from src.filterTilts.libFilterTilts import plotFilterTiltsResults

def filterTiltsDL(ts,model,clmethod,outputFolder,plot=None,probThr=0.1,probAction="assingToGood",threads=24):
    
    if (clmethod=="binary"):
        from src.deepLearning.predictTilts_Binary import predict_tilts
        if (model=="default"):
            model=os.getenv("CRYOBOOST_HOME")+"/data/models/michaelNet_0.5/model.pkl"
        pngOut=outputFolder+os.path.sep +"png/"
        print("generating pngs from manual sorting " + pngOut)
        os.makedirs(pngOut, exist_ok=True)
        ts=predict_tilts(ts,model,batchSize=60,gpu=0,probThr=probThr,probAction=probAction,max_workers=threads,pngOutPutPath=pngOut)
        
    if (clmethod=="oneclass"):    
        assert("not implemented yet")
    
    try:
        plotFilterTiltsResults(ts,outputFolder,classLabelName="cryoBoostDlLabel",predScoreLabelName="cryoBoostDlProbability",titlNameLabel="cryoBoostKey",plot=1,threads=threads)
    except Exception as exc:
        print("error plotting filter tilts result")
        print(exc)
    
   
    
    return ts


