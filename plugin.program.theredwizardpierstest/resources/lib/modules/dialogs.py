import os
from typing import List
import xbmc
from xbmcaddon import Addon
from . import pyxbmct

ICON = Addon().getAddonInfo('icon')
PATH = Addon().getAddonInfo('path')
OVERLAY = os.path.join(PATH, 'resources', 'lib', 'modules', 'pyxbmct', 'textures', 'confluence', 'AddonWindow', 'ContentPanel.png')


class YesNoDialog(pyxbmct.BlankDialogWindow): 
    def __init__(self, heading: str, message: str, icon: str=None, fanart:str=None):
        super().__init__()
        self.setGeometry(1290, 730, 50, 30)
        #self.setGeometry(640, 480, 50, 30)
        self.heading = heading
        self.message = message
        self.icon = icon
        self.fanart = fanart
        self.selected = -1
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.set_controls()
        self.set_navigation()
        self.setFocus(self.yes_button)
    
    def set_controls(self):
        # Backgrounds
        self.fanart = pyxbmct.Image(Addon().getAddonInfo('fanart'))
        self.placeControl(self.fanart, 0, 0, 52, 32)
        self.overlay = pyxbmct.Image(OVERLAY)
        self.placeControl(self.overlay, -1, -1, 54, 34)
        
        # Buttons
        self.yes_button = pyxbmct.Button('Yes')
        self.placeControl(self.yes_button, 45, 5, 5, 3)
        self.connect(self.yes_button, self.yes_selected)
        
        self.no_button = pyxbmct.Button('No')
        self.placeControl(self.no_button, 45, 13, 5, 3)
        self.connect(self.no_button, self.no_selected)
        
        self.remind_button = pyxbmct.Button('Remind')
        self.placeControl(self.remind_button, 45, 22, 5, 3)
        self.connect(self.remind_button, self.remind_selected)
        
        # Textbox
        self.textbox = pyxbmct.TextBox()
        self.placeControl(self.textbox, 4, 1, 38, 19)
        self.textbox.setText(self.message)
        
        # Icon
        self.icon_control = pyxbmct.Image(self.icon, aspectRatio=2)
        self.placeControl(self.icon_control, 1, 22, 47, 7)
        
        
    def yes_selected(self):
        self.selected = 0
        self.close()
        
    def no_selected(self):
        self.selected = 1
        self.close()
    
    def remind_selected(self):
        self.selected = 2
        self.close()
    
    def setAnimation(self, control):
        # Set fade animation for all add-on window controls
        control.setAnimations([('WindowOpen', 'effect=slide start=0,200 end=0 time=300 tween=quadratic',),
                                ('WindowClose', 'effect=fade start=100 end=0 time=500',)])

    def set_navigation(self):
        # Set navigation between controls
        self.yes_button.controlLeft(self.remind_button)
        self.yes_button.controlRight(self.no_button)
        self.no_button.controlLeft(self.yes_button)
        self.no_button.controlRight(self.remind_button)
        self.remind_button.controlLeft(self.no_button)
        self.remind_button.controlRight(self.yes_button)
    
    def run(self) -> int:
        self.doModal()
        return self.selected


class SelectDialog(pyxbmct.BlankDialogWindow): 
    def __init__(self, heading:str, labels: List[str]=None, icon: str=ICON):
        super().__init__()
        self.setGeometry(1290, 730, 50, 30)
        #self.setGeometry(640, 480, 50, 30)
        self.heading = heading
        self.labels = [] if labels is None else labels
        self.icon = icon
        self.selected = -1
        self.set_controls()
        self.set_navigation()
    
    def set_controls(self):
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)
        self.fanart = pyxbmct.Image(Addon().getAddonInfo('fanart'))
        self.placeControl(self.fanart, 0, 0, 50, 30)
        self.overlay = pyxbmct.Image(OVERLAY)
        self.placeControl(self.overlay, -1, -1, 52, 32)
        self.close_button = pyxbmct.Button('Cancel')
        self.placeControl(self.close_button, 45, 27, 5, 3)
        self.connect(self.close_button, self.close)
        
        # List
        self.list = pyxbmct.List(_space=4, _itemHeight=65)
        self.placeControl(self.list, 4, 1, 49, 19)
        self.icon_control = pyxbmct.Image(self.icon, aspectRatio=2)
        self.placeControl(self.icon_control, 1, 22, 47, 7)
        self.list.addItems(self.labels)
        self.connect(self.list, lambda: self.update_selected(self.list.getListItem(self.list.getSelectedPosition()).getLabel()))
    
    def update_selected(self, label: str):
        self.selected = self.labels.index(label)
        self.close()
    
    def setAnimation(self, control):
        # Set fade animation for all add-on window controls
        control.setAnimations([('WindowOpen', 'effect=slide start=0,200 end=0 time=300 tween=quadratic',),
                                ('WindowClose', 'effect=fade start=100 end=0 time=500',)])

    def set_navigation(self):
        # Set navigation between controls
        self.list.controlUp(self.close_button)
        self.list.controlDown(self.close_button)
        self.list.controlLeft(self.close_button)
        self.list.controlRight(self.close_button)
        self.close_button.controlUp(self.list)
        self.close_button.controlDown(self.list)
        self.close_button.controlLeft(self.list)
        self.close_button.controlRight(self.list)
        # Set initial focus
        self.setFocus(self.list)
    
    def run(self) -> int:
        self.doModal()
        return self.selected

def select_dialog(heading: str, labels: List[str]=None, icon: str=Addon().getAddonInfo('icon')):
    dialog = SelectDialog(heading, labels=labels, icon=icon)
    selected = dialog.run()
    del dialog
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    return selected

def yes_no_remind_dialog(heading: str, message: str, icon: str, fanart: str):
    dialog = YesNoDialog(heading, message, icon, fanart)
    selected = dialog.run()
    del dialog
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    return selected


    