# -*- coding: utf-8 -*-
import json
from windows.base_window import BaseDialog
# from modules.kodi_utils import logger

class Select(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.window_id = 2025
		self.kwargs = kwargs
		self.enumerate = self.kwargs.get('enumerate', 'false')
		self.multi_choice = self.kwargs.get('multi_choice', 'false')
		self.multi_line = self.kwargs.get('multi_line', 'false')
		self.preselect = self.kwargs.get('preselect', [])
		self.items = json.loads(self.kwargs['items'])
		self.heading = self.kwargs.get('heading', '')
		self.media_type = self.kwargs.get('media_type', '')
		self.narrow_window = self.kwargs.get('narrow_window', 'false')
		self.enable_context_menu = self.kwargs.get('enable_context_menu', 'false') == 'true'
		self.set_focus = self.kwargs.get('set_focus', None)
		self.item_list = []
		self.chosen_indexes = []
		self.selected = None
		self.control_id = None
		self.set_properties()
		self.make_menu()

	def onInit(self):
		self.add_items(self.window_id, self.item_list)
		if self.preselect:
			if len(self.preselect) == len(self.item_list): self.setProperty('select_button', 'deselect_all')
			for index in self.preselect:
				self.item_list[index].setProperty('check_status', 'checked')
				self.chosen_indexes.append(index)
		self.setFocusId(self.window_id)
		if self.set_focus is not None: self.select_item(self.window_id, self.set_focus)

	def run(self):
		self.doModal()
		self.clearProperties()
		return self.selected

	def onClick(self, controlID):
		self.control_id = None
		if controlID in (10, 11, 12, 13):
			if controlID == 10:
				self.selected = sorted(self.chosen_indexes)
				self.close()
			elif controlID == 11:
				self.close()
			elif controlID in (12, 13):
				item_list_indexes = list(range(0, len(self.item_list)))
				if controlID == 12: status, select_property, self.chosen_indexes = 'checked', 'deselect_all', item_list_indexes
				else: status, select_property, self.chosen_indexes = '', 'select_all', []
				for index in item_list_indexes: self.item_list[index].setProperty('check_status', status)
				self.setProperty('select_button', select_property)
				try: self.setFocusId(10)
				except: pass
		else: self.control_id = controlID

	def onAction(self, action):
		chosen_listitem = self.get_listitem(self.window_id)
		if action in self.selection_actions:
			if not self.control_id: return
			position = self.get_position(self.window_id)
			if self.multi_choice == 'true':
				if chosen_listitem.getProperty('check_status') == 'checked':
					chosen_listitem.setProperty('check_status', '')
					self.chosen_indexes.remove(position)
				else:
					chosen_listitem.setProperty('check_status', 'checked')
					self.chosen_indexes.append(position)
			else:
				self.selected = position
				return self.close()
		elif action in self.context_actions or action in self.closing_actions: return self.close()

	def make_menu(self):
		def builder():
			for count, item in enumerate(self.items, 1):
				listitem = self.make_listitem()
				if enum: line1 = '%02d. %s' % (count, item['line1'])
				else: line1 = item['line1']
				if 'line2' in item: line2 = item['line2']
				else: line2 = ''
				if 'icon' in item: listitem.setProperty('icon', item['icon'])
				else: listitem.setProperty('icon', '')
				listitem.setProperty('line1', line1)
				listitem.setProperty('line2', line2)
				yield listitem
		enum = self.enumerate == 'true'
		self.item_list = list(builder())

	def set_properties(self):
		self.setProperty('multi_choice', self.multi_choice)
		self.setProperty('multi_line', self.multi_line)
		self.setProperty('select_button', 'select_all')
		self.setProperty('heading', self.heading)
		self.setProperty('narrow_window', self.narrow_window)

def _handle_scroll_area_nav(dialog, action, ok_id=10, cancel_id=11):
	if getattr(dialog, 'scroll_focus', 'false') != 'true': return False
	try:
		if dialog.getFocusId() != 2070: return False
	except: return False
	aid = action.getId()
	if aid == dialog.left_action:
		dialog.setFocusId(cancel_id)
		return True
	if aid == dialog.right_action:
		dialog.setFocusId(ok_id)
		return True
	return False

class Confirm(BaseDialog):
	_BTN_OK, _BTN_CANCEL, _BTN_THIRD = 3010, 3011, 3012
	_LEGACY_BTN = {_BTN_OK: 10, _BTN_CANCEL: 11, _BTN_THIRD: 12}
	_LEGACY_TO_BTN = {10: _BTN_OK, 11: _BTN_CANCEL, 12: _BTN_THIRD}

	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.ok_label = kwargs['ok_label']
		self.cancel_label = kwargs['cancel_label']
		self.third_label = kwargs.get('third_label', '')
		self.text = kwargs['text']
		self.heading = kwargs['heading']
		self.default_control = kwargs['default_control']
		self.scroll = kwargs.get('scroll', 'false')
		self.scroll_focus = kwargs.get('scroll_focus', 'false')
		self.selected = None
		self.set_properties()

	def _focus_control(self, control_id):
		try:
			return self._LEGACY_TO_BTN.get(int(control_id), int(control_id))
		except:
			return self._BTN_CANCEL

	def onInit(self):
		focus_id = 2070 if self.scroll_focus == 'true' else self._focus_control(self.default_control)
		self.setFocusId(focus_id)

	def run(self):
		self.doModal()
		return self.selected

	def onClick(self, controlID):
		try:
			controlID = int(controlID)
		except:
			return
		if controlID not in (self._BTN_OK, self._BTN_CANCEL, self._BTN_THIRD):
			return
		if self.third_label:
			self.selected = self._LEGACY_BTN[controlID]
		else:
			self.selected = controlID == self._BTN_OK
		self.close()

	def onAction(self, action):
		cancel_id = self._BTN_CANCEL if not self.third_label else self._BTN_THIRD
		if _handle_scroll_area_nav(self, action, ok_id=self._BTN_OK, cancel_id=cancel_id): return
		try:
			action_id = action.getId()
		except:
			action_id = action
		if action_id in self.closing_actions:
			self.close()

	def set_properties(self):
		self.setProperty('ok_label', self.ok_label)
		self.setProperty('cancel_label', self.cancel_label)
		self.setProperty('third_label', self.third_label)
		self.setProperty('show_third_button', 'true' if self.third_label else 'false')
		self.setProperty('text', self.text)
		self.setProperty('heading', self.heading)
		self.setProperty('scroll', self.scroll)
		self.setProperty('scroll_focus', self.scroll_focus)
		# Legacy ids: 10=OK, 11=Cancel — scrollbar ondown follows this.
		try: self.setProperty('default_control', str(int(self.default_control)))
		except: self.setProperty('default_control', '11')

class OK(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, *args)
		self.ok_label = kwargs.get('ok_label') or 'OK'
		self.text = kwargs['text']
		self.heading = kwargs['heading']
		self.scroll = kwargs.get('scroll', 'false')
		self.scroll_focus = kwargs.get('scroll_focus', 'false')
		self.set_properties()

	def onInit(self):
		self.setFocusId(2070 if self.scroll_focus == 'true' else 10)

	def run(self):
		self.doModal()

	def onClick(self, controlID):
		self.close()

	def onAction(self, action):
		if _handle_scroll_area_nav(self, action, ok_id=10, cancel_id=10): return
		if action in self.closing_actions:
			self.close()

	def set_properties(self):
		self.setProperty('ok_label', self.ok_label)
		self.setProperty('text', self.text)
		self.setProperty('heading', self.heading)
		self.setProperty('scroll', self.scroll)
		self.setProperty('scroll_focus', self.scroll_focus)
