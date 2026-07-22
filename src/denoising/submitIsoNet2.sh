#!/bin/bash -l
# Standard output and error:
#SBATCH -e run.err
#SBATCH -o run.out
# Initial working directory:
#SBATCH -D ./
# Job Name:
#SBATCH -J Isonet2
# Queue (Partition):
#SBATCH --partition=p.hpcl9
# Number of nodes and MPI tasks per node:
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:4
#
#SBATCH --mail-type=none
#SBATCH --mem 720G
#
# Wall clock limit:
#SBATCH --time=168:00:00


#IO
pathToOdd=../External/job007/warp_tiltseries/reconstruction/odd/
pathToEven=../External/job007/warp_tiltseries/reconstruction/even/
pixS=11.8 #set from star file
defocus='[55000]' #set for each tomo from star file

###### also add mpi for this job, it might be worth it

#General
numSubTomo=5000 #600 default

#Denoise
cubeDenoise=96  #96 default
epochDenoise=50 #50 default 

#Mask
columnMask=rlnDenoisedTomoName
density_percentageMask=50 
std_percentageMask=80

#Refine
cubeRefine=128  #128 default 
epochRefine=70  #70 default
archRefine=unet-large #unet-medium
bfactorRefine=300 #defult 0 for cellular 
mw_weightRefine=150 #missing Wedge corr value defulat 200
ctf_modeRefine=network #or wiener

#Run
gpuID="0,1,2,3"

####Do not change here !
echo "setting env"
module purge
module load ISONET2
module list


# --- Check input paths ---
echo "Checking input directories..."

if [ ! -d "$pathToOdd" ]; then
    echo "ERROR: Odd path does not exist: $pathToOdd"
    exit 1
fi

if [ ! -d "$pathToEven" ]; then
    echo "ERROR: Even path does not exist: $pathToEven"
    exit 1
fi

# Check if directories contain files
if [ -z "$(ls -A "$pathToOdd")" ]; then
    echo "ERROR: Odd directory exists but is empty: $pathToOdd"
    exit 1
fi

if [ -z "$(ls -A "$pathToEven")" ]; then
    echo "ERROR: Even directory exists but is empty: $pathToEven"
    exit 1
fi

echo "Input directories OK."


echo "prepraing Star File"
echo "isonet.py prepare_star --even $pathToEven --odd $pathToOdd --create_average True --pixel_size $pixS --number_subtomos $numSubTomo --defocus $defocus"
isonet.py prepare_star --even $pathToEven --odd $pathToOdd --create_average True --pixel_size $pixS --number_subtomos $numSubTomo --defocus $defocus

echo "initial Denoise for mask"
echo "isonet.py denoise tomograms.star --CTF_mode network --cube_size $cubeDenoise --epochs $epochDenoise --gpuID $gpuID"
isonet.py denoise tomograms.star --CTF_mode network --cube_size $cubeDenoise --epochs $epochDenoise --gpuID $gpuID
echo "isonet.py predict tomograms.star denoise/network_n2n_unet-medium_${cubeDenoise}_full.pt --gpuID $gpuID"
isonet.py predict tomograms.star denoise/network_n2n_unet-medium_${cubeDenoise}_full.pt --gpuID $gpuID
echo "isonet.py deconv tomograms.star --snrfalloff 0.7 --deconvstrength 1"
isonet.py deconv tomograms.star --snrfalloff 0.7 --deconvstrength 1

echo "initial Denoise for mask"
echo "isonet.py make_mask tomograms.star --density_percentage $density_percentageMask --std_percentage $std_percentageMask --input_column $columnMask"
isonet.py make_mask tomograms.star --density_percentage $density_percentageMask --std_percentage $std_percentageMask --input_column $columnMask #rlnDeconvTomoName

echo "Refine Denoise"
echo "isonet.py refine tomograms.star --method isonet2-n2n --cube_size $cubeRefine --epochs $epochRefine --mw_weight $mw_weightRefine --CTF_mode $ctf_modeRefine --gpuID $gpuID --arch $archRefine --bfactor $bfactorRefine"
isonet.py refine tomograms.star --method isonet2-n2n --cube_size $cubeRefine --epochs $epochRefine --mw_weight $mw_weightRefine --CTF_mode $ctf_modeRefine --gpuID $gpuID --arch $archRefine --bfactor $bfactorRefine
echo "isonet.py predict tomograms.star isonet_maps/network_isonet2-n2n_${archRefine}_${cubeRefine}_full.pt --gpuID $gpuID"
isonet.py predict tomograms.star isonet_maps/network_isonet2-n2n_${archRefine}_${cubeRefine}_full.pt --gpuID $gpuID

echo "Denoising done"
