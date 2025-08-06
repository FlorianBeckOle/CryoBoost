#!/usr/bin/env crboost_python 
import argparse
import os
import sys

from PyQt6.QtWidgets import QApplication
from src.gui.schemeGui import MainUI 
from src.pipe.libpipe import pipe
from src.misc.system import test_crboostSetup

def parse_arguments():
    parser = argparse.ArgumentParser(description="scheme gui")
    parser.add_argument("--scheme", "-s", required=False,default="gui" ,help="path to scheme folder or predefined schemes warp_tomo_prep/relion_tomo_prep")
    parser.add_argument("--movies", "-mov", required=False,default="None",help="Input movie dir")
    parser.add_argument("--mdocs", "-m", required=False,default="None",help="Input mdocs dir")
    parser.add_argument("--gain", "-g", required=False,help="Path to gain ref")
    parser.add_argument("--pixS", "-pS", required=False,default=None,help="Input pixelsize")
    parser.add_argument("--species", "-sp", required=False,default="noTag",help="name of species sperated by , use None to switch off particle processing")
    parser.add_argument("--Noise2Noise", "-n2n", required=False,type=str,default="True",help="use Noise2Noise filter in scheme, True/False")
    parser.add_argument("--FilterTilts", "-ft", required=False,type=str,default="True",help="remove bad tilts in scheme, True/False")
    parser.add_argument("--impPrefix", "-iP", required=False,default="auto",help="Input prefix")
    parser.add_argument("--proj", "-p", required=False,default="None",help="Output output project dir")
    parser.add_argument("--noGui", "-nG", required=False,action='store_true',help="do not open cryoboost gui")
    parser.add_argument("--autoGen", "-aG", required=False, action='store_true', help="gen Project and scheme")
    parser.add_argument("--autoLaunch", "-aL", required=False, action='store_true', help="launch relion scheme")
    parser.add_argument("--autoLaunchSync", "-aLsync", required=False, action='store_true', help="launch relion scheme synchrone")
    parser.add_argument("--skipSchemeEdit", "-skSe", required=False, action='store_true', help="skip scheme edit step on Gui")
    parser.add_argument("--relionGui", "-rg", required=False,  action='store_true', help="launch relion gui")
    args,unkArgs=parser.parse_known_args()
    num_args = len(sys.argv)-1
    args.numInputArgs=num_args
    
    # Validate species string - raise exception if it contains underscores
    if args.species != "None" and args.species != "noTag" and "_" in args.species:
        raise ValueError("Error: Species names cannot contain underscores ('_')")
    
    
    return args,unkArgs

def open_scheme_gui(args):
    app = QApplication([])
    main_ui = MainUI(args)
    main_ui.show()
    app.exec()


def main():
    
    args,addArg = parse_arguments()
    sytemOk=test_crboostSetup()
    if (sytemOk==False):
        raise Exception("CryBoost cannot be used")
        #return 0
    
    #print(args)
    if args.noGui:
        pipeRunner=pipe(args)
        pipeRunner.initProject()
        if args.autoGen:
            pipeRunner.writeScheme()
        if args.relionGui:
            pipeRunner.openRelionGui()
        if args.autoLaunch:
            pipeRunner.runScheme()
        if args.autoLaunchSync:
            pipeRunner.runSchemeSync()
    else:
        open_scheme_gui(args) 
        
        
    
if __name__ == '__main__':
    main()


