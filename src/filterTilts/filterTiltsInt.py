#!/usr/bin/env crboost_python
"""Interactive sorting of tilts into "good" and "bad" with a napari viewer.

The tilts are shown 64 at a time in a square grid. A green dot marks a good
tilt, a red dot a bad one; left click toggles a tilt, right click opens it in
IMOD. On closing the window the labels are written back to
tiltseries_labeled.star and the surviving tilts to tiltseries_filtered.star.

Notes on the implementation
---------------------------
The batch is drawn as ONE image layer holding a montage of all 64 tilts plus
ONE points layer holding all 64 label dots. The straightforward alternative -
one image and one points layer per tilt - is what made the window take up to
half an hour to appear: every add_image()/add_points() builds a vispy visual,
uploads a texture and adds a row with a thumbnail to the layer list, and 128
of those are very slow on machines with software OpenGL (e.g. over ssh -X).
Because there is only one layer, there is only one pair of contrast limits, so
_paste_tile() stretches every tilt to 0..1 individually; that gives the same
picture as a per-tilt reset_contrast_limits().

Since there are no per-tilt layers any more, a click is mapped back to a tilt
geometrically by _tile_index_from_world() instead of by looking up a layer.

Starting up is further overlapped: napari/Qt/PIL/scipy are imported lazily,
the tilts are decoded in a thread pool, and the window is shown before the
first batch is ready - _fill_pending() pastes the tilts in as they arrive.
Neighbouring batches are prefetched into an LRU cache so paging stays instant.

Environment variables (all optional)
------------------------------------
CB_TILT_MAX_DISPLAY_SIZE  longest tile edge in px, 0 = full resolution (768)
CB_TILT_THREADS           number of decoding threads (min(8, #cpus))
CB_TILT_CACHE_MB          size of the decoded-tilt cache in MB (1024)
CB_TILT_TILE_GAP          black gap between the tiles of the montage, px (0)
CB_TILT_TIMING            set to 1 for timestamped progress lines in run.out
"""

#%%
import os,shutil
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import time
import numpy as np
from src.rw.librw import tiltSeriesMeta,mdocMeta
from src.filterTilts.libFilterTilts import getDataFromPreExperiment

# napari/Qt/PIL/scipy are imported on first use instead of at module import.
# Importing napari pulls in Qt, vispy/OpenGL and the plugin manager (which
# scans the entry points of every napari plugin in the environment). The
# workflow imports this module even when the interactive sorting is skipped
# (mode "Never" / DATA_IN_DISTRIBUTION), where none of it is needed. This avoids imports if not needed.
# All of these imports happen in the main thread only, before any loader
# thread is started.
napari = None
Image = None
gaussian_filter = None
QPushButton = QVBoxLayout = QWidget = QCheckBox = QApplication = None
QLabel = QComboBox = QMessageBox = QTextEdit = None
QTimer = None

_START_T = time.time()
# Set CB_TILT_TIMING=1 to get timestamped progress messages in run.out. They
# are off by default but make it easy to see which phase is slow on a given
# machine (napari import, viewer creation, image decoding, ...).
_TIMING = bool(os.environ.get("CB_TILT_TIMING"))


def _phase(msg):
    """Timestamped startup/paging progress, only when CB_TILT_TIMING is set."""
    if _TIMING:
        print(f"[filterTilts +{time.time() - _START_T:6.1f}s] {msg}", flush=True)


def _ensure_napari():
    global napari
    if napari is None:
        _phase("importing napari (Qt/vispy/plugins) ...")
        import napari as _napari
        napari = _napari
        _phase("napari imported")
    return napari


