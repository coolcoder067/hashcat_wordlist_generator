#!/usr/bin/env python3

import argparse
import sys
import mwparserfromhell
import requests
from requests.adapters import HTTPAdapter, Retry
from time import time
from pathlib import Path
from urllib.parse import urlparse

class WordlistGenerationError(Exception):
	pass

#############################
# Separation:
# Spaces
# Dashes
# Underscore
# None
#
# Capitalization:
# camelCase
# UPPERCASE
# lowercase
# TitleCase
# oRiGiNaL
#
# Specialchars:
# original
# lettersonly
# alphanumeric
# all but punctuation
#
# Frequency:
# consecutive words
# consecutive words (important)
#############################

# Classes for processing argements
class MwSourceAction(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		values = values.rstrip('/') # type: ignore
		if not values.endswith('/api.php'): # type: ignore
			parser.error('MediaWiki source URL should end with /api.php')
		if not hasattr(namespace, 'mw_sources'):
			namespace.mw_sources = []
		namespace.mw_sources.append({
			'url': values,
			'pages': [],
			'categories': []
		})

class MwCategoryAction(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		if not hasattr(namespace, 'mw_sources'):
			parser.error(f'MediaWiki source must be specified before {option_string}')
		namespace.mw_sources[-1]['categories'].append(values) # type: ignore

class MwPageAction(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		if not hasattr(namespace, 'mw_sources'):
			parser.error(f'MediaWiki source must be specified before {option_string}')
		namespace.mw_sources[-1]['pages'].append(values) # type: ignore


# Process arguments
parser = argparse.ArgumentParser(description='Create a wordlist from a MediaWiki site. ')
parser.add_argument('--outfile', '-o', default='wordlist.txt', help='File to store generated wordlist. Default wordlist.txt')
parser.add_argument('--infile', '-i', action='append', help='Text file input')
parser.add_argument('--mw-source', action=MwSourceAction, help='The URL of the MediaWiki api endpoint. You can use this flag multiple times.')
parser.add_argument('--mw-category', action=MwCategoryAction, help='Category name for the preceding --mw-source. You can use this flag multiple times.')
parser.add_argument('--mw-page', action=MwPageAction, help='Page name for the preceding --mw-source. You can use this flag multiple times.')
parser.add_argument('--mw-url', action='append', help='A standalone MediaWiki url to scrape. You can use this flag multiple times.')
parser.add_argument('--variation-join-space', choices=['on', 'off'], default='on', help='Default ON. Join words with spaces.')
parser.add_argument('--variation-join-dash', choices=['on', 'off'], default='off', help='Default OFF. Join words with dashes.')
parser.add_argument('--variation-join-underscore', choices=['on', 'off'], default='off', help='Default OFF. Join words with underscores.')
parser.add_argument('--variation-join-none', choices=['on', 'off'], default='off', help='Default OFF. Join words without seperator.')
parser.add_argument('--variation-cap-original', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with oRiGiNalCaPiTiLiZaTiOn.')
parser.add_argument('--variation-cap-camelcase', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with camelCase.')
parser.add_argument('--variation-cap-uppercase', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with UPPERCASE.')
parser.add_argument('--variation-cap-lowercase', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with lowercase.')
parser.add_argument('--variation-cap-titlecase', choices=['on', 'off'], default='on', help='Default ON. Capitalize words with TitleCase.')
parser.add_argument('--variation-chars-original', choices=['on', 'off'], default='off', help='Default OFF. Allow all ASCII characters.')
parser.add_argument('--variation-chars-lettersonly', choices=['on', 'off'], default='off', help='Default OFF. Allow only letters A-Z.')
parser.add_argument('--variation-chars-alnum', choices=['on', 'off'], default='on', help='Default ON. Allow letters A-Z, numbers 0-9.')
parser.add_argument('--variation-chars-nopunctuation', choices=['on', 'off'], default='off', help='Default OFF. Allow all ASCII characters but ,.?!:;')
parser.add_argument('--consecutive-words', type=int, default=2, help='Default 2. The maximum number of consecutive words to form combinations with.')
parser.add_argument('--consecutive-words-important', type=int, default=5, help='Default 5. The maximum number of consecutive words to form combinations with, when text is deemed to be especially "important" (e.g. link text).')
parser.add_argument('--debug-schema', action='store_true', help='Output an additional file with an outline of the schema.')
args = parser.parse_args()
args.variation_join_dash = args.variation_join_dash == 'on'
args.variation_join_space = args.variation_join_space == 'on'
args.variation_join_underscore = args.variation_join_underscore == 'on'
args.variation_join_none = args.variation_join_none == 'on'
args.variation_cap_original = args.variation_cap_original == 'on'
args.variation_cap_camelcase = args.variation_cap_camelcase == 'on'
args.variation_cap_uppercase = args.variation_cap_uppercase == 'on'
args.variation_cap_lowercase = args.variation_cap_lowercase == 'on'
args.variation_cap_titlecase = args.variation_cap_titlecase == 'on'
args.variation_chars_original = args.variation_chars_original == 'on'
args.variation_chars_lettersonly = args.variation_chars_lettersonly == 'on'
args.variation_chars_alnum = args.variation_chars_alnum == 'on'
args.variation_chars_nopunctuation = args.variation_chars_nopunctuation == 'on'
if args.consecutive_words_important < args.consecutive_words:
	args.consecutive_words_important = args.consecutive_words

def wikicode_iterate(wikicode: mwparserfromhell.wikicode.Wikicode):
	if wikicode is not None:
		for node in wikicode.nodes:
			if isinstance(node, mwparserfromhell.nodes.Tag):
				wikicode_iterate(node.contents)
			elif isinstance(node, mwparserfromhell.nodes.Text):
				wl.continue_text_input(node.value)
			elif isinstance(node, mwparserfromhell.nodes.Wikilink):
				if node.title.startswith('Image:') or node.title.startswith('File:'):
					continue
				if node.text is None:
					wikicode_iterate(node.title)
				else:
					wikicode_iterate(node.text)
			elif isinstance(node, mwparserfromhell.nodes.ExternalLink):
				wikicode_iterate(node.title) # type: ignore
			elif isinstance(node, mwparserfromhell.nodes.Heading):
				wikicode_iterate(node.title)
			
			
class WordlistGenerator:

	def __init__(self, args):
		self.special_chars_functions = []
		if args.variation_chars_original:
			self.special_chars_functions.append(lambda text: ''.join(filter(lambda c: 32 <= ord(c) <= 126, text))) # Don't include newline, tab
		if args.variation_chars_lettersonly:
			self.special_chars_functions.append(lambda text: ''.join(filter(lambda c: ord(c) == 32 or 65 <= ord(c) <= 90 or 97 <= ord(c) <= 122, text))) # space, A-Z, a-z
		if args.variation_chars_alnum:
			self.special_chars_functions.append(lambda text: ''.join(filter(lambda c: ord(c) == 32 or 48 <= ord(c) <= 57 or 65 <= ord(c) <= 90 or 97 <= ord(c) <= 122, text))) # space, 0-9, A-Z, a-z
		if args.variation_chars_nopunctuation:
			self.special_chars_functions.append(lambda text: ''.join(filter(lambda c: 32 <= ord(c) <= 126 and c not in '!,.?;:', text))) # Don't include newline, tab, ,.?!;:
		
		self.capitalization_functions = []
		if args.variation_cap_original:
			self.capitalization_functions.append(lambda words: words)
		if args.variation_cap_camelcase:
			self.capitalization_functions.append(lambda words: (words[0].lower(), *[word[0].upper() + word[1:].lower() for word in words[1:]]))
		if args.variation_cap_uppercase:
			self.capitalization_functions.append(lambda words: (word.upper() for word in words))
		if args.variation_cap_lowercase:
			self.capitalization_functions.append(lambda words: (word.lower() for word in words))
		if args.variation_cap_titlecase:
			self.capitalization_functions.append(lambda words: (word[0].upper() + word[1:].lower() for word in words))
		
		self.join_functions = []
		if args.variation_join_space:
			self.join_functions.append(lambda words: ' '.join(words))
		if args.variation_join_none:
			self.join_functions.append(lambda words: ''.join(words))
		if args.variation_join_dash:
			self.join_functions.append(lambda words: '-'.join(words))
		if args.variation_join_underscore:
			self.join_functions.append(lambda words: '_'.join(words))
		
		self.list = set()
		self.buffers = [[] for x in self.special_chars_functions] # There is one buffer for each filtering variation (original, lettersonly, lettersnumbers)
		

	def process_variations(self, words):
		for c_func in self.capitalization_functions:
			c_words = c_func(words)
			for j_func in self.join_functions:
				self.list.add(j_func(c_words))

	def continue_text_input(self, text):
		# Special chars filtering: update buffer for each filtering variation
		for i in range(len(self.special_chars_functions)):
			words = self.special_chars_functions[i](text).split(' ')
			words = [word for word in words if word] # Filter out empty words caused by multiple spaces
			for word in words:
				self.buffers[i].append(word)
				self.buffers[i] = self.buffers[i][-args.consecutive_words:] # Trim buffer to args.consecutive_words length
				for buffer_index in range(len(self.buffers[i])):
					self.process_variations(self.buffers[i][buffer_index:]) # From buffer_index to the end of the buffer
			# Process "important" short sections
			if len(words) <= args.consecutive_words_important:
				section_buffer = []
				for word in words:
					section_buffer.append(word)
					section_buffer = section_buffer[-args.consecutive_words_important:] # Trim buffer
					for buffer_index in range(len(section_buffer)):
						self.process_variations(section_buffer[buffer_index:])




class MediawikiScraper:
	chunk_size = 50
	cache_dir = Path(__file__).parent / 'cache'

	def _safe_request(self, params):
		try:
			resp = self.session.get(self.url, params=params)
			try:
				resp.raise_for_status()
			except requests.RequestException as e:
				if self.catch_request_exceptions:
					raise WordlistGenerationError(f'HTTP error {resp.status_code} for url {resp.url}')
				raise
		except requests.RequestException as e:
			if self.catch_request_exceptions:
				raise WordlistGenerationError(f'Request error for host {self.url}: {e}')
			raise
		data = resp.json()
		if 'error' in data:
			raise WordlistGenerationError(f"Api returned error for {resp.url}: {data['error']['message']}")
		return data

	def _chunked_request(self, query_namespace, params: dict, key: str, values: set):
		values_list = list(values)
		result = []
		for i in range(0, len(values_list), self.chunk_size):
			chunk = values_list[i:i+self.chunk_size]
			params[key] = '|'.join(str(value) for value in chunk)
			data = self._safe_request(params)['query'][query_namespace]
			if type(data) is list:
				result.extend(data)
			else:
				result.extend(data.values())
		return result
	
	def _request_with_continue(self, query_namespace, params: dict, continue_param):
		result = []
		while True:
			response = self._safe_request(params)
			data = response['query'][query_namespace]
			if type(data) is list:
				result.extend(data)
			else:
				result.extend(data.values())
			if 'continue' not in data:
				break
			params[continue_param] = response['continue'][continue_param]
		return result



	def get_page_ids_from_categories(self, categories):
		page_ids = set()
		for category in categories:
			cache_location = self.cache_dir / self.hostname / 'categories' / category
			cache_location.parent.mkdir(parents=True, exist_ok=True)
			if not cache_location.is_file() or time() - cache_location.stat().st_birthtime > 30 * 24 * 3600: # Cache is older than 30 days
				# Get from internet
				params = {
					'action': 'query',
					'list': 'categorymembers',
					'cmtitle': f'Category:{category}',
					'cmlimit': 'max',
					'cmtype': 'page',
					'format': 'json'
				}
				with open(cache_location, 'w', encoding='utf-8') as file:
					for page in self._request_with_continue('categorymembers', params, 'cmcontinue'):
						page_ids.add(page['pageid'])
						file.write(str(page['pageid']) + '\n')
			else:
				with open(cache_location, 'r', encoding='utf-8') as file:
					for line in file:
						page_ids.add(int(line))
		return page_ids

	def get_ids_of_titles(self, titles):
		unknown_titles = set()
		page_ids = set()
		for page_title in titles:
			cache_location = self.cache_dir / self.hostname / 'page_titles' / page_title
			cache_location.parent.mkdir(parents=True, exist_ok=True)
			if not cache_location.is_file() or time() - cache_location.stat().st_birthtime > 30 * 24 * 3600: # Cache is older than 30 days
				# Get from internet
				unknown_titles.add(page_title)
			else:
				# Read from cache
				with open(cache_location, 'r', encoding='utf-8') as file:
					page_ids.add(int(file.read()))
		# Not in cache
		params = {
			'action': 'query',
			'format': 'json'
		}
		for page in self._chunked_request('pages', params, 'titles', titles):
			if 'missing' in page:
				raise WordlistGenerationError(f"No such page with title {page['title']}")
			page_ids.add(page['pageid'])
			cache_location = self.cache_dir / self.hostname / 'page_titles' / page['title']
			with open(cache_location, 'w', encoding='utf-8') as file:
				file.write(str(page['pageid']))
		return page_ids
	
	def get_content_of_pages(self, page_ids: set[int]):
		# Get content of pages
		page_contents = set()
		unknown_page_ids = set()
		for page_id in page_ids:
			cache_location = self.cache_dir / self.hostname / 'page_content' / str(page_id)
			cache_location.parent.mkdir(parents=True, exist_ok=True)
			if not cache_location.is_file() or time() - cache_location.stat().st_birthtime > 30 * 24 * 3600: # Cache is older than 30 days
				# Get from internet
				unknown_page_ids.add(page_id)
			else:
				# Read from cache
				with open(cache_location, 'r', encoding='utf-8') as file:
					page_contents.add(file.read())
		# Pages not in cache
		params = {
			'action': 'query',
			'prop': 'revisions',
			'rvprop': 'content',
			'rvslots': 'main',
			'format': 'json'
		}
		for page in self._chunked_request('pages', params, 'pageids', unknown_page_ids):
			c = page['revisions'][0]['slots']['main']['*']
			page_contents.add(c)
			cache_location = self.cache_dir / self.hostname / 'page_content' / str(page['pageid'])
			with open(cache_location, 'w', encoding='utf-8') as file:
				file.write(c)
		return page_contents
	
	def get_all_ids(self):
		cache_location = self.cache_dir / self.hostname / 'all_page_ids'
		cache_location.parent.mkdir(parents=True, exist_ok=True)
		ids = set()
		if not cache_location.is_file() or time() - cache_location.stat().st_birthtime > 30 * 24 * 3600: # Cache is older than 30 days
			# Get from internet
			params = {
				'action': 'query',
				'list': 'allpages',
				'aplimit': 'max',
				'format': 'json',
			}
			with open(cache_location, 'w', encoding='utf-8') as file:
				for page in self._request_with_continue('allpages', params, 'apcontinue'):
					ids.add(int(page['pageid']))
					file.write(str(page['pageid']) + '\n')
		else:
			with open(cache_location, 'r', encoding='utf-8') as file:
				for line in file:
					ids.add(int(line))
		return ids

	def __init__(self, url, session, catch_request_exceptions=True):
		self.url = url
		self.session = session
		self.catch_request_exceptions = catch_request_exceptions
		parsed = urlparse(url)
		if parsed.scheme != 'http' and parsed.scheme != 'https':
			raise WordlistGenerationError(f'Url {url} should start with http or https')
		self.hostname = parsed.hostname
		if not self.hostname:
			raise WordlistGenerationError(f'Invalid URL: {url}')




wl = WordlistGenerator(args)

try:
	# Process MediaWiki sources
	if hasattr(args, 'mw_sources') or args.mw_url is not None:
		page_ids = set()
		# Create session
		session = requests.Session()
		session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3.1 Safari/605.1.15'})
		adapter = HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]))
		session.mount('http://', adapter)
		session.mount('https://', adapter)
		# For each mediawiki source
		for config in args.mw_sources if hasattr(args, 'mw_sources') else []:
			mw = MediawikiScraper(config['url'], session)
			if len(config['categories']) == 0 and len(config['pages']) == 0:
				try:
					input(f'Since no categories or pages were specified, the ENTIRE wiki for {config["url"]} will be downloaded. Press [Enter] to confirm. ')
				except KeyboardInterrupt:
					sys.exit(1)
				page_ids |= mw.get_all_ids()

			else:
				# Get pages from each category
				page_ids |= mw.get_page_ids_from_categories(config['categories'])
				page_ids |= mw.get_ids_of_titles(config['pages'])

			for content in mw.get_content_of_pages(page_ids):
				wikicode_iterate(mwparserfromhell.parse(content))

		# Process individual URLs
		for url in args.mw_url or []:
			parsed = urlparse(url)
			if parsed.scheme != 'http' and parsed.scheme != 'https':
				raise WordlistGenerationError(f'Url {url} should start with http or https')
			title = [x for x in parsed.path.split('/') if x][-1]
			for endpoint_path in ['/api.php', '/w/api.php']:
				endpoint = urlparse(url)._replace(path=endpoint_path, fragment='').geturl()
				mw = MediawikiScraper(endpoint, session, catch_request_exceptions=False)
				try:
					page_ids |= mw.get_ids_of_titles([title])
					for content in mw.get_content_of_pages(page_ids):
						wikicode_iterate(mwparserfromhell.parse(content))
					break
				except requests.RequestException:
					continue
			else:
				# Both endpoints failed
				raise WordlistGenerationError(f"Could not find valid API endpoint for {url}")



		session.close()

	# Write rules
	with open(args.outfile, 'w', encoding='utf-8') as out_file:
		for word in wl.list:
			out_file.write(word)
			out_file.write('\n')
	print(f'Generated {len(wl.list)} base passwords.')
	
except WordlistGenerationError as e:
	print('Error: '+ str(e), file=sys.stderr)
