#!/bin/bash --norc 
# Standard output and error:
#SBATCH -e XXXerrfileXXX
#SBATCH -o XXXoutfileXXX
# Initial working directory:
#SBATCH -D ./
# Job Name:
#SBATCH -J WarpEm
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
module load intel/18.0.5
module load impi/2018.4
module load jdk
module load IMOD/4.12.17
module load ARETOMO2/1.0.0
module load ARETOMO3/2.2.2
module load WARP/2.0.0dev35
module load PYTOM-TM/0.7.10
source /fs/pool/pool-fbeck/projects/4TomoPipe/rel5Pipe/src/CryoBoost/.cbenv

module list
echo "submitting Warp"
bash --norc -c "\
XXXcommandXXX
"
#Jobs need to have \ as final additional argument as relion removes the whole line when submittion an external job!
echo "done"

