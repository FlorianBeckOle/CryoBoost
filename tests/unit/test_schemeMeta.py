from src.rw.librw import schemeMeta
import shutil,os
import pandas as pd
from collections import namedtuple

 
def test_readScheme():
    inputScheme='config/Schemes/relion_tomo_prep/'
    sc=schemeMeta(inputScheme)
    assert (sc.jobs_in_scheme == ['importmovies', 'motioncorr', 
                                 'ctffind','filtertilts','filtertiltsInter', 
                                 'aligntilts', 'reconstructionsplit','denoisetrain','denoisepredict','reconstructionfull','templatematching','tmextractcand','subtomoExtraction']).all()

def test_writeScheme():
    inputScheme='config/Schemes/relion_tomo_prep/'
    output = 'tmpOut/testScheme/'
    
    if ((output[0]!='/') and ('tmpOut' in output) and os.path.exists(output)): 
        shutil.rmtree(output)
        
    sc=schemeMeta(inputScheme)
    sc.write_scheme(output)
    scnew=schemeMeta(output)
    
    assert (sc.jobs_in_scheme == scnew.jobs_in_scheme).all()   
    for job in sc.jobs_in_scheme:
        assert (sc.job_star[job].dict['joboptions_values'] == scnew.job_star[job].dict['joboptions_values']).all().all()
 
def test_filterScheme():
    inputScheme='config/Schemes/relion_tomo_prep/'
    #nodesToFilter={0:"importmovies",1:"motioncorr",2:"ctffind",
    #            3:"aligntilts",4:"reconstructionsplit"}
    nodes = []
    Node = namedtuple('Node', ['type', 'tag', 'inputType', 'inputTag'])
    oneNode = Node(type="importmovies", tag=None, inputType=None, inputTag=None)
    nodes.append(oneNode)
    oneNode = Node(type="motioncorr", tag=None, inputType=None, inputTag=None)
    nodes.append(oneNode)
    
    nodes_dict = {i: node for i, node in enumerate(nodes)}   
    nodes_df = pd.DataFrame.from_dict(nodes_dict, orient='index')
    sc=schemeMeta(inputScheme)
    scFilt=sc.filterSchemeByNodes(nodes_df)
    
    
    assert list(nodes_df.type) == list(scFilt.jobs_in_scheme)     

    