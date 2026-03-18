import argparse
import sys
import mwparserfromhell
import requests
from time import sleep, time
from pathlib import Path
from urllib.parse import urlparse

cache_dir = Path(__file__).parent / 'cache'

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
parser.add_argument('--mw-source', action=MwSourceAction, help='The URL of the MediaWiki api endpoint.')
parser.add_argument('--mw-category', action=MwCategoryAction, help='Category name for the preceding --mw-source. You can use this flag multiple times.')
parser.add_argument('--mw-page', action=MwPageAction, help='Page name for the preceding --mw-source. You can use this flag multiple times.')
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
parser.add_argument('--variation-chars-nopunctuation', choices=['on', 'off'], default='on', help='Default ON. Allow all ASCII characters but ,.?!:;')
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

class WordlistGenerator:
	special_chars_functions = []
	if args.variation_chars_original:
		special_chars_functions.append(lambda text: ''.join(filter(lambda c: 32 <= ord(c) <= 126, text))) # Don't include newline, tab
	if args.variation_chars_lettersonly:
		special_chars_functions.append(lambda text: ''.join(filter(lambda c: ord(c) == 32 or 65 <= ord(c) <= 90 or 97 <= ord(c) <= 122, text))) # space, A-Z, a-z
	if args.variation_chars_alnum:
		special_chars_functions.append(lambda text: ''.join(filter(lambda c: ord(c) == 32 or 48 <= ord(c) <= 57 or 65 <= ord(c) <= 90 or 97 <= ord(c) <= 122, text))) # space, 0-9, A-Z, a-z
	if args.variation_chars_nopunctuation:
		special_chars_functions.append(lambda text: ''.join(filter(lambda c: 32 <= ord(c) <= 126 and c not in '!,.?;:', text))) # Don't include newline, tab, ,.?!;:
	
	capitalization_functions = []
	if args.variation_cap_original:
		capitalization_functions.append(lambda words: words)
	if args.variation_cap_camelcase:
		capitalization_functions.append(lambda words: (words[0].lower(), *[word[0].upper() + word[1:].lower() for word in words[1:]]))
	if args.variation_cap_uppercase:
		capitalization_functions.append(lambda words: (word.upper() for word in words))
	if args.variation_cap_lowercase:
		capitalization_functions.append(lambda words: (word.lower() for word in words))
	if args.variation_cap_titlecase:
		capitalization_functions.append(lambda words: (word[0].upper() + word[1:].lower() for word in words))
	
	join_functions = []
	if args.variation_join_space:
		join_functions.append(lambda words: ' '.join(words))
	if args.variation_join_none:
		join_functions.append(lambda words: ''.join(words))
	if args.variation_join_dash:
		join_functions.append(lambda words: '-'.join(words))
	if args.variation_join_underscore:
		join_functions.append(lambda words: '_'.join(words))

	def __init__(self):
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


wl = WordlistGenerator()


