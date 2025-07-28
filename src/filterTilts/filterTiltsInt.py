#!/fs/pool/pool-plitzko3/Michael/02-Software/crBoost_tutorial_test/conda3/bin/python

#%%
import os,shutil
import napari
import numpy as np
from PIL import Image
from qtpy.QtWidgets import QPushButton, QVBoxLayout, QWidget, QCheckBox, QApplication, QLabel, QComboBox, QMessageBox, QTextEdit
from scipy.ndimage import gaussian_filter
from src.rw.librw import tiltSeriesMeta,mdocMeta
from src.filterTilts.libFilterTilts import getDataFromPreExperiment
#import time

#%%
def loadImagesCBinteractive(tilseriesStar,relionProj='',outputFolder=None,threads=24):   
    ts=tiltSeriesMeta(tilseriesStar,relionProj)
    
    
    # Sort them by their Probability in ascending order
    ts.all_tilts_df = ts.all_tilts_df.sort_values(by='cryoBoostDlProbability', ascending=True)    
    return ts
def replace_borders_advanced(image, border_width=1, use_inner_mean=True):
    # Create a copy of the image
    img_with_mean_borders = image.copy()
    
    if use_inner_mean:
        # Calculate mean of inner image (excluding borders)
        mean_value = np.mean(image[border_width:-border_width, border_width:-border_width])
    else:
        # Calculate mean of entire image
        mean_value = np.mean(image)
    
    h, w = image.shape
    
    # Create border mask
    mask = np.ones_like(image, dtype=bool)
    mask[border_width:h-border_width, border_width:w-border_width] = False
    
    # Replace borders
    img_with_mean_borders[mask] = mean_value
    
    return img_with_mean_borders

#batchSize=64
#%% Load images with a Gaussian filter applied
def load_image(file_name, sigma=1.1):  # sigma controls blur amount
    
    img = Image.open(file_name)
    img=np.array(img)
    img = replace_borders_advanced(img, border_width=5, use_inner_mean=True)
    img=img.astype(np.float32)
    mean = np.mean(img)
    std = np.std(img)
    if std==0:
        std=1
    img = (img - mean) / std
    outlier_mask = img > 4.5
    img[outlier_mask]=0
    img = gaussian_filter(img, sigma=sigma)
    std = np.std(img)
    if std==0:
        std=1
    mean = np.mean(img)
    img_normalized = (img - mean) / std
        
    return img_normalized