def _ensure_qt():
    global QPushButton, QVBoxLayout, QWidget, QCheckBox, QApplication
    global QLabel, QComboBox, QMessageBox, QTextEdit
    if QPushButton is not None:
        return
    from qtpy.QtWidgets import (QPushButton as _QPushButton,
                                QVBoxLayout as _QVBoxLayout,
                                QWidget as _QWidget,
                                QCheckBox as _QCheckBox,
                                QApplication as _QApplication,
                                QLabel as _QLabel,
                                QComboBox as _QComboBox,
                                QMessageBox as _QMessageBox,
                                QTextEdit as _QTextEdit)
    QPushButton = _QPushButton
    QVBoxLayout = _QVBoxLayout
    QWidget = _QWidget
    QCheckBox = _QCheckBox
    QApplication = _QApplication
    QLabel = _QLabel
    QComboBox = _QComboBox
    QMessageBox = _QMessageBox
    QTextEdit = _QTextEdit


def _ensure_qtcore():
    global QTimer
    if QTimer is None:
        from qtpy.QtCore import QTimer as _QTimer
        QTimer = _QTimer


def _ensure_imaging():
    global Image, gaussian_filter
    if Image is None:
        from PIL import Image as _Image
        from scipy.ndimage import gaussian_filter as _gaussian_filter
        # Register the PNG codec here, in the main thread. PIL imports its
        # decoders lazily on the first Image.open(), and letting several
        # loader threads trigger that import concurrently can stall them.
        _Image.preinit()
        Image = _Image
        gaussian_filter = _gaussian_filter


def _check_display():
    """A missing/unreachable X display makes napari.Viewer() hang instead of
    failing, which looks like 'the program never starts'."""
    if os.name != "posix" or os.uname().sysname == "Darwin":
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("WARNING: neither DISPLAY nor WAYLAND_DISPLAY is set.", flush=True)
        print("         napari needs a graphical display; on a cluster use "
              "'ssh -X'/'ssh -Y' or run this on the workstation.", flush=True)

def replace_borders_advanced(image, border_width=1, use_inner_mean=True):
    # Create a copy of the image
    img_with_mean_borders = image.copy()
    
    if use_inner_mean:
        # Calculate mean of inner image (excluding borders)
        mean_value = np.mean(image[border_width:-border_width, border_width:-border_width])
    else:
        # Calculate mean of entire image
        mean_value = np.mean(image)
    
    # Replace borders (slice assignment avoids full-size mask temporaries)
    bw = border_width
    img_with_mean_borders[:bw, :] = mean_value
    img_with_mean_borders[-bw:, :] = mean_value
    img_with_mean_borders[:, :bw] = mean_value
    img_with_mean_borders[:, -bw:] = mean_value
    
    return img_with_mean_borders