try:
	# Process MediaWiki sources
	if hasattr(args, 'mw_sources'):
		# Function definitions

		def debug_print(indent_level, text):
			if args.debug_schema:
				debug_schema_file.write('|  ' * indent_level + text)
				debug_schema_file.write('\n')

		def wikicode_iterate(wikicode: mwparserfromhell.wikicode.Wikicode, debug_indent_level=0):
			if wikicode is None:
				debug_print(debug_indent_level, '(nothing)')
				return
			for node in wikicode.nodes:
				debug_print(debug_indent_level, type(node).__name__)
				if isinstance(node, mwparserfromhell.nodes.Tag):
					wikicode_iterate(node.contents, debug_indent_level + 1)
				elif isinstance(node, mwparserfromhell.nodes.Text):
					debug_print(debug_indent_level + 1, 'Value: ' + ''.join(filter(lambda c: 32 <= ord(c) <= 126, node.value)))
					wl.continue_text_input(node.value)
				elif isinstance(node, mwparserfromhell.nodes.Wikilink):
					if node.title.startswith('Image:') or node.title.startswith('File:'):
						continue
					if node.text is None:
						wikicode_iterate(node.title, debug_indent_level + 1)
					else:
						wikicode_iterate(node.text, debug_indent_level + 1)
				elif isinstance(node, mwparserfromhell.nodes.ExternalLink):
					wikicode_iterate(node.title, debug_indent_level + 1) # type: ignore
				elif isinstance(node, mwparserfromhell.nodes.Heading):
					wikicode_iterate(node.title, debug_indent_level + 1)
				else:
					debug_print(debug_indent_level, '(unrecognized element)')

		# Request all page ids of a certain category
		def get_pages_of_category(url, category):
			page_ids = set()
			params = {
				'action': 'query',
				'list': 'categorymembers',
				'cmtitle': f'Category:{category}',
				'cmlimit': 'max',
				'cmtype': 'page',
				'format': 'json'
			}
			retry_time = 5
			while True:
				while True:
					try:
						resp = session.get(url, params=params)
						if not resp.ok:
							raise WordlistGenerationError(f'HTTP error {resp.status_code} for category {category}')
						break
					except requests.RequestException as e:
						print(f'- * Request error, retrying in {retry_time} seconds...', file=sys.stderr)
						sleep(retry_time)
						retry_time *= 2
				data = resp.json()
				if len(data['query']['categorymembers']) == 0:
					raise WordlistGenerationError(f'Empty category "{category}"')
				for page in data['query']['categorymembers']:
					page_ids.add(page['pageid'])
				if 'continue' not in data:
					break
				params['cmcontinue'] = data['continue']['cmcontinue']
			return page_ids

		# Request all ids of a list of titles
		def get_ids_of_titles(url, titles):
			params = {
				'action': 'query',
				'titles': '|'.join(titles),
				'format': 'json'
			}
			retry_time = 5
			while True:
				try:
					resp = session.get(url, params=params)
					if not resp.ok:
						raise WordlistGenerationError('HTTP error {resp.status_code} when getting ids of titles')
					break
				except requests.RequestException as e:
					print(f'- * Request error, retrying in {retry_time} seconds...', file=sys.stderr)
					sleep(retry_time)
					retry_time *= 2
			data = resp.json()
			pages = {}
			for page in data['query']['pages'].values():
				if hasattr(page, 'missing'):
					raise WordlistGenerationError(f'No such page with title {page['title']}')
				pages[page['title']] = page['pageid']
				# Again, we don't lowercase page titles, because MediaWiki page titles are case-sensitive
			return pages
		
		def get_content_of_pages(url, page_ids: set[int]):
			# Mediawiki api universal limit for pageids is 50
			page_ids_list = list(page_ids)
			chunk_size = 50
			params = {
				'action': 'query',
				'prop': 'revisions',
				'rvprop': 'content',
				'rvslots': 'main',
				'format': 'json'
			}
			page_contents = {}
			retry_time = 5
			for i in range(0, len(page_ids_list), chunk_size):
				chunk = page_ids_list[i:i+chunk_size]
				params['pageids'] = '|'.join(str(page_id) for page_id in chunk)
				print(f'- - Pages {i} to {i+len(chunk)} of {len(page_ids_list)}')
				while True:
					try:
						resp = session.get(url, params=params)
						if not resp.ok:
							raise WordlistGenerationError(f'HTTP error {resp.status_code} when getting content of pages with ids {page_ids}')
						break
					except requests.RequestException as e:
						print(f'- * Request error, retrying in {retry_time} seconds...', file=sys.stderr)
						sleep(retry_time)
						retry_time *= 2
				data = resp.json()
				for page in data['query']['pages'].values():
					page_contents[page['pageid']] = page['revisions'][0]['slots']['main']['*']
			return page_contents

		# Initiate session
		session = requests.Session()
		session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3.1 Safari/605.1.15'})

		# For each mediawiki source
		for config in args.mw_sources:
			print(f'Processsing MediaWiki source: {config['url']}')
			# Parse url to get directory
			hostname = urlparse(config['url']).hostname
			if hostname == '':
				raise WordlistGenerationError(f'Invalid URL: {config['url']}')
			# Debug file
			if args.debug_schema:
				debug_schema_file = open('debug_schema.txt', 'w')


			if len(config['categories']) == 0 and len(config['pages']) == 0:
				try:
					input(f'Since no categories or pages were specified, the ENTIRE wiki for {config["url"]} will be downloaded. Press [Enter] to confirm. ')
				except KeyboardInterrupt:
					sys.exit(1)
				
				







			else:
				# Get pages from each category
				page_ids = set()
				for category in config['categories']:
					cache_location = cache_dir / hostname / 'categories' / category
					cache_location.parent.mkdir(parents=True, exist_ok=True)
					if not cache_location.is_file() or time() - cache_location.stat().st_birthtime > 30 * 24 * 3600: # Cache is older than 30 days
						# Get from internet
						print(f'- Getting pages for category "{category}"')
						category_page_ids = get_pages_of_category(config['url'], category)
						page_ids |= category_page_ids
						# Update cache
						with open(cache_location, 'w') as file:
							for page_id in category_page_ids:
								file.write(str(page_id) + '\n')
					else:
						# Read from cache
						print(f'- Using cache for category "{category}"')
						with open(cache_location, 'r') as file:
							for line in file:
								page_ids.add(int(line))

				# Add pages from command line
				unknown_titles = set()
				for page_title in config['pages']:
					cache_location = cache_dir / hostname / 'page_titles' / page_title
					cache_location.parent.mkdir(parents=True, exist_ok=True)
					if not cache_location.is_file() or time() - cache_location.stat().st_birthtime > 30 * 24 * 3600: # Cache is older than 30 days
						# Get from internet
						unknown_titles.add(page_title)
					else:
						# Read from cache
						print(f'- Using cache for id of page "{page_title}"')
						with open(cache_location, 'r') as file:
							page_ids.add(int(file.read()))

				# Process unknown titles
				if len(unknown_titles) > 0:
					print('- Getting id\'s of other pages from api')
					new_pages = get_ids_of_titles(config['url'], unknown_titles)
					for page_title, page_id in new_pages.items():
						cache_location = cache_dir / hostname / 'page_titles' / page_title
						cache_location.parent.mkdir(parents=True, exist_ok=True)
						page_ids.add(page_id)
						with open(cache_location, 'w') as file:
							file.write(str(page_id))

				# Get content of pages
				unknown_page_ids = set()
				for page_id in page_ids:
					cache_location = cache_dir / hostname / 'page_content' / str(page_id)
					cache_location.parent.mkdir(parents=True, exist_ok=True)
					if not cache_location.is_file() or time() - cache_location.stat().st_birthtime > 30 * 24 * 3600: # Cache is older than 30 days
						# Get from internet
						unknown_page_ids.add(page_id)
					else:
						# Read from cache
						print(f'- Using cache for content of page id={page_id}')
						with open(cache_location, 'r') as file:
							wikicode_iterate(mwparserfromhell.parse(file.read()))
				
				# Unknown pages
				if len(unknown_page_ids) > 0:
					print('- Getting content of other pages from api')
					page_contents = get_content_of_pages(config['url'], unknown_page_ids)
					for page_id, content in page_contents.items():
						cache_location = cache_dir / hostname / 'page_content' / str(page_id)
						cache_location.parent.mkdir(parents=True, exist_ok=True)
						with open(cache_location, 'w') as file:
							file.write(content)
						wikicode_iterate(mwparserfromhell.parse(content))

			# Close debug file
			if args.debug_schema:
				debug_schema_file.close() # type: ignore




	# Write rules
	with open(args.outfile, 'w') as out_file:
		for word in wl.list:
			out_file.write(word)
			out_file.write('\n')
	print(f'Generated {len(wl.list)} words.')
except WordlistGenerationError as e:
	print('Error: '+ str(e), file=sys.stderr)