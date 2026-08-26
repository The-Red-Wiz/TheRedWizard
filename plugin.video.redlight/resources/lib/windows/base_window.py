# -*- coding: utf-8 -*-
import xbmcgui
import re
import json
from threading import Thread
from xml.dom.minidom import parse as mdParse
from modules import kodi_utils, settings
from caches.settings_cache import get_setting, set_setting, restore_setting_default
from modules.utils import manual_function_import
# logger = kodi_utils.logger

def open_window(import_info, skin_xml, **kwargs):
	'''
	import_info: ('module', 'function')
	'''
	try:
		xml_window = create_window(import_info, skin_xml, **kwargs)
		choice = xml_window.run()
		del xml_window
		return choice
	except Exception as e:
		kodi_utils.logger('error in open_window', str(e))

def create_window(import_info, skin_xml, **kwargs):
	'''
	import_info: ('module', 'function')
	'''
	try:
		function = manual_function_import(*import_info)
		args = (skin_xml, kodi_utils.addon_path())
		xml_window = function(*args, **kwargs)
		return xml_window
	except Exception as e:
		kodi_utils.logger('error in create_window', str(e))
		return kodi_utils.notification('Error')

def window_manager(obj):
	def close():
		obj.close()
		kodi_utils.clear_property('redlight.window_loaded')
		kodi_utils.clear_property('redlight.window_stack')

	def monitor():
		timer = 0
		while not kodi_utils.get_property('redlight.window_loaded') == 'true' and timer <= 5:
			kodi_utils.sleep(50)
			timer += 0.05
		kodi_utils.hide_busy_dialog()
		obj.close()
		kodi_utils.clear_property('redlight.window_loaded')

	def runner(params):
		try:
			mode = params['mode']
			if mode == 'extras_menu_choice':
				from indexers.dialogs import extras_menu_choice
				extras_menu_choice(params)
			elif mode == 'person_data_dialog':
				from indexers.people import person_data_dialog
				person_data_dialog(params)
			else: close()
		except: close()

	def get_stack():
		try: window_stack = json.loads(kodi_utils.get_property('redlight.window_stack'))
		except: window_stack = []
		return window_stack

	def add_to_stack(params):
		window_stack.append(params)
		kodi_utils.set_property('redlight.window_stack', json.dumps(window_stack))

	def remove_from_stack():
		previous_params = window_stack.pop()
		kodi_utils.set_property('redlight.window_stack', json.dumps(window_stack))
		return previous_params
	kodi_utils.show_busy_dialog()
	try:
		kodi_utils.clear_property('redlight.window_loaded')
		current_params = obj.current_params
		new_params = obj.new_params
		window_stack = get_stack()
		if current_params: add_to_stack(current_params)
		if new_params:
			Thread(target=monitor).start()
			runner(new_params)
		elif window_stack:
			previous_params = remove_from_stack()
			if previous_params:
				Thread(target=monitor).start()
				runner(previous_params)
		else: close()
	except: close()
	kodi_utils.hide_busy_dialog()

def window_player(obj):
	def monitor():
		timer = 0
		while not kodi_utils.get_property('redlight.window_loaded') == 'true' and timer <= 5:
			kodi_utils.sleep(50)
			timer += 0.05
		kodi_utils.hide_busy_dialog()
		obj.close()
		kodi_utils.clear_property('redlight.window_loaded')

	def runner(params):
		try:
			mode = params['mode']
			if mode == 'extras_menu_choice':
				from indexers.dialogs import extras_menu_choice
				extras_menu_choice(params)
			else:
				from indexers.people import person_data_dialog
				person_data_dialog(params)
		except: close()
	try:
		window_player_url = obj.window_player_url
		if 'plugin.video.youtube' in window_player_url:
			if not kodi_utils.addon_installed('plugin.video.youtube') or not kodi_utils.addon_enabled('plugin.video.youtube'):
				return kodi_utils.notification('Youtube Plugin needed for playback')
		kodi_utils.clear_property('redlight.window_loaded')
		current_params = obj.current_params
		player = kodi_utils.kodi_player()
		player.play(window_player_url)
		kodi_utils.sleep(2000)
		while not player.isPlayingVideo(): kodi_utils.sleep(100)
		obj.close()
		while player.isPlayingVideo(): kodi_utils.sleep(100)
		kodi_utils.show_busy_dialog()
		kodi_utils.sleep(1000)
		Thread(target=monitor).start()
		runner(current_params)
	except: obj.close()
	kodi_utils.hide_busy_dialog()

class BaseDialog(xbmcgui.WindowXMLDialog):
	def __init__(self, *args):
		xbmcgui.WindowXMLDialog.__init__(self, args)
		self.args = args
		self.player = kodi_utils.kodi_player()
		self.left_action = 1
		self.right_action = 2
		self.up_action = 3
		self.down_action = 4
		self.info_action = 11
		self.selection_actions = (7, 100)
		self.closing_actions = (9, 10, 13, 92)
		self.context_actions = (101, 108, 117)

	def current_skin(self):
		return kodi_utils.current_skin()

	def get_setting(self, setting_id, setting_default=''):
		return get_setting(setting_id, setting_default)

	def set_setting(self, setting_id, value):
		set_setting(setting_id, value)

	def restore_setting_default(self, params):
		restore_setting_default(params)

	def make_listitem(self):
		return kodi_utils.make_listitem()

	def build_url(self, params):
		return kodi_utils.build_url(params)

	def execute_code(self, command, block=False):
		return kodi_utils.execute_builtin(command, block)
	
	def get_position(self, window_id):
		return self.get_control(window_id).getSelectedPosition()

	def get_listitem(self, window_id):
		return self.get_control(window_id).getSelectedItem()

	def add_items(self, _control, _items):
		self.get_control(_control).addItems(_items)

	def select_item(self, _control, _item):
		self.get_control(_control).selectItem(_item)

	def set_image(self, _control, _image):
		self.get_control(_control).setImage(_image)

	def set_label(self, _control, _label):
		self.get_control(_control).setLabel(_label)

	def set_text(self, _control, _text):
		self.get_control(_control).setText(_text)

	def set_percent(self, _control, _percent):
		self.get_control(_control).setPercent(_percent)

	def reset_window(self, _control):
		self.get_control(_control).reset()

	def get_control(self, control_id):
		return self.getControl(control_id)

	def make_contextmenu_item(self, label, action, params):
		cm_item = self.make_listitem()
		cm_item.set_properties({'label': label, 'action': action % self.build_url(params)})
		return cm_item

	def get_infolabel(self, label):
		return kodi_utils.get_infolabel(label)

	def get_visibility(self, command):
		return kodi_utils.get_visibility(command)
	
	def open_window(self, import_info, skin_xml, **kwargs):
		return open_window(import_info, skin_xml, **kwargs)

	def run_addon(self, command, block=False):
		kodi_utils.run_plugin(command, block)

	def sleep(self, time):
		kodi_utils.sleep(time)

	def path_exists(self, path):
		return kodi_utils.path_exists(path)

	def translate_path(self, path):
		return kodi_utils.translate_path(path)

	def set_home_property(self, prop, value):
		kodi_utils.set_property('redlight.%s' % prop, value)

	def get_home_property(self, prop):
		return kodi_utils.get_property('redlight.%s' % prop)

	def clear_home_property(self, prop):
		return kodi_utils.clear_property('redlight.%s' % prop)

	def get_attribute(self, obj, attribute):
		return getattr(obj, attribute)

	def set_attribute(self, obj, attribute, value):
		return setattr(obj, attribute, value)

	def clear_modals(self):
		try: del self.player
		except: pass

	def notification(self, text, duration=3000):
		return kodi_utils.notification(text, duration)

	def addon_installed(self, addon_id):
		return kodi_utils.addon_installed(addon_id)

	def addon_enabled(self, addon_id):
		return kodi_utils.addon_enabled(addon_id)

