=========
Tutorial
=========

Open CryoBoost
=================

.. code-block:: bash

   module load CRYOBOOST
   # or
   source /path/to/my/Folder/CryoBoost/.cbenv
   crboost_pipe.py -mov '/fs/pool/pool-bmapps/allSystem/appData/dataSets/copia/frames//Position_1*.eer' -m '/fs/pool/pool-bmapps/allSystem/appData/dataSets/copia/mdoc//Position_1*.mdoc' --proj testProj/copia26S --scheme "warp_tomo_prep" --species "copia,26S"
   
   #or without arguments
   crboost_pipe.py 

Adapt Tomogram Parameters
==========================

.. image:: img/setup.png

#. Click on Set Jobs to create the Job tabs.

#. Click on Auto to create a prefix.

#. Set Invert Tiltangel to No and Invert Defocus Hand to Yes.

#. Alignment: Set sample thickness to 180nm

#. Alignment: Switch off tiltaxis refinement (only 1 tomo)

#. Move to ParticleSetup_copia tap.


Adapt Copia Particle Parameters
================================

.. image:: img/particleSetupCopia.png

#. Click on Generate(Volume) to create a template

#. Click on Use Basic shape to create a sphere as template

#. Enter 3x the diamter (of copia) 550:550:550 and OK

#. Click exit

#. Click Generate(Mask) to create a Mask

#. Enter 5 for Extend 

#. Enter 5 for SoftEdge (Relion Mask parameters) and OK

#. Enter 90 as angular increment and

#. Enter 550 as diamter for peak extraction (avoid mult. extraction)

#. Enter 224 cropped (used) box size in pixels

#. Enter 384 uncropped box size in pixels

#. Move to ParticleSetup_26S tap.

Adapt 26S Particle Parameters
==============================

.. image:: img/particleSetup26S.png

#. Click on Generate(Volume) to create a template

#. Click on Fetch Pdb to download pdb from pdb www.rcsb.org

#. Enter 5GJR and click OK

#. Click Sim from Pdb to simulate em density from pdb with cistem's simulate

#. Click Gen And Exit to start the simulation

#. Click Exit

#. Click Generate(Mask) to create a Mask

#. Enter 5 for Extend  (Relion Mask parameters) 

#. Enter 6 for SoftEdge (Relion Mask parameters) and OK

#. Enter 12 to set Angular Increment

#. Enter 200 as diameter for peak extraction (half 26S diameter rod shape)

#. Enter 208 cropped box size in pixels

#. Enter 256 uncropped box size in pixels

#. Move to Start Relion tap.



Start WorkFlow
===============

.. image:: img/start.png

#. Click on Generate Project.

#. Click on Import Data.

#. Click on Start.


Check Results
=============

Tomograms:
imod External/job007/warp_tiltseries/reconstruction/deconv/Position_1_11.80Apx.mrc

.. image:: img/tomogramWarpDeconv.png


Processing Copia
================

click on open Relion 

++++++++++++++++++++++
Reconstruct Particle
++++++++++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set Extract/job12/optimisation_set.star
   Symmetry: I1
   Box size: 384
   Cropped Box size: 224
   Submit to queue: yes
   Threads: 24

++++++++++++++++++++++
Class3d 
++++++++++++++++++++++

generate a starting model good enough for mask creation
"one class classification is just faster and more stable for that purpose"

.. code-block:: bash
   
   Input: Optimisation Set Extract/job12/optimisation_set.star
   RefereceMap: Reconstruct/job016/merged.mrc
   Inital Lowpass Filter (A): 45
   Symmetry: I1
   Number of classes: 1
   Number of Iterations: 15
   Mask Diameter: 575
   Angular Sampling Interval: 3.75
   Pre-read all particles into RAM: yes
   Use GPU acceleration: yes
   Submit to queue: yes



++++++++++++++
Mask creation
++++++++++++++


