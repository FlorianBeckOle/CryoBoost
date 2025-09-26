import os
import numpy as np
from scipy import fftpack, ndimage
import mrcfile
import subprocess
from src.rw.librw import cbconfig


def gaussian_lowpass_mrc(input_mrc, output_mrc: str=None, cutoff_angstrom: float=None, 
                        voxel_size_angstrom: float = None,invert_contrast: bool = False,hard_cutoff_angstrom: float = None):
    """
    Apply Gaussian low-pass filter to MRC file
    
    Args:
        input_mrc (str): Path to input MRC file
        output_mrc (str): Path to output filtered MRC file
        cutoff_angstrom (float): Cutoff frequency in Ångströms (Å)
        voxel_size_angstrom (float, optional): Override voxel size in Ångströms. 
                                              If None, uses value from input MRC
    """
    
    if isinstance(input_mrc,str):
         with mrcfile.open(input_mrc, permissive=True) as mrc:
            volume = mrc.data.copy()
            voxel_size = voxel_size_angstrom if voxel_size_angstrom is not None else mrc.voxel_size.x
    else:
        volume=input_mrc
        voxel_size=voxel_size_angstrom
        
    # Calculate filter parameters in Ångströms
    nx, ny, nz = volume.shape
    kx = fftpack.fftfreq(nx, d=voxel_size)  # spatial frequencies in 1/Å
    ky = fftpack.fftfreq(ny, d=voxel_size)
    kz = fftpack.fftfreq(nz, d=voxel_size)
    
    kx_grid, ky_grid, kz_grid = np.meshgrid(kx, ky, kz, indexing='ij')
    k_squared = kx_grid**2 + ky_grid**2 + kz_grid**2
    k_magnitude = np.sqrt(k_squared)
    # Convert cutoff to sigma in Fourier space (1/Å)
    sigma = cutoff_angstrom / (2 * np.pi)
    gaussian_filter = np.exp(-k_squared * (2 * np.pi**2) * sigma**2)
    
     # Apply hard cutoff if specified
    if hard_cutoff_angstrom is not None:
        hard_cutoff_freq = 1.0 / hard_cutoff_angstrom
        hard_mask = k_magnitude <= hard_cutoff_freq
        gaussian_filter = gaussian_filter * hard_mask
    
    
    vol_fft = fftpack.fftn(volume)
    filtered_fft = vol_fft * gaussian_filter
    filtered_vol = np.real(fftpack.ifftn(filtered_fft))
    
    # Normalize filtered volume
    filtered_vol = filtered_vol - np.mean(filtered_vol)
    filtered_vol = filtered_vol / np.std(filtered_vol)
    
    # Invert contrast if requested
    if invert_contrast:
        filtered_vol = -filtered_vol
    
    if output_mrc is None:
        return filtered_vol
    
    # Write output MRC
    with mrcfile.new(output_mrc, overwrite=True) as mrc:
        mrc.set_data(filtered_vol.astype(np.float32))
        mrc.voxel_size = voxel_size
    
    return filtered_vol

def processVolume(input_mrc: str, output_mrc: str, cutoff_angstrom: float=None, cutoff_edge_width: float=6,
                  voxel_size_angstrom: float = None,voxel_size_angstrom_out_header: float = None ,invert_contrast: bool = False,voxel_size_angstrom_output: float = None,
                  box_size_output: float = None,envStr: str = "ConvLocal"):
    if envStr=="ConvLocal":
        CRYOBOOST_HOME=os.getenv("CRYOBOOST_HOME")
        confPath=CRYOBOOST_HOME + "/config/conf.yaml"
        conf=cbconfig(confPath)     
        envStr=conf.confdata['local']['Environment']+";"
    
    program='relion_image_handler'
    inp=' --i ' + input_mrc
    outp=' --o ' + output_mrc
    if cutoff_angstrom is not None:
        lowpass=' --lowpass ' + str(cutoff_angstrom)
   
    lowpassSm=' --filter_edge_width ' + str(cutoff_edge_width)
    if voxel_size_angstrom_output is not None:
        rescale=" --rescale_angpix " + str(voxel_size_angstrom_output)
    if invert_contrast:
        invert=" --multiply_constant -1"
    if box_size_output is not None:
        box_size=" --new_box " + str(box_size_output)
    if voxel_size_angstrom_out_header is not None:
        voxel_size_outHeader="  --force_header_angpix " + str(voxel_size_angstrom_out_header)
    if voxel_size_angstrom is not None:
        voxelIn=" --angpix " + str(voxel_size_angstrom)
    if envStr is not None:
        if not envStr.endswith(';'):
            envStr+=";"
        call=envStr + program + inp + outp
    else:
        call=program + inp + outp 
    
    if invert_contrast:
        call+=invert
    if cutoff_angstrom is not None:
        call+=lowpass
    if cutoff_edge_width is not None:
        call+=lowpassSm    
    if voxel_size_angstrom_output is not None:
        call+=rescale 
    if box_size_output is not None:
        call+=box_size       
    if voxel_size_angstrom_out_header is not None:
        call+=voxel_size_outHeader   
    if voxel_size_angstrom is not None:
        call+=voxelIn
    
    print(call)
    subprocess.run(call,shell=True)


