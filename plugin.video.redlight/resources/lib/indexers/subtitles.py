# -*- coding: utf-8 -*-
import base64
import json
import os
import re
import xbmc
import xbmcgui
import requests
from difflib import SequenceMatcher
from urllib.parse import quote, unquote
from modules import kodi_utils as ku, settings as st

timeout = 20.0
_ALERT_SUB_MAX_REMAINING = 600
# When dialogue ends long before EOF, scan the final window for the first music/SFX cue (credits roll).
# Short tails (<60s) use seconds after last dialogue/cue directly.
_SUBS_UNSUBTITLED_TAIL_SEC = 60
_SUBS_PRE_CREDITS_REMAINING_SEC = 20
_SUBS_FINAL_TAIL_SCAN_SEC = 65
_SUB_EXTS = ('.srt', '.ass', '.ssa', '.sub', '.vtt')
_ACTIVE_SUB_PROP = 'redlight.active_subtitle_path'
_SUBMAKER_SKIP_LANGS = frozenset(('sub toolbox',))
# Phrases seen in tiny provider error bodies wrapped as fake .srt downloads.
# Do NOT match bare "429" — that is a normal SRT cue index on long episodes.
_SUBMAKER_ERROR_RE = re.compile(
	r'scs:\s*an error occurred|provider error|api error|rate limit(?:ed| exceeded)?'
	r'|too many requests|try again later|invalid api key|unauthorized|http\s*429|\bstatus\s*429\b',
	re.I)
# Real episode subs are long; rate-limit stubs are a few lines / one cue.
_SUB_ERROR_PAYLOAD_MAX_CHARS = 800
_SUB_ERROR_PAYLOAD_MAX_CUES = 1
_VTT_TIMESTAMP_RE = re.compile(r'(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})')
_RELEASE_SOURCE_PATTERNS = (
	('BLURAY', ('bluray', 'blu.ray', 'blu-ray', 'bdrip', 'bd.rip', 'bdr')),
	('REMUX', ('remux', 'bdremux', 'bluray.remux', 'uhd.remux', 'complete.remux', '2160p.remux')),
	('WEB', ('webdl', 'web.dl', 'web-dl', 'webrip', 'web.rip', '.web.')),
	('HDTV', ('hdtv',)),
	('DVD', ('dvdrip', 'dvd.rip')),
	('HDRIP', ('hdrip', 'hd.rip')),
)
_PRIMARY_RELEASE_SOURCES = ('BLURAY', 'REMUX', 'WEB', 'HDTV', 'DVD', 'HDRIP')
_BLURAY_SOURCE_FAMILY = frozenset(('BLURAY', 'REMUX'))

def _normalize_release_text(text):
	return re.sub(r'[^a-z0-9.]+', '.', (text or '').lower()).strip('.')

def _release_filename_stem(filename):
	if not filename: return ''
	stem = os.path.splitext(os.path.basename(str(filename).split('|')[0].split('?')[0]))[0]
	return _normalize_release_text(stem)

def _detect_release_source_tags(text):
	norm = _normalize_release_text(text)
	tags = set()
	for tag, patterns in _RELEASE_SOURCE_PATTERNS:
		if any(pattern in norm for pattern in patterns):
			tags.add(tag)
	if 'REMUX' in tags:
		tags.add('BLURAY')
	return tags

def _primary_release_source(tags):
	if 'REMUX' in tags: return 'REMUX'
	for tag in _PRIMARY_RELEASE_SOURCES:
		if tag in tags: return tag
	return None

def _release_sources_compatible(play_primary, sub_primary):
	if not play_primary or not sub_primary: return False
	if play_primary == sub_primary: return True
	if play_primary in _BLURAY_SOURCE_FAMILY and sub_primary in _BLURAY_SOURCE_FAMILY: return True
	return False

def _subtitle_cache_release_tag(release_context):
	tags = (release_context or {}).get('tags') or set()
	if 'REMUX' in tags: return 'remux'
	if 'BLURAY' in tags: return 'bluray'
	primary = _primary_release_source(tags)
	return primary.lower() if primary else ''

def _subtitle_base_filename(imdb_id, season, episode):
	if season: return 'RedLightSubs_%s_%s_%s' % (imdb_id, season, episode)
	return 'RedLightSubs_%s' % imdb_id

def _subtitle_search_filename(imdb_id, season, episode, release_context=None):
	filename_lang = st.subs_language_for_download().replace(' ', '_')
	base = _subtitle_base_filename(imdb_id, season, episode)
	tag = _subtitle_cache_release_tag(release_context)
	if tag: return '%s_%s_%s.srt' % (base, filename_lang, tag)
	return '%s_%s.srt' % (base, filename_lang)

def _subtitle_cache_lookup_names(imdb_id, season, episode, release_context):
	tagged = _subtitle_search_filename(imdb_id, season, episode, release_context)
	if _subtitle_cache_release_tag(release_context):
		return [tagged]
	legacy = _subtitle_search_filename(imdb_id, season, episode)
	if legacy != tagged: return [tagged, legacy]
	return [tagged]

def playback_release_context(playing_filename=None, playing_item=None, season=None, episode=None):
	parts = []
	best_filename = _best_play_filename(playing_filename, playing_item, season, episode)
	if playing_item:
		for key in ('name', 'display_name', 'extraInfo', 'quality'):
			val = playing_item.get(key)
			if val: parts.append(str(val))
	if best_filename: parts.append(str(best_filename))
	elif playing_filename: parts.append(str(playing_filename))
	combined = ' '.join(parts)
	stem = _release_filename_stem(best_filename or playing_filename)
	if not stem and playing_item:
		stem = _release_filename_stem(playing_item.get('name') or playing_item.get('display_name'))
	return {'stem': stem, 'tags': _detect_release_source_tags(combined), 'text': _normalize_release_text(combined), 'filename': best_filename or ''}

def _flatten_string_values(obj, max_depth=4):
	parts = []
	if max_depth < 0: return parts
	if isinstance(obj, str):
		if obj.strip(): parts.append(obj.strip())
	elif isinstance(obj, dict):
		for val in obj.values():
			parts.extend(_flatten_string_values(val, max_depth - 1))
	elif isinstance(obj, (list, tuple)):
		for item in obj:
			parts.extend(_flatten_string_values(item, max_depth - 1))
	return parts

def _scs_payload_from_url(url):
	try:
		match = re.search(r'/subtitle/scs_([^/]+)', url or '', re.I)
		if not match: return None
		token = match.group(1)
		pad = '=' * (-len(token) % 4)
		raw = base64.urlsafe_b64decode(token + pad)
		return json.loads(raw.decode('utf-8', 'ignore'))
	except: return None