.. code-block:: bash
   
   #Remove unstructured inner part
   cd myProjct
   module load EMAN
   e2proc3d.py Class3D/job017/run_it015_class001.mrc Class3D/job017/vol4Mask.mrc --process=mask.sharp:inner_radius=73
   #Now we use the masked map to generate a soft mask with relion
   Input 3d Map: Class3D/job017/vol4Mask.mrc 
   Lowpass: 18
   Inital binarisation threshold: 0.15
   Extend binary Map this many pixels: 5
   Add soft-edge of this many pixels: 7

.. figure:: img/maskCopia.png
   :width: 220px
   
   inner part removed


+++++++++
Refine3d
+++++++++


.. code-block:: bash
   
   #Local Refinement 1.8 deg of inital one class alingment
   Input Optimisation Set Class3D/job017/optimisation_set.star
   Reference Map:  Class3D/job017/run_it015_class001.mrc
   Reference Mask: MaskCreate/job018/mask.mrc 
   Mask Diameter: 575
   RefereceMap is on absolut grayscale: Yes
   Initial Lowpass Filter: 16
   Symmetry: I1
   Use solvent flattenned FSC: yes
   Inital angluar sampling: 1.8
   Inital offset range: 2
   Local searches from auto-sampling: 1.8
   Pre-read all particles into RAM: yes
   Use GPU acceleration: yes
   Submit to queue: yes



relion full command

.. container:: toggle  
   
   .. container:: content
     
      relion XXXX command



.. figure:: img/copiaRefindedIso.png
   :width: 220px
   
   8.5A resolution (should be below 10A)




++++++++++++++
Reconstruct
++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set Refine3d/job019/optimisation_set.star
   
   Symmetry: I1
   Pre-read all particles into RAM: yes
   Box size: 384
   Cropped Box size: 224
   Submit to queue: yes
   Threads: 24   


++++++++++++++++++
PostProcessing
++++++++++++++++++

.. code-block:: bash
   
   Reference Mask: MaskCreate/job018/mask.mrc 
   Unfiltered Map: Reconstruct/job20/half1.mrc
   

+++++++++++++++++
Bayesian Polish
+++++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set: Refine3d/job019/optimisation_set.star
   Reference Half Maps:  Reconstruct/job020/half1.mrc   
   Referece Mask: MaskCreate/job018/mask.mrc   
   Input PostProcess star: PostProcess/job021/post_process.star 
   Box Size: 256
   Max Position_error: 7
   Fit Per Particle Motion: yes
   Number of Threads: 24
   Submit to queue: yes
   Additional Arguments: --it 30000

+++++++++++++++
Extract 
+++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set: Polish/job022/optimisation_set.star
   Box Size: 384
   Cropped Box Size: 224   
   Submit to queue: yes
   Threads: 24


++++++++++++++
Reconstruct
++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set Extract/job023/optimisation_set.star
   Symmetry: I1
   Box size: 384
   Cropped Box size: 224
   Submit to queue: yes
   Threads: 24   


++++++++++++++++
PostProcessing
++++++++++++++++

.. code-block:: bash
   
   Unfiltered Map: Reconstruct/job024/half1.mrc   
   Reference Mask: MaskCreate/job018/mask.mrc 


+++++++++++++++
CTF Refinement
+++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set: Extract/job023/optimisation_set.star
   Reference Half Maps:  Reconstruct/job024/half1.mrc 
   Reference Mask: MaskCreate/job018/mask.mrc 
   Input PostProcess star: PostProcess/job25/post_process.star 
   Box size: 256
   Defocus Search Range: 6000
   Defocus Regularisation Lamda: 0.2
   Submit to queue: yes
   Threads: 24   

+++++++++++++++
Extract 
+++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set: CtfRefine/job026/optimisation_set.star
   Box Size: 384
   Cropped Box Size: 224   
   Threads: 24


++++++++++++++++++
Reconstruct
++++++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set Extract/job027/optimisation_set.star
   Symmetry: I1
   Box size: 384
   Cropped Box size: 224
   Submit to queue: yes
   Threads: 24      

++++++++++++++++
PostProcessing
++++++++++++++++

.. code-block:: bash
   
   Unfiltered Map: Reconstruct/job028/half1.mrc   
   Reference Mask: MaskCreate/job018/mask.mrc 

