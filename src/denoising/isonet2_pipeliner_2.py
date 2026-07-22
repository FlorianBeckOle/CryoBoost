#!/usr/bin/env crboost_python 

'''
Added Isonet2 to the conf.yaml to be loaded too
'''

import sys
import os
import subprocess
from pathlib import Path
from src.misc.system import run_wrapperCommand
from src.rw.librw import tiltSeriesMeta
from src.denoising.denoising_orchestrator import DenoisingPipelineBase


class IsoNet2Pipeline(DenoisingPipelineBase):
    """
    IsoNet2 denoising pipeline implementation.
    This class encapsulates the entire IsoNet2 workflow, including:
    - Preparation of input data
    - Initial denoising
    - Mask creation
    - Refinement of denoising
    """

    def __init__(self, args, runFlag=None):
        """
        Initialize IsoNet2 pipeline.
        
        Parameters:
        - args: Namespace object containing pipeline parameters
        - runFlag: If "Full", automatically run the pipeline
        """
        self.args = args
        self.result = None
        
        # Get RELION project path from input star file
        self.relion_proj = self.get_relion_proj_path(args.in_mics)
        print(f"RELION project path: {self.relion_proj}")


        # Load input star file metadata
        print(f"Loading star file: {args.in_mics}")
        self.ts = tiltSeriesMeta(args.in_mics, self.relion_proj)
        self.pixel_size = (self.ts.all_tilts_df['rlnMicrographOriginalPixelSize'].iloc[0])*self.ts.all_tilts_df['rlnTomoTomogramBinning'].iloc[0]
        self.defocus_list = list(defocus for defocus in self.ts.all_tilts_df['rlnTomoNominalDefocus'].loc[self.ts.all_tilts_df['rlnTomoName'].duplicated(keep='first') == False])
        print(f"✓ Loaded {self.ts.nrTomo} tomograms")
        print(f"Pixel size: {self.pixel_size} Å\n Defocus list: {self.defocus_list}\n")

        # Setup output directory inside RELION project
        #self.output_dir = Path(self.relion_proj) / args.out_dir
        #self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = Path(args.out_dir)
        
        # Store GPU configuration
        self.gpu_ids = args.gpu_ids if hasattr(args, 'gpu_ids') else "0,1,2,3"
        
        # Validate IsoNet2-specific inputs (implemented here)
        #self.validate_method_specific_inputs()

        # Check all requirements
        self._check_requirements()

        self._setup_input_paths()

        self.validate_method_specific_inputs()
        
        # Run if flagged
        if runFlag == "Full":
            self.run_pipeline()
    
    def _check_requirements(self):
        """Validate all IsoNet2 requirements (GPU, software, etc)."""
        import shutil
        
        print("\n" + "="*60)
        print("Checking Requirements")
        print("="*60)
        
        # Check if isonet.py exists
        if not shutil.which('isonet.py'):
            raise RuntimeError(
                "isonet.py not found in PATH\n"
                "Please load IsoNet2 module: module load ISONET2"
            )
        print("✓ isonet.py available")
        
        # Check GPUs
        num_gpus, vram, gpu_ids = self.check_gpu_availability()
        if num_gpus == 0:
            raise RuntimeError("No GPUs detected. IsoNet2 requires GPUs.")
        
        print("✓ All requirements met\n")

    def validate_method_specific_inputs(self):
        pass
    
    def prepare_star_file(self):
        """Step 1: Prepare IsoNet2 star file from odd/even tomograms."""
        print("\n" + "="*60)
        print("Step 1: Preparing Star File")
        print("="*60)
        
        command = [
            "isonet.py", "prepare_star",
            "--even", str(self.path_to_even),
            "--odd", str(self.path_to_odd),
            "--create_average", "False",
            "--pixel_size", str(self.pixel_size),
            "--number_subtomos", str(self.args.num_subtomos),
            "--defocus", str(self.defocus_list)
        ]
        
        print(f"Command: {' '.join(command)}")
        
        self.result = run_wrapperCommand(
            command,
            tag="prepare_star",
            relionProj=self.relion_proj,
            #relionProj=self.relion_proj,
            filterOuputFlag="isonet2"
        )
        
        # Validate output
        star_file = self.output_dir / "tomograms.star"
        if not star_file.exists():
            raise FileNotFoundError("tomograms.star was not created")
        
        print(f"✓ Star file created: {star_file}\n")
        return self.result
    
    def initial_denoise(self):
        """Step 2: Initial denoising pass for mask generation."""
        print("\n" + "="*60)
        print("Step 2: Initial Denoising for Mask Generation")
        print("="*60)
        
        # Denoise
        print("\n[2a] Running initial denoising...")
        command_denoise = [
            "isonet.py", "denoise",
            "tomograms.star",
            "--CTF_mode", "network",
            "--cube_size", str(self.args.cube_denoise),
            "--epochs", "2", #str(self.args.epoch_denoise),
            "--gpuID", self.gpu_ids
        ]
        
        print(f"Command: {' '.join(command_denoise)}")
        
        self.result = run_wrapperCommand(
            command_denoise,
            tag="initial_denoise",
            relionProj=self.relion_proj,
            filterOuputFlag="isonet2"
        )
        
        # Predict
        print("\n[2b] Predicting on full tomograms...")
        model_path = f"denoise/network_n2n_unet-medium_{self.args.cube_denoise}_full.pt"
        command_predict = [
            "isonet.py", "predict",
            "tomograms.star",
            model_path,
            "--gpuID", self.gpu_ids
        ]
        
        self.result = run_wrapperCommand(
            command_predict,
            tag="initial_predict",
            relionProj=self.relion_proj,
            filterOuputFlag="isonet2"
        )
        
        '''
        # Deconv
        print("\n[2c] Applying deconvolution...")
        command_deconv = [
            "isonet.py", "deconv",
            "tomograms.star",
            "--snrfalloff", "0.7",
            "--deconvstrength", "1"
        ]
        
        self.result = run_wrapperCommand(
            command_deconv,
            tag="initial_deconv",
            relionProj=self.relion_proj,
            filterOuputFlag="isonet2"
        )
        '''

        print("✓ Initial denoising complete\n")
        return self.result
    
    def create_mask(self):
        """Step 3: Create binary mask from denoised tomogram."""
        print("\n" + "="*60)
        print("Step 3: Creating Mask")
        print("="*60)
        
        command = [
            "isonet.py", "make_mask",
            "tomograms.star",
            "--density_percentage", str(self.args.density_percentage_mask),
            "--std_percentage", str(self.args.std_percentage_mask),
            "--input_column", "rlnDenoisedTomoName"
        ]
        
        print(f"Command: {' '.join(command)}")
        
        self.result = run_wrapperCommand(
            command,
            tag="make_mask",
            relionProj=self.relion_proj,
            filterOuputFlag="isonet2"
        )
        
        print("✓ Mask creation complete\n")
        return self.result
    
    def refine_denoise(self):
        """Step 4: Refined denoising with full IsoNet2 settings."""
        print("\n" + "="*60)
        print("Step 4: Refined Denoising")
        print("="*60)
        
        # Refine
        print("\n[4a] Running refined denoising...")
        command_refine = [
            "isonet.py", "refine",
            "tomograms.star",
            "--method", "isonet2-n2n",
            "--cube_size", str(self.args.cube_refine),
            "--epochs", "1", #str(self.args.epoch_refine),
            "--mw_weight", str(self.args.mw_weight_refine),
            "--CTF_mode", self.args.ctf_mode_refine,
            "--gpuID", self.gpu_ids,
            "--arch", self.args.arch_refine,
            "--bfactor", str(self.args.bfactor_refine)
        ]
        
        self.result = run_wrapperCommand(
            command_refine,
            tag="refine_denoise",
            relionProj=self.relion_proj,
            filterOuputFlag="isonet2"
        )
        
        # Predict with refined model
        print("\n[4b] Predicting with refined model...")
        model_path = f"isonet_maps/network_isonet2-n2n_{self.args.arch_refine}_{self.args.cube_refine}_full.pt"
        command_predict = [
            "isonet.py", "predict",
            "tomograms.star",
            model_path,
            "--gpuID", self.gpu_ids
        ]
        
        self.result = run_wrapperCommand(
            command_predict,
            tag="refine_predict",
            relionProj=self.relion_proj,
            filterOuputFlag="isonet2"
        )
        
        print("✓ Refined denoising complete\n")
        return self.result
    
    def update_metadata(self):
        """Update RELION star file with denoising results."""
        print("\n" + "="*60)
        print("Updating Metadata")
        print("="*60)

        output_star = self.output_dir / "denoised_tomograms.star"
        if output_star.exists():
            # Write denoised results back to star file
            self.ts.writeTiltSeries(str(output_star))
            print(f"✓ Updated star file: {output_star}\n")
        else:
            print(f"⚠ Warning: {output_star} not found\n")
    
    def check_results(self):
        """Validate denoising results."""
        print("\n" + "="*60)
        print("Validating Results")
        print("="*60)
        
        # Check if key output files exist
        expected_outputs = [
            "denoised_tomograms.star",
            "denoise",
            "isonet_maps"
        ]
        
        all_exist = True
        for output_name in expected_outputs:
            path = self.output_dir / output_name
            if path.exists():
                print(f"✓ {output_name}")
            else:
                print(f"❌ Missing: {output_name}")
                all_exist = False
        
        if not all_exist:
            print("\n❌ Some expected outputs are missing")
            self.result.returncode = 1
            return False
        
        print("\n✓ All results validated\n")
        return True
    
    def run_pipeline(self):
        """
        Run the complete IsoNet2 pipeline.
        
        Follows the structure:
        1. Prepare star file
        2. Initial denoising
        3. Create mask
        4. Refined denoising
        5. Update metadata
        6. Validate results
        """
        print("\n" + "="*70)
        print("Starting IsoNet2 Denoising Pipeline")
        print("="*70)
        print(f"Odd tomograms:   {self.path_to_odd}")
        print(f"Even tomograms:  {self.path_to_even}")
        print(f"Pixel size:      {self.pixel_size} Å")
        print(f"Output:          {self.output_dir}")
        print(f"GPU IDs:         {self.gpu_ids}")
        print("="*70 + "\n")
        
        try:
            # Prepare
            self.prepare_star_file()
            
            # Denoise
            self.initial_denoise()
            self.create_mask()
            self.refine_denoise()
            
            # Finalize
            self.update_metadata()
            self.check_results()
            
            print("\n" + "="*70)
            print("IsoNet2 Pipeline Complete!")
            print("="*70)
            print(f"✓ Output location: {self.output_dir}")
            print("="*70 + "\n")
        
        except Exception as e:
            print("\n" + "="*70)
            print("ERROR: Pipeline Failed")
            print("="*70)
            print(f"Error: {str(e)}")
            print("="*70 + "\n")
            raise
        
        return self.result
    
    def check_gpu_availability(self):
        """Check available GPUs and their memory."""
        try:
            output = subprocess.check_output([
                'nvidia-smi', 
                '--query-gpu=index,memory.total', 
                '--format=csv,noheader,nounits'
            ])
            gpu_info = output.decode('utf-8').strip().split('\n')
            num_gpus = len(gpu_info)
            vram = int(gpu_info[0].split(',')[1]) / 1024
            gpu_ids = [str(i) for i in range(num_gpus)]
            
            # Check CUDA_VISIBLE_DEVICES
            cuda_visible_devices = os.environ.get('CUDA_VISIBLE_DEVICES')
            if cuda_visible_devices and cuda_visible_devices != '-1':
                gpu_ids = cuda_visible_devices.split(',')
            
            print(f"Found {num_gpus} GPUs with {vram:.1f} GB VRAM")
            print(f"GPU IDs: {gpu_ids}")
            
            return num_gpus, vram, gpu_ids
        
        except Exception as e:
            print(f"Warning: Could not detect GPUs: {e}")
            return 0, 0, []