def _decode_v3_token(token):
	try:
		pad = '=' * (-len(token) % 4)
		return base64.urlsafe_b64decode(token + pad).decode('utf-8', 'ignore')
	except: return ''

def _v3_url_from_sub_ref(sub_ref):
	if not isinstance(sub_ref, dict): return ''
	for val in (sub_ref.get('id'), sub_ref.get('url')):
		if not val: continue
		match = re.search(r'v3_([A-Za-z0-9+/=_-]+)', str(val))
		if match: return _decode_v3_token(match.group(1))
	return ''

def _filename_from_v3_url(v3_url):
	if not v3_url: return ''
	for pattern in (r'[?&]filename=([^&]+)', r'[?&]file_name=([^&]+)'):
		match = re.search(pattern, v3_url, re.I)
		if match:
			name = unquote(match.group(1)).strip()
			if name: return name
	if '://' in v3_url:
		base = os.path.basename(v3_url.split('?')[0].split('#')[0])
		if base and '.' in base and not base.isdigit(): return base
	return ''

def _episode_in_release_text(season, episode, text):
	if not text or season in (None, '') or episode in (None, ''): return False
	norm = _normalize_release_text(text)
	patterns = (
		's%02de%02d' % (int(season), int(episode)),
		's%d[eexx]%d' % (int(season), int(episode)),
		'%dx%d' % (int(season), int(episode)),
	)
	return any(pattern in norm for pattern in patterns)

def _release_filename_candidates(playing_filename=None, playing_item=None):
	candidates = []
	def add(raw):
		if not raw: return
		raw = str(raw).split('|')[0].split('?')[0].strip()
		if not raw: return
		base = os.path.basename(raw) if '://' in raw else raw
		if base and base not in candidates: candidates.append(base)
	add(playing_filename)
	try: add(ku.get_property('subs.player_filename'))
	except: pass
	if playing_item:
		for key in ('url', 'name', 'display_name', 'resolve_display', 'download_url', 'link'):
			add(playing_item.get(key))
	return candidates

def _best_play_filename(playing_filename=None, playing_item=None, season=None, episode=None):
	best, best_score = '', -999
	for candidate in _release_filename_candidates(playing_filename, playing_item):
		score = 0
		lower = candidate.lower()
		if '://' in candidate: score += 4
		if lower.endswith(('.mkv', '.mp4', '.avi', '.m2ts', '.ts', '.wmv')): score += 6
		if season not in (None, '') and episode not in (None, ''):
			if _episode_in_release_text(season, episode, candidate): score += 12
			elif re.search(r's%02d[.\s_-]' % int(season), _normalize_release_text(candidate)) and not _episode_in_release_text(season, episode, candidate):
				score -= 8
		if score > best_score:
			best_score, best = score, candidate
	return best

def _subtitle_display_name(sub_ref):
	if not isinstance(sub_ref, dict): return str(sub_ref or '')
	for key in ('file_name', 'filename', 'name', 'title', 'label', 'release'):
		val = sub_ref.get(key)
		if val and not str(val).startswith('http'): return str(val)
	v3_url = _v3_url_from_sub_ref(sub_ref)
	if v3_url:
		name = _filename_from_v3_url(v3_url)
		if name: return name
		file_match = re.search(r'/file/(\d+)', v3_url)
		if file_match: return 'opensubs_file_%s' % file_match.group(1)
		return v3_url if len(v3_url) <= 120 else v3_url[:117] + '...'
	sub_id = str(sub_ref.get('id') or '')
	if sub_id and not sub_id.startswith('http'): return sub_id
	url = str(sub_ref.get('url') or '')
	if url: return url if len(url) <= 120 else url[:117] + '...'
	return sub_id or '?'

def _subtitle_candidate_text(sub_ref):
	parts = []
	if isinstance(sub_ref, dict):
		for key in ('file_name', 'name', 'filename', 'title', 'label', 'release', 'extra', 'provider', 'id', 'url', 'lang'):
			val = sub_ref.get(key)
			if val: parts.append(str(val))
		payload = _scs_payload_from_url(sub_ref.get('url') or '')
		if payload: parts.extend(_flatten_string_values(payload))
		v3_url = _v3_url_from_sub_ref(sub_ref)
		if v3_url:
			parts.append(v3_url)
			name = _filename_from_v3_url(v3_url)
			if name: parts.append(name)
	elif sub_ref:
		parts.append(str(sub_ref))
	return ' '.join(parts)

def _score_subtitle_release_details(sub_ref, release_context):
	if not release_context: release_context = playback_release_context()
	sub_text = _subtitle_candidate_text(sub_ref)
	details = {'score': 0.0, 'stem_ratio': 0.0, 'token_hits': 0, 'play_primary': '', 'sub_primary': '', 'name': _subtitle_display_name(sub_ref)}
	if not sub_text: return details
	sub_norm = _normalize_release_text(sub_text)
	sub_stem = _release_filename_stem(sub_text)
	score = 0.0
	stem_ratio = 0.0
	token_hits = 0
	if release_context.get('stem') and sub_stem:
		stem_ratio = SequenceMatcher(None, release_context['stem'], sub_stem).ratio()
		score += stem_ratio
	if release_context.get('stem') and sub_norm:
		play_parts = [part for part in release_context['stem'].split('.') if len(part) > 2]
		token_hits = sum(1 for part in play_parts if part in sub_norm)
		if token_hits: score += min(token_hits * 0.04, 0.2)
	sub_tags = _detect_release_source_tags(sub_text)
	play_tags = release_context.get('tags') or set()
	play_primary = _primary_release_source(play_tags) or ''
	sub_primary = _primary_release_source(sub_tags) or ''
	if play_primary and sub_primary:
		if _release_sources_compatible(play_primary, sub_primary): score += 0.55
		elif play_primary in _BLURAY_SOURCE_FAMILY and sub_primary == 'WEB': score -= 0.65
		elif play_primary == 'WEB' and sub_primary in _BLURAY_SOURCE_FAMILY: score -= 0.45
		else: score -= 0.4
	elif play_primary and not sub_primary and play_primary in _BLURAY_SOURCE_FAMILY:
		if any(tag in sub_tags for tag in _BLURAY_SOURCE_FAMILY): score += 0.35
		elif 'WEB' in sub_tags: score -= 0.35
		elif not sub_tags: score -= 0.15
	if 'proper' in release_context.get('text', '') and 'proper' in sub_norm: score += 0.08
	if 'repack' in release_context.get('text', '') and 'repack' in sub_norm: score += 0.08
	details.update({'score': score, 'stem_ratio': stem_ratio, 'token_hits': token_hits, 'play_primary': play_primary, 'sub_primary': sub_primary or 'unknown'})
	return details

