from src.filterTilts.filterTiltsDL import filterTiltsDL
from src.filterTilts.filterTiltsRule import filterTiltsRule
from src.filterTilts.libFilterTilts import filterTitls
from src.filterTilts.libFilterTilts import plotFilterTiltsResults
from starfile import read as starread
from src.rw.librw import tiltSeriesMeta
import pandas as pd
import subprocess
import os
import pytest


def idfn(test_input,context):
    
    if (isinstance(test_input, dict)):
        key=list(test_input.keys())[0]
        value = str(test_input[key])
    else:
        key=""
        value = str(test_input)
   
    return f"{context['function_name']} {key}-{value}"


def test_fitlerTiltsDL_binaryWithModel():
    
    tilseriesStar="data/tilts/tilt_series_ctf.star"
    relionProj=os.path.abspath(__file__)
    relionProj=os.path.dirname(os.path.dirname(os.path.dirname(relionProj)))+os.path.sep
    model="data/models/michaelNet_0.6/model.pth"
    
    ts=tiltSeriesMeta(tilseriesStar,relionProj)
    ts=filterTiltsDL(ts,model,'binary','data/tmp/')
    filterParams = {"cryoBoostDlLabel": ("good")}
    ts.filterTilts(filterParams)
    
    assert (ts.all_tilts_df.cryoBoostTestLabel=="good").all()
    
def test_plotFitlerTilts():
    
    outputFold="tmpOut/testPlotFilterTilts"
    os.makedirs("tmpOut", exist_ok=True)
    os.makedirs(outputFold, exist_ok=True)
    inputTs="data/tilts/tilt_series_ctf.star"
    ts=tiltSeriesMeta(inputTs)
   
    if (os.path.exists(outputFold+"/logfile.pdf")):
        os.remove(outputFold+"/logfile.pdf")
    
    plotFilterTiltsResults(ts,outputFold,classLabelName="cryoBoostTestLabel",predScoreLabelName=None,plot=1)
    
    assert os.path.exists(outputFold+"/logfile.pdf")        

@pytest.mark.parametrize("test_input", 
                         [({"rlnCtfMaxResolution": (1,20,-70,70)}), 
                          ({"rlnDefocusU": (1,50000,-70,70)}), 
                          ({"rlnAccumMotionTotal": (1,10,-70,70)})],
                           ids=lambda val: idfn(val, {'function_name': 'filterTiltsRule'}))
@pytest.mark.filterTiltsRule
def test_filterTiltsRule(test_input):
    
    tilseriesStar="data/tilts/tilt_series_ctf.star"
    relionProj=os.path.abspath(__file__)
    relionProj=os.path.dirname(os.path.dirname(os.path.dirname(relionProj)))+os.path.sep
    filterParams = test_input
    
    os.makedirs("tmpOut", exist_ok=True)
    ts=tiltSeriesMeta(tilseriesStar,relionProj)
    ts=filterTiltsRule(ts,filterParams,'tmpOut')
    assert (ts.all_tilts_df.cryoBoostTestLabel=="good").all()
  
    
@pytest.mark.parametrize("test_input", 
                         [({"rlnCtfMaxResolution": (1,20,-70,70)}), 
                          ({"rlnDefocusU": (1,50000,-70,70)}), 
                          ({"rlnAccumMotionTotal": (1,10,-70,70)}), 
                          ({"model": "default"})],
                           ids=lambda val: idfn(val, {'function_name': 'filterTilts'}))
@pytest.mark.filter_tests
def test_fitlerTilts(test_input):
    
    tilseriesStar="data/tilts/tilt_series_ctf.star"
    relionProj=os.path.abspath(__file__)
    relionProj=os.path.dirname(os.path.dirname(os.path.dirname(relionProj)))+os.path.sep
    outputFold=relionProj+"tmpOut/"
    filterParams = test_input
    inpModel=None
    inpF=None
    plot=None   
    
    os.makedirs("tmpOut", exist_ok=True)
    if (next(iter(test_input))=="model"):
        inpModel=test_input["model"]
    else:
        inpF=test_input
        
    filterTitls(tilseriesStar,relionProj,inpF,inpModel,plot,outputFold)
    ts=tiltSeriesMeta(outputFold + os.path.sep + "tiltseries_filtered.star")
    assert (ts.all_tilts_df.cryoBoostTestLabel=="good").all()    


    
@pytest.mark.parametrize("test_input", 
                         [("--ctfMaxResolution '1,20,-70,70'"), 
                          ("--driftInAng '1,10,-70,70'"), 
                          ("--defocusInAng '1,50000,-70,70'"), 
                          ("--model data/models/michaelNet_0.6/model.pth")],
                           ids=lambda val: idfn(val, {'function_name': 'cryoboost_filterTilts'}))
@pytest.mark.crboost_filterTilts
def test_crboost_filterTilts(test_input):
    
    tilseriesStar="data/tilts/tilt_series_ctf.star"
    relionProj=os.path.abspath(__file__)
    relionProj=os.path.dirname(os.path.dirname(os.path.dirname(relionProj)))+os.path.sep
    outputFold=relionProj+"tmpOut/"
    
    call=relionProj + "/bin/crboost_filterTitlts.py"
    call+=" --in_mics " + relionProj + tilseriesStar
    call+=" --o " + outputFold
    #call+=" --o " + outputFold
    call+=" " + test_input
    
    result = subprocess.run(call, capture_output=True, text=True,shell=True)
    ts=tiltSeriesMeta(outputFold + os.path.sep + "tiltseries_filtered.star")
    
    assert (ts.all_tilts_df.cryoBoostTestLabel=="good").all()    

