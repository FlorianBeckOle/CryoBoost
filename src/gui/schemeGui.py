import sys
import os
import pandas as pd
import glob,random  
from PyQt6 import QtWidgets
from PyQt6.QtGui import QTextCursor
from PyQt6.uic import loadUi
from PyQt6.QtWidgets import QDialog,QTableWidget,QScrollArea,QTableWidgetItem, QVBoxLayout, QApplication, QMainWindow,QMessageBox,QWidget,QLineEdit,QComboBox,QRadioButton,QCheckBox,QSizePolicy 
from PyQt6.QtCore import Qt,QSignalBlocker
from src.pipe.libpipe import pipe
from src.rw.librw import starFileMeta,mdocMeta
from src.misc.system import run_command_async
from src.gui.libGui import get_user_selection,externalTextViewer,browse_dirs,browse_files,checkDosePerTilt,browse_filesOrFolders,change_values,change_bckgrnd,checkGainOptions,get_inputNodesFromSchemeTable,messageBox 
from src.gui.libGui import MultiInputDialog,statusMessageBox
from src.misc.libmask import genMaskRelion,caclThreshold
from src.rw.librw import schemeMeta,cbconfig,read_mdoc,importFolderBySymlink
from src.gui.edit_scheme import EditScheme
from src.gui.quick_setup import quickSetup
from src.gui.generateTemplate import TemplateGen
from src.misc.libimVol import processVolume
from src.misc.eerSampling import get_EERsections_per_frame
import subprocess, shutil
from PyQt6.QtCore import QTimer 
import mrcfile
import datetime

current_dir = os.path.dirname(os.path.abspath(__name__))
# change the path to be until src
root_dir = os.path.abspath(os.path.join(current_dir, '../'))
sys.path.append(root_dir)

#from lib.functions import get_value_from_tab