def _score_subtitle_release_match(sub_ref, release_context):
	return _score_subtitle_release_details(sub_ref, release_context).get('score', 0.0)

def _submaker_api_url(manifest, params):
	return manifest.replace('manifest', params)

def _playing_basename(playing_filename=None, playing_item=None, season=None, episode=None):
	return _best_play_filename(playing_filename, playing_item, season, episode)

def _submaker_search_params(imdb_id, season, episode, playing_filename=None, playing_item=None):
	if season not in (None, '') and episode not in (None, ''):
		base = 'subtitles/series/%s:%s:%s' % (imdb_id, season, episode)
	else:
		base = 'subtitles/movie/%s' % imdb_id
	basename = _playing_basename(playing_filename, playing_item, season, episode)
	if not basename: return base
	return '%s/filename=%s.json' % (base, quote(basename, safe=''))

def _fetch_submaker_subtitles(imdb_id, season, episode, playing_filename=None, playing_item=None, quiet=False):
	if not st.submaker_manifest_configured(): return None
	params = _submaker_search_params(imdb_id, season, episode, playing_filename, playing_item)
	try: response = _get(_submaker_api_url(st.submaker_manifest(), params), retry=True, quiet=quiet)
	except requests.RequestException as e:
		return str(e) if not quiet else None
	if not response.ok: return response.reason if not quiet else None
	return response.json().get('subtitles', [])

def _submaker_language_matches(candidate_lang, preferred_language):
	if not candidate_lang: return False
	lang = candidate_lang.strip()
	if lang.lower() in _SUBMAKER_SKIP_LANGS: return False
	if lang == preferred_language: return True
	try: pref_iso = xbmc.convertLanguage(preferred_language, xbmc.ISO_639_1)
	except: pref_iso = ''
	if pref_iso and lang.lower() == pref_iso.lower(): return True
	if pref_iso:
		try:
			cand_iso = xbmc.convertLanguage(lang, xbmc.ISO_639_1)
			if cand_iso and cand_iso.lower() == pref_iso.lower(): return True
		except: pass
		if len(lang) == 3:
			try:
				pref_iso2 = xbmc.convertLanguage(preferred_language, xbmc.ISO_639_2)
				if pref_iso2 and lang.lower() == pref_iso2.lower(): return True
			except: pass
	try:
		if xbmc.convertLanguage(lang, xbmc.ENGLISH_NAME).lower() == preferred_language.lower(): return True
	except: pass
	return False

def _submaker_usable_subs(subs):
	results = []
	for item in subs or []:
		if not item.get('url'): continue
		lang = (item.get('lang') or '').strip()
		if lang.lower() in _SUBMAKER_SKIP_LANGS or item.get('id') == 'sub_toolbox': continue
		results.append(item)
	return results

def _submaker_filter_stats(subs):
	raw = list(subs or [])
	usable = _submaker_usable_subs(raw)
	filtered = {}
	for item in raw:
		if item in usable: continue
		label = (item.get('lang') or item.get('id') or '?').strip()
		filtered[label] = filtered.get(label, 0) + 1
	return len(raw), len(usable), filtered

def _submaker_split_subs(subs, language):
	usable = _submaker_usable_subs(subs)
	preferred = [i for i in usable if _submaker_language_matches(i.get('lang'), language)]
	other = [i for i in usable if i not in preferred]
	return usable, preferred, other

def _submaker_ranked_subs(subs, language, release_context=None, preferred_only=False):
	usable, preferred, other = _submaker_split_subs(subs, language)
	ctx = release_context or playback_release_context()
	sort_key = lambda item: _score_subtitle_release_match(item, ctx)
	preferred.sort(key=sort_key, reverse=True)
	other.sort(key=sort_key, reverse=True)
	if preferred_only: return preferred
	return preferred + other

def _subtitle_text(content):
	if not content: return ''
	if not isinstance(content, str):
		try: content = content.decode('utf-8-sig', 'ignore')
		except:
			try: content = content.decode('utf-8', 'ignore')
			except: return ''
	return content.replace('\r\n', '\n').replace('\r', '\n')

def _is_submaker_error_content(content):
	text = _subtitle_text(content).strip()
	if not text: return True
	sample = text.lstrip()[:256].lower()
	if sample.startswith('<!doctype') or sample.startswith('<html'): return True
	if sample.startswith('{'):
		try:
			data = json.loads(text)
			if isinstance(data, dict) and (data.get('error') or data.get('message')): return True
		except: pass
	# Multi-cue / long files are real subs (dialogue can contain "try again later",
	# and cue index 429 must never be treated as HTTP 429).
	if len(text) > _SUB_ERROR_PAYLOAD_MAX_CHARS or _count_subtitle_cues(text) > _SUB_ERROR_PAYLOAD_MAX_CUES:
		return False
	if _SUBMAKER_ERROR_RE.search(text): return True
	return False

def _count_subtitle_cues(content):
	text = _subtitle_text(content)
	if text.lstrip().startswith('WEBVTT'): return len(_VTT_TIMESTAMP_RE.findall(text))
	return len(re.findall(r'\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3}\s*-->', text))

def _vtt_timestamp_to_srt(line):
	return _VTT_TIMESTAMP_RE.sub(lambda m: '%s,%s --> %s,%s' % (m.group(1), m.group(2), m.group(3), m.group(4)), line)

def _vtt_to_srt(content):
	text = _subtitle_text(content)
	if not text.lstrip().startswith('WEBVTT'): return text
	parts = re.split(r'\n(?=\d{2}:\d{2}:\d{2}\.\d{3}\s*-->)', text)
	out, idx = [], 1
	for part in parts:
		part = part.strip()
		if not part or part.startswith('WEBVTT') or part.startswith('NOTE'): continue
		lines = part.split('\n')
		ts_idx = 0
		if '-->' not in lines[0]:
			if len(lines) > 1 and '-->' in lines[1]: ts_idx = 1
			else: continue
		ts_line = _vtt_timestamp_to_srt(lines[ts_idx].strip())
		body = '\n'.join(lines[ts_idx + 1:]).strip()
		if not body: continue
		out.append('%d\n%s\n%s' % (idx, ts_line, body))
		idx += 1
	return ('\n\n'.join(out) + '\n') if out else ''