class BatchViewer:
    def __init__(self,inputTiltseries,output_folder=None, batch_size=64,mdocWk="mdoc/*.mdoc"):
        
        if  isinstance(inputTiltseries,str):
            self.ts=tiltSeriesMeta(inputTiltseries)
        else:
            self.ts=inputTiltseries

        print('initializing custom batch viewer', flush=True)
        print("  found " + str(len(self.ts.all_tilts_df)) + " tilts", flush=True)
        self.orgNrTilts=len(self.ts.all_tilts_df)
        self.inputTiltseries=inputTiltseries
        self.ts.all_tilts_df = self.ts.all_tilts_df.sort_values(by='cryoBoostDlProbability', ascending=True)    
        self.df_full = self.ts.all_tilts_df
        self.df = self.df_full.copy()  # Working copy to enable batching without losing rest
        self.batch_size = batch_size
        self.current_batch = 0
        self.total_batches = (len(self.df) + batch_size - 1) // batch_size # Make sure there's always at least 1 batch
        self.output_folder = output_folder
        self.viewer = napari.Viewer()
        self.viewer.mouse_drag_callbacks.append(self.on_mouse_click)
        
        self.mdocWk=mdocWk

        self.image_layers = {} 
        self.point_layers = {}

        self.run_out_layer = None # Display run.out file 
        
        self.setup_navigation()
        self.load_batch(0)
        self.prob_counter()
        self.update_log_display()

    # Save the .star file when the viewer is closed
    def on_close(self):
        print("Loading batches to save final state as .star file...", flush=True)
        # Untick only-removed checkbox and dropdown to All
        self.only_removed_check.setChecked(False)
        self.filter_by_tiltseries("All Tilt-Series")

        self.ts.all_tilts_df=self.df
        self.ts.writeTiltSeries(self.output_folder+"tiltseries_labeled.star","tilt_seriesLabel")
        filterParams = {"cryoBoostDlLabel": ("good")}
        self.ts.filterTilts(filterParams)
        self.ts.writeTiltSeries(self.output_folder+"tiltseries_filtered.star")
        preExpFolder=os.path.dirname(self.inputTiltseries)
        outputFolder=self.output_folder
        print("org number of Tilts: " + str(self.orgNrTilts))
        if os.path.exists(preExpFolder+"/warp_frameseries.settings"):
            print("Warp frame alignment detected ...getting data from: " + preExpFolder)
            getDataFromPreExperiment(preExpFolder,outputFolder)
            os.makedirs(outputFolder+"/mdoc", exist_ok=True)    
            print("  filtering mdocs: " + self.mdocWk)
            mdocWk=os.path.dirname(self.mdocWk) + os.path.sep + "*.mdoc"
            mdoc=mdocMeta(mdocWk)
            mdoc.filterByTiltSeriesStarFile(outputFolder+"tiltseries_filtered.star")
            print("  filtered mdoc has " + str(len(mdoc.all_df)) + " tilts")
            print("  writing mdoc to " + outputFolder+"/mdoc")
            mdoc.writeAllMdoc(outputFolder+"/mdoc")    
        

    def setup_navigation(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create buttons to navigate between batches
        self.prev_btn = QPushButton("Previous Batch")
        self.prev_btn.clicked.connect(self.prev_batch)
        layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next Batch")
        self.next_btn.clicked.connect(self.next_batch)
        layout.addWidget(self.next_btn)

        # Create labels with probability range of batch
        self.prob_range_label = QLabel()
        layout.addWidget(self.prob_range_label)

        self.batch_counter_label = QLabel()
        self.batch_counter_label.setStyleSheet("color: white; margin-bottom: 10px;")
        layout.addWidget(self.batch_counter_label)

        # Create checkbox to filter only removed images
        self.only_removed_check = QCheckBox('Only show tilts that will be removed')
        self.only_removed_check.stateChanged.connect(self.only_removed_ticked)
        self.only_removed_check.setEnabled(True)
        #self.only_removed_check.setChecked(True) #Have it be checked at start
        layout.addWidget(self.only_removed_check)
        
        # Add dropdown for tilt series selection
        self.tilt_series_dropdown = QComboBox()
        self.tilt_series_dropdown.addItem("All Tilt-Series")  # Default option
        unique_values = self.df_full['rlnTomoName'].unique()
        self.tilt_series_dropdown.addItems([str(x) for x in unique_values])
        self.tilt_series_dropdown.currentTextChanged.connect(self.filter_by_tiltseries)
        self.tilt_series_dropdown.setEnabled(True)
        layout.addWidget(self.tilt_series_dropdown)

        # Add button to set all labels to good
        self.set_all_good_btn = QPushButton("Set All Labels to Good")
        self.set_all_good_btn.clicked.connect(self.set_all_labels_good)
        layout.addWidget(self.set_all_good_btn)

        # Add instructions to the legend label
        self.legend = QLabel()
        self.legend.setText("""
        <b>Instructions:</b>
        <ul>
            <li><b>Left click</b> on an image to change its label (good/bad)</li>
            <li><b>Right click</b> on an image to open it in IMOD</li>
            <li>Red indicator: tilt will be removed</li>
            <li>Use the navigation buttons to move between batches</li>
        </ul>
        """)
        self.legend.setStyleSheet("background-color: #222222; color: white; padding: 10px; border-radius: 5px;")        
        self.legend.setWordWrap(True)
        layout.addWidget(self.legend)
        
        widget.setLayout(layout)
        self.viewer.window.add_dock_widget(widget, area='right')

        # widget to display the last lines of run.out
        log_header = QLabel("<b>Log:</b>")
        log_header.setStyleSheet("color: white;")
        layout.addWidget(log_header)
        
        # Create simple text display for run.out
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            background-color: #333333;
            color: #CCCCCC;
            font-family: monospace;
            border: none;
            border-radius: 5px;
        """)
        self.log_display.setFixedHeight(400)
        layout.addWidget(self.log_display)

        
    def update_log_display(self):
        try:
            run_out_path = os.path.join(self.output_folder, "run.out")
            if not os.path.exists(run_out_path):
                self.log_display.setText("Log file not found")
                return
                
            # Read last 10 lines of the file
            with open(run_out_path, 'r') as f:
                lines = f.readlines()
                last_lines = lines[-10:] if len(lines) > 10 else lines
                self.log_display.setText(''.join(last_lines))
                
            # Auto-scroll to bottom
            scrollbar = self.log_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

            scrollbar.repaint()
        except Exception as e:
            self.log_display.setText(f"Error reading log: {str(e)}")
            
            scrollbar.repaint()


    def only_removed_ticked(self, state):
        only_removed = state == 2  # Qt.Checked = 2
        
        # Update the full DataFrame with any changes made to the filtered DataFrame and vice versa
        # Create a temporary DataFrame with only the image names and updated labels
        updates_df = self.df[['cryoBoostPNG', 'cryoBoostDlLabel']]

        # Use pandas merge to update all matching rows from updates to df_full based on 'cryoBoostPNG'
        self.df_full = self.df_full.merge(
            updates_df, 
            on='cryoBoostPNG', 
            how='left', # keep all rows of df_full
            suffixes=('', '_changed') # add the suffix _changed to the added column to avoid name conflicts    
        )

        # If an entry exists in the _changed column, set the mask to True
        mask = ~self.df_full['cryoBoostDlLabel_changed'].isna()
        # Update the label of the df_full where the mask is True
        self.df_full.loc[mask, 'cryoBoostDlLabel'] = self.df_full.loc[mask, 'cryoBoostDlLabel_changed']
        # Drop the temporary column of df_full
        self.df_full = self.df_full.drop(columns=['cryoBoostDlLabel_changed'])

        if only_removed and not len(self.df_full[self.df_full['cryoBoostDlLabel'] == "bad"]) == 0:
            # Reset to accurately display currently shown tilt series 
            self.tilt_series_dropdown.setCurrentText("All Tilt-Series")            
            self.df = self.df_full[self.df_full['cryoBoostDlLabel'] == "bad"].copy()
            print("\nOnly showing images that will be removed", flush=True)
            self.update_log_display()
        else:
            self.df = self.df_full.copy()
            if only_removed and len(self.df_full[self.df_full['cryoBoostDlLabel'] == "bad"]) == 0:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setText("No bad labels found")
                msg.setWindowTitle("Filter Information")
                msg.exec_()

        self.total_batches = (len(self.df) + self.batch_size - 1) // self.batch_size
        self.current_batch = 0  

        self.load_batch(0)
        self.prob_counter()


    def prob_counter(self):
        try:
            # Calculate indices for current batch
            start_idx = self.current_batch * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(self.df))
            
            # Get current batch probabilities
            current_batch = self.df.iloc[start_idx:end_idx]
            
            # Check if current_batch is empty
            if len(current_batch) == 0:
                self.prob_range_label.setText("No probability data available")
                return
            
            min_prob = current_batch['cryoBoostDlProbability'].iloc[0]
            max_prob = current_batch['cryoBoostDlProbability'].iloc[-1]
            self.prob_range_label.setText(f"Displayed Probability Range: {min_prob:.3f} - {max_prob:.3f}")
        except Exception as e:
            print(f"\nError in prob_counter: {e}", flush=True)
            self.prob_range_label.setText("Error getting probability data")


    def filter_by_tiltseries(self, selected_ts):
        # Update the full DataFrame with any changes made to the filtered DataFrame and vice versa
        # Create a temporary DataFrame with only the image names and updated labels
        updates_df = self.df[['cryoBoostPNG', 'cryoBoostDlLabel']]

        # Use pandas merge to update all matching rows from updates to df_full based on 'cryoBoostPNG'
        self.df_full = self.df_full.merge(
            updates_df, 
            on='cryoBoostPNG', 
            how='left', # keep all rows of df_full
            suffixes=('', '_changed') # add the suffix _changed to the added column to avoid name conflicts    
        )

        # If an entry exists in the _changed column, set the mask to True
        mask = ~self.df_full['cryoBoostDlLabel_changed'].isna()
        # Update the label of the df_full where the mask is True
        self.df_full.loc[mask, 'cryoBoostDlLabel'] = self.df_full.loc[mask, 'cryoBoostDlLabel_changed']
        # Drop the temporary column of df_full
        self.df_full = self.df_full.drop(columns=['cryoBoostDlLabel_changed'])

        # Filter based on selected tilt series
        if selected_ts == "All Tilt-Series":
            self.df = self.df_full.copy()
        else:
            # Untick only-removed checkbox
            self.only_removed_check.setChecked(False)
            self.df = self.df_full[self.df_full['rlnTomoName'] == selected_ts].copy()
    
        self.total_batches = (len(self.df) + self.batch_size - 1) // self.batch_size
        self.current_batch = 0  
            
        self.load_batch(0)
        self.prob_counter()


    def set_all_labels_good(self):
        # Show confirmation dialog
        confirm = QMessageBox()
        confirm.setWindowTitle("Confirm Action")
        confirm.setText("Are you sure you want to set ALL labels to good?")
        confirm.setInformativeText("This will override all previous labelling decisions")
        confirm.setIcon(QMessageBox.Warning)
        confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        confirm.setDefaultButton(QMessageBox.Cancel)
        
        # Get user's decision
        response = confirm.exec_()
        
        if response == QMessageBox.Yes:
            # Set all labels in the working df and the main df to "good"
            self.df['cryoBoostDlLabel'] = "good"
            self.df_full['cryoBoostDlLabel'] = "good"
            
            # Update the current batch display to reflect changes
            for i, layer_name in enumerate(self.point_layers):
                if self.point_layers[i].visible:
                    self.point_layers[i].face_color = 'green'
                    self.point_layers[i].border_color = 'green'
            
            print("\nAll labels have been set to 'good'", flush=True)
            # Reload the current batch to ensure all indicators are updated
            self.update_log_display()
            self.load_batch(self.current_batch)
        else:
            print("\nOperation cancelled", flush=True)
            self.update_log_display()

    # replacement instead of new layer
    def load_batch(self, batch_num):###
        #startT = time.time()        
        self.current_batch = batch_num
        
        # Get images for this batch
        start_idx = batch_num * self.batch_size
        end_idx = min(start_idx + self.batch_size, len(self.df))
        batch_df = self.df.iloc[start_idx:end_idx]
        batch_size = len(batch_df)
        
        # Calculate grid layout
        n_images = batch_size
        grid_size = int(np.ceil(np.sqrt(n_images)))
        self.viewer.grid.shape = (grid_size, grid_size)
        
        # Create layers if this is the first batch
        first_load = len(self.image_layers) == 0
        if first_load:
            for i in range(self.batch_size):
                # Create placeholder layers even if we don't have that many images
                layer_name = f'image_layer_{i}'
                # Add an empty image first (will be replaced)
                empty_img = np.zeros((512, 512), dtype=np.float32)
                img_layer = self.viewer.add_image(
                    empty_img,
                    name=layer_name,
                    colormap='gray',
                    blending='additive',
                    visible=(i < batch_size),  # Only show if we have data for it
                    contrast_limits=None
                )
                self.image_layers[i] = img_layer
                
                # Add corresponding point layer
                point_pos = [[30, 30]]  # Position near top-left corner
                point_layer = self.viewer.add_points(
                    point_pos,
                    name=f'label_indicator_{i}',
                    size=30,
                    face_color='red',  # Default color
                    border_color='red',
                    symbol='disc',
                    visible=(i < batch_size)  # Only show if we have data for it
                )
                self.point_layers[i] = point_layer
        
        # Update layers with new batch data
        for i in range(self.batch_size):
            # Hide all layers first
            self.image_layers[i].visible = False
            self.point_layers[i].visible = False
            self.image_layers[i].name = f'image_layer_{i}'
            self.point_layers[i].name = f'label_indicator_{i}'
        
        # Update with actual data for this batch
        for i, (_, row) in enumerate(batch_df.iterrows()):
            img_path = row['cryoBoostPNG']
            
            # Load and update image data
            img = load_image(img_path)
            self.image_layers[i].data = img
            self.image_layers[i].name = img_path  # Update name to show current image path
            self.image_layers[i].visible = True
            self.image_layers[i].reset_contrast_limits() # Re-apply the contrast when the image is updated (first empty image --> need to update)
            
            # Update point layer color
            color = 'green' if row['cryoBoostDlLabel'] == "good" else 'red'
            self.point_layers[i].face_color = color
            self.point_layers[i].border_color = color
            self.point_layers[i].name = f'label_indicator_{img_path}'
            self.point_layers[i].visible = True
  
        # Position layers in grid with spacing
        spacing = 10  # pixels
        if len(batch_df) > 0:
            img_height, img_width = self.image_layers[0].data.shape
            
            for i in range(batch_size):
                # Calculate grid position
                row_idx = i // grid_size
                col_idx = i % grid_size
                
                # Calculate pixel position with spacing
                x = col_idx * (img_width + spacing)
                y = row_idx * (img_height + spacing)
                
                # Update layer translations
                self.image_layers[i].translate = (y, x)  # napari uses (y,x) ordering
                self.point_layers[i].translate = (y, x)
        
        # Reset view to show all images
        self.viewer.reset_view()
        
        # Update button states
        self.prev_btn.setEnabled(batch_num > 0)
        self.next_btn.setEnabled(batch_num < self.total_batches - 1)
        # Update batch counter label
        self.batch_counter_label.setText(f"Showing batch {batch_num + 1} of {self.total_batches}")  
        self.prob_counter()
        #endT = time.time()
        #print(f"Total time: {endT - startT} seconds", flush=True)
        
        #print(f'\nloaded batch {batch_num + 1} of {self.total_batches}',flush=True)
        #self.update_log_display()


    def next_batch(self):
        if self.current_batch < self.total_batches - 1:
            #startT = time.time()
            self.load_batch(self.current_batch + 1)


    def prev_batch(self):
        if self.current_batch > 0:
            self.load_batch(self.current_batch - 1)


    def on_mouse_click(self, layer, event):
        # Left button is 1, right button is 2
        if event.button == 1:
            self.on_left_click(layer, event)
        elif event.button == 2:
            self.on_right_click(layer, event)

    
    def on_left_click(self, layer, event):
        # Get the clicked coordinates in world space
        coordinates = event.position
        x, y = int(coordinates[1]), int(coordinates[0])  # Swap x,y as napari uses (y,x)
    
        # Find which layer was clicked
        clicked_layer = None
        for current_layer in self.viewer.layers:
            if isinstance(current_layer, napari.layers.Image):
                # Get layer position and scale
                translate = current_layer.translate
                scale = current_layer.scale
                
                # Transform world coordinates to layer coordinates
                layer_x = (x - translate[1]) / scale[1]
                layer_y = (y - translate[0]) / scale[0]
                
                # Get image dimensions
                img_height, img_width = current_layer.data.shape
                
                # Check if click is within layer bounds
                if (0 <= layer_x < img_width and 
                    0 <= layer_y < img_height):
                    clicked_layer = current_layer
                    break

        if clicked_layer is not None and not clicked_layer.name.startswith("image_layer_"):
            # Get image name from layer
            img_name = clicked_layer.name            
            # Find corresponding index in DataFrame
            index = self.df[self.df['cryoBoostPNG'] == img_name].index[0]
            
            # Toggle the label
            if self.df.loc[index, 'cryoBoostDlLabel'] == 'good':
                invLabel = 'bad'
            if self.df.loc[index, 'cryoBoostDlLabel'] == 'bad':
                invLabel = 'good'
            self.df.loc[index, 'cryoBoostDlLabel'] = invLabel
            #new_label = self.df.loc[index, 'cryoBoostDlLabel']
            print(f"\nUpdated label for {img_name} to {invLabel}", flush=True)
            self.update_log_display()
            # Update point color
            color = 'green' if invLabel == 'good' else 'red'
            indicator_layer = self.viewer.layers[f'label_indicator_{img_name}']
            indicator_layer.face_color = color
            indicator_layer.border_color = color 
            

    def on_right_click(self, layer, event):
        # Get the clicked coordinates in world space
        coordinates = event.position
        x, y = int(coordinates[1]), int(coordinates[0])  # Swap x,y as napari uses (y,x)
    
        # Find which layer was clicked
        clicked_layer = None
        for current_layer in self.viewer.layers:
            if isinstance(current_layer, napari.layers.Image):
                # Get layer position and scale
                translate = current_layer.translate
                scale = current_layer.scale
                
                # Transform world coordinates to layer coordinates
                layer_x = (x - translate[1]) / scale[1]
                layer_y = (y - translate[0]) / scale[0]
                
                # Get image dimensions
                img_height, img_width = current_layer.data.shape
                
                # Check if click is within layer bounds
                if (0 <= layer_x < img_width and 
                    0 <= layer_y < img_height):
                    clicked_layer = current_layer
                    break
        
        if clicked_layer is not None and not clicked_layer.name.startswith("image_layer_"):
            # Get image name from layer
            img_name = clicked_layer.name
            
            # Find corresponding index in DataFrame
            index = self.df[self.df['cryoBoostPNG'] == img_name].index[0]
            
            # Get the MRC file path
            mrc_name = self.df.loc[index, 'rlnMicrographName']

            try:
                print(f"\nOpening {mrc_name} with IMOD", flush=True)
                print("  imod " + mrc_name, flush=True)
                os.system("imod " + mrc_name)
            except Exception as e:
                print(f"\nError opening file with IMOD: {e}")
            self.update_log_display()


#%%
def filterTiltsInterActive(inputList, output_folder=None,mode="onFailure"):

    inputBase=os.path.basename(inputList)
    if inputBase=="tiltseries_filtered.star":
        inputListOrg=inputList
        inputList=inputList.replace("tiltseries_filtered.star","tiltseries_labeled.star")
        # print("mode======: "+mode)
        # print("file exists"+ str(os.path.exists(inputList.replace("tiltseries_filtered.star","DATA_IN_DISTRIBUTION"))))
        # print("comp State"+str(mode=="onFailure" and os.path.exists(inputList.replace("tiltseries_filtered.star","DATA_IN_DISTRIBUTION"))) )
        didFile=os.path.dirname(inputList)+os.path.sep+"DATA_IN_DISTRIBUTION"
        if mode=="Never" or (mode=="onFailure" and os.path.exists(didFile)):
            print("Skipping manual sort",flush=True)
            ts=tiltSeriesMeta(inputListOrg)
            ts.writeTiltSeries(output_folder+"tiltseries_filtered.star")
            if os.path.exists(os.path.dirname(inputListOrg)+"/warp_frameseries.settings"):
                print("Warp frame alignment detected ...getting data from: " + os.path.dirname(inputListOrg),flush=True)
                getDataFromPreExperiment(os.path.dirname(inputListOrg),output_folder)
                mdocFold=os.path.dirname(inputListOrg) + "/mdoc"
                if os.path.exists(mdocFold):
                    print("mdoc folder detected " + mdocFold,flush=True)
                    print("copy " + mdocFold  + " to " + output_folder,flush=True)
                    shutil.copytree(mdocFold, output_folder+"/mdoc")
            return   
    print("preparing napari",flush=True)
    viewer = BatchViewer(inputList, output_folder)
    app = QApplication.instance() 
    app.lastWindowClosed.connect(viewer.on_close) 
    napari.run()

if __name__ == '__main__':
    filterTiltsInterActive()
