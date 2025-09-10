
from torch import nn
from fastai.data.transforms import Transform
from fastai.vision.all import ImageBlock,CategoryBlock, Resize
from fastai.data.block import noop
from fastai.data.transforms import FuncSplitter
from fastai.data.block import DataBlock
import PIL

class SmallSimpleCNN(nn.Module):
        def __init__(self):
            super(SmallSimpleCNN, self).__init__()
            self.conv1 = nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1)
            self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1)
            self.conv3 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
            self.conv4 = nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1)
            self.conv5 = nn.Conv2d(128, 256, kernel_size=3, stride=1, padding=1)
            self.fc1 = nn.Linear(256 * 12 * 12, 512)
            self.fc2 = nn.Linear(512, 512)
            self.fc3 = nn.Linear(512, 2)
            self.activationF = nn.ReLU()
            self.maxpool = nn.MaxPool2d(kernel_size=2, stride=2)
            
        def forward(self, x):
            x = self.activationF(self.conv1(x))
            x = self.maxpool(x)
            x = self.activationF(self.conv2(x))
            x = self.maxpool(x)
            x = self.activationF(self.conv3(x))
            x = self.maxpool(x)
            x = self.activationF(self.conv4(x))
            x = self.maxpool(x)
            x = self.activationF(self.conv5(x))
            x = self.maxpool(x)
            x = x.view(x.size(0), -1)
            x = self.activationF(self.fc1(x))
            x = self.activationF(self.fc2(x))
            x = self.fc3(x)
            return x
 
class ConvertToRGB(Transform):
    def encodes(self, img: PIL.Image.Image):
        return img.convert("RGB")
def get_datablockForPilImageStack(pilImageStack):
    """
    Create and return a DataBlock and vocabulary using the provided pilImageStack.
    
    Parameters:
        pilImageStack (list): A list of PIL Images.
    
    Returns:
        dblock (DataBlock): The DataBlock configured for this image list.
        vocab (list): The predefined vocabulary.
    """
    vocab = ['bad', 'good']
    dblock = DataBlock(
        blocks=(ImageBlock, CategoryBlock(vocab=vocab)),
        get_items=noop,  # Items are already in memory.
        splitter=FuncSplitter(lambda o: o is pilImageStack[0]),
        get_y=lambda o: vocab[0],  # Always return "Bad" (you can adjust as needed).
        item_tfms=[ConvertToRGB(), Resize(384)]
    )
    return dblock


class SmallSimpleCNNGray(nn.Module):
    def __init__(self):
        super(SmallSimpleCNNGray, self).__init__()
        # Increased number of filters in conv layers
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, stride=1, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        self.conv4 = nn.Conv2d(128, 256, kernel_size=3, stride=1, padding=1)
        self.bn4 = nn.BatchNorm2d(256)
        self.conv5 = nn.Conv2d(256, 512, kernel_size=3, stride=1, padding=1)
        self.bn5 = nn.BatchNorm2d(512)
        # New convolutional layer
        self.conv6 = nn.Conv2d(512, 1024, kernel_size=3, stride=1, padding=1)
        self.bn6 = nn.BatchNorm2d(1024)
        
        # Adjusted FC layers with updated input dimensions (now 1024*6*6)
        self.fc1 = nn.Linear(1024 * 6 * 6, 1024)
        self.dropout1 = nn.Dropout(0.5)
        self.fc2 = nn.Linear(1024, 512)
        self.dropout2 = nn.Dropout(0.5)
        self.fc3 = nn.Linear(512, 256)

        self.dropout3 = nn.Dropout(0.5)
        self.fc4 = nn.Linear(256, 2)

        self.activationF = nn.ReLU()
        #self.activationF = nn.Tanh()
        self.maxpool = nn.MaxPool2d(kernel_size=2, stride=2)
        
    def forward(self, x):
        x = self.activationF(self.bn1(self.conv1(x)))
        x = self.maxpool(x)
        x = self.activationF(self.bn2(self.conv2(x)))
        x = self.maxpool(x)
        x = self.activationF(self.bn3(self.conv3(x)))
        x = self.maxpool(x)
        x = self.activationF(self.bn4(self.conv4(x)))
        x = self.maxpool(x)
        x = self.activationF(self.bn5(self.conv5(x)))
        x = self.maxpool(x)
        # New convolutional layer in forward pass
        x = self.activationF(self.bn6(self.conv6(x)))
        x = self.maxpool(x)
        x = x.view(x.size(0), -1)
        x = self.dropout1(self.activationF(self.fc1(x)))
        x = self.dropout2(self.activationF(self.fc2(x)))

        x = self.dropout3(self.activationF(self.fc3(x)))
        x = self.fc4(x)

        return x

model = SmallSimpleCNNGray()

class ConvertToGray(Transform):
    def encodes(self, img: PIL.Image.Image):
        return img.convert("L")  # Convert to grayscale

def get_datablockForPilImageStackGray(pilImageStack):
    """
    Create and return a DataBlock and vocabulary using the provided pilImageStack.
    
    Parameters:
        pilImageStack (list): A list of PIL Images.
    
    Returns:
        dblock (DataBlock): The DataBlock configured for this image list.
        vocab (list): The predefined vocabulary.
    """
    vocab = ['bad', 'good']
    dblock = DataBlock(
        blocks=(ImageBlock, CategoryBlock(vocab=vocab)),
        get_items=noop,  # Items are already in memory.
        splitter=FuncSplitter(lambda o: o is pilImageStack[0]),
        get_y=lambda o: vocab[0],  # Always return "Bad" (you can adjust as needed).
        item_tfms=[ConvertToGray()]
    )
    return dblock