def _prepare_subtitle_file_content(content, log_reject=False, reject_label='SubMaker'):
	text = _subtitle_text(content)
	if not text or _is_submaker_error_content(text):
		if log_reject and text:
			ku.logger('Red Light', '%s: rejected provider error payload' % reject_label)
		return None
	if text.lstrip().startswith('WEBVTT'):
		text = _vtt_to_srt(text)
	if not text or _count_subtitle_cues(text) < 2:
		if log_reject:
			ku.logger('Red Light', '%s: rejected empty or single-cue download' % reject_label)
		return None
	if not _looks_like_subtitle_content(text): return None
	return text

def _looks_like_subtitle_content(content):
	if not content: return False
	text = _subtitle_text(content)
	if not text or _is_submaker_error_content(text): return False
	sample = text.lstrip()[:256].lower()
	if sample.startswith('<!doctype') or sample.startswith('<html'): return False
	return bool(re.search(r'\d{1,2}:\d{2}:\d{2}', text))

def _download_submaker_content(download_fn, subs, language, release_context=None, search_params='', quiet=False):
	usable, preferred, other = _submaker_split_subs(subs, language)
	if not preferred:
		if not quiet:
			raw_count, _, _ = _submaker_filter_stats(subs)
			if raw_count and not usable:
				ku.logger('Red Light', 'SubMaker: only filtered placeholder results returned (configure SubMaker providers)')
			else:
				ku.logger('Red Light', 'SubMaker: no %s subs in response (%d other languages ignored)' % (language, len(other)))
		return None
	ranked = _submaker_ranked_subs(subs, language, release_context=release_context, preferred_only=True)
	for item in ranked:
		response = download_fn(item.get('url'))
		if isinstance(response, str) or not getattr(response, 'ok', False):
			continue
		try: content = response.text
		except: content = response.content
		prepared = _prepare_subtitle_file_content(content, log_reject=not quiet)
		if prepared:
			if not quiet:
				try:
					label = _subtitle_display_name(item)
					if len(label) > 120: label = label[:117] + '...'
					play_tag = _subtitle_cache_release_tag(release_context) or 'unknown'
					lang = (item.get('lang') or '?') if isinstance(item, dict) else '?'
					ku.logger('Red Light', 'SubMaker pick (%s) [%s]: %s' % (play_tag, lang, label))
				except: pass
			return prepared
	return None

def _get(url, stream=False, retry=False, quiet=False):
	response = requests.get(url, stream=stream, timeout=timeout)
	if retry and response.status_code in (403, 429):
		if not quiet and st.subs_show_notifications():
			ku.notification('SubMaker rate limited. Retrying in 10 secs...', 3500)
		ku.sleep(10000)
		return _get(url, stream=stream, quiet=quiet)
	return response

def _normalize_stream_lang_code(code):
	if not code: return code
	if code == 'gre': return 'ell'
	return code

def _find_subtitle_stream_index(player, preferred_languages):
	try: streams = list(player.getAvailableSubtitleStreams() or [])
	except: return None
	if not streams: return None
	normalized = [_normalize_stream_lang_code(code) for code in streams]
	for pref in preferred_languages:
		for idx, code in enumerate(normalized):
			if _submaker_language_matches(code, pref): return idx
	return None

def _find_forced_subtitle_stream_index():
	props = _player_properties(['currentsubtitle', 'subtitles'])
	if not props: return None
	current = props.get('currentsubtitle') or {}
	if current.get('is_forced') and current.get('index') is not None:
		return int(current['index'])
	for item in props.get('subtitles') or []:
		if item.get('is_forced') and item.get('index') is not None:
			return int(item['index'])
	return None

def subtitle_notify_poster(meta, media_type='movie'):
	if not meta: return ku.get_icon('box_office')
	if media_type == 'episode':
		if st.avoid_episode_spoilers() and int(meta.get('playcount', 0) or 0) == 0:
			return meta.get('fanart') or meta.get('poster') or ku.addon_fanart()
		return meta.get('ep_thumb') or meta.get('fanart') or meta.get('poster') or ku.get_icon('box_office')
	return meta.get('poster') or ku.get_icon('box_office')

def _subtitle_playback_active(player=None):
	try:
		if player is not None:
			if hasattr(player, '_owns_active_playback') and not player._owns_active_playback():
				return False
			return player.isPlayingVideo() or player.isPlaying()
	except:
		pass
	try:
		return ku.get_visibility('Window.IsActive(fullscreenvideo)')
	except:
		return False

def _subtitle_path_already_active(player, path):
	if not path or not player:
		return False
	try:
		if ku.get_property(_ACTIVE_SUB_PROP) != path:
			return False
		active = player.getSubtitles() or ''
		base = os.path.basename(path)
		return path in active or (base and base in active)
	except:
		return False

def _subtitle_user_notify(message, poster=None, settle_ms=150, player=None):
	if not st.subs_show_notifications(): return
	if player is not None and not _subtitle_playback_active(player):
		return
	ku.notification(message, icon=poster, settle_ms=settle_ms)

def _notify_subtitles_ready(poster=None, local=False, cached=False, is_episode=False, player=None):
	if not st.subs_show_notifications(): return
	if player is not None and not _subtitle_playback_active(player):
		return
	for _ in range(40):
		if ku.get_visibility('Window.IsActive(fullscreenvideo)'): break
		ku.sleep(100)
	if player is not None and not _subtitle_playback_active(player):
		return
	settle_ms = 500 if is_episode else 200
	if local:
		message = 'Local subtitles found'
	elif cached:
		message = 'Cached subtitles found'
	else:
		message = 'Downloaded subtitles found'
	ku.notification(message, icon=poster, settle_ms=settle_ms)

def _enable_forced_local_subtitles(player, poster=None, notify=True, is_episode=False):
	stream_index = _find_forced_subtitle_stream_index()
	if stream_index is None: return False
	try: player.setSubtitleStream(stream_index)
	except: return False
	if st.auto_enable_subs(): player.showSubtitles(True)
	if notify: _notify_subtitles_ready(poster=poster, local=True, is_episode=is_episode, player=player)
	return True

def enable_local_subtitles(player, poster=None, notify=True, is_episode=False):
	if st.subs_language_is_forced_local():
		return _enable_forced_local_subtitles(player, poster=poster, notify=notify, is_episode=is_episode)
	preferred_languages = st.subs_language_preferences()
	try: current = player.getSubtitles()
	except: current = ''
	if current:
		for pref in preferred_languages:
			if _submaker_language_matches(current, pref):
				if st.auto_enable_subs(): player.showSubtitles(True)
				if notify: _notify_subtitles_ready(poster=poster, local=True, is_episode=is_episode, player=player)
				return True
	stream_index = _find_subtitle_stream_index(player, preferred_languages)
	if stream_index is not None:
		try: player.setSubtitleStream(stream_index)
		except: pass
		if st.auto_enable_subs(): player.showSubtitles(True)
		if notify: _notify_subtitles_ready(poster=poster, local=True, is_episode=is_episode, player=player)
		return True
	return False

