
from fastai.learner import load_learner
from fastai.vision.utils import get_image_files
from torch.utils.data import DataLoader
from fastai.vision.core import PILImage,ToTensor
from fastai.vision.data import ImageDataLoaders
from fastai.vision.augment import Normalize
from fastai.vision.data import imagenet_stats
from fastai.vision.all import vision_learner
from fastai.vision.all import xresnet18
from fastai.metrics import accuracy,error_rate
from torch import nn
from torch import torch
from pathlib import Path
import matplotlib.pyplot as plt
import timm
import seaborn as sns
from sklearn.metrics import precision_score, recall_score, accuracy_score,f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import confusion_matrix
from tqdm import tqdm
from starfile import read as starread   
import mrcfile
from PIL import Image
import os
from concurrent.futures import ProcessPoolExecutor
from skimage.transform import resize
import numpy as np
import pandas as pd
from scipy.fft import fft2, ifft2, fftshift, ifftshift
import pickle



def mrc_to_pil_image(mrc_path,sz):
    """
    Convert an MRC file to a PIL Image object.

    Parameters:
    - mrc_path: Path to the MRC file.

    Returns:
    - A PIL Image object.
    """
    
    with mrcfile.open(mrc_path, permissive=True) as mrc:
        image_array = mrc.data
        from skimage.transform import resize
        image_array = resize(image_array, (sz, sz), anti_aliasing=True)
        image_array = (image_array -image_array.mean())
        if image_array.std() != 0:
            image_array=image_array / image_array.std()
        # Convert to uint8 if the image is not in this format. Adjust according to your data range.
        image_array = (image_array - image_array.min()) / (image_array.max() - image_array.min()) * 255.0
        image_array = image_array.astype('uint8')
        # Create a PIL Image from the NumPy array
        pil_image = Image.fromarray(image_array)
        return pil_image


def getTiltImagePathFromTiltStar(pathToStarFile: str, pathToRelionProj: str) -> pd.Series:
    """
    Reads a RELION tilt series STAR file and returns a pandas Series containing the paths to the tilt images.

    Parameters:
    - pathToStarFile (str): Path to the RELION tilt series STAR file.
    - pathToRelionProj (str): Path to the RELION project folder.

    Returns:
    - A pandas Series containing the paths to the tilt images.
    """
    st = starread(pathToStarFile)
    tilts = pd.Series([])
    for ts in st["rlnTomoTiltSeriesStarFile"]:
        stts = starread(os.path.join(pathToRelionProj, ts))
        #tmp = os.path.join(pathToRelionProj, stts["rlnMicrographName"])
        tmp=pathToRelionProj + "/" + stts['rlnMicrographName']
        tilts = pd.concat([tilts, tmp])

    return tilts, len(st)


