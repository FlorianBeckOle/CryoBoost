#!/bin/bash --norc 
# Standard output and error:
#SBATCH -e XXXerrfileXXX
#SBATCH -o XXXoutfileXXX
# Initial working directory:
#SBATCH -D ./
# Job Name:
#SBATCH -J Relion
# Queue (Partition):
#SBATCH --partition=XXXextra3XXX
# Number of nodes and MPI tasks per node:
#SBATCH --nodes=XXXextra1XXX
#SBATCH --ntasks=XXXmpinodesXXX
#SBATCH --ntasks-per-node=XXXextra2XXX
#SBATCH --cpus-per-task=XXXthreadsXXX
#SBATCH --gres=gpu:XXXextra4XXX
#
#SBATCH --mail-type=none
#SBATCH --mem XXXextra5XXX
#
# Wall clock limit:
#SBATCH --time=168:00:00


#clean up environment
module purge
export PATH=/fs/pool/pool-bmapps/hpcl8/sys/soft/modules/4.2.1/localFold/bin:/usr/local/bin:/usr/bin:/bin:/usr/lib/mit/bin:/usr/lib/mit/sbin
unset LD_LIBRARY_PATH

#build up environment variables
source /fs/pool/pool-fbeck/projects/4TomoPipe/rel5Pipe/src/CryoBoost/.cbenv
module load intel/18.0.5
module load impi/2018.4
module load IMOD/4.12.17
module load jdk
module load ARETOMO2/1.1.2
module load RELION/5.0.0NC
module load PYTOM-TM/0.7.10

module list
echo "submitting relion"
srun bash --norc -c 'XXXcommandXXX'
echo "done"