def _alert_sub_filename(imdb_id, season, episode, release_context=None):
	return _subtitle_search_filename(imdb_id, season, episode, release_context)

def _opensubs_base_filename(imdb_id, season, episode):
	if season: return 'RedLightOpenSubs_%s_%s_%s' % (imdb_id, season, episode)
	return 'RedLightOpenSubs_%s' % imdb_id

def _opensubs_alert_filename(imdb_id, season, episode, release_context=None):
	filename_lang = st.subs_language_for_download().replace(' ', '_')
	base = _opensubs_base_filename(imdb_id, season, episode)
	tag = _subtitle_cache_release_tag(release_context)
	if tag: return '%s_%s_%s.srt' % (base, filename_lang, tag)
	return '%s_%s.srt' % (base, filename_lang)

def _opensubs_alert_path(imdb_id, season, episode, release_context=None):
	return '%s%s' % ('special://temp/', _opensubs_alert_filename(imdb_id, season, episode, release_context))

def _looks_like_subtitle_path(value):
	if not value or value.strip() in ('(External)',): return False
	lower = value.lower().strip()
	if any(lower.endswith(ext) for ext in _SUB_EXTS): return True
	if lower.startswith('special://'): return True
	if '://' in lower: return any(ext in lower for ext in _SUB_EXTS)
	if os.path.sep in value or value.startswith('/') or (len(value) > 2 and value[1] == ':'):
		return any(lower.endswith(ext) for ext in _SUB_EXTS)
	return False

def _dedupe_paths(paths):
	seen, results = set(), []
	for path in paths:
		if not path: continue
		try: key = os.path.normcase(os.path.normpath(ku.translate_path(path) if path.startswith('special://') else path))
		except: key = path
		if key in seen: continue
		seen.add(key)
		results.append(path)
	return results

def _player_properties(properties):
	players = ku.get_jsonrpc({'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetActivePlayers', 'params': {}})
	if not players: return None
	player_id = players[0]['playerid']
	return ku.get_jsonrpc({'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetProperties',
		'params': {'playerid': player_id, 'properties': properties}})

def _subs_enabled(player=None):
	try:
		if player is None: player = xbmc.Player()
		if player.getSubtitles(): return True
	except: pass
	try:
		props = _player_properties(['subtitleenabled'])
		return bool(props and props.get('subtitleenabled'))
	except: pass
	return False

def _active_subtitle_paths_from_player():
	props = _player_properties(['subtitleenabled', 'currentsubtitle', 'subtitles'])
	if not props or not props.get('subtitleenabled'): return []
	paths, current = [], props.get('currentsubtitle') or {}
	current_index = current.get('index')
	for item in props.get('subtitles') or []:
		if current_index is not None and item.get('index') != current_index: continue
		for key in ('filename', 'path', 'name'):
			val = (item.get(key) or '').strip()
			if _looks_like_subtitle_path(val): paths.append(val)
	for key in ('filename', 'path', 'name'):
		val = (current.get(key) or '').strip()
		if _looks_like_subtitle_path(val): paths.append(val)
	return _dedupe_paths(paths)

def _addon_temp_subtitle_dirs():
	return (
		'special://temp/',
		'special://profile/addon_data/service.subtitles.a4ksubtitles/temp/',
	)

def _recent_subtitles_in_dir(directory, since_ts=None):
	try:
		native = ku.translate_path(directory.rstrip('/') + '/')
		if not os.path.isdir(native): return []
		found = []
		for name in os.listdir(native):
			lower = name.lower()
			if lower == 'sub.zip' or lower.endswith('.translated'): continue
			if not lower.endswith(_SUB_EXTS): continue
			full = os.path.join(native, name)
			if since_ts and os.path.getmtime(full) < (since_ts - 5): continue
			found.append((os.path.getmtime(full), full))
		found.sort(reverse=True)
		return [path for _, path in found]
	except: return []

def _sidecar_subtitle_paths(playing_filename=None, playing_url=None):
	paths = []
	for raw in (playing_url, playing_filename):
		if not raw: continue
		base_url = raw.split('|')[0].split('?')[0]
		if base_url.startswith(('http://', 'https://', 'plugin://')): continue
		translated = ku.translate_path(base_url) if base_url.startswith('special://') else base_url
		if not os.path.isfile(translated): continue
		folder, stem = os.path.dirname(translated), os.path.splitext(os.path.basename(translated))[0]
		try:
			for name in os.listdir(folder):
				lower = name.lower()
				if not lower.endswith(_SUB_EXTS): continue
				if lower.startswith(stem.lower()) or stem.lower() in lower:
					paths.append(os.path.join(folder, name))
		except: pass
	return _dedupe_paths(paths)

def _opensubs_cache_lookup_names(imdb_id, season, episode, release_context):
	tagged = _opensubs_alert_filename(imdb_id, season, episode, release_context)
	if _subtitle_cache_release_tag(release_context):
		return [tagged]
	legacy = _opensubs_alert_filename(imdb_id, season, episode)
	if legacy != tagged: return [tagged, legacy]
	return [tagged]

def _subtitle_cache_file_usable(path):
	try:
		with ku.open_file(path) as file:
			content = file.read()
		return bool(_prepare_subtitle_file_content(content))
	except:
		return False

def _subtitle_is_prior_playback_cache(path, player=None):
	"""True when the subtitle file predates the current play attempt (true disk reuse)."""
	if not path:
		return False
	try:
		native = ku.translate_path(path) if str(path).startswith('special://') else path
		if not os.path.isfile(native):
			return False
		started = getattr(player, '_playback_started_at', None) if player is not None else None
		if started is None:
			return True
		return os.path.getmtime(native) < (started - 5)
	except:
		return True

def _existing_submaker_subtitle_cache(imdb_id, season, episode, playing_filename=None, playing_item=None, require_configured=True):
	if require_configured and not st.submaker_manifest_configured(): return None
	release_context = playback_release_context(playing_filename, playing_item, season, episode) if (playing_filename or playing_item) else None
	for name in _subtitle_cache_lookup_names(imdb_id, season, episode, release_context):
		path = '%s%s' % ('special://temp/', name)
		if _subtitle_cache_file_usable(path):
			return path
	return None

