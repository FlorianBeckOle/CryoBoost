#!/usr/bin/env crboost_python 
"""
High-level orchestrator for tomogram denoising.
Supports multiple denoising methods: IsoNet2, (others in the future)
"""

from pathlib import Path
import os
from abc import ABC, abstractmethod
#import yaml
#from src.rw.librw import tiltSeriesMeta


class TomogramDenoiser:
    """
    High-level orchestrator for tomogram denoising.
    
    Routes to appropriate denoising pipeline based on method selection.
    Handles validation and RELION integration.
    """
    
    def __init__(self, args):
        """
        Initialize denoising orchestrator.
        
        Parameters:
        - args: Namespace object with denoising parameters
        """
        self.args = args
        self.method = args.method
        self.output_dir = Path(args.out_dir)
        #self.ts = tiltSeriesMeta(args.in_mics) 
        
        # Validate method
        self.supported_methods = ['IsoNet2']
        if self.method not in self.supported_methods:
            raise ValueError(
                f"Unknown denoising method: {self.method}\n"
                f"Supported methods: {', '.join(self.supported_methods)}"
            )
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize the selected denoising pipeline
        # (Pipeline handles its own validation)
        self.pipeline = self._create_pipeline()
    
    def _create_pipeline(self):
        """
        Factory method to create the appropriate denoising pipeline.
        
        Returns:
        - Pipeline instance (IsoNet2Pipeline etc.)
        """
        print(f"\n{'='*70}")
        print(f"Initializing {self.method} Denoising Pipeline")
        print(f"{'='*70}\n")
        
        if self.method == 'IsoNet2':
            from .isonet2_pipeliner import IsoNet2Pipeline
            return IsoNet2Pipeline(self.args)
        
        else:
            raise NotImplementedError(f"Method '{self.method}' not implemented")
    
    def run(self):
        """
        Execute the complete denoising pipeline.
        
        Returns:
        - Result object from pipeline execution
        """
        print(f"\n{'='*70}")
        print(f"Starting {self.method} Denoising")
        print(f"{'='*70}")
        print(f"Method:          {self.method}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'='*70}\n")
        
        try:
            # Run pipeline (it handles its own validation)
            result = self.pipeline.run_pipeline()
            
            # Create RELION success marker
            if result.returncode == 0:
                self._create_success_marker()
            
            print(f"\n{'='*70}")
            print(f"{self.method} Denoising Complete!")
            print(f"{'='*70}\n")
            
            return result
        
        except Exception as e:
            print(f"\n{'='*70}")
            print(f"ERROR: {self.method} Denoising Failed")
            print(f"{'='*70}")
            print(f"Error: {str(e)}")
            print("="*70 + "\n")
            raise
    
    def _create_success_marker(self):
        """Create RELION job success marker file."""
        success_file = self.output_dir / "RELION_JOB_EXIT_SUCCESS"
        success_file.touch()
        print(f"✓ Created success marker: {success_file}")
    
    @staticmethod
    def get_supported_methods():
        """Get list of supported denoising methods."""
        return ['IsoNet2']
    
    @staticmethod
    def get_method_description(method):
        """Get description of a denoising method."""
        descriptions = {
            'IsoNet2': 'Deep learning denoising with missing wedge correction',
        }
        return descriptions.get(method.lower(), 'Unknown method')
    

class DenoisingPipelineBase(ABC):
    """Abstract base class for denoising pipelines."""
    
    @abstractmethod
    def run_pipeline(self):
        """Execute the complete denoising pipeline."""
        pass
    
    @abstractmethod
    def check_gpu_availability(self):
        """Check available GPUs."""
        pass
    
    def _setup_input_paths(self):
        """
        Setup and validate input paths.
        If paths don't exist or are empty, errors are raised here.
        """
        print("\n" + "="*60)
        print("Setting Up Input Paths")
        print("="*60)
        
        # Setup odd path
        if self.args.path_to_odd:
            self.path_to_odd = Path(self.args.path_to_odd)
        else:
            first_tomogram = self.ts.all_tilts_df["rlnTomoReconstructedTomogramHalf1"].iloc[0]
            self.path_to_odd = Path(first_tomogram).parent
            self.path_to_odd = self.path_to_odd / "ODD" ########################### #TODO  only works for Relion like this

        
        # Validate odd exists and has files
        if not self.path_to_odd.exists():
            raise FileNotFoundError(f"Odd path does not exist: {self.path_to_odd}")
        if not any(self.path_to_odd.iterdir()):
            raise FileNotFoundError(f"Odd directory is empty: {self.path_to_odd}")
        print(f"  ✓ Odd directory: {self.path_to_odd}")
        
        # Setup even path
        if self.args.path_to_even:
            self.path_to_even = Path(self.args.path_to_even)
        else:
            first_tomogram = self.ts.all_tilts_df["rlnTomoReconstructedTomogramHalf2"].iloc[0]
            self.path_to_even = Path(first_tomogram).parent
            self.path_to_even = self.path_to_even / "EVN" ########################### #TODO only works for Relion too 
        
        # Validate even exists and has files
        if not self.path_to_even.exists():
            raise FileNotFoundError(f"Even path does not exist: {self.path_to_even}")
        if not any(self.path_to_even.iterdir()):
            raise FileNotFoundError(f"Even directory is empty: {self.path_to_even}")
        print(f"  ✓ Even directory: {self.path_to_even}")
        
        print("✓ Input paths validated\n")

    @abstractmethod
    def validate_method_specific_inputs(self):
        """
        Validate method-specific inputs beyond odd/even paths.
        
        Each pipeline can override to add custom validation.
        """
        pass

    def get_relion_proj_path(self, in_mics):
        """
        Extract RELION project path from star file path.
        """
        rel_proj = os.path.dirname(os.path.dirname(os.path.dirname(in_mics)))
        if rel_proj and rel_proj != "":
            return rel_proj + "/"
        return "./"
