# -*- coding: utf-8 -*-
import os
import re

# Bundled Scene / P2P groups (TRaSH-style tiers as a static reference — not a live importer).
# Higher score sorts first within the current Results Sorting keys. Quality is never jumped.
_TIER_1 = frozenset((
	'3ctweb', 'aida', 'bhdstudio', 'btw', 'byndr', 'crisc', 'ctrlhd', 'deflate', 'ebp', 'epsilon',
	'flux', 'framestor', 'hifi', 'hone', 'kralimarko', 'kitsune', 'ncmt', 'ntb', 'playnerd', 'pmp',
	'qoq', 'sa89', 'slignome', 'successfulcrab', 'surfinbird', 'tayto', 'tepes', 'tommy', 'visum',
	'xebec',
))
_TIER_2 = frozenset((
	'amb3r', 'bluhd', 'cfl', 'chd', 'crfw', 'd-z0n3', 'd3g', 'decibel', 'don', 'fum', 'geckos',
	'hallowed', 'hdchina', 'hdman', 'hds', 'hidt', 'ijp', 'ika', 'ntg', 'pauliso', 'peculate',
	'pter', 'sigma', 'sicfoi', 'w4nk3r', 'welp',
))
_TIER_3 = frozenset((
	'evo', 'joy', 'kogi', 'monkee', 'phoenix', 'qman', 'strife',
))
_SCORES = {}
for _name in _TIER_1: _SCORES[_name] = 3
for _name in _TIER_2: _SCORES[_name] = 2
for _name in _TIER_3: _SCORES[_name] = 1

# Source / codec tokens that can appear as the last hyphen segment — never treat as a group.
_NOT_GROUP = frozenset((
	'aac', 'amzn', 'atvp', 'av1', 'avc', 'bluray', 'complete', 'criterion', 'dd5', 'ddp5', 'dsnp',
	'dts', 'dv', 'h264', 'h265', 'hdr', 'hdr10', 'hevc', 'hmax', 'hybrid', 'imax', 'internal',
	'multi', 'nf', 'pcok', 'proper', 'repack', 'remux', 'sdr', 'season', 'truehd', 'uhd', 'web',
	'webdl', 'webrip', 'x264', 'x265',
))

_NAME_RE = re.compile(r'[\s_]+')


def _filename_blob(name):
	if not name: return ''
	raw = str(name).split('|')[0].split('?')[0].strip()
	if not raw: return ''
	stem = os.path.splitext(os.path.basename(raw))[0]
	return _NAME_RE.sub('.', stem).strip('.').lower()


def _group_from_blob(blob):
	if not blob: return ''
	bracket = re.search(r'[\[(]([a-z0-9][a-z0-9@.\-]{1,19})[\])]\s*$', blob)
	if bracket:
		token = bracket.group(1).replace('@', '').strip('.')
		if _score_token(token): return token
		blob = blob[:bracket.start()].rstrip('.')
	hyphen = re.search(r'-([a-z0-9][a-z0-9@.]{1,19})$', blob)
	if hyphen:
		return hyphen.group(1).replace('@', '').strip('.')
	return ''


def _score_token(token):
	if not token: return 0
	key = token.lower().replace('@', '')
	if key in _NOT_GROUP: return 0
	direct = _SCORES.get(key)
	if direct: return direct
	# D-Z0N3 stored with hyphen; blob may keep it as d-z0n3 or d.z0n3
	return _SCORES.get(key.replace('.', '-'), 0)


def release_group_boost(item):
	'''Integer 0–3. Safe no-op when the name has no known group.'''
	if not isinstance(item, dict): return 0
	aio = item.get('aio_release_group') or ''
	score = _score_token(str(aio).strip())
	if score: return score
	for key in ('display_name', 'name', 'url'):
		blob = _filename_blob(item.get(key))
		score = _score_token(_group_from_blob(blob))
		if score: return score
		# Known group as a delimited suffix when hyphen parse missed (e.g. D-Z0N3).
		if blob:
			for group, value in _SCORES.items():
				if len(group) < 3: continue
				if blob.endswith('-' + group) or blob.endswith('.' + group):
					return value
	return 0