class FontUtils:
	def execute_custom_fonts(self, skin_files=[]):
		if not skin_files and not self.skin_change_check(): return
		replacement_values, skin_font_xml = [], ''
		replacement_values_append = replacement_values.append
		skin_folder = self.get_skin_folder()
		if skin_folder: skin_font_xml = kodi_utils.translate_path('special://skin/%s/Font.xml' % skin_folder)
		if skin_font_xml: self.skin_font_info = self.get_font_info(skin_font_xml) or self.default_font_info()
		else: self.skin_font_info = self.default_font_info()
		for item in ((21, False, 'font10'), (26, False, 'font12'), (30, False, 'font13'), (33, False, 'font14'), (38, False, 'font16'), (60, True, 'font60')):
			replacement_values_append(self.match_font(*item))
		if not skin_files:
			kodi_utils.set_property('redlight.current_skin', self.current_skin)
			kodi_utils.set_property('redlight.current_font', self.current_font)
		skin_files = skin_files or kodi_utils.list_dirs(kodi_utils.translate_path('special://home/addons/plugin.video.redlight/resources/skins/Default/1080i/'))[1]
		for item in skin_files: self.replace_font(item, replacement_values)

	def get_skin_folder(self):
		folder_options = ('xml', '1080', '720', '1080p', '720p', '1080i', '720i', '16x9')
		skin_folder = None
		try:
			skin_folder = mdParse(kodi_utils.translate_path('special://skin/addon.xml')).getElementsByTagName('extension')[0].getElementsByTagName('res')[0].getAttribute('folder')
			if not skin_folder:
				s_folder = kodi_utils.list_dirs(kodi_utils.translate_path('special://skin'))[0]
				skin_folder = [i for i in s_folder if i in folder_options][0]
		except: pass
		return skin_folder

	def skin_change_check(self):
		self.current_skin, self.current_font = kodi_utils.current_skin(), kodi_utils.jsonrpc_get_system_setting('lookandfeel.font', 'Default')
		if self.current_skin != kodi_utils.get_property('redlight.current_skin') or self.current_font != kodi_utils.get_property('redlight.current_font'): return True
		return False

	def match_font(self, size, bold, fallback):
		font_tag = 'REDLIGHT_%s%s' % (size, '_BOLD' if bold else '')
		size_range = range(int(size * 0.75), int(size * 1.25))
		compatibility_range = range(int(size * 0.50), int(size * 1.50))
		compatibility_fonts = [i['name'] for i in self.skin_font_info if i['name'] == fallback and i['size'] in compatibility_range]
		if compatibility_fonts: return (font_tag, compatibility_fonts[0])
		sized_fonts = [i for i in self.skin_font_info if i['size'] in size_range]
		if not sized_fonts: return fallback
		fonts = [i for i in sized_fonts if i['bold'] == bold and not i['extra_styles']] or [i for i in sized_fonts if i['bold'] == bold] \
				or [i for i in sized_fonts if not i['extra_styles']] or sized_fonts
		return (font_tag, [i['name'] for i in fonts if i['size'] == min([i['size'] for i in fonts], key=lambda k: abs(k-size))][0])

	def get_font_info(self, skin_font_xml):
		extras_keys = ('upper', 'uppercase', 'italic', 'capitalize', 'black', 'mono', 'symbol')
		results = []
		if not skin_font_xml: return results
		results_append = results.append
		try:
			all_fonts = mdParse(skin_font_xml).getElementsByTagName('fontset')
			try: fontset = [i for i in all_fonts if i.getAttribute('id').lower() == self.current_font.lower()][0]
			except: fontset = all_fonts[0]
			font_element = fontset.getElementsByTagName('font')
			for item in font_element:
				try: name = item.getElementsByTagName('name')[0].firstChild.data
				except: continue
				try: size = int(item.getElementsByTagName('size')[0].firstChild.data)
				except: continue
				try: style = item.getElementsByTagName('style')[0].firstChild.data.lower()
				except: style = ''
				name_compare = name.lower()
				bold = any('bold' in item for item in (name_compare, style))
				extra_styles = any(item in style for item in extras_keys)
				if not extra_styles: extra_styles = any(item in name_compare for item in extras_keys)
				results_append({'name': name, 'size': size, 'bold': bold, 'extra_styles': extra_styles})
		except: pass
		return results

	def replace_font(self, window, replacement_values):
		file = kodi_utils.translate_path('special://home/addons/plugin.video.redlight/resources/skins/Default/1080i/' + window)
		with kodi_utils.open_file(file) as f: content = f.read()
		for item in replacement_values:
			try: content = re.sub(r'<font>(.*?)</font> <\!-- %s -->' % item[0], '<font>%s</font> <!-- %s -->' % (item[1], item[0]), content)
			except: pass
		with kodi_utils.open_file(file, 'w') as f: f.write(content)

	def default_font_info(self):
		return [{'name': 'font10', 'size': 21, 'bold': False, 'extra_styles': False},
				{'name': 'font12', 'size': 26, 'bold': False, 'extra_styles': False},
				{'name': 'font13', 'size': 30, 'bold': False, 'extra_styles': False},
				{'name': 'font14', 'size': 33, 'bold': False, 'extra_styles': False},
				{'name': 'font16', 'size': 38, 'bold': False, 'extra_styles': False},
				{'name': 'font45', 'size': 45, 'bold': False, 'extra_styles': False},
				{'name': 'font60', 'size': 60, 'bold': False, 'extra_styles': False}]