def _existing_opensubs_subtitle_cache(imdb_id, season, episode, playing_filename=None, playing_item=None, require_configured=True):
	if require_configured and not st.opensubs_configured(): return None
	release_context = playback_release_context(playing_filename, playing_item, season, episode) if (playing_filename or playing_item) else None
	for name in _opensubs_cache_lookup_names(imdb_id, season, episode, release_context):
		path = '%s%s' % ('special://temp/', name)
		if _subtitle_cache_file_usable(path):
			return path
	return None

def _any_existing_subtitle_cache(imdb_id, season, episode, playing_filename=None, playing_item=None):
	return (
		_existing_submaker_subtitle_cache(imdb_id, season, episode, playing_filename, playing_item, require_configured=False)
		or _existing_opensubs_subtitle_cache(imdb_id, season, episode, playing_filename, playing_item, require_configured=False)
	)

def _provider_subtitle_cache(provider, imdb_id, season, episode, playing_filename=None, playing_item=None):
	if provider == 'opensubs':
		return _existing_opensubs_subtitle_cache(imdb_id, season, episode, playing_filename, playing_item)
	return _existing_submaker_subtitle_cache(imdb_id, season, episode, playing_filename, playing_item)

def _fetch_submaker_live_subtitle(imdb_id, season, episode, playing_filename=None, playing_item=None, quiet=False):
	if not st.submaker_manifest_configured(): return None
	release_context = playback_release_context(playing_filename, playing_item, season, episode)
	search_filename = _subtitle_search_filename(imdb_id, season, episode, release_context)
	final_path = '%s%s' % ('special://temp/', search_filename)
	search_params = _submaker_search_params(imdb_id, season, episode, playing_filename, playing_item)
	subs = _fetch_submaker_subtitles(imdb_id, season, episode, playing_filename, playing_item, quiet=quiet)
	if not isinstance(subs, list) or not subs: return None
	content = _download_submaker_content(
		lambda url: _get(url, stream=True, retry=True, quiet=quiet), subs, st.subs_language_for_download(),
		release_context=release_context, search_params=search_params, quiet=quiet)
	if not content: return None
	try:
		with ku.open_file(final_path, 'w') as file: file.write(content)
		ku.set_property(_ACTIVE_SUB_PROP, final_path)
	except: return None
	return final_path

def _provider_subtitle_live(provider, imdb_id, season, episode, year=None, playing_filename=None, playing_item=None, log_pick=False, quiet=False):
	if provider == 'opensubs':
		if not st.opensubs_configured(): return None
		try:
			from apis.opensubs_api import fetch_alert_subtitle
			return fetch_alert_subtitle(imdb_id, season, episode, year, playing_filename, playing_item, log_pick=log_pick, skip_cache=True)
		except: return None
	return _fetch_submaker_live_subtitle(imdb_id, season, episode, playing_filename, playing_item, quiet=quiet)

def resolve_external_subtitle(primary, imdb_id, season=None, episode=None, year=None, playing_filename=None, playing_item=None, log_pick=False, quiet=False):
	# Selected source first (own cache, then download). The other provider's cache must not
	# replace that download. If the selected source has nothing: other provider live, then any cache.
	primary = 'opensubs' if primary == 'opensubs' else 'submaker'
	other = 'opensubs' if primary == 'submaker' else 'submaker'
	path = _provider_subtitle_cache(primary, imdb_id, season, episode, playing_filename, playing_item)
	if path:
		remember_active_subtitle_path(path)
		return path, True
	path = _provider_subtitle_live(primary, imdb_id, season, episode, year, playing_filename, playing_item, log_pick=log_pick, quiet=quiet)
	if path: return path, False
	other_ready = st.opensubs_configured() if other == 'opensubs' else st.submaker_manifest_configured()
	if other_ready:
		if not quiet:
			try: ku.logger('Red Light', 'Subtitles: %s miss, trying %s' % ('OpenSubtitles' if primary == 'opensubs' else 'SubMaker', 'OpenSubtitles' if other == 'opensubs' else 'SubMaker'))
			except: pass
		path = _provider_subtitle_live(other, imdb_id, season, episode, year, playing_filename, playing_item, log_pick=log_pick, quiet=quiet)
		if path: return path, False
	path = _any_existing_subtitle_cache(imdb_id, season, episode, playing_filename, playing_item)
	if path:
		remember_active_subtitle_path(path)
		return path, True
	return None, False

def _alert_temp_paths(imdb_id, season, episode, playing_filename=None, playing_item=None):
	if not imdb_id: return []
	paths = []
	base = _subtitle_base_filename(imdb_id, season, episode)
	release_context = playback_release_context(playing_filename, playing_item, season, episode) if (playing_filename or playing_item) else None
	if st.submaker_manifest_configured():
		seen_names = set()
		for name in _subtitle_cache_lookup_names(imdb_id, season, episode, release_context):
			seen_names.add(name)
			paths.append('%s%s' % ('special://temp/', name))
		try:
			temp = ku.translate_path('special://temp/')
			if os.path.isdir(temp):
				for name in os.listdir(temp):
					if name.startswith(base) and name.endswith('.srt') and name not in seen_names:
						paths.append('%s%s' % ('special://temp/', name))
		except: pass
	if st.opensubs_configured():
		for name in _opensubs_cache_lookup_names(imdb_id, season, episode, release_context):
			paths.append('%s%s' % ('special://temp/', name))
	return paths

def _collect_subtitle_candidates(player, playing_filename, imdb_id, season, episode, playback_started_at=None, playing_item=None):
	paths, seen = [], set()
	def add(path, require_episode_match=False):
		if not path: return
		if require_episode_match and not _subtitle_path_matches_episode(path, imdb_id, season, episode):
			return
		try: key = os.path.normcase(os.path.normpath(ku.translate_path(path) if path.startswith('special://') else path))
		except: key = path
		if key in seen: return
		seen.add(key)
		paths.append(path)
	for path in _alert_temp_paths(imdb_id, season, episode, playing_filename, playing_item): add(path)
	for path in _active_subtitle_paths_from_player(): add(path, require_episode_match=True)
	active_prop = ku.get_property(_ACTIVE_SUB_PROP)
	if active_prop: add(active_prop, require_episode_match=True)
	if playback_started_at:
		for directory in _addon_temp_subtitle_dirs():
			for path in _recent_subtitles_in_dir(directory, playback_started_at):
				add(path, require_episode_match=True)
	try: playing_url = player.getPlayingFile() if player else None
	except: playing_url = None
	for path in _sidecar_subtitle_paths(playing_filename, playing_url): add(path)
	return paths

