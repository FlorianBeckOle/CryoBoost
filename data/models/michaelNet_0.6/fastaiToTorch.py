
from src.deepLearning.modelClasses import CustomDataset
from src.deepLearning.modelClasses import SmallSimpleCNN 
from fastai.vision.all import *
import torch

model='modelNativeFastAi.pkl'

torch.cuda.set_device(0) 
learnFastAi =load_learner(model)
torch_model = learnFastAi.model
torch.save(torch_model.state_dict(), 'model.pth')