.. figure:: img/finalPostProcessing.png
   :width: 220px
   
   7.5A resolution (should be below 8.5A)





Processing 26S
================

++++++++++++++++++++++
Reconstruct Particle
++++++++++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set Extract/job015/optimisation_set.star
   
   Symmetry: C2
   Pre-read all particles into RAM: yes
   Box size: 256
   Cropped Box size: 208
   Submit to queue: yes
   Threads: 24

++++++++++++++
Mask creation
++++++++++++++

.. code-block:: bash
   
   Input 3d Map: Reconstruct/job030/merged.mrc 
   Lowpass: 20
   Inital binarisation threshold: 6
   Extend binary Map this many pixels: 12
   Add soft-edge of this many pixels: 8

++++++++++++++++++++++
Class3d
++++++++++++++++++++++

.. code-block:: bash
   
   Input: Optimisation Set Extract/job015/optimisation_set.star
   RefereceMap: Reconstruct/job030/merged.mrc
   Input Mask: MaskCreate/job031/mask.mrc
   Inital Lowpass Filter (A): 60
   Symmetry: C2
   Number of Iterations: 30
   Number of Classes: 9
   Angular Sampling Interval: 3.7
   Offset Search Range: 8
   Perform Local Angular Search: Yes
   Local Anguglar Search Range: 24
   Tau Fudge: 1.05
   Mask Diameter: 550
   Pre-read all particles into RAM: yes
   Use GPU acceleration: yes
   Submit to queue: yes

++++++++++++++++++++++
Subset selection
++++++++++++++++++++++

.. code-block:: bash
   
   #Select the "cleanest" 26S class
   Input: Optimisation Set Class3D/job32/optimisation_set.star


.. figure:: img/select26S.png
   :width: 220px
   
   


+++++++++
Refine3d
+++++++++

.. code-block:: bash
   
   Input Optimisation Set: 
   Input Particle List: Select/job033/particles.star
   Input Tomogram Set: External/job014/tomograms.star
   Reference Map:  Reconstruct/job030/merged.mrc
   Reference Mask: MaskCreate/job031/mask.mrc
   Mask Diameter: 510
   Initial Lowpass Filter: 60
   Symmetry: C2
   Use solvent flattened FSC: yes
   
   Pre-read all particles into RAM: yes
   Use GPU acceleration: yes
   Submit to queue: yes

++++++++++++++++++++++
Reconstruct Particle
++++++++++++++++++++++

.. code-block:: bash
   
   Input Optimisation Set Refine3d/job034/optimisation_set.star
   
   Symmetry: C2
   Box size: 256
   Cropped Box size: 208
   Submit to queue: yes
   Threads: 24

++++++++++++++++
PostProcessing
++++++++++++++++

.. code-block:: bash
   
   Unfiltered Map: Reconstruct/job035/half1.mrc   
   Reference Mask: MaskCreate/job031/mask.mrc 
   #should be below 40A

.. figure:: img/postProcessed26S.png
   :width: 220px
   
   37A resolution


Co-Refine both species in M 
============================

.. code-block:: bash



Add new data (from a new folder) to an existing project 
=======================================================

* If crboost_pipe.py was closed, open it again
   with the same project path and path to new frames and mdocs
   (here frames2 and mdoc2).
   
   .. code-block:: bash

      module load CRYOBOOST
      # or
      source /path/to/my/Folder/CryoBoost/.cbenv
      crboost_pipe.py --proj testProj/copia -mov '/fs/pool/pool-bmapps/allSystem/appData/dataSets/copia/frames2/*.eer' -m '/fs/pool/pool-bmapps/allSystem/appData/dataSets/copia/mdoc2/*.mdoc' --pixS 2.95
   
* If crboost_pipe.py is still running, move to Jobs and Set-Up and browse/adapt the path for the new frames and mdocs.

.. code-block:: none      
   
   frames: /fs/pool/pool-bmapps/allSystem/appData/dataSets/copia/frames2/*.eer
   mdoc: /fs/pool/pool-bmapps/allSystem/appData/dataSets/copia/mdoc2/*.mdoc


#. Move to Start Relion.

#. Click on Import Data.

#. Click on Start.