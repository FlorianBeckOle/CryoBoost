
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
    fn_exe         crboost_warp_ts_alignment.py
  in_3dref         "" 
 in_coords         "" 
   in_mask         "" 
    in_mic         Schemes/warp_tomo_prep/aligntilts/tilt_series.star
    in_mov         "" 
   in_part         "" 
other_args         " \" 
param1_label      "tomo_dimensions" 
param1_value      "4096x4096x2048" 
param2_label      "gain_path" 
param2_value      "None" 
param3_label      "gain_operations" 
param3_value      "None" 
param4_label      "mdocWk" 
param4_value      "mdoc/*.mdoc"
param5_label      "alignment_program"
param5_value      "Aretomo" 
param6_label      "aretomo_sample_thickness" 
param6_value      "200"    
param7_label      "imod_patch_size_and_overlap"
param7_value      "200:50"
param8_label      "rescale_angpixs" 
param8_value      "12" 
param9_label      "refine_tilt_axis" 
param9_value      "False" 
param10_label     "perdevice" 
param10_value     "1" 
nr_threads        1
do_queue         Yes 
queuename    openmpi 
qsub     sbatch 
qsubscript    qsub/qsub_warp_hpcl89.sh 
min_dedicated          1 
qsub_extra1          1 
qsub_extra2          1 
qsub_extra3    p.hpcl8 
qsub_extra4      1 
qsub_extra5      370G
 