def _box_reduce(img, factor):
    """Average factor x factor blocks, same output size as PIL Image.reduce()."""
    h, w = img.shape
    hp = -(-h // factor) * factor
    wp = -(-w // factor) * factor
    if hp != h or wp != w:
        img = np.pad(img, ((0, hp - h), (0, wp - w)), mode='edge')
    return img.reshape(hp // factor, factor,
                       wp // factor, factor).mean(axis=(1, 3)).astype(np.float32)


#batchSize=64
#%% Load images with a Gaussian filter applied
def load_image(file_name, sigma=1.1, max_size=None):  # sigma controls blur amount
    
    _ensure_imaging()
    img = Image.open(file_name)
    # The tilts are shown as small tiles of a grid, so the full camera
    # resolution is never visible. Box-averaging down keeps the montage small.
    # It is done AFTER the filters below, so the result is the same as the
    # one-layer-per-tilt version, which filtered at full resolution.
    factor = 1
    if max_size:
        factor = max(1, int(-(-max(img.size) // int(max_size))))
    img=np.asarray(img)
    img = replace_borders_advanced(img, border_width=5, use_inner_mean=True)
    img=img.astype(np.float32, copy=False)
    mean = float(np.mean(img))
    std = float(np.std(img))
    if std==0:
        std=1
    img -= mean
    img /= std
    img[img > 4.5]=0
    img = gaussian_filter(img, sigma=sigma, output=np.float32)
    std = float(np.std(img))
    if std==0:
        std=1
    mean = float(np.mean(img))
    img -= mean
    img /= std
    if factor > 1:
        img = _box_reduce(img, factor)
        
    return img

class BatchViewer:
    def __init__(self,inputTiltseries,output_folder=None, batch_size=64,mdocWk="mdoc/*.mdoc",
                 threads=None, max_display_size=768, cache_mb=1024):
        
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
        self.mdocWk=mdocWk

        # State of the montage; see the module docstring for why the batch is
        # one layer rather than one layer per tilt.
        #   _montage     the (grid*cell_h, grid*cell_w) array that is displayed
        #   _tile_paths  PNG path of each tile of the current batch, in order
        #   _colors      'green'/'red' per tile, mirrored to the points layer
        #   _tile_shape  size of one tilt, _cell = _tile_shape + the gap
        self.montage_layer = None
        self.points_layer = None
        self._montage = None
        self._tile_paths = []
        self._colors = []
        self._grid_size = 1
        self._tile_shape = (2, 2)
        self._cell = (2, 2)

        # Image loading: decode/filter a batch in parallel, keep the decoded
        # tilts of the neighbouring batches in an LRU cache and prefetch them
        # in the background, so paging is not I/O or CPU bound any more.
        # See the module docstring for the environment variables used here.
        self.max_display_size = int(os.environ.get("CB_TILT_MAX_DISPLAY_SIZE", max_display_size))
        if self.max_display_size <= 0:
            self.max_display_size = None
        if threads is None:
            threads = min(8, os.cpu_count() or 4)
        self.threads = max(1, int(os.environ.get("CB_TILT_THREADS", threads)))
        self.cache_bytes = int(os.environ.get("CB_TILT_CACHE_MB", cache_mb)) * 1024 * 1024
        self._cache = OrderedDict()
        self._cache_used = 0
        self._cache_lock = threading.Lock()
        self._inflight = {}
        self._failed = set()
        self._pool = ThreadPoolExecutor(max_workers=self.threads,
                                        thread_name_prefix="tiltLoader")
        print("  loading with " + str(self.threads) + " threads, display size "
              + str(self.max_display_size), flush=True)

        # Import napari and build the window FIRST, before any loader thread is
        # started, so the window appears as early as possible and the import
        # cannot be affected by background work.
        _check_display()
        self.viewer = _ensure_napari().Viewer()
        _phase("napari viewer created")
        self.viewer.mouse_drag_callbacks.append(self.on_mouse_click)

        # Now that the expensive import is done, start decoding/filtering the
        # first batch in the background: it overlaps with building the side
        # panel and the layers below instead of running after them.
        # PIL/scipy are imported here, in the main thread, so that the loader
        # threads never import anything themselves.
        _ensure_imaging()
        self._prefetch(0)

        self.run_out_layer = None # Display run.out file 
        
        self.setup_navigation()
        _phase("side panel built")
        self._fill_timer = None
        # progressive: open the window now, fill the tilts in as they decode
        self.load_batch(0, progressive=True)
        self.prob_counter()
        self.update_log_display()
        _phase("first batch displayed - viewer ready")

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
        
        self._pool.shutdown(wait=False)
        

    def setup_navigation(self):
        _ensure_qt()
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
                
            # Read the last 10 lines from the tail of the file only
            # (run.out keeps growing, reading it completely got slower and
            #  slower and this runs on every click)
            tail_bytes = 65536
            with open(run_out_path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                f.seek(max(0, file_size - tail_bytes))
                data = f.read()
            lines = data.decode('utf-8', 'replace').splitlines(True)
            if file_size > tail_bytes and len(lines) > 1:
                lines = lines[1:]  # drop the partial first line
            last_lines = lines[-10:] if len(lines) > 10 else lines
            self.log_display.setText(''.join(last_lines))
                
            # Auto-scroll to bottom
            scrollbar = self.log_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

            scrollbar.repaint()
        except Exception as e:
            self.log_display.setText(f"Error reading log: {str(e)}")


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
            self._colors = ['green'] * len(self._colors)
            self._apply_colors()
            
            print("\nAll labels have been set to 'good'", flush=True)
            # Reload the current batch to ensure all indicators are updated
            self.update_log_display()
            self.load_batch(self.current_batch)
        else:
            print("\nOperation cancelled", flush=True)
            self.update_log_display()

    def _submit(self, path):
        """Queue an image for loading. Returns None if it is already cached."""
        with self._cache_lock:
            if path in self._cache:
                self._cache.move_to_end(path)
                return None
            future = self._inflight.get(path)
            if future is None:
                future = self._pool.submit(self._load_and_cache, path)
                self._inflight[path] = future
        return future


    def _load_and_cache(self, path):
        """Decode+filter one tilt in a loader thread and put it in the cache.

        Runs off the GUI thread; PIL and scipy release the GIL for the heavy
        parts, so several tilts really do decode in parallel.
        """
        t0 = time.time()
        try:
            img = load_image(path, max_size=self.max_display_size)
        except Exception as e:
            # A tilt that cannot be read must not stall the viewer: remember it
            # as failed, show an empty tile and carry on.
            with self._cache_lock:
                self._inflight.pop(path, None)
                self._failed.add(path)
            print("  ERROR reading " + str(path) + ": " + str(e), flush=True)
            raise
        if _TIMING:
            # Shows whether a single tilt is slow to read (storage) or whether
            # it is simply the number of tilts that costs the time.
            self._loads_done = getattr(self, '_loads_done', 0) + 1
            if self._loads_done <= 3:
                _phase(f"tilt {self._loads_done}: decoded "
                       f"{img.shape[1]}x{img.shape[0]} in {time.time() - t0:.2f}s")
        with self._cache_lock:
            self._inflight.pop(path, None)
            if path not in self._cache:
                self._cache[path] = img
                self._cache_used += img.nbytes
            self._cache.move_to_end(path)
            while self._cache_used > self.cache_bytes and len(self._cache) > 1:
                _, dropped = self._cache.popitem(last=False)
                self._cache_used -= dropped.nbytes
        return img


    def _get_images(self, paths):
        """Decoded tilts for these paths, waiting for the ones not cached yet."""
        # submit everything first so the loads run in parallel
        futures = [self._submit(path) for path in paths]
        images = []
        blank = None
        for path, future in zip(paths, futures):
            try:
                if future is not None:
                    images.append(future.result())
                    continue
                with self._cache_lock:
                    img = self._cache.get(path)
                    if img is not None:
                        self._cache.move_to_end(path)
                images.append(img if img is not None else self._load_and_cache(path))
            except Exception:
                # Already reported by _load_and_cache: show an empty tile
                # instead of tearing down the whole viewer
                if blank is None:
                    blank = np.zeros(self._image_shape(path), dtype=np.float32)
                images.append(blank)
        return images


    def _submit_batch(self, paths):
        """Queue all tilts of a batch without waiting for any of them."""
        for path in paths:
            self._submit(path)


    def _image_shape(self, path):
        """Tile shape after downsampling, from the PNG header only.

        Image.open() just reads the header, so this costs one small read
        instead of decoding a tilt, and gives the grid layout up front.
        """
        _ensure_imaging()
        try:
            with Image.open(path) as img:
                width, height = img.size
        except Exception as e:
            print("  could not read image size of " + str(path) + ": " + str(e), flush=True)
            return (512, 512)
        if self.max_display_size:
            factor = int(-(-max(width, height) // int(self.max_display_size)))
            if factor > 1:
                # Image.reduce() rounds the size up, match it exactly so the
                # placeholder tile has the same shape as the decoded tilt
                width = -(-width // factor)
                height = -(-height // factor)
        return (height, width)


    def _start_fill(self, batch_num, paths, pending):
        """Start filling the tiles listed in `pending` from the Qt event loop.

        The window is shown before the first batch has finished decoding; this
        timer copies each tilt into the montage as it arrives, so the user can
        already scroll and click while the rest is still loading.
        """
        self._fill_batch = batch_num
        self._fill_paths = paths
        self._fill_pendingIdx = list(pending)
        if not pending:
            self._fill_done_t = None
            return
        self._fill_start_t = time.time()
        _ensure_qtcore()
        if getattr(self, '_fill_timer', None) is None:
            self._fill_timer = QTimer()
            self._fill_timer.setInterval(100)
            self._fill_timer.timeout.connect(self._fill_pending)
        self._fill_timer.start()


    def _fill_pending(self):
        """Paste the tilts that finished decoding into the montage.

        Called by the timer of _start_fill(), i.e. in the GUI thread, which is
        the only thread allowed to touch napari layers.
        """
        batch_num = self._fill_batch
        still_pending = []
        filled = 0
        canvas = self._canvas_widget()
        if canvas is not None:
            canvas.setUpdatesEnabled(False)
        try:
            for i in self._fill_pendingIdx:
                if batch_num != self.current_batch:
                    # The user paged away while this batch was still loading
                    still_pending = []
                    break
                path = self._fill_paths[i]
                with self._cache_lock:
                    img = self._cache.get(path)
                    if img is not None:
                        self._cache.move_to_end(path)
                    failed = path in self._failed
                    inflight = path in self._inflight
                if img is None:
                    # Unreadable tilts are dropped, otherwise this would keep
                    # polling for an image that will never arrive
                    if not failed:
                        if not inflight:
                            # Neither cached nor loading: the entry was evicted
                            # from the cache before it could be shown. Queue it
                            # again, so the fill can never spin forever.
                            self._submit(path)
                        still_pending.append(i)
                    continue
                if i >= len(self._tile_paths) or self._tile_paths[i] != path:
                    continue  # the slot belongs to another batch meanwhile
                self._paste_tile(self._montage, i, img)
                filled += 1
            if filled:
                # One texture upload for all tilts that arrived in this tick,
                # instead of one per tilt
                self.montage_layer.data = self._montage
                self._set_contrast_limits(self.montage_layer)
        finally:
            if canvas is not None:
                canvas.setUpdatesEnabled(True)
                if filled:
                    canvas.update()
        self._fill_pendingIdx = still_pending
        if not still_pending:
            self._fill_timer.stop()
            if batch_num == self.current_batch:
                _phase(f"all {len(self._fill_paths)} tilts of batch "
                       f"{batch_num + 1} shown "
                       f"({time.time() - self._fill_start_t:.1f}s after the window opened)")


    def _prefetch(self, batch_num):
        if batch_num < 0 or batch_num >= self.total_batches:
            return
        start_idx = batch_num * self.batch_size
        end_idx = min(start_idx + self.batch_size, len(self.df))
        for path in self.df['cryoBoostPNG'].iloc[start_idx:end_idx]:
            self._submit(path)


    def _canvas_widget(self):
        """Widget whose repaints are suppressed while a batch is swapped in."""
        try:
            canvas = self.viewer.window._qt_viewer.canvas
        except Exception:
            return None
        widget = getattr(canvas, 'native', canvas)
        return widget if hasattr(widget, 'setUpdatesEnabled') else None


    def _paste_tile(self, montage, i, img):
        """Copy one decoded tilt into its cell of the montage.

        A single layer has a single pair of contrast limits, so each tilt is
        stretched to 0..1 here and the limits of the layer are pinned to
        (0, 1). That is the same intensity mapping a per-tilt
        reset_contrast_limits() would give (min -> black, max -> white).
        """
        cell_h, cell_w = self._cell
        tile_h, tile_w = self._tile_shape
        row_idx, col_idx = divmod(i, self._grid_size)
        y = row_idx * cell_h
        x = col_idx * cell_w
        # Clip, in case a tilt has a slightly different size than the first one
        h = min(tile_h, img.shape[0])
        w = min(tile_w, img.shape[1])
        tile = img[:h, :w]
        low = float(tile.min())
        high = float(tile.max())
        span = high - low
        dest = montage[y:y + h, x:x + w]
        if span <= 0:
            dest[:] = 0.0
            return
        np.copyto(dest, tile, casting='unsafe')
        dest -= low
        dest /= span


    def _apply_colors(self):
        """Push the label colours of the whole batch to the points layer."""
        if self.points_layer is None or not self._colors:
            return
        colors = list(self._colors)
        self.points_layer.face_color = colors
        self.points_layer.border_color = colors


    def _tile_index_from_world(self, y, x):
        """Which tilt of the batch is at this canvas position (or None)."""
        if self.montage_layer is None or not self._tile_paths:
            return None
        try:
            translate = self.montage_layer.translate
            y -= float(translate[0])
            x -= float(translate[1])
        except Exception:
            pass
        cell_h, cell_w = self._cell
        tile_h, tile_w = self._tile_shape
        if y < 0 or x < 0:
            return None
        row_idx = int(y // cell_h)
        col_idx = int(x // cell_w)
        if row_idx >= self._grid_size or col_idx >= self._grid_size:
            return None
        # Clicks in the gap between two tiles belong to neither
        if (y - row_idx * cell_h) >= tile_h or (x - col_idx * cell_w) >= tile_w:
            return None
        index = row_idx * self._grid_size + col_idx
        if index >= len(self._tile_paths):
            return None
        return index


    @staticmethod
    def _set_contrast_limits(layer):
        """Pin the montage to 0..1; _paste_tile() scaled every tilt to fit."""
        try:
            layer.contrast_limits_range = (0.0, 1.0)
            layer.contrast_limits = (0.0, 1.0)
        except Exception:
            layer.reset_contrast_limits()


    def load_batch(self, batch_num, progressive=False):
        """Show one batch of tilts as a single montage image + one points layer.

        The two layers are created on the first call and only get new data
        afterwards, so paging never adds or removes layers.

        progressive=True returns as soon as the (still empty) montage is on
        screen and lets _fill_pending() paste the tilts in as they decode. It
        is used for the very first batch, where waiting would delay the window.
        """
        startT = time.time()
        self.current_batch = batch_num
        
        # Get images for this batch
        start_idx = batch_num * self.batch_size
        end_idx = min(start_idx + self.batch_size, len(self.df))
        batch_df = self.df.iloc[start_idx:end_idx]
        batch_size = len(batch_df)
        
        # Calculate grid layout
        n_images = batch_size
        grid_size = max(1, int(np.ceil(np.sqrt(n_images))))
        
        # Decode + filter the whole batch in parallel (cached/prefetched
        # tilts are returned immediately)
        img_paths = list(batch_df['cryoBoostPNG'])
        labels = list(batch_df['cryoBoostDlLabel'])
        if progressive:
            # Do NOT block until all tilts of the batch are decoded. The loads
            # are already queued in the pool; the tiles are filled in by
            # _fill_pending() from the Qt event loop as they arrive, so the
            # window is usable immediately.
            self._submit_batch(img_paths)
            tile_shape = self._image_shape(img_paths[0]) if img_paths else (2, 2)
            _phase(f"tile shape {tile_shape[1]}x{tile_shape[0]}, "
                   f"filling {len(img_paths)} tilts in the background")
            images = [None] * len(img_paths)
        else:
            _phase(f"decoding {len(img_paths)} tilts ...")
            images = self._get_images(img_paths)
            tile_shape = images[0].shape if images else (2, 2)
            _phase(f"decoded {len(img_paths)} tilts in {time.time() - startT:.1f}s")

        # Lay the batch out as ONE montage array: tile i goes to row i//grid,
        # column i%grid of a grid_size x grid_size grid of cells.
        # spacing 0 = tiles touch, like napari's grid mode; set
        # CB_TILT_TILE_GAP to insert a black separator between the tiles.
        spacing = max(0, int(os.environ.get("CB_TILT_TILE_GAP", 0)))
        tile_h, tile_w = tile_shape
        cell_h, cell_w = tile_h + spacing, tile_w + spacing
        self._grid_size = grid_size
        self._tile_shape = (tile_h, tile_w)
        self._cell = (cell_h, cell_w)
        self._tile_paths = img_paths
        self._colors = ['green' if lab == "good" else 'red' for lab in labels]

        montage = np.zeros((grid_size * cell_h, grid_size * cell_w), dtype=np.float32)
        pending = []
        for i in range(batch_size):
            if images[i] is None:
                pending.append(i)  # pasted later by _fill_pending()
            else:
                self._paste_tile(montage, i, images[i])
        self._montage = montage

        # One label dot per tilt, near the top-left corner of its tile
        positions = np.array([[(i // grid_size) * cell_h + 30,
                               (i % grid_size) * cell_w + 30]
                              for i in range(batch_size)],
                             dtype=float).reshape(-1, 2)
        
        # Create the two layers once, afterwards only their data is swapped.
        # The repaint stays suppressed while both are updated.
        canvas = self._canvas_widget()
        if canvas is not None:
            canvas.setUpdatesEnabled(False)
        try:
            if self.montage_layer is None:
                self.montage_layer = self.viewer.add_image(
                    montage,
                    name='tilts',
                    colormap='gray',
                    blending='additive',
                    contrast_limits=(0.0, 1.0),
                )
                self.points_layer = self.viewer.add_points(
                    positions,
                    name='labels',
                    size=30,
                    face_color=list(self._colors) if self._colors else 'red',
                    border_color=list(self._colors) if self._colors else 'red',
                    symbol='disc',
                )
                _phase("created 2 layers (montage + labels)")
            else:
                self.montage_layer.data = montage
                self.points_layer.data = positions
                self._apply_colors()
            self._set_contrast_limits(self.montage_layer)
        finally:
            if canvas is not None:
                canvas.setUpdatesEnabled(True)
                canvas.update()
        
        # Reset view to show all images
        self.viewer.reset_view()
        
        # Fill the tilts that are still being decoded, from the event loop
        self._start_fill(batch_num, img_paths, pending)
        
        # Update button states
        self.prev_btn.setEnabled(batch_num > 0)
        self.next_btn.setEnabled(batch_num < self.total_batches - 1)
        # Update batch counter label
        self.batch_counter_label.setText(f"Showing batch {batch_num + 1} of {self.total_batches}")  
        self.prob_counter()
        
        # Warm the cache for the next/previous batch in the background so that
        # paging feels instant
        self._prefetch(batch_num + 1)
        self._prefetch(batch_num - 1)
        
        _phase(f"loaded batch {batch_num + 1} of {self.total_batches} in "
               f"{time.time() - startT:.2f}s")


    def next_batch(self):
        if self.current_batch < self.total_batches - 1:
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
        # The batch is a single montage layer, so the clicked tilt follows from
        # the position in the grid instead of from a per-tilt layer
        tile = self._tile_index_from_world(float(coordinates[0]), float(coordinates[1]))
        if tile is None:
            return

        img_name = self._tile_paths[tile]
        # Find corresponding index in DataFrame
        index = self.df[self.df['cryoBoostPNG'] == img_name].index[0]
        
        # Toggle the label
        invLabel = 'bad' if self.df.loc[index, 'cryoBoostDlLabel'] == 'good' else 'good'
        self.df.loc[index, 'cryoBoostDlLabel'] = invLabel
        print(f"\nUpdated label for {img_name} to {invLabel}", flush=True)
        self.update_log_display()
        # Update point color
        self._colors[tile] = 'green' if invLabel == 'good' else 'red'
        self._apply_colors()
            

    def on_right_click(self, layer, event):
        # Get the clicked coordinates in world space
        coordinates = event.position
        tile = self._tile_index_from_world(float(coordinates[0]), float(coordinates[1]))
        if tile is None:
            return

        img_name = self._tile_paths[tile]
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
    _ensure_qt()
    app = QApplication.instance() 
    app.lastWindowClosed.connect(viewer.on_close) 
    _phase("entering napari event loop")
    napari.run()

if __name__ == '__main__':
    filterTiltsInterActive()
