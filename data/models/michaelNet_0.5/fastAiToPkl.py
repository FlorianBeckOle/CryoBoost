import torch
import pickle
from fastai.learner import load_learner

torch.cuda.set_device(0)
model="modelNativeFastAi.pkl"
learn =load_learner(model)
with open('model.pkl', 'wb') as f:
       pickle.dump(learn, f)