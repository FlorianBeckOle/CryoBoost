#!/fs/pool/pool-fbeck/projects/4TomoPipe/trainClassifyer/softFastAI/conda3/bin/python
import argparse
import os
import sys

from PyQt6.QtWidgets import QApplication
from src.gui.schemeGui import MainUI 
from src.pipe.libpipe import pipe

def parse_arguments():
    parser = argparse.ArgumentParser(description="scheme gui")
    parser.add_argument("--scheme", "-s", required=False,default="relion_tomo_prep" ,help="path to scheme folder")
    parser.add_argument("--movies", "-mov", required=False,default="None",help="Input input movie dir")
    parser.add_argument("--mdocs", "-m", required=False,default="None",help="Input input mdocs dir")
    parser.add_argument("--proj", "-p", required=False, help="Output output project dir")
    parser.add_argument("--noGui", "-nG", required=False,action='store_true',help="do not open cryoboost gui")
    parser.add_argument("--autoGen", "-aG", required=False, action='store_true', help="gen Project and scheme")
    parser.add_argument("--autoLaunch", "-aL", required=False, action='store_true', help="launch relion scheme")
    parser.add_argument("--autoLaunchSync", "-aLsync", required=False, action='store_true', help="launch relion scheme synchrone")
    parser.add_argument("--skipSchemeEdit", "-skSe", required=False, action='store_true', help="skip scheme edit step on Gui")
    parser.add_argument("--relionGui", "-rg", required=False,  action='store_true', help="launch relion gui")
    args,unkArgs=parser.parse_known_args()
    return args,unkArgs

def open_scheme_gui(args):
    app = QApplication([])
    main_ui = MainUI(args)
    main_ui.show()
    app.exec()


def main():
    
    args,addArg = parse_arguments()
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

