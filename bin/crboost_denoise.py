#!/usr/bin/env crboost_python 

import argparse
import os
import sys
from pathlib import Path


def parse_arguments():
    """
    Parse command line arguments for tomogram denoising pipeline.
    
    Returns:
    - args: Namespace object with all parameters
    - unkArgs: Unknown arguments (for compatibility)
    """
    parser = argparse.ArgumentParser(
        description="CryoBoost Tomogram Denoising Pipeline"
    )
    
    # === Required Arguments ===
    parser.add_argument("--in_mics", "-in_mic", required=True, help="Input tilt series STAR file")
    parser.add_argument("--path_to_odd", required=False, help="Path to directory containing odd tomograms")
    parser.add_argument("--path_to_even", required=False, help="Path to directory containing even tomograms")
    parser.add_argument("--o", "-out_dir", required=True, help="Output directory name", dest="out_dir")

    parser.add_argument("--method", required=False, default="IsoNet2", help="Denoising method to use (default: IsoNet2)")

    # === General Parameters ===
    parser.add_argument("--num_subtomos", type=int, required=False, default=600, help="Number of subtomograms to extract (default: 600)")

    # === Initial Denoising Parameters (method_specific_arg) ===
    parser.add_argument(
        "--cube_denoise",
        type=int,
        required=False,
        default=96,
        help="Cube size for initial denoising (default: 96)"
    )
    parser.add_argument(
        "--epoch_denoise",
        type=int,
        required=False,
        default=50,
        help="Number of training epochs for initial denoising (default: 50)"
    )
    
    # === Mask Parameters (method_specific_arg) ===
    parser.add_argument(
        "--density_percentage_mask",
        type=int,
        required=False,
        default=50,
        help="Density percentage threshold for mask creation (default: 50)"
    )
    parser.add_argument(
        "--std_percentage_mask",
        type=int,
        required=False,
        default=80,
        help="Standard deviation percentage for mask creation (default: 80)"
    )
    
    # === Refinement Parameters (method_specific_arg) ===
    parser.add_argument(
        "--cube_refine",
        type=int,
        required=False,
        default=128,
        help="Cube size for refined denoising (default: 128)"
    )
    parser.add_argument(
        "--epoch_refine",
        type=int,
        required=False,
        default=70,
        help="Number of training epochs for refined denoising (default: 70)"
    )
    parser.add_argument(
        "--arch_refine",
        type=str,
        required=False,
        default="unet-large",
        choices=["unet-small", "unet-medium", "unet-large"],
        help="Network architecture for refinement (default: unet-large)"
    )
    parser.add_argument(
        "--bfactor_refine",
        type=int,
        required=False,
        default=300,
        help="B-factor for sharpening (default: 300)"
    )
    parser.add_argument(
        "--mw_weight_refine",
        type=int,
        required=False,
        default=150,
        help="Missing wedge correction weight (default: 150)"
    )
    parser.add_argument(
        "--ctf_mode_refine",
        type=str,
        required=False,
        default="network",
        choices=["network", "wiener"],
        help="CTF correction mode (default: network)"
    )
    
    # === GPU Configuration ===
    parser.add_argument(
        "--gpu_ids",
        "-g",
        required=False,
        default="0,1,2,3",
        help="Comma-separated GPU IDs to use (default: 0,1,2,3)"
    )
    
    # === RELION Compatibility ===
    parser.add_argument(
        "--j",
        "-nr_threads",
        dest="threads",
        required=False,
        default=None,
        help="Nr of threads used. Ignore!"
    )
    
    args, unkArgs = parser.parse_known_args()
    return args, unkArgs


def main():
    """
    Main entry point for CryoBoost denoising pipeline.
    """
    try:
        # Parse arguments
        args, unkArgs = parse_arguments()
        
        # Import orchestrator
        from src.denoising.denoising_orchestrator import TomogramDenoiser
        
        print("="*70)
        print("CryoBoost Tomogram Denoising Pipeline")
        print("="*70)
        print(f"Method:          {args.method}")
        print(f"Input STAR:      {args.in_mics}")
        print(f"Odd tomograms:   {args.path_to_odd}")
        print(f"Even tomograms:  {args.path_to_even}")
        print(f"Output:          {args.out_dir}")
        print("="*70 + "\n")
        
        # Create and run denoiser
        denoiser = TomogramDenoiser(args)
        result = denoiser.run()
        
        # Create RELION success marker
        if result.returncode == 0:
            success_file = os.path.join(args.out_dir, "RELION_JOB_EXIT_SUCCESS")
            Path(success_file).touch()
            print(f"✓ Success marker created: {success_file}")
        
        sys.exit(0 if result.returncode == 0 else 1)
    
    except FileNotFoundError as e:
        print(f"\n❌ FILE NOT FOUND: {e}")
        sys.exit(1)
    
    except ValueError as e:
        print(f"\n❌ INVALID ARGUMENT: {e}")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()