def resize_by_fourier_cropping(image_array, new_shape):
    
    f_transform = fft2(image_array)
    f_transform_shifted = fftshift(f_transform)
    current_shape = f_transform_shifted.shape
    resized_f_transform_shifted = np.zeros(new_shape, dtype=f_transform_shifted.dtype)
    center_current = [dim // 2 for dim in current_shape]
    center_new = [dim // 2 for dim in new_shape]
    slices_current = [slice(center - min(center, new_center), center + min(center, new_center)) 
                      for center, new_center in zip(center_current, center_new)]
    slices_new = [slice(new_center - min(center, new_center), new_center + min(center, new_center)) 
                  for center, new_center in zip(center_current, center_new)]
    resized_f_transform_shifted[tuple(slices_new)] = f_transform_shifted[tuple(slices_current)]
    resized_f_transform = ifftshift(resized_f_transform_shifted)
    resized_image_array = ifft2(resized_f_transform).real
    #resized_image_array = np.clip(resized_image_array, 0, 255)
    #resized_image_array = resized_image_array.astype(np.uint8)

    return resized_image_array


def mrc_to_pil_image_parallel(mrc_path_sz_pngOutputFold):
    """
    Convert an MRC file to a PIL Image object. This function is designed to be called in parallel.
    
    Parameters:
    - mrc_path_sz: A tuple containing the MRC file path and the target size (sz).
    
    Returns:
    - A PIL Image object.
    """
    mrc_path, sz,ignoreNonSquare,pngOutputFold = mrc_path_sz_pngOutputFold
    with mrcfile.open(mrc_path, permissive=True) as mrc:
        image_array = mrc.data
        # print("in mrc paralell:" + pngOutputFold)
        if pngOutputFold is not None:
            image_array_tmp=image_array.astype(np.float32)
            meanT = np.mean(image_array_tmp)
            stdT = np.std(image_array_tmp)
            maskT=image_array_tmp>(meanT+(4*stdT))
            image_array_tmp[maskT]=meanT
            image_array_tmp = (image_array - image_array.min()) / (image_array.max() - image_array.min())
            image_array_tmp = (image_array_tmp * 255).astype(np.uint8)
            namepng = os.path.splitext(os.path.basename(mrc_path))[0]
            Image.fromarray(image_array_tmp).save(pngOutputFold+os.path.sep+namepng+".png")

            
        ratio=max(image_array.shape)/min(image_array.shape)
        imgIsNonSquare=min(image_array.shape)!=max(image_array.shape)
        
        if imgIsNonSquare and ignoreNonSquare==0:
            #print("in ns0")
            image_arrayOrg=image_array
            min_dimension = min(image_array.shape)
            crop_size = min_dimension#
            start_x = 0+30 # (image_array.shape[0] - crop_size) // 2
            start_y = 0+30 #(image_array.shape[1] - crop_size) // 2
            image_array = image_array[start_x:start_x + crop_size-30, start_y:start_y + crop_size]
            #print("shape0",image_array.shape)
         
        if imgIsNonSquare and ignoreNonSquare==1:
            image_array=resize_by_fourier_cropping(image_array,[sz,round(sz*ratio)])
            #image_array = resize(image_array, (sz, round(sz*ratio)), anti_aliasing=True)
        else:
            image_array=resize_by_fourier_cropping(image_array,[sz,sz])
    
        if pngOutputFold is not None:
            if imgIsNonSquare:
                image_array_tmp = resize_by_fourier_cropping(image_array,[sz,round(sz*ratio)])
            else:
                image_array_tmp = image_array
            image_array_tmp = (image_array_tmp - image_array_tmp.min()) / (image_array_tmp.max() - image_array_tmp.min())
            image_array_tmp = (image_array_tmp * 255).astype(np.uint8)
            namepng = os.path.splitext(os.path.basename(mrc_path))[0]
            Image.fromarray(image_array_tmp).save(pngOutputFold+os.path.sep+namepng+".png")
        
            
        image_array = (image_array - image_array.mean())
        if image_array.std() != 0:
            image_array = image_array / image_array.std()
        image_array = (image_array - image_array.min()) / (image_array.max() - image_array.min()) * 255.0
        image_array = image_array.astype('uint8')
        
        if imgIsNonSquare and ignoreNonSquare==0:
            pil1 = Image.fromarray(image_array)
        else:
            pil_image=Image.fromarray(image_array)
            return pil_image
          
        if imgIsNonSquare:
            image_array=image_arrayOrg
            min_dimension = min(image_array.shape)
            crop_size = min_dimension#
            start_x =0+30
            start_y = (image_array.shape[1] - crop_size) #-20#// 2
            image_array = image_array[start_x:start_x + crop_size-30, start_y:start_y + crop_size-30]
            #print("shape1",image_array.shape)
            image_array=resize_by_fourier_cropping(image_array,[sz,sz])
            image_array = (image_array - image_array.mean())
            if image_array.std() != 0:
                image_array = image_array / image_array.std()
            image_array = (image_array - image_array.min()) / (image_array.max() - image_array.min()) * 255.0
            image_array = image_array.astype('uint8')
            pil2 = Image.fromarray(image_array)
           
            return pil1,pil2

def mrcFilesToPilImageStackParallel(mrcFiles, sz, max_workers=20,ignoreNonSquare=0,pngOutputPath=None):
    """
    Convert MRC files to PIL Image objects in parallel.
    
    Parameters:
    - mrcFiles: A list of paths to MRC files.
    - sz: Target size for the PIL images.
    
    Returns:
    - A list of PIL Image objects.
    """
    
    with ProcessPoolExecutor(max_workers) as executor:
        pil_images = list(executor.map(mrc_to_pil_image_parallel, [(mrc_path, sz,ignoreNonSquare,pngOutputPath) for mrc_path in mrcFiles]))
    return pil_images


def predictPilImageStack(pilImageStack,learn):
    """
    Predict the class of a PIL image stack using a fastai learner.

    Parameters:
    - pilImageStack (PIL Image): The PIL image stack to predict.
    - learn (fastai learner): The fastai learner to use for prediction.
    
    Returns:
    - tuple: A tuple containing the predicted labels and probabilities.
    """
        
    
    has_testdl=hasattr(learn.dls, 'test_dl')    
    if has_testdl:
        print("  using direct test_dl")
        test_dl = learn.dls.test_dl(pilImageStack, with_labels=False,batch_tfms=Normalize.from_stats(*imagenet_stats))
    else:
        print("  using dablock to create test_dl")
        from src.deepLearning.modelClasses import get_datablockForPilImageStackGray
        dblock=get_datablockForPilImageStackGray(pilImageStack)
        dls = dblock.dataloaders(pilImageStack,with_labels=False,batch_tfms=Normalize.from_stats(*imagenet_stats))
        test_dl = dls.test_dl(pilImageStack)
    
    preds, _ = learn.get_preds(dl=test_dl)
    pred_probs = [max(pred).item() for pred in preds]
    
    if max(pred_probs)<1.01:
        decoded_preds = preds.argmax(dim=-1)
        pred_labels = [learn.dls.vocab[pred] for pred in decoded_preds]
    else:
        from torch.nn import functional as F
        probs = F.softmax(preds, dim=1)
        decoded_preds = probs.argmax(dim=-1)
        pred_labels = [learn.dls.vocab[pred] for pred in decoded_preds]
        pred_probs = [float(prob.max()) for prob in probs]
    
    return pred_labels,pred_probs
    

def predict_tilts(ts,model,sz=384,batchSize=50,gpu=0,probThr=0.1,probAction="assingToGood",max_workers=20,pngOutPutPath=None,modelType='byExtension'):
    """
    Predict the class of a PIL image stack using a fastai learner.

    Parameters:
    pilImageStack (PIL Image): The PIL image stack to predict.
    learn (fastai learner): The fastai learner to use for prediction.

    Returns:
    tuple: A tuple containing the predicted labels and probabilities.
    """
    
    tiltspath=ts.getMicrographMovieNameFull()
    print("found:",str(len(tiltspath)),"tilts from",str(ts.nrTomo),'tomograms')
     
    nrBatch=round(len(tiltspath)/batchSize)
    if nrBatch<1:
        nrBatch=1
    
    batches = np.array_split(tiltspath,nrBatch )
    all_pLabels = []
    all_pProb = []
    
    torch.cuda.set_device(gpu) 
    print("loading model:",model)
    _,modelExt=os.path.splitext(model)
    
    if modelExt==".pkl":
        with open(model, 'rb') as f:
            learn = pickle.load(f)
    if modelExt==".pth":
        from fastai.vision.all import Learner
        from src.deepLearning.modelClasses import get_datablockForPilImageStackGray
        from src.deepLearning.modelClasses import SmallSimpleCNNGray
        pytorch_model = SmallSimpleCNNGray()
        pytorch_model.load_state_dict(torch.load(model))
        pilImageStack=mrcFilesToPilImageStackParallel(batches[0],sz,max_workers,ignoreNonSquare=0,pngOutputPath=None)
        dblock=get_datablockForPilImageStackGray(pilImageStack)
        dls = dblock.dataloaders(pilImageStack,with_labels=False)#,batch_tfms=Normalize.from_stats(*imagenet_stats))
        learn = Learner(dls=dls, model=pytorch_model, loss_func=nn.CrossEntropyLoss())    
    
    _=learn.model.eval()
    
    
    for i, batch in enumerate(tqdm(batches, desc="Predicting Tilts"), 1):
        pilImageBatch=mrcFilesToPilImageStackParallel(batch,sz,max_workers,ignoreNonSquare=0,pngOutputPath=pngOutPutPath)
        
        if isinstance(pilImageBatch[0], tuple):
            ib0=[]
            ib1=[]
            for item in pilImageBatch:
                ib0.append(item[0])
                ib1.append(item[1])
            
            pLables0,pProb0=predictPilImageStack(ib0,learn)
            pLables1,pProb1=predictPilImageStack(ib1,learn)
            pLables=[]
            pProb=[]
            for i in range(len(pLables0)):
                if pLables0[i] == 'good' and pLables1[i] == 'good':
                    pLables.append('good')
                    pProb.append((pProb0[i]+pProb1[i])/2)
                else:
                    pLables.append('bad')
                    if pLables0[i] == 'bad':
                        pProb.append(pProb0[i])
                    else:
                        pProb.append(pProb1[i])    
        else:
            pLables,pProb=predictPilImageStack(pilImageBatch,learn)
        
        all_pLabels.extend(pLables)
        all_pProb.extend(pProb)
    
    png_list = [pngOutPutPath + os.path.sep + os.path.splitext(os.path.basename(x))[0] + '.png' for x in ts.all_tilts_df['rlnMicrographName']]
    for i, p in enumerate(all_pProb):
        if (p < float(probThr)):
            if (probAction=="assignToGood"):
                all_pLabels[i] = "good"
            else:
                all_pLabels[i] = "bad"    
        
    df = pd.DataFrame({
    'cryoBoostDlLabel': all_pLabels,
    'cryoBoostDlProbability': all_pProb,
    'cryoBoostKey': tiltspath,
    'cryoBoostPNG': png_list
    })
    
    ts.addColumns(df)
        
    return ts 
        