class MainUI(QMainWindow):
    """
    Main window of the UI.
    """
    def __init__(self,args):
        """
        Setting up the buttons in the code and connecting them to their respective functions.
        """ 
        super(MainUI, self).__init__()
        loadUi(os.path.abspath(__file__).replace('.py','.ui'), self)
       
        self.system=self.selSystemComponents()
        self.cbdat=self.initializeDataStrcuture(args)
        if (self.cbdat is None):
            QApplication.instance().quit()
            sys.exit()
            return
        self.setCallbacks()
        self.adaptWidgetsToJobsInScheme()
        self.genSchemeTable()
        
        self.groupBox_WorkFlow.setEnabled(False)
        self.groupBox_Setup.setEnabled(False)
        #self.groupBox_Project.setEnabled(False)
        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.setTabVisible(1, False)
        
        if (self.cbdat.args.autoGen or self.cbdat.args.skipSchemeEdit):
            self.makeJobTabsFromScheme()
    
    def adaptWidgetsToJobsInScheme(self):
        
        if "fsMotionAndCtf" in self.cbdat.scheme.jobs_in_scheme.values:
            self.dropDown_gainRot.clear()  # This will remove all items from the dropdown
            self.dropDown_gainRot.addItem("No transpose")
            self.dropDown_gainRot.addItem("Transpose")
        
         
    def selSystemComponents(self):
        system = type('', (), {})() 
        if shutil.which("zenity") is None:
           system.filebrowser="qt"
        else:   
           system.filebrowser="zenity"
        return system
                
    def initializeDataStrcuture(self,args):
        #custom varibales
        cbdat = type('', (), {})() 
        cbdat.CRYOBOOST_HOME=os.getenv("CRYOBOOST_HOME")
        warpSchemeExists=os.path.exists(str(args.proj) +  "/Schemes/" + "warp_tomo_prep" + "/scheme.star")
        relioSchemeExists=os.path.exists(str(args.proj) +  "/Schemes/" + "relion_tomo_prep" + "/scheme.star")
        if relioSchemeExists:
            args.scheme="relion_tomo_prep"
        if warpSchemeExists:
            args.scheme="warp_tomo_prep"
        
        if args.numInputArgs > -1 and not (warpSchemeExists or relioSchemeExists):
            dialog = quickSetup(args)
            res=dialog.exec()
            args=dialog.getResult()
            if args is None:
                print("cancelled quick setup")
                cbdat= None
                return cbdat
            
        if args.scheme=="gui":
            args.scheme=get_user_selection()
        if args.scheme=="relion_tomo_prep" or args.scheme=="default":      
            cbdat.defaultSchemePath=cbdat.CRYOBOOST_HOME + "/config/Schemes/relion_tomo_prep/"
        if args.scheme=="warp_tomo_prep":
            cbdat.defaultSchemePath=cbdat.CRYOBOOST_HOME + "/config/Schemes/warp_tomo_prep/"
        if args.scheme=="browse":
            cbdat.defaultSchemePath=browse_dirs(target_field=None,target_fold=None,dialog=self.system.filebrowser)
           
        cbdat.confPath=cbdat.CRYOBOOST_HOME + "/config/conf.yaml"
        cbdat.pipeRunner= None
        cbdat.conf=cbconfig(cbdat.confPath)     
        cbdat.localEnv=cbdat.conf.confdata['local']['Environment']+";"
        cbdat.args=args
        cbdat.filtScheme=1
        if os.path.exists(str(args.proj) +  "/Schemes/" + args.scheme + "/scheme.star"):
            print("WARNING missing reload of options")
            print("======> check mdoc invert")
            print("WARNING missing reload of options")
            cbdat.scheme=schemeMeta(args.proj +  "/Schemes/" + args.scheme )
            args.scheme=cbdat.scheme
            invTilt=self.textEdit_invertTiltAngle.toPlainText()
            if invTilt == "Yes":
                invTilt=True
            else:
                invTilt=False
            cbdat.pipeRunner=pipe(args,invMdocTiltAngle=invTilt);
            cbdat.args.skipSchemeEdit=True
            cbdat.filtScheme=0
        else:    
            cbdat.scheme=schemeMeta(cbdat.defaultSchemePath)
            if args.Noise2Noise == "False":
                cbdat.scheme=cbdat.scheme.removeNoiseToNoiseFilter()
            if args.FilterTilts == "False":
                cbdat.scheme=cbdat.scheme.removefilterTiltsJobs()
            if args.species != "noTag" and args.species != "None":
                speciesList = [x.strip() for x in args.species.split(',')]
                cbdat.scheme=cbdat.scheme.addParticleJobs(speciesList) 
            if args.species == "None":
                cbdat.scheme=cbdat.scheme.removeParticleJobs()
                   
        
        return cbdat
    
    def setCallbacks(self):
        self.btn_makeJobTabs.clicked.connect(self.makeJobTabsFromScheme)
        #self.groupBox_in_paths.setEnabled(False)
        self.line_path_movies.textChanged.connect(self.setPathMoviesToJobTap)
        self.line_path_mdocs.textChanged.connect(self.setPathMdocsToJobTap)
        self.line_path_mdocs.textChanged.connect(self.updateTomogramsForTraining)
        self.line_path_gain.textChanged.connect(self.setPathGainToJobTap)
        self.line_path_new_project.textChanged.connect(self.updateLogViewer)
        self.line_path_crImportPrefix.textChanged.connect(self.updateTomogramsForTraining)
        self.dropDown_gainRot.activated.connect(self.setGainRotToJobTap)
        self.dropDown_gainFlip.activated.connect(self.setGainFlipJobTap)
        self.textEdit_pixelSize.textChanged.connect(self.setPixelSizeToJobTap)
        self.textEdit_dosePerTilt.textChanged.connect(self.setdosePerTiltToJobTap)
        self.textEdit_nomTiltAxis.textChanged.connect(self.setTiltAxisToJobTap)
        
        #self.textEdit_invertTiltAngle.textChanged.connect(self.setInvertTiltAngleToJobTap)
        self.textEdit_invertDefocusHand.textChanged.connect(self.setInvertDefocusHandToJobTap)
        
        self.textEdit_eerFractions.textChanged.connect(self.setEerFractionsToJobTap)
        self.textEdit_areTomoSampleThick.textChanged.connect(self.setAreTomoSampleThickToJobTap)
        
        self.textEdit_areTomoPatch.textChanged.connect(self.setAreTomoPatchToJobTap)
        self.textEdit_algRescaleTilts.textChanged.connect(self.setAlgRescaleTiltsJobTap)
        
        self.textEdit_ImodPatchSize.textChanged.connect(self.setImodPatchSizeToJobTap)
        self.textEdit_imodPatchOverlap.textChanged.connect(self.setImodPatchOverlapToJobTap)
        
        self.textEdit_refineTiltAxisNrTomo.textChanged.connect(self.setTiltAxisRefineParamToJobTap)
        self.textEdit_refineTiltAxisIter.textChanged.connect(self.setTiltAxisRefineParamToJobTap)
        self.dropDown_doRefineTiltAxis.activated.connect(self.setTiltAxisRefineParamToJobTap)
        
        self.dropDown_tomoAlignProgram.activated.connect(self.setTomoAlignProgramToJobTap)
        self.btn_openWorkFlowLog.clicked.connect(self.openExtLogViewerWorkFlow)
        self.btn_openWorkFlowLog.clicked.connect(self.openExtLogViewerWorkFlow)
        self.btn_openJobOutpuLog.clicked.connect(self.openExtLogViewerJobOutput)
        self.btn_openJobErrorLog.clicked.connect(self.openExtLogViewerJobError)
        #self.textBrowser_workFlow.clicked.connect(self.openExtLogViewer) 
        self.btn_browse_movies.clicked.connect(self.browsePathMovies)
        self.btn_browse_mdocs.clicked.connect(self.browsePathMdocs)
        self.btn_browse_denoisingModel.clicked.connect(self.browseDenoisingModel)
        self.textEdit_tomoForDenoiseTrain.textChanged.connect(self.setTomoForDenoiseTrainToJobTap)
        self.textEdit_pathDenoiseModel.textChanged.connect(self.setPathDenoiseModelToJobTap)
        self.textEdit_modelForFilterTilts.textChanged.connect(self.setmodelForFilterTiltsToJobTap)
        self.textEdit_probThr.textChanged.connect(self.setProbThrToJobTap)
        self.dropDown_FilterTiltsMode.activated.connect(self.setFilterTiltsModeToJobTap)
        self.textEdit_recVoxelSize.textChanged.connect(self.setRecVoxelSizeToJobTap)
        self.textEdit_recTomosize.textChanged.connect(self.setRecTomosizeToJobTap)
        self.btn_browse_gain.clicked.connect(self.browsePathGain)
        self.btn_browse_autoPrefix.clicked.connect(self.generatePrefix)
        self.btn_use_movie_path.clicked.connect(self.mdocs_use_movie_path)
        self.dropDown_config.activated.connect(self.loadConfig)
        self.dropDown_probThrBehave.activated.connect(self.setProbBehaveToJobTab)
        self.btn_browse_target.clicked.connect(self.browsePathTarget)
        self.btn_genProject.clicked.connect(self.generateProject)
        self.btn_updateWorkFlow.clicked.connect(self.updateWorkflow)    
        self.btn_importData.clicked.connect(self.importData)
        self.btn_startWorkFlow.clicked.connect(self.startWorkflow)
        self.btn_showClusterStatus.clicked.connect(self.showClusterStatus)
        self.checkBox_openRelionGui.stateChanged.connect(self.openRelionGui)
        self.btn_stopWorkFlow.clicked.connect(self.stopWorkflow)
        self.btn_unlockWorkFlow.clicked.connect(self.unlockWorkflow)
        self.btn_resetWorkFlow.clicked.connect(self.resetWorkflow)
        self.btn_resetWorkFlowHead.clicked.connect(self.resetWorkflowHead)
        self.dropDown_nrNodes.activated.connect(self.setNrNodesToJobTap)
        self.dropDown_partitionName.activated.connect(self.setNrNodesToJobTap)
        self.checkBox_shareNodes.stateChanged.connect(self.setNrNodesToJobTap)
        self.dropDown_nrNodes.setCurrentIndex(2)
        self.dropDown_jobSize.setCurrentIndex(1)
        self.dropDown_jobSize.activated.connect(self.setNrNodesFromJobSize)
        for i in self.cbdat.conf.microscope_presets:
            self.dropDown_config.addItem(self.cbdat.conf.microscope_presets[i])
        self.dropDown_config.setCurrentIndex(0)
        self.btn_scheduleJobs.clicked.connect(self.scheduleJobs)
        
    def genSchemeTable(self):
        self.table_scheme.setColumnCount(1) #origianlly 4
        self.labels_scheme = ["Job Name"] #, "Fork", "Output if True", "Boolean Variable"]
        self.table_scheme.setHorizontalHeaderLabels(self.labels_scheme) 
        self.table_scheme.setRowCount(len(self.cbdat.scheme.jobs_in_scheme))    
        for i, job in enumerate(self.cbdat.scheme.jobs_in_scheme):
            self.table_scheme.setItem(i, 0, QTableWidgetItem(str(job))) 
            self.table_scheme.setItem(i, 1, QTableWidgetItem())
            #self.table_scheme.item(i, 1).setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            #self.table_scheme.item(i, 1).setCheckState(Qt.CheckState.Unchecked)
            #self.table_scheme.setItem(i, 2, QTableWidgetItem(str("undefined")))
            #self.table_scheme.setItem(i, 3, QTableWidgetItem(str("undefined")))
            
    def makeJobTabsFromScheme(self):
        """
        insert a new tab for every job and place a table with the parameters found in the respective job.star
        file in the ["joboptions_values"] df.
        """
        
        self.tabWidget.setTabVisible(1,True)
        
        if ((self.check_edit_scheme.isChecked()) and (self.cbdat.args.autoGen == False) and (self.cbdat.args.skipSchemeEdit == False)):
            try:
                dialog=EditScheme(self.cbdat.scheme)
                res=dialog.exec()
                newScheme=dialog.getResult()
                if newScheme is not None:
                    self.cbdat.scheme = newScheme
                else:
                    return        
                self.genSchemeTable()
            except Exception as e:
                messageBox(title="Error", text="Error while editing scheme")
                print(e)
                return
        else:
            pass
            # inputNodes,inputNodes_df=get_inputNodesFromSchemeTable(self.table_scheme,jobsOnly=True)
            # if self.cbdat.filtScheme:
            #     self.cbdat.scheme=self.cbdat.scheme.filterSchemeByNodes(inputNodes_df)
       
        self.genParticleSetups()        
       
        insertPosition=self.jobTapNrSetUpTaps
        for job in self.cbdat.scheme.jobs_in_scheme:
           self.schemeJobToTab(job,self.cbdat.conf,insertPosition)
           insertPosition += 1 

        self.groupBox_WorkFlow.setEnabled(True)
        self.groupBox_Setup.setEnabled(True)
        self.groupBox_Project.setEnabled(True)
        
        
        if (self.cbdat.args.mdocs != None):
            self.line_path_mdocs.setText(self.cbdat.args.mdocs)
        if (self.cbdat.args.movies != None):
             self.line_path_movies.setText(self.cbdat.args.movies)
        if (self.cbdat.args.proj != None):
             self.line_path_new_project.setText(self.cbdat.args.proj)
        if (self.cbdat.args.pixS != None):
             self.textEdit_pixelSize.setText(self.cbdat.args.pixS)
        if (self.cbdat.args.gain != None):
            if not os.path.isfile(self.cbdat.args.gain):
                raise Exception("file not found: "+self.cbdat.args.gain)
            if not os.path.isabs(self.cbdat.args.gain):
                self.line_path_gain.setText(os.path.abspath(self.cbdat.args.gain)) 
            else:
                self.line_path_gain.setText(self.cbdat.args.gain)
        if "denoisetrain" in self.cbdat.scheme.jobs_in_scheme.values  or "denoisepredict" in self.cbdat.scheme.jobs_in_scheme.values:
            pass
            #params_dict = {"generate_split_tomograms": "Yes" }
            #self.setParamsDictToJobTap(params_dict)
        self.loadConfig()
        self.btn_makeJobTabs.setEnabled(False)
        
    def genParticleSetups(self):
        
        self.jobTapNrSetUpTaps=1
        #self.tabWidget.removeTab(self.jobTapNrSetUpTaps)
        self.widgets = [] 
        self.layouts = []
        for job in self.cbdat.scheme.jobs_in_scheme:
            if job.startswith("templatematching"):
                
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                
                container_widget = QtWidgets.QWidget()
                scroll_area.setWidget(container_widget)
                layout = QVBoxLayout(container_widget)
                layout.setSpacing(1)
                layout.setContentsMargins(1,1, 1, 1)
                self.layouts.append(layout)
                tag=job.split("_")
                if len(tag)>1:
                    tabName="ParticleSetup_"+tag[1]
                else:
                    tabName="ParticleSetup"
                
                widget=self.iniWidget(job)
                layout.addWidget(widget,stretch=0)
                self.widgets.append(widget)
                scroll_area.setWidget(container_widget)
                self.tabWidget.insertTab(self.jobTapNrSetUpTaps, scroll_area, tabName)
                self.jobTapNrSetUpTaps+=1   

            if job.startswith("tmextractcand"):    
                widget=self.iniWidget(job)
                layout.addWidget(widget,stretch=0)             
            
            if job.startswith("subtomoExtraction"):    
                widget=self.iniWidget(job)
                layout.addWidget(widget,stretch=0)  
        
        for layout in self.layouts:   
            spacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
            layout.addItem(spacer)    
                                    
                
    def iniWidget(self,jobName):             
        
        if len(jobName.split('_'))>1:
            jobName=jobName.split("_")[0]

        srcBasePase=self.cbdat.CRYOBOOST_HOME
        widget = QtWidgets.QWidget()
        if jobName=="templatematching":
            widgetPath=srcBasePase+'/src/gui/widgets/templateMatching.ui'
        if jobName=="tmextractcand":
            widgetPath=srcBasePase+'/src/gui/widgets/candidateExtraction.ui'
        if jobName=="subtomoExtraction":
            widgetPath=srcBasePase+'/src/gui/widgets/particleReconstruction.ui'
        
        widget = loadUi(widgetPath,widget)
        widget.setContentsMargins(0, 0, 0, 0)
        widget=self.setCallbacksPartcileSetup(widget,jobName)
        
        return widget
           
       
        
    def setCallbacksPartcileSetup(self,widget,jobName):
        
        if jobName=="templatematching":
            widget.line_path_tm_template_volume.textChanged.connect(self.setTmVolumeTemplateToJobTap)
            widget.line_path_tm_template_volumeSym.textChanged.connect(self.setTmVolumeTemplateSymToJobTap)
            widget.line_path_tm_template_volumeMask.textChanged.connect(self.setTmVolumeTemplateMaskToJobTap)    
            widget.btn_browse_tm_template_volume.clicked.connect(self.browseTmVolumeTemplate)
            widget.btn_browse_tm_template_volumeMask.clicked.connect(self.browseTmVolumeTemplateMask)
            widget.btn_view_tm_template_volume.clicked.connect(self.viewTmVolumeTemplate)
            widget.btn_view_tm_template_volumeMask.clicked.connect(self.viewTmVolumeTemplateMask)
            widget.btn_generate_tm_template_volume.clicked.connect(self.generateTmVolumeTemplate)
            widget.btn_generate_tm_template_volumeMask.clicked.connect(self.generateTmVolumeTemplateMask)
            widget.chkbox_tm_template_volumeMaskNonSph.stateChanged.connect(self.setTmVolumeTemplateMaskNonSpToJobTap)
            widget.dropDown_tm_SearchVolType.currentTextChanged.connect(self.setTmVolumeTypeToJobTap)
            widget.line_path_tm_SearchVolSplit.textChanged.connect(self.setTmSearchVolSplitToJobTap)            
            widget.line_path_tm_SearchVolMaskFold.textChanged.connect(self.setTmSearchVolMaskFoldToJobTap)
            widget.btn_browse_tm_SearchVolMaskFold.clicked.connect(self.browseSearchVolMaskFold)
            widget.checkBox_tm_CtfWeight.stateChanged.connect(self.setTmCtfWeightToJobTap)
            widget.checkBox_tm_DoseWeight.stateChanged.connect(self.setTmDoseWeightToJobTap)
            widget.checkBox_tm_RandomPhaseCorrection.toggled.connect(self.setTmRandomPhaseCorrectionToJobTap)
            widget.checkBox_tm_SpectralWhitening.toggled.connect(self.setTmSpectralWhiteningToJobTap)
            widget.line_path_tm_BandPass.textChanged.connect(self.setTmBandPassToJobTap)            
            widget.line_path_tm_AngSamp.textChanged.connect(self.setTmAngSampToJobTap)            
            widget.btn_browse_tm_AngList.clicked.connect(self.browseTmAngList)
        
        if jobName=="tmextractcand":
            widget.line_path_ce_diaInAng.textChanged.connect(self.setCeDiaInAngToJobTap)
            widget.dropDown_cutOffType.currentTextChanged.connect(self.setCeScoreCutOffTypeToJobTap)
            widget.line_path_ce_cutOffVal.textChanged.connect(self.setCeScoreCutOffValueToJobTap)
            widget.line_path_ce_maxNumParticles.textChanged.connect(self.setCeMaxNumParticlesToJobTap)
            widget.line_path_ce_maskFold.textChanged.connect(self.setCeMaskFoldPathToJobTap)
            widget.btn_browse_ce_maskFold.clicked.connect(self.browseCeMaskFold)
            widget.dropDown_scoreFiltType.currentTextChanged.connect(self.setCeScoreFiltTypeToJobTap)
            widget.line_path_ce_scoreFiltVal.textChanged.connect(self.setCeScoreFiltValueToJobTap)
            widget.dropDown_ce_implementation.currentTextChanged.connect(self.setCeImplementationToJobTap)
        
        if jobName=="subtomoExtraction":
            widget.line_path_partRecBoxSzCropped.textChanged.connect(self.setPartRecBoxSzCroppedToJobTap)
            widget.line_path_partRecBoxSzUnCropped.textChanged.connect(self.setPartRecBoxSzUnCroppedToJobTap)
            widget.line_path_partRecPixS.textChanged.connect(self.setPartRecPixSToJobTap)

                
        return widget                    
        
    def schemeJobToTab(self,job,conf,insertPosition):
        # arguments: insertTab(index where it's inserted, widget that's inserted, name of tab)
        self.tabWidget.insertTab(insertPosition, QWidget(), job)
        # build a table with the dataframe containinng the parameters for the respective job in the tab
        df_job = self.cbdat.scheme.job_star[job].dict["joboptions_values"]
        nRows, nColumns = df_job.shape
        # create empty table with the dimensions of the df
        self.table = QTableWidget(self)
        self.table.setColumnCount(nColumns)
        self.table.setRowCount(nRows)
        self.table.setHorizontalHeaderLabels(("Parameter", "Value"))
       
        for row in range(nRows):
            for col in range(nColumns):
                # set the value that should be added to the respective col/row combination in the df containing the parameters
                current_value =df_job.iloc[row, col]
                # see whether there is an alias for the parameter (only for the Parameters column)
                if col == 0:
                    alias = conf.get_alias(job, current_value)
                    # if there is an alias, set the widgetItem to this alias, else, do as normal
                    if alias != None:
                        self.table.setItem(row, col, QTableWidgetItem(alias))
                    else:
                        self.table.setItem(row, col, QTableWidgetItem(current_value))
                    self.table.item(row, col).setFlags(self.table.item(row, col).flags() & ~Qt.ItemFlag.ItemIsEditable)
                else:
                    self.table.setItem(row, col, QTableWidgetItem(current_value))
        # set where this table should be placed
        tab_layout = QVBoxLayout(self.tabWidget.widget(insertPosition))
        tab_layout.addWidget(self.table)
        #self.table.setMinimumSize(1500, 400)            
        
    def getTagFromCurrentTab(self):
         
        if len(self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_"))>1:
            jobTag="_"+self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_")[1]
        else:
            jobTag=""
        
        return jobTag
    
    def splitJobByTag(self,jobName):
        
        if len(jobName.split("_"))>1:
            jobBase=jobName.split("_")[0]
            jobTag="_"+jobName.split("_")[1]
        else: 
            jobBase=jobName
            jobTag=""
        
        return jobBase,jobTag
    
        
    def setTmSearchVolMaskFoldToJobTap(self,textLine):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget().findChild(QComboBox, "dropDown_tm_implementation")  # Find QTextEdit named "text1"
        imp = widget.currentText()
        argsFull="--implementation " + imp + " --volumeMaskFold " + textLine + " --gpu_ids auto"
        
        params_dict = {"other_args":argsFull }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
        
        
    def setPathMoviesToJobTap(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        
        import re
        params_dict = {"movie_files": "frames/*" + os.path.splitext(self.line_path_movies.text())[1] }
        self.setParamsDictToJobTap(params_dict)
        folderName = self.line_path_movies.text()
        if (bool(re.search(r'[\*\?\[\]]', folderName))):
            folderName = os.path.dirname(folderName)
        folderName = folderName.rstrip(os.sep) + os.sep
        files = {ext: glob.glob(f"{folderName}*.{ext}") for ext in ['tif', 'tiff', 'eer']}
        max_type = max(files.items(), key=lambda x: len(x[1]))
        selected_files = max_type[1]
        if selected_files:
            self.groupBox_Frames.setTitle("Frames   (" + str(len(selected_files)) + "  " + max_type[0] + " files found in folder)")
            self.groupBox_Frames.setStyleSheet("QGroupBox { color: green; }")
        else:
            self.groupBox_Frames.setTitle("Frames   (0 files found)")
            self.groupBox_Frames.setStyleSheet("QGroupBox { color: red; }")
        ext="*.eer"
        self.updateEERFractions()
    
    def updateEERFractions(self):
        folder=os.path.join(os.path.dirname(self.line_path_movies.text()),'')  # Ensure folder path ends with a slash
        ext="*.eer"
        eerFiles=glob.glob(folder + "/" + ext)
        if not eerFiles:  # checks if list is empty
           self.textEdit_eerFractions.setEnabled(False)
           return  
        try:
            self.textEdit_eerFractions.setEnabled(True)
            print("Nr eer files found: " + str(len(eerFiles)))
            totDosePerTilt=float(self.textEdit_dosePerTilt.toPlainText())
            tragetDosePerFrame=float(self.textEdit_eerFractions.toPlainText())
            nrFramesToGroup=get_EERsections_per_frame(eerFiles[0],dosePerTilt=totDosePerTilt,dosePerRenderedFrame=tragetDosePerFrame)
            if "motioncorr" in self.cbdat.scheme.jobs_in_scheme.values: 
                params_dict = {"eer_grouping": str(nrFramesToGroup) }
                self.setParamsDictToJobTap(params_dict,["motioncorr"]) 
            if "fsMotionAndCtf" in self.cbdat.scheme.jobs_in_scheme.values:
                params_dict = {"param1_value": str(nrFramesToGroup) }
                self.setParamsDictToJobTap(params_dict,["fsMotionAndCtf"]) 
        except Exception as e: 
            pass
            
    
               
    def setTmVolumeTemplateToJobTap(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volume")  # Find QTextEdit named "text1"
        text = text_field.text()  # Get text content
        params_dict = {"in_3dref":text }
        if len(self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_"))>1:
            jobTag="_"+self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_")[1]
        else:
            jobTag=""
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    def setTmVolumeTypeToJobTap(self,textDropDown):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        if textDropDown=="Uncorrected":
            text="rlnTomoReconstructedTomogram"       
        if textDropDown=="Deconv (Warp)":
            text="rlnTomoReconstructedTomogramDeconv"
        if textDropDown=="Filtered":
            text="rlnTomoReconstructedTomogramDenoised"
       
        params_dict = {"param1_value":text }
        
        if len(self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_"))>1:
            jobTag="_"+self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_")[1]
        else:
            jobTag=""
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    def getTagFromParentTab(self, widget):
        """
        Find parent QTabWidget and the tab name containing the widget
        Returns: tuple (QTabWidget, tab_name) or (None, None) if not found
        """
        from PyQt6.QtWidgets import QTabWidget
        jobTag=""
        current = widget
        while current:
            parent = current.parent()
            if isinstance(parent, QTabWidget):
                for i in range(parent.count()):
                    if parent.widget(i).isAncestorOf(widget):
                        tab_name = parent.tabText(i)
                        if len(tab_name.split("_"))>1:
                            jobTag="_"+tab_name.split("_")[1]
                        else:
                            jobTag=""
                        return jobTag
            current = parent
        
        return jobTag
    
    def setTmSearchVolSplitToJobTap(self,textLine):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
       
        # print("callback==="+ tag)
        params_dict = {"param10_value":textLine }
        # jobTag=self.getTagFromCurrentTab()
        widget = self.sender() 
        jobTag = self.getTagFromParentTab(widget)
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    def setTmCtfWeightToJobTap(self,state):
    
        if state==0:
            flag="False"
        else:
            flag="True"
        params_dict = {"param6_value":str(flag) }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    def setTmDoseWeightToJobTap(self,state):
    
        if state==0:
            flag="False"
        else:
            flag="True"
        params_dict = {"param7_value":str(flag) }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    def setTmRandomPhaseCorrectionToJobTap(self,state):
    
        params_dict = {"param9_value":str(state) }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    def setTmBandPassToJobTap(self,text):
        
        params_dict = {"param5_value":str(text) }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    def browseTmAngList(self):
        
        targetFold=os.getcwd()
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_AngSamp") 
        dirName=browse_files(text_field,self.system.filebrowser)
        
        
    def setTmAngSampToJobTap(self,text):
        
        params_dict = {"param3_value":str(text) }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    
        
    
    def setTmSpectralWhiteningToJobTap(self,state):
    
        # if state==0:
        #     flag="False"
        # else:
        #     flag="True"
        params_dict = {"param8_value":str(state) }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    
    
    def browseSearchVolMaskFold(self):
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_SearchVolMaskFold") 
        targetFold=os.getcwd()
        dirName=browse_dirs(text_field,targetFold,self.system.filebrowser)
        
    
    def setTmVolumeTemplateMaskNonSpToJobTap(self):
        
        widget = self.tabWidget.currentWidget()
        chk = widget.findChild(QCheckBox, "chkbox_tm_template_volumeMaskNonSph")  # Find QTextEdit named "text1"
        text = str(chk.isChecked())  # Get text content
        params_dict = {"param4_value":text }
        if len(self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_"))>1:
            jobTag="_"+self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_")[1]
        else:
            jobTag=""
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    
    def setTmVolumeTemplateMaskToJobTap(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volumeMask")  # Find QTextEdit named "text1"
        maskName = text_field.text()  # Get text content
        tag=self.getTagFromCurrentTab()
        tag=tag[1:]
        if os.path.isfile(maskName):
            pixSRec=self.getReconstructionPixelSizeFromJobTab()
            with mrcfile.open(maskName, header_only=True) as mrc:
                pixSMask = mrc.voxel_size.x
                boxsize = mrc.header.nx  # or 
               
            if pixSRec!=str(pixSMask):
                msg = QMessageBox()
                msg.setWindowTitle("Problem!")
                msg.setText("Pixelsize of template/mask and tomograms differ!\n\nDo you want to resize the template")
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setMinimumWidth(300)
                result = msg.exec()
                if result == QMessageBox.StandardButton.Yes:
                    importedVol=self.adaptVolume(maskName,boxsize,pixSMask,pixSRec,checkInvert=False,tag=tag)
            else:
                importedVol=self.adaptVolume(maskName,boxsize,pixSMask,pixSRec,checkInvert=False,tag=tag)
            absPathToVol=os.path.abspath(importedVol)        
        else:
            absPathToVol=maskName
       
        with QSignalBlocker(text_field):
            text_field.setText(absPathToVol)
        
        params_dict = {"in_mask":maskName }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    def browseTmVolumeTemplateMask(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        targetFold=os.getcwd()
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volumeMask") 
        dirName=browse_files(text_field,self.system.filebrowser)
    
    def viewTmVolumeTemplateMask(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volumeMask") 
        self.viewVolume(text_field.text())    
    
    def viewTmVolumeTemplate(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volume") 
        self.viewVolume(text_field.text())    
    
    def generateTmVolumeTemplate(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget()
       
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volume") 
        tag=self.getTagFromCurrentTab()
        pixS=self.getReconstructionPixelSizeFromJobTab()
        
        if self.line_path_new_project.text()=="":
             messageBox("Info","No Projcet Path. Specify Projcet Path")
             projPath=browse_dirs()   
        else:
            projPath=self.line_path_new_project.text()
        templateFolder=projPath+os.path.sep+"templates"+ os.path.sep + tag[1:]
        os.makedirs(templateFolder, exist_ok=True)
        
        self.template_dialog = TemplateGen()
        self.template_dialog.line_edit_templatePixelSize.setText(pixS)
        self.template_dialog.line_edit_outputFolder.setText(templateFolder)
        self.template_dialog.framePixs=self.textEdit_pixelSize.toPlainText()
        result = self.template_dialog.exec()
        with QSignalBlocker(text_field):
            text_field.setText(self.template_dialog.line_edit_mapFile.text())
        params_dict = {"in_3dref":os.path.abspath(text_field.text()) }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    
    def getReconstructionPixelSizeFromJobTab(self):
        
        widget = self.tabWidget.currentWidget()
        index = self.tabWidget.indexOf(widget)
        scheme=self.updateSchemeFromJobTabs(self.cbdat.scheme,self.tabWidget)
        self.tabWidget.setCurrentIndex(index)
        tag=self.getTagFromCurrentTab()
        
        if "tsReconstruct"+tag in scheme.jobs_in_scheme.values: 
            pixS=scheme.job_star['tsReconstruct'+tag].dict['joboptions_values']['rlnJobOptionValue'][9]
            return pixS
        if "reconstructionfull"+tag in scheme.jobs_in_scheme.values: 
            pixS = scheme.job_star['reconstructionfull'+tag].dict['joboptions_values'][
            scheme.job_star['reconstructionfull'].dict['joboptions_values']['rlnJobOptionVariable'] == 'binned_angpix'
            ]['rlnJobOptionValue'].values[0]
            return pixS    
        if "tsReconstruct" in scheme.jobs_in_scheme.values: 
            pixS=scheme.job_star['tsReconstruct'].dict['joboptions_values']['rlnJobOptionValue'][9]
            return pixS
        if "reconstructionfull" in scheme.jobs_in_scheme.values: 
            pixS = scheme.job_star['reconstructionfull'].dict['joboptions_values'][
            scheme.job_star['reconstructionfull'].dict['joboptions_values']['rlnJobOptionVariable'] == 'binned_angpix'
            ]['rlnJobOptionValue'].values[0]
            return pixS    
        
        if pixS is None:
            messageBox("Problem","No Reconstruction Job. You cannot run template matching")
            pixS=-1
        
        return pixS
        
        
        
    def generateTmVolumeTemplateMask(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volumeMask") 
        text_fieldTempl = widget.findChild(QLineEdit, "line_path_tm_template_volume") 
        inputVol=text_fieldTempl.text().replace("_black.mrc","_white.mrc")
        if not os.path.isfile(inputVol):
            messageBox("Problem","No Template Volume. Generate Template Volume first")
            return
        maskName=os.path.splitext(inputVol.replace("_white.mrc",".mrc"))[0]+"_mask.mrc"
        lowpass=20
        thr=caclThreshold(inputVol,lowpass=None)
        thr=round(thr['fb'],5)
        
        fields = {
        "MaskPath": maskName,
        "Threshold": str(thr),
        "Extend": "3",
        "SoftEdge": "4",
        "LowPass": str(lowpass)
         }
        dialog = MultiInputDialog(fields)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            val = dialog.getInputs()
            msg=statusMessageBox("Generating Mask")
            genMaskRelion(inputVol,
                          val["MaskPath"],
                          val["Threshold"],
                          val["Extend"],
                          val["SoftEdge"],  
                          val["LowPass"],
                          threads=20,
                          envStr=self.cbdat.localEnv,
                           )
            with QSignalBlocker(text_field):
                text_field.setText(val["MaskPath"])
            params_dict = {"in_mask":os.path.abspath(maskName) }
            jobTag=self.getTagFromCurrentTab()
            self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
            msg.close()
    def setTmVolumeTemplateSymToJobTap(self):
        
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volumeSym")  # Find QTextEdit named "text1"
        text = text_field.text()  # Get text content
        params_dict = {"param2_value":text }
        if len(self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_"))>1:
            jobTag="_"+self.tabWidget.tabText(self.tabWidget.currentIndex()).split("_")[1]
        else:
            jobTag=""
        print(jobTag)
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
        
    def viewVolume(self,volume):
        os.system(self.cbdat.localEnv + " imod " + volume)
        os.system(self.cbdat.localEnv + " chimera " + volume) 
       
    def setTmVolumeTemplateToJobTap(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volume")  # Find QTextEdit named "text1"
        tmVolName = text_field.text()
        tag=self.getTagFromCurrentTab()
        tag=tag[1:]
        if os.path.isfile(tmVolName):
            pixSRec=self.getReconstructionPixelSizeFromJobTab()
            with mrcfile.open(tmVolName, header_only=True) as mrc:
                pixSTemplate = mrc.voxel_size.x
                boxsize = mrc.header.nx  # or 
               
            if pixSRec!=str(pixSTemplate):
                msg = QMessageBox()
                msg.setWindowTitle("Problem!")
                msg.setText("Pixelsize of template/mask and tomograms differ!\n\nDo you want to resize the template")
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.setMinimumWidth(300)
                result = msg.exec()
                if result == QMessageBox.StandardButton.Yes:
                    importedVol=self.adaptVolume(tmVolName,boxsize,pixSTemplate,pixSRec,tag=tag)
            else:
                importedVol=self.adaptVolume(tmVolName,boxsize,pixSTemplate,pixSRec,tag=tag)
            absPathToVol=os.path.abspath(importedVol)        
        else:
            absPathToVol=tmVolName
       
        with QSignalBlocker(text_field):
            text_field.setText(absPathToVol)
            
        params_dict = {"in_3dref":absPathToVol }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["templatematching"+jobTag])
    
    def adaptVolume(self,inputVolName,boxsize,pixSTemplate,pixSRec,checkInvert=True,tag=""):
        templateFold="templates/"+ tag 
        tmBase= templateFold + "/template_box"
        if self.line_path_new_project.text()=="":
            msg=messageBox("Info","No Projcet Path. Specify Projcet Path")
            projPath=browse_dirs()   
        else:
            projPath=self.line_path_new_project.text()
        if checkInvert:
            msg = QMessageBox()
            msg.setWindowTitle("Decision")
            msg.setText("Mass needs to black!\n\nDo you want to invert the template")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            result = msg.exec()
            if result == QMessageBox.StandardButton.Yes:
                invert=True
            else:
                invert=False
        else:
            invert=False        
        
        calcBox=boxsize*(float(pixSTemplate)/float(pixSRec))
        offset=32
        newBox = ((calcBox + offset - 1) // offset)*offset
        if newBox<96:
            newBox=96
        os.makedirs(os.path.join(projPath,"templates"),exist_ok=True)
        
        if checkInvert:
            resizedVolNameB=os.path.join(projPath,tmBase +str(newBox)+"_apix"+str(pixSRec) + "_black.mrc")
        else:
            resizedVolNameB=os.path.join(projPath,tmBase +str(newBox)+"_apix"+str(pixSRec) + "_mask.mrc")
        
        os.makedirs(os.path.dirname(resizedVolNameB),exist_ok=True)
        envStr=self.cbdat.localEnv
        processVolume(inputVolName,resizedVolNameB, voxel_size_angstrom=pixSTemplate,
                voxel_size_angstrom_out_header=pixSRec,voxel_size_angstrom_output=pixSRec,
                box_size_output=newBox,invert_contrast=invert,envStr=envStr)
    
        if checkInvert:
            resizedVolNameW=os.path.join(projPath,tmBase +str(newBox)+"_apix"+str(pixSRec) + "_white.mrc")
            invI=invert==False
            processVolume(inputVolName,resizedVolNameW, voxel_size_angstrom=pixSTemplate,
                        voxel_size_angstrom_out_header=pixSRec,voxel_size_angstrom_output=pixSRec,
                        box_size_output=newBox,invert_contrast=invI,envStr=envStr)
        
        
        return resizedVolNameB
        
    
    def browseTmVolumeTemplate(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        targetFold=os.getcwd()
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_tm_template_volume") 
        dirName=browse_files(text_field,self.system.filebrowser)
        
    def setCeScoreCutOffTypeToJobTap(self,text):   
        params_dict = {"param1_value":text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
   
    def setCeScoreCutOffValueToJobTap(self,text):   
        params_dict = {"param2_value":text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
   
    def setCeDiaInAngToJobTap(self,text):
        params_dict = {"param3_value":text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
    
    def setCeMaxNumParticlesToJobTap(self,text):
        params_dict = {"param4_value":text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
    
    def setCeScoreFiltTypeToJobTap(self,text):   
        params_dict = {"param6_value":text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
    
    def setCeScoreFiltValueToJobTap(self,text):   
        params_dict = {"param7_value":text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
   
    def setCeMaskFoldPathToJobTap(self,text):
        params_dict = {"param8_value":text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
    
    def setCeImplementationToJobTap(self,text):
        
        textToSet="--implementation " + text + "\'"
        params_dict = {"other_args": textToSet }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["tmextractcand"+jobTag])
    
    def setPartRecBoxSzCroppedToJobTap(self,text):
        
        params_dict = {"crop_size": text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["subtomoExtraction"+jobTag])
    def setPartRecBoxSzUnCroppedToJobTap(self,text):
        
        params_dict = {"box_size": text }
        jobTag=self.getTagFromCurrentTab()
        self.setParamsDictToJobTap(params_dict,["subtomoExtraction"+jobTag])
    
    def setPartRecPixSToJobTap(self,text,jobTag=None):
        
        if jobTag is None:
            jobTag=self.getTagFromCurrentTab()
        pixS=self.textEdit_pixelSize.toPlainText()
        if pixS.replace(".", "", 1).isdigit() and text.replace(".", "", 1).isdigit():
            binF=float(text)/float(pixS)
            params_dict = {"binning": str(binF) }
            self.setParamsDictToJobTap(params_dict,["subtomoExtraction"+jobTag])
    
    def browseCeMaskFold(self):
        """
        Sets the path to movies in the importmovies job to the link provided in the line_path_movies field.
        Then, sets the parameters dictionary to the jobs in the tab widget.

        Args:
            None

        Returns:
            None
        """
        targetFold=os.getcwd()
        widget = self.tabWidget.currentWidget()
        text_field = widget.findChild(QLineEdit, "line_path_ce_maskFold") 
        dirName=browse_dirs(text_field,targetFold,self.system.filebrowser)
    
        
    def setPathMdocsToJobTap(self):
        """
        Sets the parameters dictionary to the jobs in the tab widget for the mdoc files.

        This function retrieves the file extension from the `line_path_mdocs` text field and constructs the `mdoc_files` parameter dictionary. The constructed dictionary is then passed to the `setParamsDictToJobTap` method.

        Parameters:
            None

        Returns:
            None
        """
        
        params_dict = {"mdoc_files": "mdoc/*" + os.path.splitext(self.line_path_mdocs.text())[1] }
        
        import re
        
        
        
        if "ctffind" in self.cbdat.scheme.jobs_in_scheme.values:
            thoneRingFade = self.cbdat.scheme.getJobOptions("ctffind").loc[
                             self.cbdat.scheme.getJobOptions("ctffind")["rlnJobOptionVariable"] == "exp_factor_dose",
                             "rlnJobOptionValue"
                             ].values[0]  
            if self.textEdit_dosePerTilt.toPlainText().isnumeric():
                checkDosePerTilt(self.line_path_mdocs.text(),float(self.textEdit_dosePerTilt.toPlainText()),float(thoneRingFade))
        
        self.setParamsDictToJobTap(params_dict)
        try:
            mdoc=mdocMeta(self.line_path_mdocs.text())
            nrMdoc=mdoc.param4Processing["NumMdoc"]
            if nrMdoc>0:
                self.groupBox_mdoc.setTitle("Mdoc   (" + str(nrMdoc) + " mdoc files found in folder)")
                self.groupBox_mdoc.setStyleSheet("QGroupBox { color: green; }")
            else:
                self.groupBox_mdoc.setTitle("Mdoc   (0 files found)")
                self.groupBox_mdoc.setStyleSheet("QGroupBox { color: red; }")
            
            self.textEdit_pixelSize.setText(str(mdoc.param4Processing["PixelSize"]))
            dosePerTilt=mdoc.param4Processing["DosePerTilt"]
            if dosePerTilt<0.1 or dosePerTilt > 9:
                print("dose per tilt from mdoc out of range setting to 3")
                dosePerTilt=3.0
            self.textEdit_dosePerTilt.setText(str(dosePerTilt))
            self.textEdit_nomTiltAxis.setText(str(mdoc.param4Processing["TiltAxisAngle"]))
            self.textEdit_recTomosize.setText(str(mdoc.param4Processing["ImageSize"])+str("x2048"))
            # if int(mdoc.param4Processing["ImageSize"].split("x")[0])>4096:
            #     print("detected large camera chip size increasing default patch size by 10 percent")
            #     self.textEdit_ImodPatchSize.setText=(str(800))
            line_edits = self.tabWidget.findChildren(QLineEdit, "line_path_partRecPixS")
            for line_edit in line_edits:
                current_value = line_edit.text()
                line_edit.setText(str(mdoc.param4Processing["PixelSize"]))
        except: 
            self.groupBox_mdoc.setTitle("Mdoc   (0 files found)")
            self.groupBox_mdoc.setStyleSheet("QGroupBox { color: red; }")
        
        
    #self.textEdit_tomoForDenoiseTrain.textChanged.connect(self.setTomoForDenoiseTrainToJobTap)
    #self.textEdit_pathDenoiseModel.textChanged.connect(self.setPathDenoiseModelToJobTap)
    
    def showClusterStatus(self):
        
        sshStr=self.cbdat.conf.confdata['submission'][0]['SshCommand']
        headNode=self.cbdat.conf.confdata['submission'][0]['HeadNode']
        command=sshStr + " " + headNode + ' "' + "sinfo -o '%P %.6D %.6t' | sort -k3 | grep -v 'PAR'" + '"'
        print(command)
        proc=subprocess.Popen(command,shell=True ,stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate()
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle('Information')
        msg_box.setText(stdout)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.resize(2000, 400) 
        msg_box.exec()
       
    def setTomoForDenoiseTrainToJobTap(self):
  
        params_dict = {"tomograms_for_training": self.textEdit_tomoForDenoiseTrain.toPlainText() }
        self.setParamsDictToJobTap(params_dict)
    
    def setPathDenoiseModelToJobTap(self):
  
        params_dict = {"care_denoising_model": self.textEdit_pathDenoiseModel.toPlainText() }
        self.setParamsDictToJobTap(params_dict)
    
    def setmodelForFilterTiltsToJobTap(self):
        
        params_dict = {"param1_value": self.textEdit_modelForFilterTilts.toPlainText() }
        self.setParamsDictToJobTap(params_dict,applyToJobs="filtertilts")
    
    def setProbThrToJobTap(self):
        
        params_dict = {"param5_value": self.textEdit_probThr.toPlainText() }
        self.setParamsDictToJobTap(params_dict,applyToJobs="filtertilts")
    
    def setFilterTiltsModeToJobTap(self,index):
        params_dict = {"param1_value":  self.dropDown_FilterTiltsMode.currentText()}
        self.setParamsDictToJobTap(params_dict,applyToJobs="filtertiltsInter")

    
    def setProbBehaveToJobTab(self):
        
        params_dict = {"param6_value": self.dropDown_probThrBehave.currentText() }
        self.setParamsDictToJobTap(params_dict,applyToJobs="filtertilts")
    
    
    def updateTomogramsForTraining(self):
        wk_mdocs=self.line_path_mdocs.text()
        mdocList=glob.glob(wk_mdocs)
        pref=self.line_path_crImportPrefix.text()
        mdocList=[mdoc for mdoc in mdocList]# if pref in mdoc]
        #tomoNames=[pref+os.path.splitext(os.path.basename(path))[0].replace(".st","") for path in mdocList]
        tomoNames=[pref+os.path.splitext(os.path.splitext(os.path.basename(path))[0])[0] for path in mdocList]
        if len(tomoNames)<3:
            nTomo=len(tomoNames)
        else:
            nTomo=3
        tomoNamesSub=random.sample(tomoNames, k=nTomo)
        tomoStr=":".join(tomoNamesSub)
        self.textEdit_tomoForDenoiseTrain.setText(tomoStr)
       
    def setPixelSizeToJobTap(self):
        textline=self.textEdit_pixelSize.toPlainText()
        params_dict = {"angpix": textline}
        self.setParamsDictToJobTap(params_dict,["importmovies"])      
        if textline.replace('.', '', 1).isdigit():  # Allows one decimal point
            bin4Pixs=str(float(textline)*4)
            self.textEdit_algRescaleTilts.setText(bin4Pixs)
            self.textEdit_recVoxelSize.setText(bin4Pixs)
        if "fsMotionAndCtf" in self.cbdat.scheme.jobs_in_scheme.values:
            nyPixs=(float(textline)*2)+0.2
            valCRangeMax=self.cbdat.scheme.getJobOptions("fsMotionAndCtf").loc[
                             self.cbdat.scheme.getJobOptions("fsMotionAndCtf")["rlnJobOptionVariable"] == "param7_value",
                             "rlnJobOptionValue"
                             ].values[0]  
            minCRange=float(valCRangeMax.split(":")[0])
            maxCrange=float(valCRangeMax.split(":")[1])
            if nyPixs>maxCrange:
                crange=str(minCRange) + ":" + str(nyPixs)
                params_dict = {"param7_value": crange}
                self.setParamsDictToJobTap(params_dict,["fsMotionAndCtf"])
        
        if "tsCtf" in self.cbdat.scheme.jobs_in_scheme.values:
            nyPixs=(float(textline)*2)+0.2
            valCRangeMax=self.cbdat.scheme.getJobOptions("tsCtf").loc[
                             self.cbdat.scheme.getJobOptions("tsCtf")["rlnJobOptionVariable"] == "param2_value",
                             "rlnJobOptionValue"
                             ].values[0]  
            minCRange=float(valCRangeMax.split(":")[0])
            maxCrange=float(valCRangeMax.split(":")[1])
            if nyPixs>maxCrange:
                crange=str(minCRange) + ":" + str(nyPixs)
                params_dict = {"param2_value": crange}
                self.setParamsDictToJobTap(params_dict,["tsCtf"])
        
                
            
    def setdosePerTiltToJobTap(self):
        params_dict = {"dose_rate": self.textEdit_dosePerTilt.toPlainText()} 
        if "ctffind" in self.cbdat.scheme.jobs_in_scheme.values:
            thoneRingFade = self.cbdat.scheme.getJobOptions("ctffind").loc[
                             self.cbdat.scheme.getJobOptions("ctffind")["rlnJobOptionVariable"] == "exp_factor_dose",
                             "rlnJobOptionValue"
                             ].values[0]  
            if self.textEdit_dosePerTilt.toPlainText().isnumeric():
                checkDosePerTilt(self.line_path_mdocs.text(),float(self.textEdit_dosePerTilt.toPlainText()),float(thoneRingFade))
        
        self.setParamsDictToJobTap(params_dict,["importmovies"])       
        self.updateEERFractions()
        
    def setTiltAxisToJobTap(self):
        params_dict = {"tilt_axis_angle": self.textEdit_nomTiltAxis.toPlainText()} 
        self.setParamsDictToJobTap(params_dict,["importmovies"]) 
    
    def setPathGainToJobTap(self):
        
        gainPath=self.line_path_gain.text()
        
        if len(gainPath)==0:
            gainPath="None"
        
        params_dict = {"fn_gain_ref": gainPath} 
        self.setParamsDictToJobTap(params_dict,["motioncorr"]) 
        params_dict = {"param2_value": gainPath} 
        self.setParamsDictToJobTap(params_dict,["fsMotionAndCtf"]) 
        
    
    def setGainRotToJobTap(self):
        if "motioncorr" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"gain_rot": self.dropDown_gainRot.currentText()} 
            checkGainOptions(self.line_path_gain.text(),self.dropDown_gainRot.currentText(),self.dropDown_gainFlip.currentText())
            self.setParamsDictToJobTap(params_dict,["motioncorr"]) 
        if "fsMotionAndCtf" in self.cbdat.scheme.jobs_in_scheme.values:   
            selFlip=self.dropDown_gainFlip.currentText()
            selRot=self.dropDown_gainRot.currentText()
            gainOpString=""
            if selFlip=="Flip upside down (1)":
                gainOpString=gainOpString+"flip_y"
            if selFlip=="Flip left to right (2)":
                if gainOpString!="":
                    gainOpString=gainOpString+":"
                gainOpString=gainOpString+"flip_x"
            if selRot=="Transpose":
                if gainOpString!="":
                    gainOpString=gainOpString+":"
                gainOpString=gainOpString+"transpose"
            
            if len(gainOpString)==0:
                gainOpString='None'
            #checkGainOptions(self.line_path_gain.text(),self.dropDown_gainRot.currentText(),self.dropDown_gainFlip.currentText())
            params_dict = {"param3_value": gainOpString}
           
            self.setParamsDictToJobTap(params_dict,["fsMotionAndCtf"]) 
        
        
    def setGainFlipJobTap(self):
        if "motioncorr" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"gain_flip": self.dropDown_gainFlip.currentText()} 
            checkGainOptions(self.line_path_gain.text(),self.dropDown_gainRot.currentText(),self.dropDown_gainFlip.currentText())
            self.setParamsDictToJobTap(params_dict,["motioncorr"]) 
        if "fsMotionAndCtf" in self.cbdat.scheme.jobs_in_scheme.values:   
            
            selFlip=self.dropDown_gainFlip.currentText()
            selRot=self.dropDown_gainRot.currentText()
            gainOpString=""
            if selFlip=="Flip upside down (1)":
                gainOpString=gainOpString+"flip_y"
            if selFlip=="Flip left to right (2)":
                if gainOpString!="":
                    gainOpString=gainOpString+":"
                gainOpString=gainOpString+"flip_x"
            if selRot=="Transpose":
                if gainOpString!="":
                    gainOpString=gainOpString+":"
                gainOpString=gainOpString+"transpose"
            
            #checkGainOptions(self.line_path_gain.text(),self.dropDown_gainRot.currentText(),self.dropDown_gainFlip.currentText())
            if len(gainOpString)==0:
                gainOpString='None'
            params_dict = {"param3_value": gainOpString}
        
            self.setParamsDictToJobTap(params_dict,["fsMotionAndCtf"]) 
            
    def setInvertTiltAngleToJobTap(self):
        params_dict = {"flip_tiltseries_hand": self.textEdit_invertHand.toPlainText()} 
        self.setParamsDictToJobTap(params_dict,["importmovies"]) 
    def setInvertDefocusHandToJobTap(self):
        params_dict = {"flip_tiltseries_hand": self.textEdit_invertDefocusHand.toPlainText()} 
        self.setParamsDictToJobTap(params_dict,["importmovies"]) 
        print("setting Warp Handness same as Relion")
        if self.textEdit_invertDefocusHand.toPlainText()=="Yes":
            print("  Warp Handness set_flip")
            params_dict = {"param4_value": "set_flip"} 
        else:
            print("  Warp Handness set_noflip")
            params_dict = {"param4_value": "set_noflip"} 
        self.setParamsDictToJobTap(params_dict,["tsCtf"]) 
        
        
        
    def setRecVoxelSizeToJobTap(self):
        if "reconstructionsplit" in self.cbdat.scheme.jobs_in_scheme.values or "reconstructionfull" in self.cbdat.scheme.jobs_in_scheme.values: 
            params_dict = {"binned_angpix": self.textEdit_recVoxelSize.toPlainText()} 
            self.setParamsDictToJobTap(params_dict,["reconstructionsplit"])
            self.setParamsDictToJobTap(params_dict,["reconstructionfull"])
        if "tsReconstruct" in self.cbdat.scheme.jobs_in_scheme.values: 
            params_dict = {"param1_value": self.textEdit_recVoxelSize.toPlainText()} 
            self.setParamsDictToJobTap(params_dict,["tsReconstruct"])
    def setRecTomosizeToJobTap(self):
        if "reconstructionsplit" in self.cbdat.scheme.jobs_in_scheme.values or "reconstructionfull" in self.cbdat.scheme.jobs_in_scheme.values: 
            params_dict = {}
            dims = self.textEdit_recTomosize.toPlainText().split("x")
            params_dict["xdim"] = dims[0]
            params_dict["ydim"] = dims[1]
            params_dict["zdim"] = dims[2]
            self.setParamsDictToJobTap(params_dict,["reconstructionsplit"])
            self.setParamsDictToJobTap(params_dict,["reconstructionfull"])
        if "tsReconstruct" in self.cbdat.scheme.jobs_in_scheme.values: 
            tomoSz=self.textEdit_recTomosize.toPlainText().split("x")
            tomoSz=str(tomoSz[1])+"x"+str(tomoSz[0])+"x"+str(tomoSz[2])
            params_dict = {"param1_value": tomoSz} 
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"])

        
    def setEerFractionsToJobTap(self):
        
        self.updateEERFractions()
        # if "motioncorr" in self.cbdat.scheme.jobs_in_scheme.values: 
        #     params_dict = {"eer_grouping": self.textEdit_eerFractions.toPlainText()}
        #     self.setParamsDictToJobTap(params_dict,["motioncorr"]) 
        # if "fsMotionAndCtf" in self.cbdat.scheme.jobs_in_scheme.values:
        #     params_dict = {"param1_value": self.textEdit_eerFractions.toPlainText()}
        #     self.setParamsDictToJobTap(params_dict,["fsMotionAndCtf"]) 
            
    def setAreTomoSampleThickToJobTap(self):
        
        params_dict = {"tomogram_thickness": self.textEdit_areTomoSampleThick.toPlainText()} 
        self.setParamsDictToJobTap(params_dict,["aligntilts"]) 
        
        if "aligntiltsWarp" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"param6_value": self.textEdit_areTomoSampleThick.toPlainText()}
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"]) 
    #self.textEdit_areTomoPatch.textChanged.connect(self.setAreTomoPatchToJobTap)
    #self.textEdit_algRescaleTilts.textChanged.connect(self.setAlgRescaleTiltsJobTap)
    def setAreTomoPatchToJobTap(self):
        
        if "aligntiltsWarp" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"other_args": self.textEdit_areTomoPatch.toPlainText()}
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"]) 
        
    def setAlgRescaleTiltsJobTap(self):
        
        if "aligntiltsWarp" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"param8_value": self.textEdit_algRescaleTilts.toPlainText()}
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"]) 
        
            
    # def setAreTomoSampleThickToJobTap(self):
    #     params_dict = {"aretomo_thickness": self.textEdit_areTomoSampleThick.toPlainText()} 
    #     self.setParamsDictToJobTap(params_dict,["aligntilts"]) 
    
    def setTiltAxisRefineParamToJobTap(self):
        if "aligntiltsWarp" in self.cbdat.scheme.jobs_in_scheme.values:
            if self.dropDown_doRefineTiltAxis.currentText() == "False":
                refineStr = "0:0"
            else:
                refineStr = self.textEdit_refineTiltAxisIter.toPlainText()+":"+self.textEdit_refineTiltAxisNrTomo.toPlainText()
            params_dict = {"param9_value": refineStr}
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"]) 
    
    def setImodPatchSizeToJobTap(self):
        params_dict = {"patch_size": self.textEdit_ImodPatchSize.toPlainText()} 
        self.setParamsDictToJobTap(params_dict,["aligntilts"]) 
        if "aligntiltsWarp" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"param7_value": self.textEdit_ImodPatchSize.toPlainText()+
                           ":"+self.textEdit_imodPatchOverlap.toPlainText()
                           }
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"]) 
    
    def setImodPatchOverlapToJobTap(self):
        params_dict = {"patch_overlap": self.textEdit_imodPatchOverlap.toPlainText()} 
        self.setParamsDictToJobTap(params_dict,["aligntilts"]) 
        if "aligntiltsWarp" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"param7_value": self.textEdit_ImodPatchSize.toPlainText()+
                           ":"+self.textEdit_imodPatchOverlap.toPlainText()
                           }
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"]) 
        
        
    def setNrNodesFromJobSize(self):
       
       if self.dropDown_jobSize.currentText().strip()=="small":
            self.dropDown_nrNodes.setCurrentText("1")
       if self.dropDown_jobSize.currentText().strip()=="medium":
            self.dropDown_nrNodes.setCurrentText("3") 
       if self.dropDown_jobSize.currentText().strip()=="large":
            self.dropDown_nrNodes.setCurrentText("5") 
       
       self.setNrNodesToJobTap() 
            
    def setTomoAlignProgramToJobTap(self):
        
        programSelected=self.dropDown_tomoAlignProgram.currentText()
        if (programSelected=="Imod"):
            params_dictAre = {"do_aretomo2": "No"}
            params_dictImod = {"do_imod_patchtrack": "Yes"}
        
        if (programSelected=="Aretomo"):
            params_dictAre = {"do_aretomo2": "Yes"}
            params_dictImod = {"do_imod_patchtrack": "No"}
        
        self.setParamsDictToJobTap(params_dictAre,["aligntilts"])
        self.setParamsDictToJobTap(params_dictImod,["aligntilts"])
        if "aligntiltsWarp" in self.cbdat.scheme.jobs_in_scheme.values:
            params_dict = {"param5_value": programSelected}
            self.setParamsDictToJobTap(params_dict,["aligntiltsWarp"]) 
        
        
    def setNrNodesToJobTap(self):
       
        nrNodes=int(self.dropDown_nrNodes.currentText())
        partion=self.dropDown_partitionName.currentText()
        shareNodes=self.checkBox_shareNodes.isChecked()
        for job in self.cbdat.scheme.jobs_in_scheme:
            jobNoTag,_=self.splitJobByTag(job) 
            comDict=self.cbdat.conf.getJobComputingParams([jobNoTag,nrNodes,partion],shareNodes)
            if (comDict is not None):
                self.setParamsDictToJobTap(comDict,applyToJobs=job)
        vRam=int(self.cbdat.conf.confdata['computing'][partion]['VRAM'].replace("G",""))
        if vRam>40:
            spString="2:2:1"
        else:
            spString="4:4:2"
        line_edits = self.tabWidget.findChildren(QLineEdit, "line_path_tm_SearchVolSplit")
        for line_edit in line_edits:
            line_edit.setText(spString)
                

         
    def setParamsDictToJobTap(self,params_dict,applyToJobs="all"):
        """
        A function that sets the parameters dictionary to the jobs in the tab widget based on the given parameters.

        Args:
            params_dict (dict): A dictionary containing the parameters to be set.
            applyToJobs (str, optional): A List specifying which jobs to apply the p
            arameters to. Defaults to "all".
               
        Returns:
            None
        """
        if applyToJobs == "all":
           applyToJobs = list(self.cbdat.scheme.jobs_in_scheme)
        if isinstance(applyToJobs, str):
            applyToJobs = [applyToJobs]
         
        idxOrg=self.tabWidget.currentIndex()
        
        for current_tab in self.cbdat.scheme.jobs_in_scheme:
            #print(current_tab in applyToJobs)
            if current_tab in applyToJobs:
                index_import = self.cbdat.scheme.jobs_in_scheme[self.cbdat.scheme.jobs_in_scheme == current_tab].index
                self.tabWidget.setCurrentIndex(index_import.item()+self.jobTapNrSetUpTaps-1)
                table_widget = self.tabWidget.currentWidget().findChild(QTableWidget)
                change_values(table_widget, params_dict, self.cbdat.scheme.jobs_in_scheme,self.cbdat.conf)
        self.tabWidget.setCurrentIndex(idxOrg)
    
    
    def browsePathMovies(self):
        
        #browse_files(self.line_path_movies)
        targetFold=os.getcwd()
        dirName=browse_dirs(self.line_path_movies,targetFold,self.system.filebrowser)
        if glob.glob(dirName+"*.tif"):
            self.line_path_movies.setText(dirName + "*.tif")
        if glob.glob(dirName+"*.tiff"):
            self.line_path_movies.setText(dirName + "*.tiff")
        if glob.glob(dirName+"*.eer"):
            self.line_path_movies.setText(dirName + "*.eer")  
        
    def browsePathMdocs(self):
        targetFold=os.getcwd()
        dirName=browse_dirs(None,targetFold,self.system.filebrowser)
        if glob.glob(dirName+"*.mdoc"):
            self.line_path_mdocs.setText(dirName + "*.mdoc")

    def browsePathGain(self):
        browse_files(self.line_path_gain,self.system.filebrowser)
    
    def browseDenoisingModel(self):
        browse_files(self.textEdit_pathDenoiseModel,self.system.filebrowser)

    def generatePrefix(self):
       current_datetime = datetime.datetime.now()
       prefix=current_datetime.strftime("%Y-%m-%d-%H-%M-%S_")
       self.line_path_crImportPrefix.setText(prefix)
        
    def mdocs_use_movie_path(self):
        movieP=self.line_path_movies.text()
        mpRoot,ext= os.path.splitext(movieP)
        self.line_path_mdocs.setText(mpRoot+".mdoc")

    def startWorkflow(self):
        
        if self.checkPipeRunner()==False:
            return
        
        if self.cbdat.pipeRunner.checkForLock():
            messageBox("lock exists","stop workflow first")
            return
        print(self.cbdat.pipeRunner.getCurrentNodeScheme())
        
        if self.cbdat.pipeRunner.getCurrentNodeScheme()=="EXIT":
            reply = QMessageBox.question(self, 'Workflow has finished!',
                                 "WorkFlow has finished. To run it again on new data you need to reset the workflow head. Do you want to reset the workflow head?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
       
            if reply == QMessageBox.StandardButton.Yes:
                self.cbdat.pipeRunner.setCurrentNodeScheme("WAIT")
            else:
                return    
        
        self.cbdat.pipeRunner.runScheme()
    
    def scheduleJobs(self):
        
        if self.checkPipeRunner()==False:
            return
        
        self.cbdat.pipeRunner.scheduleJobs()
        
    def openRelionGui(self):
        
        if self.checkPipeRunner()==False:
            self.checkBox_openRelionGui.setChecked(False)
            return
        
        if self.checkBox_openRelionGui.isChecked():
            self.cbdat.pipeRunner.openRelionGui()    
         
    
    def stopWorkflow(self):
        
        if self.checkPipeRunner()==False:
            return
        reply = QMessageBox.question(self, 'Message',
                                 "Do you really want to stop the workflow?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.cbdat.pipeRunner.abortScheme()
  
       
    def resetWorkflow(self):
       
       if self.checkPipeRunner()==False:
            return
       
       if (self.cbdat.pipeRunner.checkForLock()):
            messageBox("lock exists","stop workflow first")
            return
       
       reply = QMessageBox.question(self, 'Message',
                                 "Do you really want to reset the workflow?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
       if reply == QMessageBox.StandardButton.Yes:
            self.cbdat.pipeRunner.resetScheme()          
         
    def resetWorkflowHead(self):
       
       if self.checkPipeRunner()==False:
            return
       
       if (self.cbdat.pipeRunner.checkForLock()):
            messageBox("lock exists","stop workflow first")
            return
       
       reply = QMessageBox.question(self, 'Reset',
                                 "Do you really want to reset the workflow head?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
       
       if reply == QMessageBox.StandardButton.Yes:
            self.cbdat.pipeRunner.setCurrentNodeScheme("WAIT")      
    
    
    def unlockWorkflow(self):
       
       if self.checkPipeRunner()==False:
            return
       self.cbdat.pipeRunner.unlockScheme()          
    
    def checkPipeRunner(self,warnProjectExists=False):
        
        if self.cbdat.pipeRunner is not None: 
            if (warnProjectExists):
                messageBox("Project!","You have already a Project")
            return True    
        else:
            if (warnProjectExists==False):
                messageBox("No Project!","Generate a Project first")
            return False 
    
    def openExtLogViewerWorkFlow(self):
        logMid=self.cbdat.scheme.scheme_star.dict["scheme_general"]["rlnSchemeName"].replace("Schemes/","").replace("/","")
        logfile_path=self.line_path_new_project.text()+os.path.sep + logMid +".log"
        self.viewer = externalTextViewer(logfile_path)
        self.viewer.show()
        
    def openExtLogViewerJobOutput(self):
        
        if (self.cbdat.pipeRunner is  None):
            return
        
        logOut,logError=self.cbdat.pipeRunner.getLastJobLogs()
        logfile_path=logOut
        self.viewer = externalTextViewer(logfile_path)
        self.viewer.show()
    
    def openExtLogViewerJobError(self):
        
        if (self.cbdat.pipeRunner is  None):
            return
        
        logOut,logError=self.cbdat.pipeRunner.getLastJobLogs()
        logfile_path=logError
        self.viewer = externalTextViewer(logfile_path)
        self.viewer.show()
    
    
    def view_log_file(self, log_file_path):
        """
        This function reads the content of a log file and displays it in a text browser.

        Parameters:
        log_file_path (str): The path to the log file.

        Returns:
        None. The function updates the text in the text browser.
        """
        if (self.cbdat.pipeRunner is None):
            return
        
        try:
            with open(log_file_path, 'r') as log_file:
                log_content = log_file.read()
                self.textBrowser_workFlow.setText(log_content)
        except Exception as e:
            self.textBrowser_workFlow.setText(f"Failed to read log file: {e}")
        self.textBrowser_workFlow.moveCursor(QTextCursor.MoveOperation.End)    
        
        logOut,logError=self.cbdat.pipeRunner.getLastJobLogs()
       
        
        try:
            with open(logOut, 'rb') as log_file:  # Open in binary mode
                binary_lines = log_file.readlines()
                log_contentOut = []
                
                for i, binary_line in enumerate(binary_lines):
                    line = binary_line.decode('utf-8')
                    starts_with_cr = binary_line.startswith(b'\r')
                    if starts_with_cr:
                        line = line.split('\r')[-1]
                    cleaned_line = self.process_backspaces(line).strip()
                    if cleaned_line:
                        log_contentOut.append(cleaned_line)

                if len(log_contentOut) > 200:
                    log_contentOut = log_contentOut[-200:]
                
                log_contentOutStr = "\n".join(log_contentOut)
                self.textBrowserJobsOut.setText(log_contentOutStr)
            
            log_contentError= []
            with open(logError, 'r') as log_fileError:
                # log_contentError = log_fileError.readlines()
                for lineError in log_fileError:
                   cleaned_lineError = self.process_backspaces(lineError).strip()
                   if cleaned_lineError:
                        log_contentError.append(cleaned_lineError)
                if len(log_contentError) > 200:
                     log_contentError=log_contentError[-200:]
                
                if self.checkBox_jobErrroShowWarning.isChecked()==False:
                    log_contentError = [line for line in log_contentError if "warning" not in line.lower() and "warn" not in line.lower()]
                    
                log_contentErrorStr= "\n".join(log_contentError)
                self.textBrowserJobsError.setText(log_contentErrorStr)    
        except Exception as e:
            #print(e)
            self.textBrowserJobsOut.setText(f"Logfile not available your job is probably waiting\nCheck queue") #{e})
        self.textBrowserJobsOut.moveCursor(QTextCursor.MoveOperation.End) 
        self.textBrowserJobsError.moveCursor(QTextCursor.MoveOperation.End)
    
    
    def process_backspaces(self,line):
        
        result = []
        for char in line:
            if char == '\b':  # '\b' is the backspace character in Python
                if result:
                    result.pop()  # Remove the last character in the result
            else:
                result.append(char)
        return ''.join(result)
    
    
    def loadConfig(self):
        """
        go through all parameters of all tabs and see whether any parameter is in the config_microscopes file
        (= contains all parameters that are solely dependent on the setup) under the chosen setup. If a parameter
        is found, its value is set to the value defined in the config_microscopes for this parameter.
        """
        microscope = self.dropDown_config.currentText()
        microscope_parameters=self.cbdat.conf.get_microscopePreSet(microscope)
       
        self.textEdit_invertTiltAngle.setText(microscope_parameters["invert_tiltAngles"])
        self.textEdit_invertDefocusHand.setText(microscope_parameters["invert_defocusHandness"])
        

    def browsePathTarget(self):
        defPath=os.getcwd()   
        browse_dirs(self.line_path_new_project,defPath,self.system.filebrowser)
       

    def updateLogViewer(self):
        print("logViewer updated")
        logMid=self.cbdat.scheme.scheme_star.dict["scheme_general"]["rlnSchemeName"].replace("Schemes/","").replace("/","")
        logfile_path=self.line_path_new_project.text()+ os.path.sep + logMid +".log"
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()  
        if not hasattr(self, 'timer'):
            self.timer = QTimer(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.view_log_file(logfile_path))
        self.timer.start(4000)  # Updat
    
    def generateProject(self):
        """
        first, create a symlink to the frames and mdoc files and change the absolute paths provided by the browse 
        function to relative paths to these links and change the input fields accordingly.
        Then, go through all tabs that were created using the makeJobTabs function, select the table that is in that tab
        and iterate through the columns and rows of that table, checking whether there is an alias (and reverting
        it if there is) and then writing the value into the df for the job.star file at the same position as it 
        is in the table (table is created based on this df so it should always be the same position and name). 
        """
        
        if self.checkPipeRunner(warnProjectExists=True):
            return
        
        scheme=self.cbdat.scheme
        scheme=self.updateSchemeFromJobTabs(scheme,self.tabWidget)
        self.cbdat.scheme=scheme
        
        args=self.cbdat.args
        args.mdocs=self.line_path_mdocs.text()
        args.movies=self.line_path_movies.text()
        args.proj=self.line_path_new_project.text()
        args.scheme=scheme
        invTilt=self.textEdit_invertTiltAngle.toPlainText()
        if invTilt == "Yes":
            invTilt=True
        else:
            invTilt=False
        pipeRunner=pipe(args,invMdocTiltAngle=invTilt)
        pipeRunner.initProject()
        pipeRunner.writeScheme()
        #pipeRunner.scheme.schemeFilePath=args.proj +  "/Schemes/relion_tomo_prep/scheme.star"
        self.cbdat.pipeRunner=pipeRunner
        
    def updateWorkflow(self):
        
        if self.checkPipeRunner()==False:
            return
        scheme=self.cbdat.scheme
        scheme=self.updateSchemeFromJobTabs(scheme,self.tabWidget)
        scheme.scheme_star=starFileMeta(self.cbdat.pipeRunner.scheme.schemeFilePath)
        self.cbdat.scheme=scheme
        self.cbdat.pipeRunner.scheme=scheme
        self.cbdat.pipeRunner.writeScheme()
        
    def importData(self):    
        
        if self.checkPipeRunner()==False:
            return
        self.cbdat.pipeRunner.pathFrames=self.line_path_movies.text()
        self.cbdat.pipeRunner.pathMdoc=self.line_path_mdocs.text()
        self.cbdat.pipeRunner.importPrefix=self.line_path_crImportPrefix.text()
        self.cbdat.pipeRunner.importData()    
        #scheme=self.updateSchemeFromJobTabs(scheme,self.tabWidget)
        #self.cbdat.pipeRunner.writeScheme()
    
    def updateSchemeFromJobTabs(self,scheme,tabWidget):
        """
        Updates the given scheme by iterating over each job tab in the given tab widget and updating the corresponding job's star file based on the table widget's contents.

        Parameters:
            scheme (Scheme): The scheme object to be updated.
            tabWidget (QTabWidget): The tab widget containing the job tabs.

        Returns:
            Scheme: The updated scheme object.
        """
        
        for job_tab_index in range(1, len(scheme.jobs_in_scheme) + 1):
            tabWidget.setCurrentIndex(job_tab_index+self.jobTapNrSetUpTaps-1)
            table_widget = tabWidget.currentWidget().findChild(QTableWidget)
            jobName = scheme.jobs_in_scheme[job_tab_index]
            scheme.job_star[jobName]=self.updateSchemeJobFromTable(scheme.job_star[jobName], table_widget,jobName,self.cbdat.conf)

            
        tabWidget.setCurrentIndex(len(self.cbdat.scheme.jobs_in_scheme) + self.jobTapNrSetUpTaps)
        return scheme    
    
    def updateSchemeJobFromTable(self,job, table_widget, jobName, conf):
        """
        update the job_star_dict with the values of the table_widget
        """
        nRows = table_widget.rowCount()
        nCols = table_widget.columnCount()
        
        for row in range(nRows):
            for col in range(nCols):
                value = table_widget.item(row, col).text()
                if col == 0:
                    original_param_name = conf.get_alias_reverse(jobName, value)
                    if original_param_name != None:
                        # param_name = original_param_name
                        value = original_param_name     
                # insert value at the position defined by the index of the table
                job.dict["joboptions_values"].iloc[row, col] = value
        
        return job
   
        
    

    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = MainUI()
    ui.show()
    app.exec()