def tom_cart2sph(I):
    """
    Transform 3D-volumes from cartesian to spherical coordinates.
    Parameters:
    -----------
    I : ndarray
        3D input array in cartesian coordinates
    Returns:
    --------
    pol : ndarray
        3D array in spherical coordinates
    """
    # Get dimensions
    nx, ny, nz = I.shape
    
    # Calculate parameters for spherical grid
    nradius = max(max(nx, ny), nz) // 2
    ntheta = 2 * nradius
    nphi = 2 * ntheta
    
    # Create spherical coordinate grids
    r = np.linspace(0, nradius-1, nradius)
    phi = np.linspace(0, 2*np.pi*(1-1/nphi), nphi)
    theta = np.linspace(0, np.pi, ntheta)
    r, phi, theta = np.meshgrid(r, phi, theta, indexing='ij')
    
    # Convert to cartesian coordinates
    eps = 0
    px = r * np.cos(phi) * np.sin(theta) + nradius + 1 + eps
    py = r * np.sin(phi) * np.sin(theta) + nradius + 1 + eps
    pz = r * np.cos(theta) + nradius + 1
    
    # Clear memory
    del r, phi, theta
    
    # Calculate interpolation weights
    px_floor = np.floor(px).astype(int)
    py_floor = np.floor(py).astype(int)
    pz_floor = np.floor(pz).astype(int)
    px_ceil = np.ceil(px).astype(int)
    py_ceil = np.ceil(py).astype(int)
    pz_ceil = np.ceil(pz).astype(int)
    
    # Clip indices to valid range
    px_floor = np.clip(px_floor-1, 0, nx-1)
    py_floor = np.clip(py_floor-1, 0, ny-1)
    pz_floor = np.clip(pz_floor-1, 0, nz-1)
    px_ceil = np.clip(px_ceil-1, 0, nx-1)
    py_ceil = np.clip(py_ceil-1, 0, ny-1)
    pz_ceil = np.clip(pz_ceil-1, 0, nz-1)
    
    tx = px - np.floor(px)
    ty = py - np.floor(py)
    tz = pz - np.floor(pz)
    
    # Perform trilinear interpolation using proper 3D indexing
    c000 = I[px_floor, py_floor, pz_floor]
    c100 = I[px_ceil, py_floor, pz_floor]
    c010 = I[px_floor, py_ceil, pz_floor]
    c001 = I[px_floor, py_floor, pz_ceil]
    c110 = I[px_ceil, py_ceil, pz_floor]
    c101 = I[px_ceil, py_floor, pz_ceil]
    c011 = I[px_floor, py_ceil, pz_ceil]
    c111 = I[px_ceil, py_ceil, pz_ceil]
    
    # Calculate interpolated values
    pol = (1-tx)*(1-ty)*(1-tz)*c000 + \
          tx*(1-ty)*(1-tz)*c100 + \
          (1-tx)*ty*(1-tz)*c010 + \
          (1-tx)*(1-ty)*tz*c001 + \
          tx*ty*(1-tz)*c110 + \
          tx*(1-ty)*tz*c101 + \
          (1-tx)*ty*tz*c011 + \
          tx*ty*tz*c111
    
    return pol
