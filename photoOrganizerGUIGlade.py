# coding: latin-1

'''
Created on Mar 01, 2013

@author: hifly

'''

import os
import math
import urllib2
import logging.config
import twitterUtil
import photoOrganizerStorage
import photoOrganizerUtil
import photoEffects
import StringIO
import Image
import imghdr
import threading
from transparentWindow import TransparentWindow
from editWindow import EditWindow
from entryCompletion import EntryCompletion
from loadingWindow import LoadingWindow
from cairo import ImageSurface 
from gi.repository import Gtk,GdkPixbuf,Gdk,GObject,GLib
from photoOrganizerStorage import PhotoOrganizerPref
from photoOrganizerUtil import AlbumCollection
from photoOrganizerUtil import Album
from photoOrganizerUtil import PhotoFile
from photoOrganizerUtil import PeopleTag

#logging conf
logging.config.fileConfig('config/logging.conf')
logger = logging.getLogger('photoOrganizer')

#Initializing the gtk's thread engine
GObject.threads_init()

#const
GLADE_CONF = "glade/photoOrganizerGui.glade"

#global vars
global totalPhotoDictionary 
totalPhotoDictionary = {}
global imageMap
imageMap = {}

#context menu not designed in GLADE
UI_INFO = """
<ui>
  <popup name='PopupMenu'>
    <menu action="Effects">
        <menuitem action='EditGreyScale' />
        <menuitem action='EditSepia' />
        <menuitem action='EditSolarize' />
        <menuitem action='EditEqualize' />
        <menuitem action='EditDarkViolet' />
        <menuitem action='EditLightGreen' />
        <menuitem action='EditWhite' />
        <menuitem action='EditGreen' /> 
    </menu>  
    <menu action="Edit">
        <menuitem action='EditRotateLeft' />
        <menuitem action='EditRotateRight' />
        <menuitem action='EditMirror' />
        <menuitem action='EditFlip' />
        <menuitem action='EditCrop' />
        <menuitem action='EditResize' />
    </menu>
    <menu action="Transform">
        <menuitem action='EditSharpness' />
        <menuitem action='EditDeform' />
    </menu>
    <menu action="Stylish">
        <menuitem action='EditBordered' />
        <menuitem action='EditUnbordered' />
        <menuitem action='EditPolaroid' />
        <menuitem action='EditFrame' />
        <menuitem action='EditWatermark' />
    </menu>
    <menu action="Filter">
        <menuitem action='EditBlur' />
        <menuitem action='EditGaussian' /> 
        <menuitem action='EditContour' />
        <menuitem action='EditEdge' />
        <menuitem action='EditEmboss' />
        <menuitem action='EditSmooth' />
        <menuitem action='EditSharpen' />
    </menu>
    <menu action="Color">
        <menuitem action='EditColor' />
        <menuitem action='EditColorize' /> 
        <menuitem action='EditPosterize' />
        <menuitem action='EditContrast' />
        <menuitem action='EditAutocontrast' />
    </menu>
    <menu action="Light">
        <menuitem action='EditInvert' />
        <menuitem action='EditBrigthness' />
        <menuitem action='EditLight' /> 
    </menu>
    <menu action="Other">
        <menuitem action='EditOriginalSize' />
        <menuitem action='EditHistogram' /> 
        <menuitem action='EditTagPeople' />
        <menuitem action='EditGrab' /> 
        <menuitem action='EditWebcam' /> 
        <menuitem action='EditSave' />
    </menu>
   </popup>
</ui>
"""

class UpdateAlbum(threading.Thread):
    def __init__(self,album,treestore,statusBar,context):
        #ref to album
        self.album = album
        #ref to path to scan
        self.path = album.title
        #ref to tree element
        self.treestore = treestore
        #ref to status bar
        self.statusBar = statusBar
        self.context = context
        threading.Thread.__init__(self)
    
    
    def update_tree_store(self,store,pathToSearch):
        rootiter = store.get_iter_first()
        self.update_rows(store, rootiter,pathToSearch)

    def update_rows(self,store, treeiter,pathToSearch):
        while treeiter != None:
            if pathToSearch in str(store[treeiter][:]):
                self.treestore.remove(treeiter)
            if store.iter_has_child(treeiter):
                childiter = store.iter_children(treeiter)
                self.update_rows(store, childiter,pathToSearch)
            treeiter = store.iter_next(treeiter)
            
    def run(self):
        for (path, dirs,files) in os.walk(self.path):
            for file in files:
                key = totalPhotoDictionary.get(self.path+"/"+file, None )
                if key is None:
                    #img is not in a previous scanning
                    if imghdr.what(self.path+"/"+file)!=None:
                        rowIndex = 0
                        for row in self.treestore:
                            iterPath = Gtk.TreePath(rowIndex)
                            treeiter = self.treestore.get_iter(iterPath)
                            treeiterChild = self.treestore.iter_children(treeiter)
                            while treeiterChild is not None:
                                treeiter2Child = self.treestore.iter_children(treeiterChild)
                                while treeiter2Child is not None:
                                    treeiter2ChildValue = self.treestore[treeiter2Child][:]
                                    if self.path in treeiter2ChildValue:
                                        self.treestore.append(treeiter2Child,['%s' %self.path+"/"+file])
                                        self.statusBar.push(self.context,"added:"+self.path+"/"+file)
                                        while Gtk.events_pending():
                                            Gtk.main_iteration_do(False)
                                        photoFile = photoOrganizerUtil.get_exif_data(self.path+"/"+file)
                                        if photoFile==None:
                                            photoFile = PhotoFile()  
                                        photoFile.dirName = path
                                        photoFile.fileName = file
                                        photoFile.shortName = photoFile.fileName
                                        #add to original album
                                        self.album.pics.append(photoFile)
                                        #add to dic
                                        totalPhotoDictionary[self.path+"/"+file] = photoFile
                                        #update imageMap
                                        subImageMap = {}
                                        subImageMap[photoFile.fileName] = photoFile
                                        imageMap[self.path].update(subImageMap)
                                    treeiter2Child = self.treestore.iter_next(treeiter2Child)
                                    
                                treeiterChild = self.treestore.iter_next(treeiterChild)
                            rowIndex+=1
        
        listIndex = 0
        
        #scan album to check if there are pics removed
        for photo in self.album.pics:
            isFile = os.path.exists(photo.dirName+"/"+photo.fileName)
            if isFile==False:
                #del from dic
                key = totalPhotoDictionary.get(self.path+"/"+photo.fileName, None )
                if key is not None:
                    del totalPhotoDictionary[self.path+"/"+photo.fileName]
                #del from album pics
                self.album.pics.pop(listIndex)
                #update imageMap
                subImageMap = imageMap[self.path]
                del subImageMap[photo.fileName]
                #delete from treeview
                self.update_tree_store(self.treestore,self.path+"/"+photo.fileName)
        
                self.statusBar.push(self.context,"removed:"+self.path+"/"+photo.fileName)
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
            listIndex+=1
               

