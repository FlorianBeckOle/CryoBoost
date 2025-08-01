
# version 50001

data_scheme_general

_rlnSchemeName                       Schemes/warp_tomo_prep/
_rlnSchemeCurrentNodeName            WAIT
 

# version 50001

data_scheme_floats

loop_ 
_rlnSchemeFloatVariableName #1 
_rlnSchemeFloatVariableValue #2 
_rlnSchemeFloatVariableResetValue #3 
do_at_most   500.000000   500.000000 
maxtime_hr    48.000000    48.000000 
  wait_sec   180.000000   180.000000 
 

# version 50001

data_scheme_operators

loop_ 
_rlnSchemeOperatorName #1 
_rlnSchemeOperatorType #2 
_rlnSchemeOperatorOutput #3 
_rlnSchemeOperatorInput1 #4 
_rlnSchemeOperatorInput2 #5 
EXIT       exit  undefined  undefined  undefined
EXIT_maxtime exit_maxtime  undefined maxtime_hr  undefined 
WAIT       wait  undefined   wait_sec  undefined 
 

# version 50001

data_scheme_jobs

loop_ 
_rlnSchemeJobNameOriginal #1 
_rlnSchemeJobName #2 
_rlnSchemeJobMode #3 
_rlnSchemeJobHasStarted #4 
importmovies importmovies   continue            0 
fsMotionAndCtf fsMotionAndCtf continue 0 
filtertilts  filtertilts continue 0
filtertiltsInter filtertiltsInter   continue            0
aligntiltsWarp aligntiltsWarp continue 0 
tsCtf tsCtf continue 0 
tsReconstruct tsReconstruct continue 0
denoisetrain    denoisetrain    continue        0      
denoisepredict    denoisepredict    continue        0 
templatematching  templatematching   continue      0 
tmextractcand  tmextractcand   continue      0 
subtomoExtraction subtomoExtraction continue    0

# version 50001

data_scheme_edges

loop_ 
_rlnSchemeEdgeInputNodeName #1 
_rlnSchemeEdgeOutputNodeName #2 
_rlnSchemeEdgeIsFork #3 
_rlnSchemeEdgeOutputNodeNameIfTrue #4 
_rlnSchemeEdgeBooleanVariable #5 
WAIT EXIT_maxtime            0  undefined  undefined 
EXIT_maxtime importmovies            0  undefined  undefined 
importmovies fsMotionAndCtf       0 undefined  undefined 
fsMotionAndCtf filtertilts        0 undefined  undefined
filtertilts  filtertiltsInter     0 undefined  undefined
filtertiltsInter aligntiltsWarp           0 undefined  undefined   
aligntiltsWarp    tsCtf               0 undefined  undefined
tsCtf tsReconstruct                  0 undefined  undefined
tsReconstruct  denoisetrain          0 undefined  undefined
denoisetrain    denoisepredict          0 undefined undefined
denoisepredict  templatematching              0 undefined  undefined
templatematching tmextractcand         0 undefined undefined
tmextractcand     subtomoExtraction            0 undefined undefined
subtomoExtraction    EXIT                    0 undefined  undefined