class ExtrasUtils:
	def __init__(self):
		self.media_heading = '[B]{label} $INFO[Window.Property({label_lookup}.number)][/B]'
		self.media_highlight = '[B]{label} | [/B]$INFO[ListItem.Property(name)]$INFO[ListItem.Property(release_date), • ]$INFO[ListItem.Property(vote_average), • ]'
		self.wide_thumb_highlight = '[B]{label} | [/B]$INFO[ListItem.Property(name)]'
		self.extras_items = {
		2050: {'insert_values': {'active_lookup': 'plot_enabled', 'content_lookup': 'plot'},
								'template': self.single_text_template()},
		2051: {'insert_values': {'heading_label': self.media_heading.format(label='Cast', label_lookup='cast'),
								'highlight_label': self.media_highlight.format(label='Cast')},
								'template': self.cast_thumb_template()},
		2052: {'insert_values': {'heading_label': self.media_heading.format(label='Recommended', label_lookup='recommended'),
								'highlight_label': self.media_highlight.format(label='Recommended')},
								'template': self.thumb_media_template()},
		2053: {'insert_values': {'heading_label': self.media_heading.format(label='Related', label_lookup='related'),
								'highlight_label': self.media_highlight.format(label='Related')},
								'template': self.thumb_media_template()},
		2054: {'insert_values': {'heading_label': self.media_heading.format(label='More Like This', label_lookup='more_like_this'),
								'highlight_label': self.media_highlight.format(label='More Like This')},
								'template': self.thumb_media_template()},
		2055: {'insert_values': {'heading_label': self.media_heading.format(label='Similar', label_lookup='ai_similar'),
								'highlight_label': self.media_highlight.format(label='Similar')},
								'template': self.thumb_media_template()},
		2056: {'insert_values': {'heading_label': self.media_heading.format(label='Reviews', label_lookup='imdb_reviews')},
								'template': self.text_media_template()},
		2057: {'insert_values': {'heading_label': self.media_heading.format(label='Comments', label_lookup='trakt_comments')},
								'template': self.text_media_template()},
		2058: {'insert_values': {'heading_label': self.media_heading.format(label='Trivia', label_lookup='imdb_trivia')},
								'template': self.text_media_template()},
		2059: {'insert_values': {'heading_label': self.media_heading.format(label='Blunders', label_lookup='imdb_blunders')},
								'template': self.text_media_template()},
		2060: {'insert_values': {}, 'template': self.parentsguide_template()},
		2061: {'insert_values': {'heading_label': self.media_heading.format(label='In Trakt Lists', label_lookup='trakt_in_lists')},
								'template': self.in_lists_template()},
		2062: {'insert_values': {'heading_label': self.media_heading.format(label='Videos', label_lookup='youtube_videos'),
								'highlight_label': self.wide_thumb_highlight.format(label='Videos')},
								'template': self.wide_thumb()},
		2063: {'insert_values': {'heading_label': self.media_heading.format(label='More from Year', label_lookup='more_from_year'),
								'highlight_label': self.media_highlight.format(label='More from Year')},
								'template': self.thumb_media_template()},
		2064: {'insert_values': {'heading_label': self.media_heading.format(label='More from Genres', label_lookup='more_from_genres'),
								'highlight_label': self.media_highlight.format(label='More from Genres')},
								'template': self.thumb_media_template()},
		2065: {'insert_values': {'heading_label': self.media_heading.format(label='More from Networks', label_lookup='more_from_networks'),
								'highlight_label': self.media_highlight.format(label='More from Networks')},
								'template': self.thumb_media_template()},
		2066: {'insert_values': {}, 'template': self.collection_template()}
						
						}

	def run(self):
		try:
			finished_templates = []
			skin_file = 'extras.xml'
			file = kodi_utils.translate_path('special://home/addons/plugin.video.redlight/resources/skins/Default/1080i/%s' % skin_file)
			media_list = settings.extras_order()
			if not media_list: return
			media_list = [i for i in media_list if i in self.extras_items]
			if not media_list: return
			media_list_length = len(media_list)
			first_container = media_list[0]
			last_container = media_list[media_list_length - 1]
			for index, item in enumerate(media_list):
				if index == 0: previous_item = 14
				else: previous_item = media_list[index - 1]
				if index == media_list_length - 1: next_item = 10
				else: next_item = media_list[index + 1]
				item_values = self.extras_items[item]
				template = item_values['template']
				insert_values = item_values['insert_values']
				insert_values.update({'container_no': item, 'scrollbar_no': item + 2000, 'p_container_no': previous_item, 'n_container_no': next_item})
				template = template.format(**insert_values)
				finished_templates.append(template)
			body = ''.join(finished_templates)
			fmt = {'first_container': first_container, 'last_container': last_container}
			content = self.prefix_template().format(**fmt) + body + self.suffix_template().format(**fmt)
			with kodi_utils.open_file(file, 'w') as f: f.write(content)
			FontUtils().execute_custom_fonts(skin_files=[skin_file])
		except Exception as e:
			kodi_utils.logger('ExtrasUtils', str(e))

	def thumb_media_template(self):
		return  '''\
				<control type="group">
				    <visible>Integer.IsGreater(Container({container_no}).NumItems,0)</visible>
				    <height>760</height>
				    <control type="group">
				        <control type="label">
				            <width min="30" max="1160">auto</width>
				            <height>20</height>
				            <font>font14</font> <!-- REDLIGHT_33 -->
				            <textcolor>FFCCCCCC</textcolor>
				            <label>{heading_label}</label>
				            <visible>!Control.HasFocus({container_no})</visible>
				        </control>
				        <control type="label">
				            <width min="30" max="1160">auto</width>
				            <height>20</height>
				            <font>font14</font> <!-- REDLIGHT_33 -->
				            <textcolor>FFCCCCCC</textcolor>
				            <label>{highlight_label}</label>
				            <visible>Control.HasFocus({container_no})</visible>
				        </control>
				        <control type="fixedlist" id="{container_no}">
				            <animation effect="slide" end="-472,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,1) | Integer.IsEqual(Container({container_no}).NumItems,2)">Conditional</animation>
				            <animation effect="slide" end="-236,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,3) | Integer.IsEqual(Container({container_no}).NumItems,4)">Conditional</animation>
				            <pagecontrol>{scrollbar_no}</pagecontrol>
				            <top>60</top>
				            <width>1180</width>
				            <height>360</height>
				            <onup>{p_container_no}</onup>
				            <ondown>{scrollbar_no}</ondown>
				            <orientation>horizontal</orientation>
				            <scrolltime tween="sine">500</scrolltime>
				            <focusposition>2</focusposition>
				            <movement>2</movement>
				            <itemlayout height="360" width="236">
				                <control type="image">
				                    <left>8</left>
				                    <top>8</top>
				                    <height max="344">auto</height>
				                    <width max="220">auto</width>
				                    <aspectratio>keep</aspectratio>
				                    <texture diffuse="redlight_diffuse/poster-50.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
				                </control>
				            </itemlayout>
				            <focusedlayout height="360" width="236">
				                <control type="image">
				                    <animation effect="fade" start="100" end="60" condition="Control.HasFocus({scrollbar_no})">Conditional</animation>
				                    <animation type="Focus" reversible="false">
				                        <effect type="zoom" end="105" time="75" tween="sine" easing="out" center="auto" />
				                        <effect type="zoom" end="95" time="225" tween="sine" delay="100" easing="out" center="auto" />
				                    </animation>
				                    <left>0</left>
				                    <top>5</top>
				                    <height>350</height>
				                    <width>236</width>
				                    <texture colordiffuse="FFCCCCCC">redlight_diffuse/poster-50.png</texture>
				                    <visible>Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})</visible>
				                </control>
				                <control type="image">
				                    <left>8</left>
				                    <top>8</top>
				                    <height max="344">auto</height>
				                    <width max="220">auto</width>
				                    <aspectratio>keep</aspectratio>
				                    <texture diffuse="redlight_diffuse/poster-50.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
				                </control>
				            </focusedlayout>
				        </control>
				        <control type="scrollbar" id="{scrollbar_no}">
				            <left>5</left>
				            <top>432</top>
				            <width>1170</width>
				            <height>15</height>
				            <onup>{container_no}</onup>
				            <ondown>{n_container_no}</ondown>
				            <texturesliderbackground colordiffuse="FF1F2020">redlight_common/white.png</texturesliderbackground>
				            <texturesliderbar colordiffuse="FF555556">redlight_common/white.png</texturesliderbar>
				            <texturesliderbarfocus colordiffuse="FFCCCCCC">redlight_common/white.png</texturesliderbarfocus>
				            <showonepage>false</showonepage>
				            <orientation>Horizontal</orientation>
				            <visible>String.IsEqual(Window.Property(enable_scrollbars),true) + [Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
				        </control>
				        <control type="image">
				            <top>215</top>
				            <left>20</left>
				            <width>25</width>
				            <height>25</height>
				            <texture colordiffuse="CCCCCCCC" background="true">redlight_common/arrow_left.png</texture>
				            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasPrevious</visible>
				        </control>
				        <control type="image">
				            <top>215</top>
				            <left>1135</left>
				            <width>25</width>
				            <height>25</height>
				            <texture colordiffuse="CCCCCCCC" background="true" flipx="true">redlight_common/arrow_left.png</texture>
				            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasNext</visible>
				        </control>
				    </control>
				</control>
'''

	def cast_thumb_template(self):
		"""Cast tiles: name + role under the photo, clipped to the thumb width. Full text stays in the Cast heading on focus."""
		return  '''\
				<control type="group">
				    <visible>Integer.IsGreater(Container({container_no}).NumItems,0)</visible>
				    <height>760</height>
				    <control type="group">
				        <control type="label">
				            <width min="30" max="1160">auto</width>
				            <height>20</height>
				            <font>font14</font> <!-- REDLIGHT_33 -->
				            <textcolor>FFCCCCCC</textcolor>
				            <label>{heading_label}</label>
				            <visible>!Control.HasFocus({container_no})</visible>
				        </control>
				        <control type="label">
				            <width min="30" max="1160">auto</width>
				            <height>20</height>
				            <font>font14</font> <!-- REDLIGHT_33 -->
				            <textcolor>FFCCCCCC</textcolor>
				            <label>{highlight_label}</label>
				            <visible>Control.HasFocus({container_no})</visible>
				        </control>
				        <control type="fixedlist" id="{container_no}">
				            <animation effect="slide" end="-472,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,1) | Integer.IsEqual(Container({container_no}).NumItems,2)">Conditional</animation>
				            <animation effect="slide" end="-236,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,3) | Integer.IsEqual(Container({container_no}).NumItems,4)">Conditional</animation>
				            <pagecontrol>{scrollbar_no}</pagecontrol>
				            <top>60</top>
				            <width>1180</width>
				            <height>360</height>
				            <onup>{p_container_no}</onup>
				            <ondown>{scrollbar_no}</ondown>
				            <orientation>horizontal</orientation>
				            <scrolltime tween="sine">500</scrolltime>
				            <focusposition>2</focusposition>
				            <movement>2</movement>
				            <itemlayout height="360" width="236">
				                <control type="image">
				                    <left>8</left>
				                    <top>8</top>
				                    <height max="268">auto</height>
				                    <width max="220">auto</width>
				                    <aspectratio>keep</aspectratio>
				                    <texture diffuse="redlight_diffuse/poster-50.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
				                </control>
				                <control type="label">
				                    <left>8</left>
				                    <top>282</top>
				                    <width>220</width>
				                    <height>22</height>
				                    <font>font10</font> <!-- REDLIGHT_21 -->
				                    <textcolor>FFCCCCCC</textcolor>
				                    <align>center</align>
				                    <aligny>center</aligny>
				                    <scroll>true</scroll>
				                    <label>$INFO[ListItem.Property(cast_name)]</label>
				                </control>
				                <control type="label">
				                    <left>8</left>
				                    <top>304</top>
				                    <width>220</width>
				                    <height>22</height>
				                    <font>font10</font> <!-- REDLIGHT_21 -->
				                    <textcolor>FF999999</textcolor>
				                    <align>center</align>
				                    <aligny>center</aligny>
				                    <scroll>true</scroll>
				                    <label>$INFO[ListItem.Property(cast_role)]</label>
				                </control>
				            </itemlayout>
				            <focusedlayout height="360" width="236">
				                <control type="image">
				                    <animation effect="fade" start="100" end="60" condition="Control.HasFocus({scrollbar_no})">Conditional</animation>
				                    <animation type="Focus" reversible="false">
				                        <effect type="zoom" end="105" time="75" tween="sine" easing="out" center="auto" />
				                        <effect type="zoom" end="95" time="225" tween="sine" delay="100" easing="out" center="auto" />
				                    </animation>
				                    <left>0</left>
				                    <top>5</top>
				                    <height>278</height>
				                    <width>236</width>
				                    <texture colordiffuse="FFCCCCCC">redlight_diffuse/poster-50.png</texture>
				                    <visible>Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})</visible>
				                </control>
				                <control type="image">
				                    <left>8</left>
				                    <top>8</top>
				                    <height max="268">auto</height>
				                    <width max="220">auto</width>
				                    <aspectratio>keep</aspectratio>
				                    <texture diffuse="redlight_diffuse/poster-50.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
				                </control>
				                <control type="label">
				                    <left>8</left>
				                    <top>282</top>
				                    <width>220</width>
				                    <height>22</height>
				                    <font>font10</font> <!-- REDLIGHT_21 -->
				                    <textcolor>FFCCCCCC</textcolor>
				                    <align>center</align>
				                    <aligny>center</aligny>
				                    <scroll>false</scroll>
				                    <label>$INFO[ListItem.Property(cast_name)]</label>
				                </control>
				                <control type="label">
				                    <left>8</left>
				                    <top>304</top>
				                    <width>220</width>
				                    <height>22</height>
				                    <font>font10</font> <!-- REDLIGHT_21 -->
				                    <textcolor>FF999999</textcolor>
				                    <align>center</align>
				                    <aligny>center</aligny>
				                    <scroll>false</scroll>
				                    <label>$INFO[ListItem.Property(cast_role)]</label>
				                </control>
				            </focusedlayout>
				        </control>
				        <control type="scrollbar" id="{scrollbar_no}">
				            <left>5</left>
				            <top>432</top>
				            <width>1170</width>
				            <height>15</height>
				            <onup>{container_no}</onup>
				            <ondown>{n_container_no}</ondown>
				            <texturesliderbackground colordiffuse="FF1F2020">redlight_common/white.png</texturesliderbackground>
				            <texturesliderbar colordiffuse="FF555556">redlight_common/white.png</texturesliderbar>
				            <texturesliderbarfocus colordiffuse="FFCCCCCC">redlight_common/white.png</texturesliderbarfocus>
				            <showonepage>false</showonepage>
				            <orientation>Horizontal</orientation>
				            <visible>String.IsEqual(Window.Property(enable_scrollbars),true) + [Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
				        </control>
				        <control type="image">
				            <top>140</top>
				            <left>20</left>
				            <width>25</width>
				            <height>25</height>
				            <texture colordiffuse="CCCCCCCC" background="true">redlight_common/arrow_left.png</texture>
				            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasPrevious</visible>
				        </control>
				        <control type="image">
				            <top>140</top>
				            <left>1135</left>
				            <width>25</width>
				            <height>25</height>
				            <texture colordiffuse="CCCCCCCC" background="true" flipx="true">redlight_common/arrow_left.png</texture>
				            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasNext</visible>
				        </control>
				    </control>
				</control>
'''

	def text_media_template(self):
		return '''\
				<control type="group">
				    <visible>Integer.IsGreater(Container({container_no}).NumItems,0)</visible>
				    <height>760</height>
				    <control type="group">
				        <control type="label">
				            <width max="1160">auto</width>
				            <height>20</height>
				            <font>font14</font> <!-- REDLIGHT_33 -->
				            <textcolor>FFCCCCCC</textcolor>
				            <align>left</align>
				            <aligny>bottom</aligny>
				            <label>{heading_label}</label>
				        </control>
				        <control type="panel" id="{container_no}">
				            <pagecontrol>{scrollbar_no}</pagecontrol>
				            <top>60</top>
				            <width>1180</width>
				            <height>360</height>
				            <onup>{p_container_no}</onup>
				            <ondown>{scrollbar_no}</ondown>
				            <orientation>horizontal</orientation>
				            <scrolltime tween="sine">500</scrolltime>
				            <itemlayout height="380" width="590">
				                <control type="image">
				                    <height>360</height>
				                    <width>580</width>
				                    <texture colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texture>
				                </control>
				                <control type="textbox">
				                    <top>15</top>
				                    <left>20</left>
				                    <width>540</width>
				                    <height>308</height>
				                    <font>font12</font> <!-- REDLIGHT_26 -->
				                    <align>center</align>
				                    <aligny>top</aligny>
				                    <textcolor>FFCCCCCC</textcolor>
				                    <label>$INFO[ListItem.Property(text)]</label>
				                    <autoscroll>false</autoscroll>
				                </control>
				            </itemlayout>
				            <focusedlayout height="380" width="590">
				                <control type="image">
				                    <height>360</height>
				                    <width>580</width>
				                    <texture colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texture>
				                </control>
				                <control type="textbox">
				                    <top>15</top>
				                    <left>20</left>
				                    <width>540</width>
				                    <height>308</height>
				                    <font>font12</font> <!-- REDLIGHT_26 -->
				                    <align>center</align>
				                    <aligny>top</aligny>
				                    <textcolor>FF1F2020</textcolor>
				                    <label>$INFO[ListItem.Property(text)]</label>
				                    <autoscroll>false</autoscroll>
				                </control>
				            </focusedlayout>
				        </control>
				        <control type="scrollbar" id="{scrollbar_no}">
				            <top>432</top>
				            <width>1170</width>
				            <height>15</height>
				            <onup>{container_no}</onup>
				            <ondown>{n_container_no}</ondown>
				            <texturesliderbackground colordiffuse="FF1F2020">redlight_common/white.png</texturesliderbackground>
				            <texturesliderbar colordiffuse="FF555556">redlight_common/white.png</texturesliderbar>
				            <texturesliderbarfocus colordiffuse="FFCCCCCC">redlight_common/white.png</texturesliderbarfocus>
				            <showonepage>false</showonepage>
				            <orientation>Horizontal</orientation>
				            <visible>String.IsEqual(Window.Property(enable_scrollbars),true) + [Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
				        </control>
				        <control type="image">
				            <top>225</top>
				            <left>20</left>
				            <width>25</width>
				            <height>25</height>
				            <texture colordiffuse="CCCCCCCC" background="true">redlight_common/arrow_left.png</texture>
				            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasPrevious</visible>
				        </control>
				        <control type="image">
				            <top>225</top>
				            <left>1125</left>
				            <width>25</width>
				            <height>25</height>
				            <texture colordiffuse="CCCCCCCC" background="true" flipx="true">redlight_common/arrow_left.png</texture>
				            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasNext</visible>
				        </control>
				    </control>
				</control>
'''

	def single_text_template(self):
		return '''\
                <control type="group">
                    <visible>String.IsEqual(Window.Property({active_lookup}),true)</visible>
                    <height>730</height>
                    <control type="group">
                        <control type="button" id="{container_no}">
                            <width>1180</width>
                            <height>390</height>
                            <onup>{p_container_no}</onup>
                            <ondown>{n_container_no}</ondown>
                            <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                            <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                        </control>
                        <control type="textbox">
                            <top>15</top>
                            <left>15</left>
                            <width>1150</width>
                            <height>340</height>
                            <font>font13</font> <!-- REDLIGHT_30 -->
                            <align>center</align>
                            <aligny>center</aligny>
                            <textcolor>FFCCCCCC</textcolor>
                            <label>$INFO[Window.Property({content_lookup})]</label>
                            <autoscroll time="1500" delay="6000" repeat="3000">true</autoscroll>
                            <visible>!Control.HasFocus({container_no})</visible>
                        </control>
                        <control type="textbox">
                            <top>15</top>
                            <left>15</left>
                            <width>1150</width>
                            <height>340</height>
                            <font>font13</font> <!-- REDLIGHT_30 -->
                            <align>center</align>
                            <aligny>center</aligny>
                            <textcolor>FF1F2020</textcolor>
                            <label>$INFO[Window.Property(plot)]</label>
                            <autoscroll>false</autoscroll>
                            <visible>Control.HasFocus({container_no})</visible>
                        </control>
                    </control>
                </control>
'''

	def prefix_template(self):
		return '''\
<?xml version="1.0" encoding="UTF-8"?>
<window>
    <defaultcontrol>10</defaultcontrol>
    <controls>
        <control type="group">
            <width>1920</width>
            <height>1080</height>
            <control type="image">
                <texture colordiffuse="FF000000">redlight_common/white.png</texture>
            </control>
            <control type="image" id="202">
                <aspectratio>scale</aspectratio>
                <animation effect="fade" end="25" time="400">WindowOpen</animation>
            </control>
        </control>
        <control type="group">
            <animation effect="fade" end="100" time="200" delay="400">WindowOpen</animation>
            <control type="group">
                <left>5</left>
                <control type="image">
                    <top>5</top>
                    <width>60</width>
                    <height>60</height>
                    <aspectratio aligny="top">keep</aspectratio>
                    <texture>$INFO[Window(10000).Property(redlight.addon_icon_mini)]</texture>
                </control>
                <control type="group">
                    <visible>String.IsEqual(ListItem.Property(info_alert),)</visible>
                    <control type="label">
                        <top>20</top>
                        <left>1590</left>
                        <width max="300">auto</width>
                        <height>20</height>
                        <font>font37</font> <!-- REDLIGHT_38 -->
                        <textcolor>FFCCCCCC</textcolor>
                        <align>right</align>
                        <aligny>center</aligny>
                        <label>[B]$INFO[System.Time][/B]</label>
                    </control>
                    <control type="label">
                        <top>50</top>
                        <left>1540</left>
                        <width max="350">auto</width>
                        <height>20</height>
                        <font>font10</font> <!-- REDLIGHT_21 -->
                        <textcolor>FFCCCCCC</textcolor>
                        <align>right</align>
                        <aligny>center</aligny>
                        <label>$INFO[System.Date]</label>
                    </control>
                </control>
                <control type="group">
                    <left>1250</left>
                    <top>25</top>
                    <control type="image">
                        <top>0</top>
                        <left>610</left>
                        <width>35</width>
                        <height>35</height>
                        <aspectratio>keep</aspectratio>
                        <texture>redlight_common/info.png</texture>
                        <visible>!String.IsEqual(ListItem.Property(info_alert),)</visible>
                    </control>
                    <control type="label">
                        <width max="600">auto</width>
                        <height>20</height>
                        <font>font10</font> <!-- REDLIGHT_21 -->
                        <textcolor>FFCCCCCC</textcolor>
                        <align>right</align>
                        <aligny>bottom</aligny>
                        <label>$INFO[ListItem.Property(info_alert)]</label>
                        <visible>!String.IsEqual(ListItem.Property(info_alert),)</visible>
                    </control>
                </control>
            </control>
            <control type="group">
                <control type="image" id="200">
                    <top>80</top>
                    <left>1250</left>
                    <width>650</width>
                    <height>1000</height>
                    <aspectratio>keep</aspectratio>
                    <texture diffuse="redlight_diffuse/poster-50.png" background="true" />
                </control>
                <control type="group">
                    <control type="image" id="201">
                        <top>35</top>
                        <left>70</left>
                        <height max="250">auto</height>
                        <width max="1110">auto</width>
                        <aspectratio>keep</aspectratio>
                        <align>center</align>
                        <aligny>bottom</aligny>
                    </control>
                    <control type="label">
                        <top>150</top>
                        <left>70</left>
                        <width max="1130">auto</width>
                        <height>30</height>
                        <font>font60</font> <!-- REDLIGHT_60_BOLD -->
                        <textcolor>FFCCCCCC</textcolor>
                        <align>center</align>
                        <aligny>bottom</aligny>
                        <label>[B]$INFO[Window.Property(title)][/B]</label>
                        <visible>String.IsEqual(Window.Property(clearlogo),false)</visible>
                    </control>
                </control>
            </control>
            <!-- Title/logo stay fixed. Genre/ratings + action buttons scroll with the lists (no focus-linked fade/slide — those break mouse). -->
            <control type="grouplist">
                <top>295</top>
                <left>35</left>
                <width>1190</width>
                <height>785</height>
                <orientation>vertical</orientation>
                <scrolltime tween="sine">500</scrolltime>
                <itemgap>-300</itemgap>
                <usecontrolcoords>true</usecontrolcoords>
                <control type="group">
                    <height>730</height>
                    <control type="group">
                        <left>15</left>
                        <control type="group">
                            <animation effect="slide" end="0,25" time="0" condition="String.IsEqual(Window.Property(display_extra_ratings),false)">Conditional</animation>
                            <control type="label">
                                <width max="1150">auto</width>
                                <height>25</height>
                                <font>font14</font> <!-- REDLIGHT_33 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <align>center</align>
                                <label>[I]$INFO[Window.Property(genre)][/I]</label>
                            </control>
                            <control type="grouplist">
                                <top>55</top>
                                <width max="1150">auto</width>
                                <orientation>horizontal</orientation>
                                <itemgap>10</itemgap>
                                <align>center</align>
                                <control type="image" id="203">
                                    <width>45</width>
                                    <height>45</height>
                                    <aspectratio>keep</aspectratio>
                                    <align>center</align>
                                    <aligny>center</aligny>
                                </control>
                                <control type="label" id="2001">
                                    <width max="1026">auto</width>
                                    <height>32</height>
                                    <font>font13</font> <!-- REDLIGHT_30 -->
                                    <textcolor>FFCCCCCC</textcolor>
                                    <align>left</align>
                                </control>
                            </control>
                            <control type="label" id="3001">
                                <top>105</top>
                                <width max="1150">auto</width>
                                <height>25</height>
                                <font>font14</font> <!-- REDLIGHT_33 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <align>center</align>
                            </control>
                            <control type="grouplist">
                                <top>165</top>
                                <width max="1110">auto</width>
                                <orientation>horizontal</orientation>
                                <itemgap>30</itemgap>
                                <align>center</align>
                                <control type="grouplist">
                                    <width>130</width>
                                    <orientation>horizontal</orientation>
                                    <itemgap>0</itemgap>
                                    <align>center</align>
                                    <visible>String.IsEqual(Window.Property(metascore_rating),true)</visible>
                                    <control type="image" id="4101">
                                        <width>52</width>
                                        <height>32</height>
                                        <aspectratio>keep</aspectratio>
                                        <align>right</align>
                                        <aligny>center</aligny>
                                    </control>
                                    <control type="label" id="4001">
                                        <width max="75">auto</width>
                                        <height>32</height>
                                        <font>font13</font> <!-- REDLIGHT_30 -->
                                        <textcolor>FFCCCCCC</textcolor>
                                        <align>left</align>
                                        <aligny>center</aligny>
                                    </control>
                                </control>
                                <control type="grouplist">
                                    <width>130</width>
                                    <orientation>horizontal</orientation>
                                    <itemgap>0</itemgap>
                                    <align>center</align>
                                    <visible>String.IsEqual(Window.Property(tomatometer_rating),true)</visible>
                                    <control type="image" id="4102">
                                        <width>52</width>
                                        <height>32</height>
                                        <aspectratio>keep</aspectratio>
                                        <align>right</align>
                                        <aligny>center</aligny>
                                    </control>
                                    <control type="label" id="4002">
                                        <width max="75">auto</width>
                                        <height>32</height>
                                        <font>font13</font> <!-- REDLIGHT_30 -->
                                        <textcolor>FFCCCCCC</textcolor>
                                        <align>left</align>
                                        <aligny>center</aligny>
                                    </control>
                                </control>
                                <control type="grouplist">
                                    <width>130</width>
                                    <orientation>horizontal</orientation>
                                    <itemgap>0</itemgap>
                                    <align>center</align>
                                    <visible>String.IsEqual(Window.Property(tomatousermeter_rating),true)</visible>
                                    <control type="image" id="4103">
                                        <width>52</width>
                                        <height>32</height>
                                        <aspectratio>keep</aspectratio>
                                        <align>right</align>
                                        <aligny>center</aligny>
                                    </control>
                                    <control type="label" id="4003">
                                        <width max="75">auto</width>
                                        <height>32</height>
                                        <font>font13</font> <!-- REDLIGHT_30 -->
                                        <textcolor>FFCCCCCC</textcolor>
                                        <align>left</align>
                                        <aligny>center</aligny>
                                    </control>
                                </control>
                                <control type="grouplist">
                                    <width>130</width>
                                    <orientation>horizontal</orientation>
                                    <itemgap>10</itemgap>
                                    <align>center</align>
                                    <visible>String.IsEqual(Window.Property(imdb_rating),true)</visible>
                                    <control type="image" id="4104">
                                        <width>52</width>
                                        <height>32</height>
                                        <aspectratio>keep</aspectratio>
                                        <align>right</align>
                                        <aligny>center</aligny>
                                    </control>
                                    <control type="label" id="4004">
                                        <width max="75">auto</width>
                                        <height>32</height>
                                        <font>font13</font> <!-- REDLIGHT_30 -->
                                        <textcolor>FFCCCCCC</textcolor>
                                        <align>left</align>
                                        <aligny>center</aligny>
                                    </control>
                                </control>
                                <control type="grouplist">
                                    <width>130</width>
                                    <orientation>horizontal</orientation>
                                    <itemgap>0</itemgap>
                                    <align>center</align>
                                    <visible>String.IsEqual(Window.Property(tmdb_rating),true)</visible>
                                    <control type="image" id="4105">
                                        <width>52</width>
                                        <height>32</height>
                                        <aspectratio>keep</aspectratio>
                                        <align>right</align>
                                        <aligny>center</aligny>
                                    </control>
                                    <control type="label" id="4005">
                                        <width max="75">auto</width>
                                        <height>32</height>
                                        <font>font13</font> <!-- REDLIGHT_30 -->
                                        <textcolor>FFCCCCCC</textcolor>
                                        <align>left</align>
                                        <aligny>center</aligny>
                                    </control>
                                </control>
                            </control>
                        </control>
                    </control>
                    <control type="group">
                        <top>225</top>
                        <control type="group">
                            <control type="button" id="10">
                                <width>275</width>
                                <height>70</height>
                                <onleft>13</onleft>
                                <onright>11</onright>
                                <onup>{last_container}</onup>
                                <ondown>14</ondown>
                                <label>$INFO[Window.Property(button10.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                            <control type="button" id="11">
                                <left>300</left>
                                <width>275</width>
                                <height>70</height>
                                <onleft>10</onleft>
                                <onright>12</onright>
                                <onup>{last_container}</onup>
                                <ondown>15</ondown>
                                <label>$INFO[Window.Property(button11.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                            <control type="button" id="12">
                                <left>600</left>
                                <width>275</width>
                                <height>70</height>
                                <onleft>11</onleft>
                                <onright>13</onright>
                                <onup>{last_container}</onup>
                                <ondown>16</ondown>
                                <label>$INFO[Window.Property(button12.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                            <control type="button" id="13">
                                <left>900</left>
                                <width>275</width>
                                <height>70</height>
                                <onleft>12</onleft>
                                <onright>10</onright>
                                <onup>{last_container}</onup>
                                <ondown>17</ondown>
                                <label>$INFO[Window.Property(button13.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                        </control>
                        <control type="group">
                            <top>90</top>
                            <control type="button" id="14">
                                <width>275</width>
                                <height>70</height>
                                <onleft>17</onleft>
                                <onright>15</onright>
                                <onup>10</onup>
                                <ondown>{first_container}</ondown>
                                <label>$INFO[Window.Property(button14.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                            <control type="button" id="15">
                                <left>300</left>
                                <width>275</width>
                                <height>70</height>
                                <onleft>14</onleft>
                                <onright>16</onright>
                                <onup>11</onup>
                                <ondown>{first_container}</ondown>
                                <label>$INFO[Window.Property(button15.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                            <control type="button" id="16">
                                <left>600</left>
                                <width>275</width>
                                <height>70</height>
                                <onleft>15</onleft>
                                <onright>17</onright>
                                <onup>12</onup>
                                <ondown>{first_container}</ondown>
                                <label>$INFO[Window.Property(button16.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                            <control type="button" id="17">
                                <left>900</left>
                                <width>275</width>
                                <height>70</height>
                                <onleft>16</onleft>
                                <onup>13</onup>
                                <onright>14</onright>
                                <ondown>{first_container}</ondown>
                                <label>$INFO[Window.Property(button17.label)]</label>
                                <font>font13</font> <!-- REDLIGHT_30 -->
                                <textcolor>FFCCCCCC</textcolor>
                                <focusedcolor>FF1F2020</focusedcolor>
                                <texturefocus colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texturefocus>
                                <texturenofocus colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texturenofocus>
                                <align>center</align>
                                <aligny>center</aligny>
                            </control>
                        </control>
                    </control>
                </control>

'''

	def suffix_template(self):
		return '''\
            </control>
        </control>
    </controls>
</window>

'''

	def collection_template(self):
		return '''\
                <control type="group">
                    <visible>Integer.IsGreater(Container({container_no}).NumItems,0)</visible>
                    <height>760</height>
                    <control type="group">
                        <control type="label">
                            <width min="30" max="1160">auto</width>
                            <height>20</height>
                            <font>font14</font> <!-- REDLIGHT_33 -->
                            <textcolor>FFCCCCCC</textcolor>
                            <label>[B]$INFO[Window.Property(more_from_collection.name)] $INFO[Window.Property(more_from_collection.number)][/B]</label>
                            <visible>!Control.HasFocus({container_no})</visible>
                        </control>
                        <control type="label">
                            <width min="30" max="1160">auto</width>
                            <height>20</height>
                            <font>font14</font> <!-- REDLIGHT_33 -->
                            <textcolor>FFCCCCCC</textcolor>
                            <label>[B]$INFO[Window.Property(more_from_collection.name)] | [/B]$INFO[ListItem.Property(name)]$INFO[ListItem.Property(release_date), • ]$INFO[ListItem.Property(vote_average), • ]</label>
                            <visible>Control.HasFocus({container_no})</visible>
                        </control>
                        <control type="group">
                            <top>60</top>
                            <control type="image">
                                <height>360</height>
                                <width>933</width>
                                    <texture colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texture>
                                <visible>Integer.IsGreater(Container({container_no}).NumItems,1)</visible>
                            </control>
                            <control type="image">
                                <height>360</height>
                                <width>1169</width>
                                    <texture colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texture>
                                <visible>Integer.IsGreater(Container({container_no}).NumItems,2)</visible>
                            </control>
                            <control type="image">
                                <left>6</left>
                                <top>6</top>
                                <width>224</width>
                                <height>348</height>
                                <aspectratio>keep</aspectratio>
                                <texture diffuse="redlight_diffuse/poster-50.png" background="true">$INFO[Window.Property(more_from_collection.poster)]</texture>
                            </control>
                            <control type="textbox">
                                <left>235</left>
                                <top>6</top>
                                <width>218</width>
                                <height>348</height>
                                <font>font12</font> <!-- REDLIGHT_26 -->
                                <align>center</align>
                                <aligny>center</aligny>
                                <textcolor>FFCCCCCC</textcolor>
                                <label>$INFO[Window.Property(more_from_collection.overview)]</label>
                                <autoscroll time="1500" delay="6000" repeat="3000">true</autoscroll>
                            </control>
                        </control>
                        <control type="fixedlist" id="{container_no}">
                            <animation effect="slide" end="-236,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,2)">Conditional</animation>
                            <pagecontrol>{scrollbar_no}</pagecontrol>
                            <top>60</top>
                            <left>460</left>
                            <width>708</width>
                            <height>360</height>
                            <onup>{p_container_no}</onup>
                            <ondown>{scrollbar_no}</ondown>
                            <orientation>horizontal</orientation>
                            <scrolltime tween="sine">500</scrolltime>
                            <focusposition>1</focusposition>
                            <movement>1</movement>
                            <itemlayout height="360" width="236">
                                <control type="image">
                                    <left>8</left>
                                    <top>8</top>
                                    <height max="344">auto</height>
                                    <width max="220">auto</width>
                                    <aspectratio>keep</aspectratio>
                                    <texture diffuse="redlight_diffuse/poster-50.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                            </itemlayout>
                            <focusedlayout height="360" width="236">
                                <control type="image">
                                    <animation effect="fade" start="100" end="60" condition="Control.HasFocus({scrollbar_no})">Conditional</animation>
                                    <animation type="Focus" reversible="false">
                                        <effect type="zoom" end="105" time="75" tween="sine" easing="out" center="auto" />
                                        <effect type="zoom" end="95" time="225" tween="sine" delay="100" easing="out" center="auto" />
                                    </animation>
                                    <left>0</left>
                                    <top>5</top>
                                    <height>350</height>
                                    <width>236</width>
                                    <texture colordiffuse="FFCCCCCC">redlight_diffuse/poster-50.png</texture>
                                    <visible>Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})</visible>
                                </control>
                                <control type="image">
                                    <left>8</left>
                                    <top>8</top>
                                    <height max="344">auto</height>
                                    <width max="220">auto</width>
                                    <aspectratio>keep</aspectratio>
                                    <texture diffuse="redlight_diffuse/poster-50.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                            </focusedlayout>
                        </control>
                        <control type="scrollbar" id="{scrollbar_no}">
                            <top>432</top>
                            <width>1170</width>
                            <height>15</height>
                            <onup>{container_no}</onup>
                            <ondown>{n_container_no}</ondown>
                            <texturesliderbackground colordiffuse="FF1F2020">redlight_common/white.png</texturesliderbackground>
                            <texturesliderbar colordiffuse="FF555556">redlight_common/white.png</texturesliderbar>
                            <texturesliderbarfocus colordiffuse="FFCCCCCC">redlight_common/white.png</texturesliderbarfocus>
                            <showonepage>false</showonepage>
                            <orientation>Horizontal</orientation>
                            <visible>String.IsEqual(Window.Property(enable_scrollbars),true) + [Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
                        </control>
                        <control type="image">
                            <top>215</top>
                            <left>480</left>
                            <width>25</width>
                            <height>25</height>
                            <texture colordiffuse="CCCCCCCC" background="true">redlight_common/arrow_left.png</texture>
                            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasPrevious</visible>
                        </control>
                        <control type="image">
                            <top>215</top>
                            <left>1120</left>
                            <width>25</width>
                            <height>25</height>
                            <texture colordiffuse="CCCCCCCC" background="true" flipx="true">redlight_common/arrow_left.png</texture>
                            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasNext</visible>
                        </control>
                    </control>
                </control>
'''

	def wide_thumb(self):
		return '''\
                <control type="group">
                    <visible>Integer.IsGreater(Container({container_no}).NumItems,0)</visible>
                    <height>760</height>
                    <control type="group">
                        <control type="label">
                            <width min="30" max="1160">auto</width>
                            <height>20</height>
                            <font>font14</font> <!-- REDLIGHT_33 -->
                            <textcolor>FFCCCCCC</textcolor>
                            <label>{heading_label}</label>
                            <visible>!Control.HasFocus({container_no})</visible>
                        </control>
                        <control type="label">
                            <width min="30" max="1160">auto</width>
                            <height>20</height>
                            <font>font14</font> <!-- REDLIGHT_33 -->
                            <textcolor>FFCCCCCC</textcolor>
                            <label>{highlight_label}</label>
                            <visible>Control.HasFocus({container_no})</visible>
                        </control>
                        <control type="fixedlist" id="{container_no}">
                            <animation effect="slide" end="-392,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,1) | Integer.IsEqual(Container({container_no}).NumItems,2)">Conditional</animation>
                            <pagecontrol>{scrollbar_no}</pagecontrol>
                            <top>60</top>
                            <width>1180</width>
                            <height>360</height>
                            <onup>{p_container_no}</onup>
                            <ondown>{scrollbar_no}</ondown>
                            <orientation>horizontal</orientation>
                            <scrolltime tween="sine">500</scrolltime>
                            <focusposition>1</focusposition>
                            <movement>1</movement>
                            <itemlayout height="360" width="392">
                                <control type="image">
                                    <left>8</left>
                                    <top>8</top>
                                    <height max="344">auto</height>
                                    <width max="376">auto</width>
                                    <aspectratio>keep</aspectratio>
                                    <texture diffuse="redlight_diffuse/landscape.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                            </itemlayout>
                            <focusedlayout height="360" width="392">
                                <control type="image">
                                    <animation effect="fade" start="100" end="60" condition="Control.HasFocus({scrollbar_no})">Conditional</animation>
                                    <animation type="Focus" reversible="false">
                                        <effect type="zoom" end="105" time="75" tween="sine" easing="out" center="auto" />
                                        <effect type="zoom" end="95" time="225" tween="sine" delay="100" easing="out" center="auto" />
                                    </animation>
                                    <left>0</left>
                                    <top>32</top>
                                    <height>296</height>
                                    <width>393</width>
                                    <texture colordiffuse="FFCCCCCC">redlight_diffuse/landscape.png</texture>
                                    <visible>Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})</visible>
                                </control>
                                <control type="image">
                                    <left>8</left>
                                    <top>8</top>
                                    <height max="344">auto</height>
                                    <width max="376">auto</width>
                                    <aspectratio>keep</aspectratio>
                                    <texture diffuse="redlight_diffuse/landscape.png" background="true">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                            </focusedlayout>
                        </control>
                        <control type="scrollbar" id="{scrollbar_no}">
                            <left>5</left>
                            <top>432</top>
                            <width>1165</width>
                            <height>15</height>
                            <onup>{container_no}</onup>
                            <ondown>{n_container_no}</ondown>
                            <texturesliderbackground colordiffuse="FF1F2020">redlight_common/white.png</texturesliderbackground>
                            <texturesliderbar colordiffuse="FF555556">redlight_common/white.png</texturesliderbar>
                            <texturesliderbarfocus colordiffuse="FFCCCCCC">redlight_common/white.png</texturesliderbarfocus>
                            <showonepage>false</showonepage>
                            <orientation>Horizontal</orientation>
                            <visible>String.IsEqual(Window.Property(enable_scrollbars),true) + [Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
                        </control>
                        <control type="image">
                            <top>230</top>
                            <left>20</left>
                            <width>25</width>
                            <height>25</height>
                            <texture colordiffuse="CCCCCCCC" background="true">redlight_common/arrow_left.png</texture>
                            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasPrevious</visible>
                        </control>
                        <control type="image">
                            <top>230</top>
                            <left>1125</left>
                            <width>25</width>
                            <height>25</height>
                            <texture colordiffuse="CCCCCCCC" background="true" flipx="true">redlight_common/arrow_left.png</texture>
                            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasNext</visible>
                        </control>
                    </control>
                </control>
'''

	def in_lists_template(self):
		return '''\
                <control type="group">
                    <visible>Integer.IsGreater(Container({container_no}).NumItems,0)</visible>
                    <height>760</height>
                    <control type="group">
                        <control type="label">
                            <width max="1160">auto</width>
                            <height>20</height>
                            <font>font14</font> <!-- REDLIGHT_33 -->
                            <textcolor>FFCCCCCC</textcolor>
                            <align>left</align>
                            <aligny>bottom</aligny>
                            <label>{heading_label}</label>
                        </control>
                        <control type="fixedlist" id="{container_no}">
                            <animation effect="slide" end="-472,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,1) | Integer.IsEqual(Container({container_no}).NumItems,2)">Conditional</animation>
                            <animation effect="slide" end="-236,0" time="0" condition="Integer.IsEqual(Container({container_no}).NumItems,3) | Integer.IsEqual(Container({container_no}).NumItems,4)">Conditional</animation>
                            <pagecontrol>{scrollbar_no}</pagecontrol>
                            <top>60</top>
                            <width>1180</width>
                            <height>360</height>
                            <onup>{p_container_no}</onup>
                            <ondown>{scrollbar_no}</ondown>
                            <orientation>horizontal</orientation>
                            <scrolltime tween="sine">500</scrolltime>
                            <focusposition>2</focusposition>
                            <movement>2</movement>
                            <itemlayout height="360" width="236">
                                <control type="image">
                                    <height>360</height>
                                    <width>230</width>
                                    <texture colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texture>
                                </control>
                                <control type="image">
                                    <left>-35</left>
                                    <top>20</top>
                                    <width>300</width>
                                    <height>300</height>
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <aspectratio>scale</aspectratio>
                                    <texture colordiffuse="0DFFFFFF">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                                <control type="textbox">
                                    <left>5</left>
                                    <top>10</top>
                                    <width>220</width>
                                    <height>340</height>
                                    <font>font12</font> <!-- REDLIGHT_26 -->
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <textcolor>FFCCCCCC</textcolor>
                                    <label>$INFO[ListItem.Property(name)]</label>
                                    <autoscroll>false</autoscroll>
                                </control>
                                <control type="image">
                                    <top>-300</top>
                                    <left>90</left>
                                    <width>50</width>
                                    <aspectratio>keep</aspectratio>
                                    <texture colordiffuse="red">redlight_common/overlay_selected.png</texture>
                                    <visible>String.IsEqual(ListItem.Property(liked_status),true)</visible>
                                </control>
                            </itemlayout>
                            <focusedlayout height="360" width="236">
                                <control type="image">
                                    <width>230</width>
                                    <height>360</height>
                                    <texture colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texture>
                                    <visible>Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})</visible>
                                    <animation effect="fade" start="100" end="60" condition="Control.HasFocus({scrollbar_no})">Conditional</animation>
                                </control>
                                <control type="image">
                                    <height>360</height>
                                    <width>230</width>
                                    <texture colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texture>
                                    <visible>![Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
                                </control>
                                <control type="image">
                                    <left>-35</left>
                                    <top>20</top>
                                    <width>300</width>
                                    <height>300</height>
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <aspectratio>scale</aspectratio>
                                    <texture colordiffuse="1A1F2020">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                                <control type="textbox">
                                    <left>5</left>
                                    <top>10</top>
                                    <width>220</width>
                                    <height>340</height>
                                    <font>font12</font> <!-- REDLIGHT_26 -->
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <textcolor>FF1F2020</textcolor>
                                    <label>$INFO[ListItem.Property(name)]</label>
                                    <autoscroll>false</autoscroll>
                                    <visible>Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})</visible>
                                </control>
                                <control type="textbox">
                                    <left>5</left>
                                    <top>10</top>
                                    <width>220</width>
                                    <height>340</height>
                                    <font>font12</font> <!-- REDLIGHT_26 -->
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <textcolor>FFCCCCCC</textcolor>
                                    <label>$INFO[ListItem.Property(name)]</label>
                                    <autoscroll>false</autoscroll>
                                    <visible>![Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
                                </control>
                                <control type="image">
                                    <top>-300</top>
                                    <left>90</left>
                                    <width>50</width>
                                    <aspectratio>keep</aspectratio>
                                    <texture colordiffuse="red">redlight_common/overlay_selected.png</texture>
                                    <visible>String.IsEqual(ListItem.Property(liked_status),true)</visible>
                                </control>
                            </focusedlayout>
                        </control>
                        <control type="scrollbar" id="{scrollbar_no}">
                            <left>5</left>
                            <top>432</top>
                            <width>1170</width>
                            <height>15</height>
                            <onup>{container_no}</onup>
                            <ondown>{n_container_no}</ondown>
                            <texturesliderbackground colordiffuse="FF1F2020">redlight_common/white.png</texturesliderbackground>
                            <texturesliderbar colordiffuse="FF555556">redlight_common/white.png</texturesliderbar>
                            <texturesliderbarfocus colordiffuse="FFCCCCCC">redlight_common/white.png</texturesliderbarfocus>
                            <showonepage>false</showonepage>
                            <orientation>Horizontal</orientation>
                            <visible>String.IsEqual(Window.Property(enable_scrollbars),true) + [Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})]</visible>
                        </control>
                        <control type="image">
                            <top>215</top>
                            <left>20</left>
                            <width>25</width>
                            <height>25</height>
                            <texture colordiffuse="CCCCCCCC" background="true">redlight_common/arrow_left.png</texture>
                            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasPrevious</visible>
                        </control>
                        <control type="image">
                            <top>215</top>
                            <left>1135</left>
                            <width>25</width>
                            <height>25</height>
                            <texture colordiffuse="CCCCCCCC" background="true" flipx="true">redlight_common/arrow_left.png</texture>
                            <visible>[Control.HasFocus({container_no}) | Control.HasFocus({scrollbar_no})] + Container({container_no}).HasNext</visible>
                        </control>
                    </control>
                </control>
'''

	def parentsguide_template(self):
		return '''\
                <control type="group">
                    <visible>Integer.IsGreater(Container(2060).NumItems,0)</visible>
                    <height>760</height>
                    <control type="group">
                        <control type="label">
                            <width max="1160">auto</width>
                            <height>20</height>
                            <font>font14</font> <!-- REDLIGHT_33 -->
                            <textcolor>FFCCCCCC</textcolor>
                            <align>left</align>
                            <aligny>bottom</aligny>
                            <label>[B]Parental Guide $INFO[Window.Property(imdb_parentsguide.number)][/B]</label>
                        </control>
                        <control type="panel" id="2060">
                            <top>60</top>
                            <width>1180</width>
                            <height>360</height>
                            <onup>{p_container_no}</onup>
                            <ondown>{n_container_no}</ondown>
                            <orientation>horizontal</orientation>
                            <scrolltime tween="sine">500</scrolltime>
                            <itemlayout height="360" width="236">
                                <control type="image">
                                    <height>360</height>
                                    <width>230</width>
                                    <texture colordiffuse="$INFO[Window(10000).Property(redlight.window_theme.extras)]" border="30">redlight_common/circle.png</texture>
                                </control>
                                <control type="image">
                                    <left>6</left>
                                    <top>40</top>
                                    <width>224</width>
                                    <height>320</height>
                                    <aspectratio>scale</aspectratio>
                                    <texture colordiffuse="FFCCCCCC" border="30">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                                <control type="textbox">
                                    <left>6</left>
                                    <top>6</top>
                                    <width>224</width>
                                    <height>75</height>
                                    <font>font12</font> <!-- REDLIGHT_26 -->
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <textcolor>FFCCCCCC</textcolor>
                                    <label>$INFO[ListItem.Property(name)]</label>
                                    <autoscroll>false</autoscroll>
                                </control>
                                <control type="textbox">
                                    <left>6</left>
                                    <top>280</top>
                                    <width>224</width>
                                    <height>75</height>
                                    <font>font12</font> <!-- REDLIGHT_26 -->
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <textcolor>FFCCCCCC</textcolor>
                                    <label>$INFO[ListItem.Property(ranking)]</label>
                                    <autoscroll>false</autoscroll>
                                </control>
                            </itemlayout>
                            <focusedlayout height="360" width="236">
                                <control type="image">
                                    <width>230</width>
                                    <height>360</height>
                                    <texture colordiffuse="FFCCCCCC" border="30">redlight_common/circle.png</texture>
                                </control>
                                <control type="image">
                                    <left>6</left>
                                    <top>40</top>
                                    <width>224</width>
                                    <height>320</height>
                                    <aspectratio>scale</aspectratio>
                                    <texture colordiffuse="FF1F2020" border="30">$INFO[ListItem.Property(thumbnail)]</texture>
                                </control>
                                <control type="textbox">
                                    <left>6</left>
                                    <top>6</top>
                                    <width>224</width>
                                    <height>75</height>
                                    <font>font12</font> <!-- REDLIGHT_26 -->
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <textcolor>FF1F2020</textcolor>
                                    <label>$INFO[ListItem.Property(name)]</label>
                                    <autoscroll>false</autoscroll>
                                </control>
                                <control type="textbox">
                                    <left>6</left>
                                    <top>280</top>
                                    <width>224</width>
                                    <height>75</height>
                                    <font>font12</font> <!-- REDLIGHT_26 -->
                                    <align>center</align>
                                    <aligny>center</aligny>
                                    <textcolor>FF1F2020</textcolor>
                                    <label>$INFO[ListItem.Property(ranking)]</label>
                                    <autoscroll>false</autoscroll>
                                </control>
                            </focusedlayout>
                        </control>
                    </control>
                </control>
'''