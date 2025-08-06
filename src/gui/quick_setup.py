import sys,os
from PyQt6.QtWidgets import QDialog
from collections import namedtuple
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                            QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton,QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog
from src.gui.libGui import browse_dirs

class quickSetup(QDialog):
    def __init__(self,args):
        super().__init__()
        self.initUI(args)
        
    def initUI(self,args):
        # Set window title and size
        self.setWindowTitle('CryoBoost Quick Setup')
        self.resize(400, 200)
        
        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout) 
        self.args=args
        # Create dropdown for workflow selection
        workflow_layout = QHBoxLayout()
        workflow_label = QLabel("Workflow:")
        self.workflow_dropdown = QComboBox()
        self.CRYOBOOST_HOME=os.getenv("CRYOBOOST_HOME")
        folder_path = self.CRYOBOOST_HOME + "/config/Schemes/"
        workflows = [entry.name for entry in os.scandir(folder_path) if entry.is_dir()]
        workflows.append("browse")
        self.workflow_dropdown.addItems(workflows)
        if args.scheme in workflows:
            self.workflow_dropdown.setCurrentText(args.scheme)
        workflow_layout.addWidget(workflow_label)
        workflow_layout.addWidget(self.workflow_dropdown)
        self.workflow_dropdown.setToolTip("Select a workflow from the dropdown or choose 'browse' to select a custom scheme.")
        self.workflow_dropdown.currentTextChanged.connect(self.workflow_selected)
        main_layout.addLayout(workflow_layout)
        
         # Create checkbox for Filter Tilts
        self.filterTilts_cb = QCheckBox("Filter tilts (remove bad tilts)")
        main_layout.addWidget(self.filterTilts_cb)
        if args.FilterTilts == "True":
            self.filterTilts_cb.setChecked(True)
        else:
            self.filterTilts_cb.setChecked(False)
        
        # Create checkbox for Noise2Noise filter
        self.noise2noise_cb = QCheckBox("Noise2Noise filter")
        main_layout.addWidget(self.noise2noise_cb)
        if args.Noise2Noise == "True":
            self.noise2noise_cb.setChecked(True)
        else:
            self.noise2noise_cb.setChecked(False)
        
        # Create checkbox for Particle Setup
        self.particle_setup_cb = QCheckBox('Particle Setup (Template Matching,Peak Extraction,Particle Reconstruction)') 
        if args.species == "None":
            self.particle_setup_cb.setChecked(False)
        else:
            self.particle_setup_cb.setChecked(True)
        
        # Connect the toggled signal instead of stateChanged
        self.particle_setup_cb.toggled.connect(self.toggle_species_field)
        main_layout.addWidget(self.particle_setup_cb)
        
        # Create text field for species
        self.inputSpecies = args.species
        species_layout = QHBoxLayout()
        species_label = QLabel("Particle Species Names:")
        species_label.setToolTip("Enter species names separated by commas (e.g., Ribosome,Proteasome,Other)")
        self.species_input = QLineEdit()
        self.species_input.setPlaceholderText("Ribosome,Proteasome,Other")
        self.species_input.setEnabled(True)
        self.species_input.textChanged.connect(self.validate_species_name)
        if args.species == "None":
            self.species_input.setEnabled(False)

        species_layout.addWidget(species_label)
        species_layout.addWidget(self.species_input)
        main_layout.addLayout(species_layout)
        self.species_input.setText(args.species)

        # Add some spacing
        main_layout.addSpacing(20)
        
        # Add OK and Cancel buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.cancel_button.clicked.connect(self.cancelCallback)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
        
    def cancelCallback(self):
        # Handle cancel button click
        self.args=None
        self.close()
    
       
    def workflow_selected(self, text):
        # Handle the workflow selection change
        if text == "browse":
            # Open a file dialog to select a custom scheme
            options = QFileDialog.Option.DontUseNativeDialog
            file_name=browse_dirs(target_field=None,target_fold=None)
            if file_name and file_name != "/":
                self.workflow_dropdown.addItem(file_name)
                self.workflow_dropdown.setCurrentText(file_name)
       
        
    def toggle_species_field(self, checked):
        # Enable/disable the species field based on the particle setup checkbox
        self.species_input.setEnabled(checked)
        if checked:
            self.species_input.setText("noTag")  # Default value when enabled
        else: 
            self.species_input.setText("None")
    
    def validate_species_name(self, text):
        
        if "_" in text:
            # Show warning message if underscore is found
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Warning: Underscore in Species Name")
            msg_box.setText("Species name contains underscores ('_').")
            msg_box.setInformativeText("Underscores in species names are not possible")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
    
        
    def on_ok_clicked(self):
        # Get values from the form
        
        if self.noise2noise_cb.isChecked():
            self.args.Noise2Noise = "True"
        else:
            self.args.Noise2Noise = "False"
        
        if self.filterTilts_cb.isChecked():
            self.args.FilterTilts = "True"
        else:
            self.args.FilterTilts = "False"

        if self.particle_setup_cb.isChecked():
            if "_" in self.species_input.text():
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setWindowTitle("Warning: Underscore in Species Name")
                msg_box.setText("Species name contains underscores ('_').")
                msg_box.setInformativeText("Remove underscore from species names to continue")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()
                return    
            
            if self.species_input.text() == "":
                self.species_input.setText("noTag")
            else:    
                self.args.species = self.species_input.text()
        else:
            self.args.species = "None"
        
        self.args.scheme=self.workflow_dropdown.currentText()
        
         
        self.close()
    def getResult(self):
        return self.args    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = quickSetup("")
    window.show()
    sys.exit(app.exec())
    