class PhotoOrganizerGUI(Gtk.Window):
    
    def __init__(self):
        #references
        self.imagePathOpened = None
        self.thubnailPanel = {}
        self.twitterCurrentQuery = None
        self.currenWinImage = None
        self.entry_folder_text = None
        self.hiddenFolders = None
        self.peopleTag = None
        self.mainEditMenuOpened = False
        self.mainOtherMenuOpened = False
        self.mainEffectsMenuOpened = False
        self.mainTransformMenuOpened = False
        self.mainStylishMenuOpened = False
        self.mainFilterMenuOpened = False
        self.mainColorMenuOpened = False
        self.mainLightMenuOpened = False

        #build GUI from glade
        self.builder = Gtk.Builder()
        self.builder.add_from_file(GLADE_CONF)
        handlers = {
                    "on_PhotoOrganizer_delete_event": self.on_PhotoOrganizer_delete_event,
                    "on_PhotoOrganizer_search_event": self.on_PhotoOrganizer_search_event,
                    "on_PhotoOrganizer_twitter_search_event": self.on_PhotoOrganizer_twitter_search_event,
                    "on_PhotoOrganizer_autocontrast_clicked": self.on_PhotoOrganizer_autocontrast_clicked,
                    "on_PhotoOrganizer_invert_clicked": self.on_PhotoOrganizer_invert_clicked,
                    "on_PhotoOrganizer_posterize_clicked": self.on_PhotoOrganizer_posterize_clicked,
                    "on_PhotoOrganizer_blur_clicked":self.on_PhotoOrganizer_blur_clicked,
                    "on_PhotoOrganizer_contour_clicked":self.on_PhotoOrganizer_contour_clicked,
                    "on_PhotoOrganizer_edge_clicked": self.on_PhotoOrganizer_edge_clicked,
                    "on_PhotoOrganizer_emboss_clicked": self.on_PhotoOrganizer_emboss_clicked,
                    "on_PhotoOrganizer_smooth_clicked": self.on_PhotoOrganizer_smooth_clicked,
                    "on_PhotoOrganizer_brightness_clicked": self.on_PhotoOrganizer_brightness_clicked,
                    "on_PhotoOrganizer_contrast_clicked": self.on_PhotoOrganizer_contrast_clicked,
                    "on_PhotoOrganizer_sharpness_clicked": self.on_PhotoOrganizer_sharpness_clicked,
                    "on_PhotoOrganizer_sharpen_clicked": self.on_PhotoOrganizer_sharpen_clicked,
                    "on_PhotoOrganizer_color_clicked":self.on_PhotoOrganizer_color_clicked,
                    "on_PhotoOrganizer_light_clicked":self.on_PhotoOrganizer_light_clicked,
                    "on_PhotoOrganizer_gaussian_clicked":self.on_PhotoOrganizer_gaussian_clicked,
                    "on_PhotoOrganizer_colorize_clicked":self.on_PhotoOrganizer_colorize_clicked,       
                    "on_PhotoOrganizer_mainEdit_clicked":self.on_PhotoOrganizer_mainEdit_clicked,
                    "on_PhotoOrganizer_mainOther_clicked":self.on_PhotoOrganizer_mainOther_clicked,
                    "on_PhotoOrganizer_mainEffects_clicked":self.on_PhotoOrganizer_mainEffects_clicked,
                    "on_PhotoOrganizer_mainTransform_clicked":self.on_PhotoOrganizer_mainTransform_clicked,
                    "on_PhotoOrganizer_mainStylish_clicked":self.on_PhotoOrganizer_mainStylish_clicked,
        }
        #handler of GUI signals
        self.builder.connect_signals(handlers)
        
        #change textview color
        parse, color = Gdk.Color.parse('#F0F0F0')
        self.builder.get_object("detailsEntry").modify_bg(Gtk.StateType.NORMAL, color) 
            
        #show main window
        self.window = self.builder.get_object("PhotoOrganizer")
        self.window.connect("key_press_event",self.on_PhotoOrganizer_image_keypress_event)   
        #center the window
        self.window.set_position(Gtk.WindowPosition.CENTER)       
        #maximize the window 
        self.window.maximize()
        self.window.show_all()
        
        #load pref at startup, including albums saved
        self.loadPreferences()

        #main gtk
        Gtk.main()
    
    def create_image_context_menu(self):
        action_group = Gtk.ActionGroup("my_actions")
        action_group.add_actions([     
            ("Effects", Gtk.STOCK_ZOOM_FIT, "Effects", "<control><alt>O", None,None), 
            ("Edit", Gtk.STOCK_ZOOM_FIT, "Edit", "<control><alt>O", None,None),      
            ("Transform", Gtk.STOCK_ZOOM_FIT, "Transform", "<control><alt>O", None,None), 
            ("Stylish", Gtk.STOCK_ZOOM_FIT, "Stylish", "<control><alt>O", None,None), 
            ("Filter", Gtk.STOCK_ZOOM_FIT, "Filter", "<control><alt>O", None,None),  
            ("Color", Gtk.STOCK_ZOOM_FIT, "Color", "<control><alt>O", None,None), 
            ("Light", Gtk.STOCK_ZOOM_FIT, "Light", "<control><alt>O", None,None), 
            ("Other", Gtk.STOCK_ZOOM_FIT, "Other", "<control><alt>O", None,None),        
            ("EditOriginalSize", Gtk.STOCK_ZOOM_FIT, "Original size", "<control><alt>O", None,
             self.on_PhotoOrganizer_original_size_clicked),
            ("EditMirror", Gtk.STOCK_OK, "Mirror", "<control><alt>M", None,
             self.on_PhotoOrganizer_mirror_clicked),
            ("EditFlip", Gtk.STOCK_OK, "Flip", "<control><alt>M", None,
             self.on_PhotoOrganizer_flip_clicked),
            ("EditRotateLeft", Gtk.STOCK_REFRESH, "Rotate left", "<control><alt>R", None,
             self.on_PhotoOrganizer_rotate_clicked),
            ("EditRotateRight", Gtk.STOCK_REFRESH, "Rotate right", "<control><alt>Q", None,
             self.on_PhotoOrganizer_rotate_right_clicked),
            ("EditBordered", Gtk.STOCK_REFRESH, "Border", "<control><alt>B", None,
             self.on_PhotoOrganizer_border_clicked),
            ("EditUnbordered", Gtk.STOCK_REFRESH, "Unborder", "<control><alt>U", None,
             self.on_PhotoOrganizer_unborder_clicked),                      
            ("EditAutocontrast", Gtk.STOCK_REFRESH, "Autocontrast", "<control><alt>A", None,
             self.on_PhotoOrganizer_autocontrast_clicked),        
            ("EditDeform", Gtk.STOCK_REFRESH, "Deform", "<control><alt>D", None,
             self.on_PhotoOrganizer_deform_clicked),    
            ("EditEqualize", Gtk.STOCK_REFRESH, "Equalize", "<control><alt>E", None,
             self.on_PhotoOrganizer_equalize_clicked),      
            ("EditGreyScale", Gtk.STOCK_REFRESH, "GreyScale", "<control><alt>G", None,
             self.on_PhotoOrganizer_greyscale_clicked), 
            ("EditInvert", Gtk.STOCK_OK, "Invert", "<control><alt>I", None,
             self.on_PhotoOrganizer_invert_clicked), 
            ("EditPosterize", Gtk.STOCK_OK, "Posterize", "<control><alt>P", None,
             self.on_PhotoOrganizer_posterize_clicked),  
            ("EditSolarize", Gtk.STOCK_OK, "Solarize", "<control><alt>Z", None,
             self.on_PhotoOrganizer_solarize_clicked),         
            ("EditBlur", Gtk.STOCK_OK, "Blur", "<control><alt>K", None,
             self.on_PhotoOrganizer_blur_clicked),
            ("EditContour", Gtk.STOCK_OK, "Contour", "<control><alt>W", None,
             self.on_PhotoOrganizer_contour_clicked),   
            ("EditEdge", Gtk.STOCK_OK, "Edge", "<control><alt>E", None,
             self.on_PhotoOrganizer_edge_clicked),
            ("EditEmboss", Gtk.STOCK_OK, "Emboss", "<control><alt>B", None,
             self.on_PhotoOrganizer_emboss_clicked),     
            ("EditSmooth", Gtk.STOCK_OK, "Smooth", "<control><alt>T", None,
             self.on_PhotoOrganizer_smooth_clicked), 
            ("EditSharpen", Gtk.STOCK_OK, "Sharpen", "<control><alt>H", None,
             self.on_PhotoOrganizer_sharpen_clicked), 
            ("EditColor", Gtk.STOCK_OK, "Color", "<control><alt>Y", None,
             self.on_PhotoOrganizer_color_clicked), 
            ("EditBrigthness", Gtk.STOCK_OK, "Brigthness", "<control><alt>B", None,
             self.on_PhotoOrganizer_brightness_clicked),
            ("EditContrast", Gtk.STOCK_OK, "Contrast", "<control><alt>L", None,
             self.on_PhotoOrganizer_contrast_clicked),  
            ("EditSharpness", Gtk.STOCK_OK, "Sharpness", "<control><alt>G", None,
             self.on_PhotoOrganizer_sharpness_clicked), 
            ("EditPolaroid", Gtk.STOCK_OK, "Polaroid", "<control><alt>P", None,
             self.on_PhotoOrganizer_polaroid_clicked),  
            ("EditSepia", Gtk.STOCK_OK, "Sepia", "<control><alt>J", None,
             self.on_PhotoOrganizer_sepia_clicked),  
            ("EditDarkViolet", Gtk.STOCK_OK, "Dark Violet", "<control><alt>V", None,
             self.on_PhotoOrganizer_darkViolet_clicked), 
            ("EditLightGreen", Gtk.STOCK_OK, "Light Green", "<control><alt>X", None,
             self.on_PhotoOrganizer_lightGreen_clicked), 
            ("EditWhite", Gtk.STOCK_OK, "White", "<control><alt>E", None,
             self.on_PhotoOrganizer_white_clicked), 
            ("EditGreen", Gtk.STOCK_OK, "Green", "<control><alt>J", None,
             self.on_PhotoOrganizer_green_clicked), 
            ("EditWatermark", Gtk.STOCK_OK, "Watermark", "<control><alt>Z", None,
             self.on_PhotoOrganizer_watermark_clicked),  
            ("EditHistogram", Gtk.STOCK_OK, "Histogram", "<control><alt>Z", None,
             self.on_PhotoOrganizer_histogram_clicked),          
            ("EditCrop", Gtk.STOCK_OK, "Crop", "<control><alt>Z", None,
             self.on_PhotoOrganizer_crop_clicked),  
            ("EditLight", Gtk.STOCK_OK, "Light", "<control><alt>Z", None,
             self.on_PhotoOrganizer_light_clicked),         
            ("EditGaussian", Gtk.STOCK_OK, "Gaussian", "<control><alt>G", None,
             self.on_PhotoOrganizer_gaussian_clicked),   
            ("EditColorize", Gtk.STOCK_OK, "Colorize", "<control><alt>U", None,
             self.on_PhotoOrganizer_colorize_clicked),                                                                                                                                  
            ("EditSave", Gtk.STOCK_SAVE, "Save", "<control><alt>S", None,
             self.on_PhotoOrganizer_save_clicked),
            ("EditTagPeople", Gtk.STOCK_SAVE, "TagPeople", "<control><alt>S", None,
             self.on_PhotoOrganizer_tagPeople_clicked),    
            ("EditWebcam", Gtk.STOCK_SAVE, "Webcam", "<control><alt>S", None,
             self.on_PhotoOrganizer_webcam_clicked),          
            ("EditFrame", Gtk.STOCK_SAVE, "Frame", "<control><alt>S", None,
             self.on_PhotoOrganizer_frame_clicked),                                            
        ])
        uimanager = Gtk.UIManager()
        # Throws exception if something went wrong
        uimanager.add_ui_from_string(UI_INFO)
        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)
        uimanager.insert_action_group(action_group)
        return uimanager
    
    
    '''
        SECTION FOR EVENTS
    '''
    
    #event on quit app
    def on_PhotoOrganizer_delete_event  (self, *args):
        if(self.lastAlbumCollectionScanned is not None):
            #save the preferences
            photoFile = PhotoOrganizerPref(self.hiddenFolders,self.entry_folder_text,self.lastAlbumCollectionScanned,self.peopleTag)
            photoOrganizerStorage.savePref(photoFile)
        Gtk.main_quit()
    
    #event on filesystem search
    def on_PhotoOrganizer_search_event  (self, *args):
        #set no twitter search
        self.twitterSearch = False
        dialog = Gtk.FileChooserDialog("Please choose a folder", self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             "Select", Gtk.ResponseType.OK))
        dialog.set_default_size(800, 400)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            #get directory selected
            self.searchEntry = dialog.get_filename()
            self.removeSearchResult(self.builder.get_object("treeviewAlbum"));
            
            # You'll need to import gobject
            GObject.timeout_add(100, self.callScanPhoto)
            dialog.destroy()
        else:
            dialog.destroy()

    def on_PhotoOrganizer_twitter_search_event(self,widget,event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Return":
            self.twitterSearch = True
            self.removeSearchResult(self.builder.get_object("treeviewTwitter"));    
            queryToSend = self.builder.get_object("twitterSearchField").get_text()
            numberOfTweets = self.builder.get_object("twitterSpin").get_value_as_int()
            try:
                self.twitterSearchResult = twitterUtil.searchMediaTweets(queryToSend,numberOfTweets) 
                if(self.twitterSearchResult is not None and len(self.twitterSearchResult.entries)>0):
                    #create album collection
                    albumCollection = AlbumCollection()
                    album = Album()
                    album.title = queryToSend
                    for entry in self.twitterSearchResult.entries:
                        photoFile = PhotoFile() 
                        photoFile.mediaUrl = entry.url;
                        photoFile.dirName = entry.url
                        photoFile.fileName = entry.url
                        photoFile.shortName = entry.url
                        photoFile.author = entry.author
                        album.pics.append(photoFile)
                    albumCollection.albums.append(album) 
                    album.totalPics = len(album.pics)
                    albumCollection.totalPics = len(album.pics)
            
                    self.twitterCurrentQuery = queryToSend
                    treeview = self.builder.get_object("treeviewTwitter")
                    self.createFixedPhotoTree(albumCollection,None,treeview)
                    #set current tab
                    self.builder.get_object("notebook1").set_current_page(1)
                    leftPanel = self.builder.get_object("leftPanel1")
                    leftPanel.add(treeview)
                    leftPanel.show_all()
                else:
                    self.on_PhotoOrganizer_search_error_event()    
            except Exception as e:
                self.on_PhotoOrganizer_generic_error_event(e)
    
    def on_PhotoOrganizer_generic_error_event  (self,e):
        dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,Gtk.ButtonsType.CANCEL,e)
        dialog.run()
        dialog.destroy()
        
    def on_PhotoOrganizer_search_error_event  (self, *args):
        extraTextDialog = None
        dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CANCEL, "No pics founded")
        if(self.twitterSearch):
            extraTextDialog = "Specify another twitter search!"
        else:
            extraTextDialog = "Specify another folder!"    
        dialog.format_secondary_text(extraTextDialog)
        dialog.run()
        dialog.destroy()
    
    def on_PhotoOrganizer_image_contextmenu_event(self, widget, event) :
        uimanager = self.create_image_context_menu()
        self.popup = uimanager.get_widget("/PopupMenu")
        #check if right mouse button was preseed
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self.popup.popup(None, None, None, None, event.button, event.time)
            return True  
        
    #event selection of a tree entry    
    def on_PhotoOrganizer_tree_entry_selected(self, widget, data = None):
        #take the treeview linked to specific tab
        currentPage = self.builder.get_object("notebook1").get_current_page()
        if currentPage == 0:
            self.currentTreeview = self.builder.get_object("treeviewAlbum")
            self.twitterSearch = False
        else:
           self.currentTreeview = self.builder.get_object("treeviewTwitter") 
           self.twitterSearch = True
        
        selection = self.currentTreeview.get_selection()
        if selection is not None:
            tree_model, tree_iter = selection.get_selected()
            if (tree_model is not None):
                imagePath = tree_model.get_value(tree_iter, 0)
                if(self.twitterSearch):
                    if(imagePath == self.twitterCurrentQuery):
                        self.createThubnailPanel(imagePath)
                    else:
                        self.createScaledImage(imagePath)
                else:
                    if os.path.isfile(imagePath):
                        self.createScaledImage(imagePath)
                    else:
                        self.createThubnailPanel(imagePath) 
    
    def on_PhotoOrganizer_thub_clicked(self, widget,event,imagePath):
        self.createScaledImage(imagePath)
    
    def on_PhotoOrganizer_mainEdit_clicked(self,widget):
        if(self.mainEditMenuOpened ==False):
            self.mainEditMenuOpened = True
            self.mainOtherMenuOpened = False
            self.mainEffectsMenuOpened = False
            self.mainTransformMenuOpened = False
            self.mainStylishMenuOpened = False
            boxBottom = self.builder.get_object("submainFunctionalitiesMenu")
            boxChildren = boxBottom.get_children()
            if len(boxChildren) >0:
                for childEl in boxChildren:
                    boxBottom.remove(childEl)
            buttonRotateLeft = Gtk.Button("Rotate Left")
            buttonRotateLeft.set_size_request(50,20)
            buttonRotateLeft.connect("clicked", self.on_PhotoOrganizer_rotate_clicked)
            buttonRotateRight = Gtk.Button("Rotate Right")
            buttonRotateRight.set_size_request(50,20)
            buttonRotateRight.connect("clicked", self.on_PhotoOrganizer_rotate_right_clicked)
            buttonMirror = Gtk.Button("Mirror")
            buttonMirror.set_size_request(50,20)
            buttonMirror.connect("clicked", self.on_PhotoOrganizer_mirror_clicked)
            buttonFlip = Gtk.Button("Flip")
            buttonFlip.set_size_request(50,20)
            buttonFlip.connect("clicked", self.on_PhotoOrganizer_flip_clicked)
            buttonCrop = Gtk.Button("Crop")
            buttonCrop.set_size_request(50,20)
            buttonCrop.connect("clicked", self.on_PhotoOrganizer_crop_clicked)
            buttonResize = Gtk.Button("Resize")
            buttonResize.set_size_request(50,20)
            boxBottom.pack_start(buttonRotateLeft, False, False, 0)
            boxBottom.pack_start(buttonRotateRight, False, False, 0)
            boxBottom.pack_start(buttonMirror, False, False, 0)
            boxBottom.pack_start(buttonFlip, False, False, 0)
            boxBottom.pack_start(buttonCrop, False, False, 0)
            boxBottom.pack_start(buttonResize, False, False, 0)
            buttonRotateLeft.show()
            buttonRotateRight.show()
            buttonMirror.show()
            buttonFlip.show()
            buttonCrop.show()
            buttonResize.show()
    
    def on_PhotoOrganizer_mainTransform_clicked(self,widget):
        if(self.mainTransformMenuOpened ==False):
            self.mainTransformMenuOpened = True
            self.mainEffectsMenuOpened = False
            self.mainOtherMenuOpened = False
            self.mainEditMenuOpened = False
            self.mainStylishMenuOpened = False
            boxBottom = self.builder.get_object("submainFunctionalitiesMenu")
            boxChildren = boxBottom.get_children()
            if len(boxChildren) >0:
                for childEl in boxChildren:
                    boxBottom.remove(childEl)
            buttonSharpness = Gtk.Button("Sharpness")
            buttonSharpness.set_size_request(50,20)
            buttonSharpness.connect("clicked", self.on_PhotoOrganizer_sharpness_clicked)
            buttonDeform = Gtk.Button("Deform")
            buttonDeform.set_size_request(50,20)
            buttonDeform.connect("clicked", self.on_PhotoOrganizer_deform_clicked)
            boxBottom.pack_start(buttonSharpness, False, False, 0)
            boxBottom.pack_start(buttonDeform, False, False, 0)
            buttonSharpness.show()
            buttonDeform.show()
      
    def on_PhotoOrganizer_mainStylish_clicked(self,widget):
        if(self.mainStylishMenuOpened ==False):
            self.mainStylishMenuOpened = True
            self.mainEffectsMenuOpened = False
            self.mainOtherMenuOpened = False
            self.mainEditMenuOpened = False
            self.mainTransformMenuOpened = False
            boxBottom = self.builder.get_object("submainFunctionalitiesMenu")
            boxChildren = boxBottom.get_children()
            if len(boxChildren) >0:
                for childEl in boxChildren:
                    boxBottom.remove(childEl)
            buttonBordered = Gtk.Button("Border")
            buttonBordered.set_size_request(50,20)
            buttonBordered.connect("clicked",self.on_PhotoOrganizer_border_clicked)
            buttonUnbordered = Gtk.Button("Unborder")
            buttonUnbordered.set_size_request(50,20)
            buttonUnbordered.connect("clicked", self.on_PhotoOrganizer_unborder_clicked)
            buttonPolaroid = Gtk.Button("Polaroid")
            buttonPolaroid.set_size_request(50,20)
            buttonPolaroid.connect("clicked", self.on_PhotoOrganizer_polaroid_clicked)
            buttonFrame = Gtk.Button("Frame")
            buttonFrame.set_size_request(50,20)
            buttonFrame.connect("clicked", self.on_PhotoOrganizer_frame_clicked)
            buttonWatermark = Gtk.Button("Watermark")
            buttonWatermark.set_size_request(50,20)
            buttonWatermark.connect("clicked", self.on_PhotoOrganizer_watermark_clicked)
            boxBottom.pack_start(buttonBordered, False, False, 0)
            boxBottom.pack_start(buttonUnbordered, False, False, 0)
            boxBottom.pack_start(buttonPolaroid, False, False, 0)
            boxBottom.pack_start(buttonFrame, False, False, 0)
            boxBottom.pack_start(buttonWatermark, False, False, 0)
            buttonBordered.show()
            buttonUnbordered.show() 
            buttonPolaroid.show()    
            buttonFrame.show() 
            buttonWatermark.show()
    
    def on_PhotoOrganizer_mainOther_clicked(self,widget):
        if(self.mainOtherMenuOpened ==False):
            self.mainOtherMenuOpened = True
            self.mainEditMenuOpened = False
            self.mainEffectsMenuOpened = False
            self.mainTransformMenuOpened = False
            self.mainStylishMenuOpened = False
            boxBottom = self.builder.get_object("submainFunctionalitiesMenu")
            boxChildren = boxBottom.get_children()
            if len(boxChildren) >0:
                for childEl in boxChildren:
                    boxBottom.remove(childEl)
            buttonHistogram = Gtk.Button("Histogram")
            buttonHistogram.set_size_request(50,20)
            buttonHistogram.connect("clicked", self.on_PhotoOrganizer_histogram_clicked)
            buttonTagpeople = Gtk.Button("Tag People")
            buttonTagpeople.set_size_request(50,20)
            buttonTagpeople.connect("clicked", self.on_PhotoOrganizer_tagPeople_clicked)
            buttonWebcam = Gtk.Button("Webcam")
            buttonWebcam.set_size_request(50,20)
            buttonWebcam.connect("clicked", self.on_PhotoOrganizer_webcam_clicked)
            buttonGrab = Gtk.Button("Grab")
            buttonGrab.set_size_request(50,20)
            buttonOriginalsize = Gtk.Button("Original Size")
            buttonOriginalsize.set_size_request(50,20)
            buttonOriginalsize.connect("clicked", self.on_PhotoOrganizer_original_size_clicked)
            buttonSave = Gtk.Button("Save")
            buttonSave.set_size_request(50,20)
            buttonSave.connect("clicked", self.on_PhotoOrganizer_save_clicked)
            boxBottom.pack_start(buttonHistogram, False, False, 0)
            boxBottom.pack_start(buttonTagpeople, False, False, 0)
            boxBottom.pack_start(buttonWebcam, False, False, 0)
            boxBottom.pack_start(buttonGrab, False, False, 0)
            boxBottom.pack_start(buttonOriginalsize, False, False, 0)
            boxBottom.pack_start(buttonSave, False, False, 0)
            buttonHistogram.show()
            buttonTagpeople.show()
            buttonWebcam.show()
            buttonGrab.show()
            buttonOriginalsize.show()
            buttonSave.show()
    
    def on_PhotoOrganizer_mainEffects_clicked(self,widget):
        if(self.mainEffectsMenuOpened ==False):
            self.mainEffectsMenuOpened = True
            self.mainOtherMenuOpened = False
            self.mainEditMenuOpened = False
            self.mainTransformMenuOpened = False
            self.mainStylishMenuOpened = False
            boxBottom = self.builder.get_object("submainFunctionalitiesMenu")
            boxChildren = boxBottom.get_children()
            if len(boxChildren) >0:
                for childEl in boxChildren:
                    boxBottom.remove(childEl)
            buttonGrey = Gtk.Button("Grey")
            buttonGrey.set_size_request(50,20)
            buttonGrey.connect("clicked", self.on_PhotoOrganizer_greyscale_clicked)
            buttonSepia = Gtk.Button("Sepia")
            buttonSepia.set_size_request(50,20)
            buttonSepia.connect("clicked", self.on_PhotoOrganizer_sepia_clicked)
            buttonSolarize = Gtk.Button("Solarize")
            buttonSolarize.set_size_request(50,20)
            buttonSolarize.connect("clicked", self.on_PhotoOrganizer_solarize_clicked)
            buttonEqualize = Gtk.Button("Equalize")
            buttonEqualize.set_size_request(50,20)
            buttonEqualize.connect("clicked", self.on_PhotoOrganizer_equalize_clicked)
            buttonDarkviolet = Gtk.Button("Dark Violet")
            buttonDarkviolet.set_size_request(50,20)
            buttonDarkviolet.connect("clicked", self.on_PhotoOrganizer_darkViolet_clicked)
            buttonLightgreen = Gtk.Button("Light Green")
            buttonLightgreen.set_size_request(50,20)
            buttonLightgreen.connect("clicked", self.on_PhotoOrganizer_lightGreen_clicked)
            buttonWhite = Gtk.Button("White")
            buttonWhite.set_size_request(50,20)
            buttonWhite.connect("clicked", self.on_PhotoOrganizer_white_clicked)
            buttonGreen = Gtk.Button("Green")
            buttonGreen.set_size_request(50,20)
            buttonGreen.connect("clicked", self.on_PhotoOrganizer_green_clicked)
            boxBottom.pack_start(buttonGrey, False, False, 0)
            boxBottom.pack_start(buttonSepia, False, False, 0)
            boxBottom.pack_start(buttonSolarize, False, False, 0)
            boxBottom.pack_start(buttonEqualize, False, False, 0)
            boxBottom.pack_start(buttonDarkviolet, False, False, 0)
            boxBottom.pack_start(buttonLightgreen, False, False, 0)
            boxBottom.pack_start(buttonWhite, False, False, 0)
            boxBottom.pack_start(buttonGreen, False, False, 0)
            buttonGrey.show()
            buttonSepia.show()
            buttonSolarize.show()
            buttonEqualize.show()
            buttonDarkviolet.show()
            buttonLightgreen.show()
            buttonWhite.show()
            buttonGreen.show()
    
    def on_PhotoOrganizer_original_size_clicked(self, widget):
        if os.path.isfile(self.imagePathOpened):
            pimage = Gtk.Image()
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.imagePathOpened)
            pimage.set_from_pixbuf(pixbuf)
            self.on_PhotoOrganizer_full_image_clicked(pimage,self.imagePathOpened)  
                    
    def on_PhotoOrganizer_rotate_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        scaled_buf = pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.COUNTERCLOCKWISE)
        self.imageOpened.set_from_pixbuf(scaled_buf)
    
    def on_PhotoOrganizer_rotate_right_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        scaled_buf = pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.CLOCKWISE)
        self.imageOpened.set_from_pixbuf(scaled_buf)
        
    def on_PhotoOrganizer_border_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_border(pixbuf,5,'red')) 
    
    def on_PhotoOrganizer_unborder_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_unborder(pixbuf)) 
    
    def on_PhotoOrganizer_autocontrast_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()   
        self.imageOpened.set_from_pixbuf(photoEffects.apply_autocontrast(pixbuf,0)) 
        
    def on_PhotoOrganizer_deform_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_deformer(pixbuf))    
    
    def on_PhotoOrganizer_equalize_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_equalizer(pixbuf))
    
    def on_PhotoOrganizer_greyscale_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_greyscale(pixbuf))
    
    def on_PhotoOrganizer_invert_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_invert(pixbuf))
    
    def on_PhotoOrganizer_mirror_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_mirror(pixbuf))
    
    def on_PhotoOrganizer_flip_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_flip(pixbuf))
              
    def on_PhotoOrganizer_darkViolet_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_darkViolet(pixbuf))  
        
    def on_PhotoOrganizer_lightGreen_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_lightGreen(pixbuf)) 
        
    def on_PhotoOrganizer_green_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_green(pixbuf)) 
        
    def on_PhotoOrganizer_white_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_white(pixbuf)) 
            
    def on_PhotoOrganizer_posterize_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_posterize(pixbuf,4))
    
    def on_PhotoOrganizer_solarize_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_solarize(pixbuf,128))
    
    def on_PhotoOrganizer_blur_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_blur(pixbuf))
    
    def on_PhotoOrganizer_contour_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_contour(pixbuf))
    
    def on_PhotoOrganizer_edge_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_edge(pixbuf))
    
    def on_PhotoOrganizer_emboss_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_emboss(pixbuf))
    
    def on_PhotoOrganizer_smooth_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_smooth(pixbuf))
    
    def on_PhotoOrganizer_sharpen_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_sharpen(pixbuf))
        
    def on_PhotoOrganizer_brightness_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_brightness(pixbuf)) 
    
    def on_PhotoOrganizer_contrast_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_contrast(pixbuf)) 
    
    def on_PhotoOrganizer_sharpness_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_sharpness(pixbuf))   
    
    def on_PhotoOrganizer_color_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_color(pixbuf))  
        
    def on_PhotoOrganizer_polaroid_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_polaroid(pixbuf,'Text default'))
    
    def on_PhotoOrganizer_sepia_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_sepia(pixbuf))
    
    def on_PhotoOrganizer_watermark_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_watermarkSignature(pixbuf))
    
    def on_PhotoOrganizer_histogram_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.createImageHistogram(pixbuf))   
    
    def on_PhotoOrganizer_light_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_light(pixbuf))  
        
    def on_PhotoOrganizer_gaussian_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_gaussian_blur(pixbuf,10))
        
    def on_PhotoOrganizer_colorize_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_colorize(pixbuf,"#000099","#99CCFF"))    
    
    def on_PhotoOrganizer_frame_clicked(self, widget):
        pixbuf = self.imageOpened.get_pixbuf()
        self.imageOpened.set_from_pixbuf(photoEffects.apply_frame(pixbuf)) 
     
    def on_PhotoOrganizer_webcam_clicked(self,widget):
        #need to be sure a imagePanel is already created
        if len(self.builder.get_object("imagePanel").get_children())==0:
            self.createImagePanel(None)
        self.imageOpened.set_from_pixbuf(photoEffects.captureWebcamImage())

    def on_PhotoOrganizer_save_clicked(self, widget):
        dialog = Gtk.FileChooserDialog("Save your image", self,Gtk.FileChooserAction.SAVE,(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,Gtk.STOCK_SAVE, Gtk.ResponseType.ACCEPT))
        dialog.set_default_size(800, 400)
     
        Gtk.FileChooser.set_do_overwrite_confirmation(dialog, True)
        Gtk.FileChooser.set_current_name(dialog, "Untitled document")
        
        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        dialog.add_filter(filter)
   
        filter = Gtk.FileFilter()
        filter.set_name("Images")
        filter.add_mime_type("image/png")
        filter.add_mime_type("image/jpeg")
        filter.add_mime_type("image/gif")
        filter.add_pattern("*.png")
        filter.add_pattern("*.jpg")
        filter.add_pattern("*.gif")
        filter.add_pattern("*.tif")
        filter.add_pattern("*.xpm")
        dialog.add_filter(filter)

        response = dialog.run()
        
        if response == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            dialog.destroy()
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            if(self.twitterSearch):
                photoOrganizerUtil.savePhotoFromUrl(self.lastTwitterImageUrl,filename)
            else:
                #should pass the quality
                outputExt = filename[filename.index('.')+1:]
                photoOrganizerUtil.savePhotoFromPixbuf(self.imageOpened.get_pixbuf(),outputExt,100,filename);
        else:
            dialog.destroy()
           
    def on_PhotoOrganizer_image_keypress_event(self,widget,event) :
        newImagePath = None
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Right":
            newImagePath = self.nextRightImage()
        if newImagePath is not None:
            self.createScaledImage(newImagePath)
        elif keyname == "Left":
          newImagePath = self.nextLeftImage()
          if newImagePath is not None:
              self.createScaledImage(newImagePath)
    
    def on_PhotoOrganizer_full_image_clicked(self,pimage,imageName):      
        self.winImage = Gtk.Window()
        self.winImage.set_title(imageName)
        self.winImage_vbox = Gtk.VBox(False,1)
        eventBox = Gtk.EventBox()
        eventBox.add(pimage)
        pimage.show()
        self.winImage_vbox.pack_start(eventBox, True, True, 0)
        self.winImage.add(self.winImage_vbox)
        (x, y) = self.get_position()
        y1 = y+50
        self.winImage.move(x, y1)
        self.winImage.show_all() 
    
    def on_PhotoOrganizer_tagPeople_clicked(self,widget):    
        imagePanel = self.builder.get_object("imagePanel")
        try:
            imagePanel.remove(imagePanel.get_children()[0])
        except:
            pass
        self.coords = []
        self.darea = Gtk.DrawingArea()
        pixbuf = self.imageOpened.get_pixbuf()
        width,height = pixbuf.get_width(),pixbuf.get_height() 
        self.imageForDrawing = Image.fromstring("RGB",(width,height),pixbuf.get_pixels() )
        self.imageForDrawingStart = True
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK) 
        self.darea.connect("draw", self.on_drawing_area_tagPeople_draw)
        self.darea.connect("button-press-event", self.on_drawing_area_tagPeople_button_press)
        #set the cursor for tagging
        cross_cursor = Gdk.Cursor(Gdk.CursorType.CROSSHAIR)
        imagePanel.get_window().set_cursor(cross_cursor)
        self.darea.set_size_request(pixbuf.get_width(),pixbuf.get_height())
        imagePanel.add_with_viewport(self.darea)
        #before showing need to get faces coordinates
        self.faces = []
        loadWindow = LoadingWindow()
        while Gtk.events_pending():
                Gtk.main_iteration_do(False)
        self.faces = photoEffects.buildFacesCoordinates(photoEffects.fromPixbufToPilImage(pixbuf))
        loadWindow.close_window()
        logger.debug("faces found:%d",len(self.faces))
        imagePanel.show_all()
    
    def on_drawing_area_tagPeople_draw(self, wid, cr):
        #the image cannot be loaded every time --> repaint
        if self.imageForDrawingStart == True:
            self.buffer = StringIO.StringIO()
            self.image = self.imageForDrawing
            self.imageForDrawingStart = False
            self.image.save(self.buffer, format="PNG")
            
        self.buffer.seek(0)
        cr.save()
        iss = ImageSurface.create_from_png(self.buffer)
        cr.set_source_surface(iss)
        
        cr.paint()
        cr.restore()
        
        #draw rectabgle with faces
        if self.faces is not None and len(self.faces)>0:
            for face in self.faces:
                xx = face[0][0]
                yy = face[0][1]
                width = face[0][2]
                height = face[0][3]
                             
                cr.move_to(xx,yy)
                cr.line_to(xx+width,yy)
                cr.move_to(xx,yy)
                cr.line_to(xx,yy+height)
                cr.move_to(xx,yy+height)
                cr.line_to(xx+width,yy+height)
                cr.move_to(xx+width,yy+height)
                cr.line_to(xx+width,yy)
                
                cr.stroke()
        
    def on_drawing_area_tagPeople_button_press(self, w, e):
        if e.type == Gdk.EventType.BUTTON_PRESS and e.button == 1:
            self.twin = TransparentWindow()
            box = Gtk.Box()
            self.tagPeopleEntry = EntryCompletion()
            #add saved people tag
            if self.peopleTag:
                for key in self.peopleTag.keys():
                    self.tagPeopleEntry.add_words([key])
            self.tagPeopleEntry.connect("key-press-event", self.on_drawing_area_tagPeople_entry_keypress)
            box.add(self.tagPeopleEntry )
            self.twin.add(box)
            self.twin.show_all()
            
            
    def on_drawing_area_tagPeople_entry_keypress(self,widget,event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Return":
            tagPeopleEntry = self.tagPeopleEntry.get_text()
            #set tooltip
            self.imageOpened.set_tooltip_text(tagPeopleEntry)
            #close transparent window
            self.twin.destroy()
            
            #split on white space
            splitString = tagPeopleEntry.split()
            #add the tag to the photo organizer pref
            if self.peopleTag is None:
                self.peopleTag = {}
                self.peopleTag[tagPeopleEntry] = []
                tag = PeopleTag()
                tag.totalPics = 1
                tag.name = splitString[0]
                tag.pics = []
                tag.pics.append(self.currentPhoto)
                self.peopleTag[tagPeopleEntry] = tag
            else:
                if tagPeopleEntry in self.photoOrganizerPref.peopleTag:
                    tag = self.peopleTag[tagPeopleEntry]
                    tag.totalPics = self.peopleTag[tagPeopleEntry].totalPics+1
                    tag.pics.append(self.currentPhoto)
                else:
                    self.peopleTag[tagPeopleEntry] = []
                    tag = PeopleTag()
                    tag.totalPics = 1
                    tag.name = splitString[0]
                    tag.pics = []
                    tag.pics.append(self.currentPhoto)
                    self.peopleTag[tagPeopleEntry] = tag
            
            #need to add the tag to the current photo
            self.currentPhoto.people.append(tagPeopleEntry)
            #need to update alcum collection
            for album in self.lastAlbumCollectionScanned.albums:
                if album.title == self.currentPhoto.dirName:
                    for pic in album.pics:
                        if pic.dirName+"/"+ pic.fileName == self.currentPhoto.dirName+"/"+ self.currentPhoto.fileName:
                            pic.people.append(tagPeopleEntry)
                            break
                    break
    
    def on_PhotoOrganizer_crop_clicked(self,widget):    
        imagePanel = self.builder.get_object("imagePanel")
        try:
            imagePanel.remove(imagePanel.get_children()[0])
        except:
            pass
        self.startAppend = False 
        self.deleteCoords = False
        self.coords = []
        self.darea = Gtk.DrawingArea()
        pixbuf = self.imageOpened.get_pixbuf()
        width,height = pixbuf.get_width(),pixbuf.get_height() 
        self.imageForDrawing = Image.fromstring("RGB",(width,height),pixbuf.get_pixels() )
        self.imageForDrawingStart = True
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK|Gdk.EventMask.POINTER_MOTION_MASK) 
        self.darea.connect("draw", self.on_drawing_area_draw)
        self.darea.connect("button-press-event", self.on_drawing_area_button_press)
        self.darea.connect("button-release-event", self.on_drawing_area_button_release)
        self.darea.connect("motion_notify_event", self.on_drawing_area_button_move) 
        self.darea.set_size_request(pixbuf.get_width(),pixbuf.get_height())
        imagePanel.add_with_viewport(self.darea)
        imagePanel.show_all()
    
    def on_drawing_area_draw(self, wid, cr):
        #the image cannot be loaded every time --> repaint
        if self.imageForDrawingStart == True:
            self.buffer = StringIO.StringIO()
            self.image = self.imageForDrawing
            self.imageForDrawingStart = False
            self.image.save(self.buffer, format="PNG")
            
        self.buffer.seek(0)
        cr.save()
        iss = ImageSurface.create_from_png(self.buffer)
        cr.set_source_surface(iss)
        cr.paint()
        cr.restore()

        for i in self.coords:
            for j in self.coords:
        
                firstCoord = self.coords[0]
                secondCoord = self.coords[len(self.coords)-1]
        
                cr.move_to(firstCoord[0],firstCoord[1])
                cr.line_to(secondCoord[0],firstCoord[1])
                cr.move_to(firstCoord[0],firstCoord[1])
                cr.line_to(firstCoord[0],secondCoord[1])
                cr.move_to(secondCoord[0],firstCoord[1])
                cr.line_to(secondCoord[0],secondCoord[1])
                cr.move_to(firstCoord[0],secondCoord[1])
                cr.line_to(secondCoord[0],secondCoord[1])
            
                cr.stroke()

                self.box = (int(firstCoord[0]),int(firstCoord[1]),int(secondCoord[0]),int(secondCoord[1]))
      

        if (self.deleteCoords == True):
            if(int(self.box[0])>int(self.box[2])):
                self.box = (self.box[2],self.box[1],self.box[0],self.box[3])
            if(int(self.box[1])>int(self.box[3])):
                self.box = (self.box[0],self.box[3],self.box[2],self.box[1])
                
            self.image = self.image.crop(self.box)
            del self.coords[:] 
            cr.set_source_rgb(1, 1, 1)
            cr.rectangle(0, 0, 1024, 768)
            cr.fill() 
        
            self.buffer = StringIO.StringIO()
            self.image.save(self.buffer, format="PNG")
            self.buffer.seek(0)
            cr.save()
            iss = ImageSurface.create_from_png(self.buffer)

            cr.set_source_surface(iss)
            cr.paint()
            cr.restore()

           
    
    def on_drawing_area_button_release(self, w, e):
        self.coords.append([e.x, e.y])
        self.darea.queue_draw()
        self.deleteCoords = True
        self.startAppend = False
    
    def on_drawing_area_button_move(self, w, e):
        if(self.startAppend == True):
            self.coords.append([e.x, e.y])
            self.darea.queue_draw()
            self.deleteCoords = False
                                  
    def on_drawing_area_button_press(self, w, e):
        if e.type == Gdk.EventType.BUTTON_PRESS and e.button == 1:
            self.coords.append([e.x, e.y])
            self.startAppend = True
    
    def nextRightImage(self):
        currentImageKey = self.imagePathOpened[self.imagePathOpened.rfind("/")+1:]
        previousKeyFounded = None
        for key, value in self.subImageMap.items():
            if previousKeyFounded is not None:
                return self.imagePathOpened[:self.imagePathOpened.rfind("/")+1]+key
            if key == currentImageKey:
                previousKeyFounded = key
    
    def nextLeftImage(self):
        currentImageKey = self.imagePathOpened[self.imagePathOpened.rfind("/")+1:]
        previousKeyFounded = None
        for key, value in self.subImageMap.items():
            if key != currentImageKey:
                previousKeyFounded = key
            if key == currentImageKey and previousKeyFounded is not None:
                return self.imagePathOpened[:self.imagePathOpened.rfind("/")+1]+previousKeyFounded 
    
    '''
        END SECTION FOR EVENTS
    '''
            
    def createScaledImage(self,imagePath): 
        pimage = Gtk.Image()
        
        if(self.twitterSearch):
            self.lastTwitterImageUrl = imagePath
            imagePath = imagePath[imagePath.index('http'):]
            response=urllib2.urlopen(imagePath)
            loader=GdkPixbuf.PixbufLoader()
            loader.write(response.read())
            loader.close() 
            pixbuf = loader.get_pixbuf()
                         
        if os.path.isfile(imagePath):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(imagePath)
            
        # scale the image          
        scaled_buf = photoEffects.scaleImageFromPixbuf(pixbuf,GdkPixbuf.InterpType.HYPER)
        pimage.set_from_pixbuf(scaled_buf)
        self.imagePathOpened = imagePath
        self.createImagePanel(pimage)
        
        if(self.twitterSearch):
            mediaUrl = self.imagePathOpened
            for entry in self.twitterSearchResult.entries:
                try:
                    if(entry.url.index(mediaUrl)!=-1):
                        self.imageOpened.set_tooltip_text("user:"+entry.author+"\ndate:"+entry.creationDate+"\ntext:"+entry.text)
                        self.imageOpened.show_all()
                        self.builder.get_object("detailsEntry").get_buffer().set_text("user:"+entry.author+"\ndate:"+entry.creationDate+"\ntext:"+entry.text)
                except:
                    pass
        else:
            self.builder.get_object("detailsEntry").get_buffer().set_text("")
            global totalPhotoDictionary 
            self.currentPhoto = totalPhotoDictionary[imagePath]
            gpsText = "\ntaken at:"
            dateText = "date:"
            authorText = "\nby:"
            descText = "\ndescription:"
            modelText = "\ncamera:"
            if self.currentPhoto.date:
                dateText = dateText+self.currentPhoto.date
            if self.currentPhoto.description:
                descText = descText+self.currentPhoto.description
            if self.currentPhoto.author:
                authorText = authorText+self.currentPhoto.author
            if self.currentPhoto.brand:
                modelText = modelText+str(self.currentPhoto.brand)+","+str(self.currentPhoto.model)
            if self.currentPhoto.latitude:
                gpsText = gpsText+str(self.currentPhoto.latitude)+","+str(self.currentPhoto.longitude)
            self.builder.get_object("detailsEntry").get_buffer().set_text(dateText+descText+authorText+modelText+gpsText)
    
    def createImagePanel(self,pimage):    
        imagePanel = self.builder.get_object("imagePanel")
        try:
            imagePanel.remove(imagePanel.get_children()[0])
        except:
            pass
        eventBox = Gtk.EventBox()
        eventBox.connect("button_press_event",self.on_PhotoOrganizer_image_contextmenu_event)
        if(pimage is not None):
            eventBox.add(pimage)
            #reference to image selected
            self.imageOpened = pimage
            pimage.show()
        else:
            self.imageOpened = Gtk.Image()
            eventBox.add(self.imageOpened)
        imagePanel.add_with_viewport(eventBox)
        imagePanel.show_all()

    def createThubnailPanel(self,imagePath):
          imagePanel = self.builder.get_object("imagePanel")
          try:
              imagePanel.remove(imagePanel.get_children()[0])
          except:
              #nothing to do
              pass
          if(imagePath in self.thubnailPanel):
               imagePanel.add(self.thubnailPanel[imagePath])
               imagePanel.show_all()
               while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
          else:          
              self.subImageMap = imageMap[imagePath]
              thubnailsSize = len(self.subImageMap.items())
              tempRows = math.ceil(thubnailsSize/10)
              tableRows = int(math.fabs(tempRows))
              if tableRows==0:
                  tableRows=1
              thubnailWindow_table = Gtk.Table(tableRows, 10, True)
              imagePanel.add(thubnailWindow_table)
              left_attach = 0
              right_attach = 1
              top_attach = 0
              bottom_attach = 1
              for key, value in self.subImageMap.items():
                   pimage = Gtk.Image()
                   eventBox = Gtk.EventBox()
                   eventBox.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
                   pixbuf = None
                   if(self.twitterSearch):
                        value.fileName = value.fileName[value.fileName.index('http'):]
                        response=urllib2.urlopen(value.fileName)
                        loader=GdkPixbuf.PixbufLoader()
                        loader.write(response.read())
                        loader.close() 
                        eventBox.connect("button_press_event", self.on_PhotoOrganizer_thub_clicked,value.fileName)
                        pixbuf = loader.get_pixbuf()
                   else:
                       eventBox.connect("button_press_event", self.on_PhotoOrganizer_thub_clicked,imagePath+"/"+value.fileName)
                       pixbuf = GdkPixbuf.Pixbuf.new_from_file(imagePath+"/"+value.fileName)           
                   scaled_buf = pixbuf.scale_simple(60,60,GdkPixbuf.InterpType.BILINEAR)
                   pimage.set_from_pixbuf(scaled_buf)
                   eventBox.add(pimage)
                   thubnailWindow_table.attach(eventBox,left_attach,right_attach,top_attach,bottom_attach)
                   thubnailWindow_table.set_col_spacings(5)
                   if right_attach <10:
                       right_attach+=1
                       left_attach+=1
                   else:
                     left_attach = 0  
                     right_attach = 1  
                     top_attach+=1 
                     bottom_attach+=1   
                   self.thubnailPanel[imagePath] = thubnailWindow_table
                   imagePanel.show_all()
                   while Gtk.events_pending():
                        Gtk.main_iteration_do(False)
    
    def callScanPhoto(self):
        loadWindow = LoadingWindow()
        
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        
        #get status_bar
        statusBar = self.builder.get_object("statusbar1")
        context = statusBar.get_context_id("example")        
        # create the treestore; the model has one column of type string
        treestore = Gtk.TreeStore(str)
        treestore.set_sort_column_id(0,Gtk.SortType.DESCENDING)
        treeview = self.builder.get_object("treeviewAlbum")    
        leftPanel = self.builder.get_object("leftPanel")
        #set current tab
        self.builder.get_object("notebook1").set_current_page(0)
        
        #need to reset
        global imageMap 
        imageMap= {}
        # call retrieve album list
        albumCollection,imageDictionary,photoDictionary = photoOrganizerUtil.walkDir(self.searchEntry,self.hiddenFolders,statusBar,context,treestore,treeview,imageMap,leftPanel)
        self.lastAlbumCollectionScanned = albumCollection 
        global totalPhotoDictionary 
        totalPhotoDictionary = photoDictionary

        if len(albumCollection.albums) >0:
            #need to erase people tags
            if(self.photoOrganizerPref is not None and self.photoOrganizerPref.peopleTag is not None):
                self.photoOrganizerPref.peopleTag = None
            imageMap = imageDictionary
            self.currentTreeview = treeview
            treeview.connect('cursor-changed', self.on_PhotoOrganizer_tree_entry_selected)
            loadWindow.close_window()
            leftPanel.show_all()
        else:
            loadWindow.close_window()
            self.on_PhotoOrganizer_search_error_event() 
    
    #create the main panel with a tree
    def createFixedPhotoTree(self,albumCollection,peopleTag,treeview):
        yearDictionary = {}
        monthDictionary = {}
        # create the treestore; the model has one column of type string
        treestore = Gtk.TreeStore(str)
        treestore.set_sort_column_id(0,Gtk.SortType.DESCENDING)
        for album in albumCollection.albums:
            
            listYearValue = yearDictionary.get(album.year) 
            if listYearValue is None:
                piter = treestore.append(None, ['%s' % album.year])
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
                yearDictionary[album.year] = piter
            
            listMonthValue = monthDictionary.get(str(album.year)+"-"+str(album.month)) 
            if listMonthValue is None:
                piter = treestore.append(yearDictionary[album.year], ['%s' % album.month])
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
                monthDictionary[str(album.year)+"-"+str(album.month)] = piter
            
            
            piter = treestore.append(monthDictionary[str(album.year)+"-"+str(album.month)], ['%s' % album.title])
            imageMap[album.title] = None
            subImageMap = {}
            for photo in album.pics:
                subImageMap[photo.fileName] = photo
                treestore.append(piter, ['%s' %album.title+"/"+photo.fileName])
            imageMap[album.title] = subImageMap  
        
        piter = treestore.append(None, [""])
        piter = treestore.append(None, ["People Tags"])
        #add people tags
        if peopleTag is not None:
            for key in peopleTag:
                piter2 = treestore.append(piter, ['%s' % key])
                for pic in peopleTag[key].pics:
                    treestore.append(piter2, ['%s' %pic.dirName+"/"+pic.fileName])
              
        treeview.set_model(treestore)
        albumNameCell = Gtk.CellRendererText()
        #build title tree string
        titleTree = "Album found ("+str(len(albumCollection.albums))+") - Total pics ("+str(albumCollection.totalPics)+")"
        albumNameCol = Gtk.TreeViewColumn(titleTree, albumNameCell, text=0)
        self.currentTreeview = treeview
        treeview.connect('cursor-changed', self.on_PhotoOrganizer_tree_entry_selected)
        treeview.insert_column(albumNameCol, 0)
            
    def removeSearchResult(self,treeview):
        try:
            #treeview.remove_column(treeview.get_column(0))
            treeview.get_model().clear()
            treeview.clear()
            self.currentTreeview.clear()
        except:
            pass  
    
    def loadPreferences(self):
        #load preferences
        self.photoOrganizerPref = photoOrganizerStorage.loadPref()
        self.peopleTag = None
        if(self.photoOrganizerPref!=None):
            self.peopleTag = self.photoOrganizerPref.peopleTag
            try:
                #load album saved
                self.hiddenFolders = self.photoOrganizerPref.hiddenFolders
                self.entry_folder_text = self.photoOrganizerPref.lastSearch
                treeview = self.builder.get_object("treeviewAlbum")
                self.createFixedPhotoTree(self.photoOrganizerPref.albumCollection,self.photoOrganizerPref.peopleTag,treeview)
                #rebuild photo indexes
                self.lastAlbumCollectionScanned = self.photoOrganizerPref.albumCollection
                savedAlbums = self.photoOrganizerPref.albumCollection
                for album in savedAlbums.albums:
                    for photo in album.pics:
                       totalPhotoDictionary[album.title+"/"+photo.fileName] = photo

                
                #set current tab
                self.builder.get_object("notebook1").set_current_page(0)
                leftPanel = self.builder.get_object("leftPanel")
                leftPanel.add_with_viewport(treeview)
                leftPanel.show_all()
                self.twitterSearch = False
                
                statusBar = self.builder.get_object("statusbar1")
                context = statusBar.get_context_id("example")  
                threads = []
                #start threads to search for new photos
                for album in savedAlbums.albums:
                    scan = UpdateAlbum(album,treeview.get_model(),statusBar,context)
                    threads.append(scan)
                    scan.start()


            #some pref properties stored could be not present --> no previous search available
            except:
                pass


def init_GUI():
    PhotoOrganizerGUI()

if __name__ == "__main__":
    init_GUI()