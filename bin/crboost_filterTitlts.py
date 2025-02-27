#!/usr/bin/env crboost_python 
import argparse
import os
import sys
from src.filterTilts.libFilterTilts import filterTitls

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '../'))
sys.path.append(root_dir)


def parse_arguments():
    parser = argparse.ArgumentParser(description="filter tilts")
    parser.add_argument("--in_mics", "-in_mics", required=True, help="Input tilt series STAR file")
    parser.add_argument("--o", dest="out_dir", required=True, help="Output directory name")
    parser.add_argument("--driftInAng","-shift",dest="rlnAccumMotionTotal",required=False, default=None, help="threshold movement")
    parser.add_argument("--defocusInAng", "-defocus",dest="rlnDefocusU" ,required=False, default=None, help="threshold defocus")
    parser.add_argument("--ctfMaxResolution", "-resolution",dest="rlnCtfMaxResolution" ,required=False, default=None, help="threshold resolution")
    parser.add_argument("--model", "-mod",dest="model" ,required=False, default=None, help="model for prediction")
    parser.add_argument("--probThreshold", "-pThr",dest="probThr" ,required=False, default=0.1, help="threshold for uncert. assignment")
    parser.add_argument("--probThrAction", "-pAct",dest="probAct" ,required=False, default="assingToGood", help="action for uncert. assignment")
    parser.add_argument("--mdocWk", "-m",required=False, default="mdoc/*.mdoc", help="path to .mdoc remove projctions according to tiltseries.star")
    # parser.add_argument("--interActiveMode", "-iam",required=False, default="onFailure", help="when to start interactive sorting (onFailure,never,always)")
    parser.add_argument("--j", "-nr_threads",dest="threads" ,required=False, default=24, help="Nr of threads used. Ignore!")
    args,unkArgs=parser.parse_known_args()
    return args,unkArgs

def main():
    
    args,addArg = parse_arguments()
    filterParams = {}
    for arg, value in vars(args).items():
        if (value==None):
            continue
        if ((arg == 'rlnAccumMotionTotal') | (arg == 'rlnDefocusU') | (arg == 'rlnCtfMaxResolution')):
            filterParams[arg] = [float(num) for num in value.split(',')]   
    
    filterTitls(args.in_mics,relionProj='',pramRuleFilter=filterParams,model=args.model,plot=None,outputFolder=args.out_dir,probThr=args.probThr,probAction=args.probAct,threads=args.threads,mdocWk=args.mdocWk
                )
    successName=args.out_dir + "/RELION_JOB_EXIT_SUCCESS"
    with open(successName, 'a'):
        os.utime(successName, None)
    
    
if __name__ == '__main__':
    main()


