=========
Setup
=========

Install Miniconda
=================
.. code-block:: bash

   targetFold=/path/to/my/pythonInstall
   wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
   chmod 755 Miniforge3-Linux-x86_64.sh
   ./Miniforge3-Linux-x86_64.sh -b -p $targetFold/conda3
   export PATH=$targetFold/conda3/bin/:$PATH
   source $targetFold/conda3/etc/profile.d/conda.sh 

Install dependencies
====================
.. code-block:: bash
   
   conda create -n cryoboost python=3.11.8
   conda activate cryoboost
   conda install nvidia/label/cuda-11.8.0::cuda-toolkit
   pip3 install torch==2.2.1  torchvision==0.17.1 torchaudio==2.2.1 --index-url https://download.pytorch.org/whl/cu118
   conda install -c fastai fastai==2.7.14
   pip3 install --ignore-installed torch==2.2.1 torchvision==0.17.1 torchaudio==2.2.1 --index-url https://download.pytorch.org/whl/cu118 --no-cache-dir
   pip install --force-reinstall numpy==1.26.3
   pip3 install pyqt6==6.7.0
   pip install starfile
   pip install biopython
   conda install -c conda-forge pymol-open-source
   conda install conda-forge::timm
   conda install seaborn mrcfile 
   pip install scikit-learn scikit-image
   pip install wget
   pip install napari     
   pip install --force-reinstall scipy==1.11.4 #downgrade needed on our system 
   #for local documentation use (optional)
   conda install sphinx sphinx_rtd_theme
   pip install sphinx-togglebutton     





Test torch and fastai installation
==================================
.. code-block:: bash
   
   python -c 'import torch; print(torch.cuda.is_available())'
   python -c 'import fastai; print(fastai.__version__)'


Install cryoboost
====================
.. code-block:: bash
   
   cd /path/to/my/Folder/
   git clone https://github.com/FlorianBeckOle/CryoBoost.git
   #get weights for bigger models
   wget -O CryoBoost/data/models/michaelNet_0.6/model.pth https://datashare.biochem.mpg.de/s/eaczrmib1ITjnnw/download

To start CryoBoost, the PATH, PYTHONPATH, CRYOBOOST_PYTHON_PATH(python intepreter), and CRYOBOOST_HOME need to be set.
Fot this, adapt the Environment in the /path/to/my/Folder/CryoBoost/conf/conf.yaml (required for remote execution), and
the /path/to/my/Folder/CryoBoost/.cbenv file as shown below. 
Then source .cbenv before starting CryoBoost.


Configure /path/to/my/Folder/CryoBoost/config/conf.yaml
=======================================================
.. code-block:: yaml
   
   Environment: "module load RELION/5.0-beta-3NC;source /path/to/my/Folder/CryoBoost/.cbenv"

Adapt /path/to/my/Folder/CryoBoost/.cbenv
==========================================
.. code-block:: bash   
   
   export CRYOBOOST_HOME=/path/to/my/Folder/CryoBoost/
   export CRYOBOOST_PYTHON_PATH=/path/to/my/pythonInstall/conda3/envs/cryoboost/bin/python
   export PYTHONPATH=$CRYOBOOST_HOME
   export PATH=$CRYOBOOST_HOME/bin:$PATH

Adapt /path/to/my/Folder/CryoBoost/config/qsub/*.sh
==========================================
.. code-block:: bash   
   
   source /path/to/my/Folder/CryoBoost/.cbenv
   


Further requiremets
=================

* check if you can login to the submission node without password (if not, see ssh-keygen in Wiki)

.. code-block:: bash
   
   ssh hpcl8001



Generate local documentation (optional)
=======================================
.. code-block:: bash
   
   cd /path/to/my/installationFolder/cryoboost
   cd docs
   make html
   
   
