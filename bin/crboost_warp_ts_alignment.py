#!/usr/bin/env crboost_python 

import argparse
import os
import sys


from src.warp.tsAlignment import tsAlignment

def parse_arguments():
    parser = argparse.ArgumentParser(description="filter tilts")
    parser.add_argument("--in_mics", "-in_mic", required=True, help="Input tilt series STAR file")
    parser.add_argument("--o", dest="out_dir", required=True, help="Output directory name")
    parser.add_argument("--j", "-nr_threads",dest="threads" ,required=False, default=None, help="Nr of threads used. Ignore!")
    
    parser.add_argument("--gain_path", required=False,default="None", help="Path to gain file")
    parser.add_argument("--gain_operations", required=False,default="None", help="Operations applied to gain e.g flip_x:transpose or flip_y") 
    parser.add_argument("--tomo_dimensions", required=False,default="4096x4049x2048", help=" Default: 4096x4049x2048. Unbinned Tomo Dimension")
    parser.add_argument("--mdocWk", required=True,default="mdoc/*.mdoc", help="Default: mdoc/*.mdoc wildcard to mdoc files")
    parser.add_argument("--rescale_angpixs", required=False,default="12", help="Rescale tilt images to this pixel size")
    
    parser.add_argument("--alignment_program", required=False,default="Aretomo", help=" Default: Aretomo opt. Imod")
    parser.add_argument("--aretomo_sample_thickness", required=False,default="200", help=" Default: 200. Thickness of sample in nm used for Alignment")
    parser.add_argument("--aretomo_patches", required=False,default="2x2", help=" Default: 2x2. Num of Aretomo patches use 0x0 to switch off")
    parser.add_argument("--imod_patch_size_and_overlap", required=False,default="200", help=" Default: 200:50 Patch size in A patch overlap in %")
    parser.add_argument("--refineTiltAxis_iter_and_batch", required=False,default="3:5", help=" Default: 3:5 (3 iterations with 5 Tomograms) Refine given Tiltaxis use 0:0 to switch off")
    
    parser.add_argument("--perdevice", required=False,default="1" ,help="Default: 1. Number of processes per GPU")
    
    args,unkArgs=parser.parse_known_args()
    return args,unkArgs

def main():
    
    args,addArg = parse_arguments()
    tsA=tsAlignment(args,runFlag="Full")
    
    if tsA.result.returncode==1:
        raise Exception("Error: tsAlignment failed")
    if tsA.result.returncode==0:
        successName=args.out_dir + "/RELION_JOB_EXIT_SUCCESS"
        with open(successName, 'a'):
             os.utime(successName, None)
    
    
if __name__ == '__main__':
    main()