def _time_part_to_seconds(part):
	part = part.replace(',', '.')
	chunks = part.split(':')
	if len(chunks) == 3:
		h, m, s = chunks
		return int(h) * 3600 + int(m) * 60 + float(s)
	if len(chunks) == 2:
		m, s = chunks
		return int(m) * 60 + float(s)
	return float(part)

def _subtitle_last_end_seconds(content):
	times = re.findall(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', content)
	if not times:
		times = [(h, m, s, '000') for h, m, s in re.findall(r'(\d{2}):(\d{2}):(\d{2})', content)]
	end_seconds = 0.0
	for h, m, s, ms in times:
		end_seconds = max(end_seconds, int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0)
	if end_seconds > 0: return end_seconds
	ass_times = re.findall(r'Dialogue:\s*\d+,(\d+:\d+:\d+[\.,]\d+),(\d+:\d+:\d+[\.,]\d+)', content, re.I)
	for _, end in ass_times:
		end_seconds = max(end_seconds, _time_part_to_seconds(end))
	return end_seconds if end_seconds > 0 else None

_SUBS_CREDITS_JUNK_RE = re.compile(
	r'addic7ed|opensubtitles|subscene|sub\s*toolbox|sync\s*&|corrections?\s*by|translated\s*by|subtitle\s*team|www\.|http',
	re.I)
_SUBS_CREDITS_ROLL_RE = re.compile(
	r'^(cast|crew|credits|starring|directed by|written by|created by|developed by|executive producers?|producers?|music by)\b',
	re.I)

def _subtitle_path_matches_episode(path, imdb_id, season, episode):
	if not path or season is None or episode is None:
		return True
	try:
		name = os.path.basename(ku.translate_path(path) if str(path).startswith('special://') else path).lower()
	except:
		name = os.path.basename(str(path)).lower()
	if 'redlightsubs_' not in name and 'redlightopensubs_' not in name:
		return True
	imdb = str(imdb_id or '').lower()
	if imdb and imdb not in name:
		return False
	s, e = int(season), int(episode)
	return ('_%s_%s_' % (s, e)) in name or ('_%s_%s.' % (s, e)) in name

def _subtitle_cue_text_is_junk(text):
	text = re.sub(r'<[^>]+>', '', text or '').strip()
	if not text: return True
	if _SUBS_CREDITS_JUNK_RE.search(text): return True
	if re.search(r'[♪♫]', text): return True
	if re.search(r'\b(music|instrumental|orchestral)\b', text, re.I): return True
	if len(text) < 80 and _SUBS_CREDITS_ROLL_RE.search(text): return True
	if re.fullmatch(r'[\s♪♫\(\)\[\]\-\*\.!]+', text): return True
	if re.fullmatch(r'\([^)]+\)', text): return True
	if re.fullmatch(r'\[[^\]]+\]', text): return True
	return False

def _subtitle_cue_end_from_time_line(line):
	match = re.search(r'-->\s*(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})', line)
	if not match: return None
	h, m, s, ms = match.groups()
	return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def _subtitle_cue_start_from_time_line(line):
	match = re.search(r'(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})\s*-->', line)
	if not match: return None
	h, m, s, ms = match.groups()
	return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def _subtitle_first_junk_start_after(content, min_start_seconds):
	first_start = None
	for block in re.split(r'\n\s*\n', content.strip()):
		lines = [line.strip() for line in block.splitlines() if line.strip()]
		if len(lines) < 2: continue
		start_seconds = None
		text_lines = []
		for line in lines:
			if '-->' in line:
				start_seconds = _subtitle_cue_start_from_time_line(line)
			elif not line.isdigit():
				text_lines.append(line)
		if start_seconds is None or start_seconds < min_start_seconds: continue
		if not _subtitle_cue_text_is_junk(' '.join(text_lines)): continue
		if first_start is None or start_seconds < first_start:
			first_start = start_seconds
	return first_start

def _subtitle_credits_entry_remaining_seconds(total_time, content):
	dialogue_end = _subtitle_last_dialogue_end_seconds(content)
	if dialogue_end is None:
		end_seconds = _subtitle_last_end_seconds(content)
		if end_seconds is None: return None
		return _bounded_alert_remaining(float(total_time) - float(end_seconds))
	gap = float(total_time) - float(dialogue_end)
	return _bounded_alert_remaining(gap)

def _subtitle_alert_remaining_seconds(total_time, content):
	dialogue_end = _subtitle_last_dialogue_end_seconds(content)
	if dialogue_end is None:
		end_seconds = _subtitle_last_end_seconds(content)
		if end_seconds is None: return None
		return _alert_remaining_from_last_cue(total_time, end_seconds)
	gap = float(total_time) - float(dialogue_end)
	if gap < _SUBS_UNSUBTITLED_TAIL_SEC:
		return _bounded_alert_remaining(gap)
	junk_start = _subtitle_first_junk_start_after(content, float(dialogue_end))
	if junk_start is not None:
		remaining = float(total_time) - junk_start
		if remaining < 0 or remaining > _ALERT_SUB_MAX_REMAINING: return None
		return int(remaining)
	return _bounded_alert_remaining(gap)

def _bounded_alert_remaining(remaining):
	try: remaining = float(remaining)
	except: return None
	if remaining < 0 or remaining > _ALERT_SUB_MAX_REMAINING: return None
	return int(remaining)

def _subtitle_last_dialogue_end_seconds(content):
	blocks = re.split(r'\n\s*\n', content.strip())
	for block in reversed(blocks):
		lines = [line.strip() for line in block.splitlines() if line.strip()]
		if len(lines) < 2: continue
		end_seconds = None
		text_lines = []
		for line in lines:
			if '-->' in line:
				end_seconds = _subtitle_cue_end_from_time_line(line)
			elif not line.isdigit():
				text_lines.append(line)
		if end_seconds is None: continue
		if not _subtitle_cue_text_is_junk(' '.join(text_lines)): return end_seconds
	return None

def _subs_alert_remaining_before_eof(remaining):
	try: remaining = float(remaining)
	except: return None
	if remaining < 0 or remaining > _ALERT_SUB_MAX_REMAINING: return None
	if remaining >= _SUBS_UNSUBTITLED_TAIL_SEC:
		remaining = _SUBS_PRE_CREDITS_REMAINING_SEC
	return int(remaining)

def _raw_remaining_from_last_cue(total_time, last_cue_end):
	remaining = float(total_time) - float(last_cue_end)
	if remaining < 0 or remaining > _ALERT_SUB_MAX_REMAINING: return None
	return int(remaining)

def _alert_remaining_from_last_cue(total_time, last_cue_end):
	return _subs_alert_remaining_before_eof(float(total_time) - float(last_cue_end))

def _seconds_remaining_before_end(sub_path, total_time, for_alert=False, credits_entry=False):
	try:
		with ku.open_file(sub_path) as file: content = file.read()
		if not _looks_like_subtitle_content(content): return None
		if credits_entry:
			remaining = _subtitle_credits_entry_remaining_seconds(total_time, content)
			if remaining is not None: return remaining
			return None
		if for_alert:
			remaining = _subtitle_alert_remaining_seconds(total_time, content)
			if remaining is not None: return remaining
		end_seconds = _subtitle_last_end_seconds(content)
		if end_seconds is None: return None
		if for_alert: return _alert_remaining_from_last_cue(total_time, end_seconds)
		return _raw_remaining_from_last_cue(total_time, end_seconds)
	except: return None

def fetch_subtitle_for_alert_timing(imdb_id, season=None, episode=None, year=None, playing_filename=None, playing_item=None):
	if not st.subs_alert_fetch_configured(): return None
	primary = 'opensubs' if st.opensubs_enabled() else 'submaker'
	path, _cached = resolve_external_subtitle(
		primary, imdb_id, season, episode, year, playing_filename, playing_item, log_pick=False, quiet=True)
	return path

def _fetch_submaker_alert_subtitle(imdb_id, season, episode, year=None, playing_filename=None, playing_item=None):
	path, _cached = resolve_external_subtitle(
		'submaker', imdb_id, season, episode, year, playing_filename, playing_item, log_pick=False, quiet=True)
	return path

def _fetch_alert_subtitle(imdb_id, season, episode):
	return _fetch_submaker_alert_subtitle(imdb_id, season, episode)

def subtitle_seconds_remaining_before_end(total_time, imdb_id, season=None, episode=None, fetch=False, player=None,
		playing_filename=None, playing_item=None, playback_started_at=None, year=None, for_alert=False, credits_entry=False, quiet=False):
	if not total_time: return None
	log_label = 'Subtitle credits entry' if credits_entry else 'Subtitle alert timing'
	for sub_path in _collect_subtitle_candidates(player, playing_filename, imdb_id, season, episode, playback_started_at, playing_item):
		remaining = _seconds_remaining_before_end(sub_path, total_time, for_alert=for_alert, credits_entry=credits_entry)
		if remaining is not None:
			if not quiet:
				try: label = os.path.basename(ku.translate_path(sub_path) if sub_path.startswith('special://') else sub_path)
				except: label = sub_path or 'unknown'
				ku.logger('Red Light', '%s (local): %s remaining=%ss' % (log_label, label, remaining))
			return remaining
	if not fetch or not imdb_id or not st.subs_alert_fetch_configured(): return None
	fetched = fetch_subtitle_for_alert_timing(imdb_id, season, episode, year, playing_filename, playing_item)
	if not fetched: return None
	remaining = _seconds_remaining_before_end(fetched, total_time, for_alert=for_alert, credits_entry=credits_entry)
	if remaining is not None and not quiet:
		try: label = os.path.basename(ku.translate_path(fetched) if fetched.startswith('special://') else fetched)
		except: label = fetched or 'unknown'
		ku.logger('Red Light', '%s (fetched): %s remaining=%ss' % (log_label, label, remaining))
	return remaining

def remember_active_subtitle_path(path):
	if path: ku.set_property(_ACTIVE_SUB_PROP, path)

def clear_active_subtitle_path():
	ku.clear_property(_ACTIVE_SUB_PROP)

def clear_subtitles_cache():
	temp_path = ku.translate_path('special://temp/')
	removed = 0
	if os.path.isdir(temp_path):
		for name in os.listdir(temp_path):
			if name.startswith('RedLightSubs_') or name.startswith('RedLightOpenSubs_'):
				try:
					os.remove(os.path.join(temp_path, name))
					removed += 1
				except: pass
	clear_active_subtitle_path()
	return removed

def _apply_external_subtitle(player, path, poster=None, notify=True, cached=False, is_episode=False):
	if not path: return False
	if not _subtitle_playback_active(player):
		return False
	already_active = _subtitle_path_already_active(player, path)
	try: player.setSubtitles(path)
	except: return False
	if st.auto_enable_subs():
		try: player.showSubtitles(True)
		except: pass
	if notify and not already_active:
		notify_cached = cached and _subtitle_is_prior_playback_cache(path, player)
		_notify_subtitles_ready(poster=poster, cached=notify_cached, is_episode=is_episode, player=player)
	return True

class Subtitles(xbmc.Player):
	def _video_file_subs(self):
		return enable_local_subtitles(self._player, poster=self.poster, is_episode=self.is_episode)

	def run(self, imdb_id, season, episode, poster, playing_filename=None, playing_item=None, active_player=None, year=None):
		self.manifest = st.submaker_manifest()
		if not self.manifest or 'manifest' not in self.manifest: return
		self.poster = poster
		self.playing_filename, self.playing_item = playing_filename, playing_item
		self.is_episode = season is not None and episode is not None
		self._player = active_player or self
		ku.sleep(2500)
		if st.submaker_prefer_local():
			if self._video_file_subs(): return
		path, cached = resolve_external_subtitle(
			'submaker', imdb_id, season, episode, year, playing_filename, playing_item, log_pick=True)
		if not path:
			return _subtitle_user_notify('No subtitles found', poster=poster, player=self._player)
		remember_active_subtitle_path(path)
		return _apply_external_subtitle(self._player, path, poster=self.poster, is_episode=self.is_episode, cached=cached)

class OpenSubtitlesSubs(xbmc.Player):
	def _video_file_subs(self):
		return enable_local_subtitles(self._player, poster=self.poster, is_episode=self.is_episode)

	def run(self, imdb_id, season, episode, poster, year=None, playing_filename=None, playing_item=None, active_player=None):
		self.poster = poster
		self.playing_filename, self.playing_item = playing_filename, playing_item
		self.is_episode = season is not None and episode is not None
		self._player = active_player or self
		ku.sleep(2500)
		if st.submaker_prefer_local():
			if self._video_file_subs(): return
		if not st.opensubs_configured():
			return _subtitle_user_notify('OpenSubtitles username and password required', poster=poster, settle_ms=500 if self.is_episode else 200, player=self._player)
		path, cached = resolve_external_subtitle(
			'opensubs', imdb_id, season, episode, year, playing_filename, playing_item, log_pick=True)
		if not path:
			return _subtitle_user_notify('No subtitles found', poster=poster, settle_ms=500 if self.is_episode else 200, player=self._player)
		remember_active_subtitle_path(path)
		return _apply_external_subtitle(self._player, path, poster=poster, is_episode=self.is_episode, cached=cached)
