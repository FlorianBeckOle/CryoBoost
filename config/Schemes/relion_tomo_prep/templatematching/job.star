
# version 30001

data_job

_rlnJobTypeLabel             relion.external
_rlnJobIsContinue                       0
_rlnJobIsTomo                           0
 
# version 30001

data_joboptions_values

loop_ 
_rlnJobOptionVariable #1 
_rlnJobOptionValue #2 
    fn_exe         crboost_match_template.py
  in_3dref         "None" 
 in_coords         "" 
   in_mask         "None" 
    in_mic         Schemes/relion_tomo_prep/reconstructionfull/tomograms.star
    in_mov         "" 
   in_part         "" 
other_args         "--implementation pytom --volumeMaskFold None --gpu_ids auto \"  
param1_label      "volumeColumn" 
param1_value      "rlnTomoReconstructedTomogram" 
param2_label      "templateSym" 
param2_value      "C1" 
param3_label      "angularSearch" 
param3_value      "12" 
param4_label      "nonSphericalMask" 
param4_value      "True"
param5_label      "bandPassFilter"
param5_value      "None" 
param6_label      "ctfWeight"
param6_value      "True"    
param7_label      "doseWeigh"
param7_value      "True"
param8_label      "spectralWhitening" 
param8_value      "False" 
param9_label      "randomPhaseCorrection" 
param9_value      "False" 
param10_label     "split" 
param10_value     "4:4:2" 
nr_threads        1
do_queue         Yes 
queuename    openmpi 
qsub     sbatch 
qsubscript    qsub/qsub_relion_hpcl89.sh 
min_dedicated          1 
qsub_extra1          1 
qsub_extra2          1 
qsub_extra3    p.hpcl8 
qsub_extra4      2 
qsub_extra5      370G
 
