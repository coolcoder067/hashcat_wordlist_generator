import argparse
import sys
import mwparserfromhell
# import requests_cache
import pywikibot
from pywikibot import pagegenerators

pywikibot.config.useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
# requests_cache.install_cache('mediawiki_cache', backend='sqlite', expire_after=2592000)

#############################
# Separation:
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
# lettersnumbers
#
# Frequency:
# consecutive words
# consecutive words (important)
#############################

# Process arguments
parser = argparse.ArgumentParser(description='Create a wordlist from a MediaWiki site. ')
parser.add_argument('url', help='The URL of the MediaWiki api. Should end with /api.php.')
parser.add_argument('--outfile', '-o', default='out.txt', help='File to store generated wordlist. Default out.txt')
parser.add_argument('--category', action='append', help='Use pages with this category. You can use this flag multiple times.')
parser.add_argument('--page', action='append', help='Use page with this name. You can use this flag multiple times.')
parser.add_argument('--variation-join-dash', choices=['on', 'off'], default='on', help='Default ON. Join words with dashes.')
parser.add_argument('--variation-join-underscore', choices=['on', 'off'], default='on', help='Default ON. Join words with underscores.')
parser.add_argument('--variation-join-none', choices=['on', 'off'], default='on', help='Default ON. Join words without seperator.')
parser.add_argument('--variation-cap-original', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with oRiGiNalCaPiTiLiZaTiOn.')
parser.add_argument('--variation-cap-camelcase', choices=['on', 'off'], default='on', help='Default ON. Capitalize words with camelCase.')
parser.add_argument('--variation-cap-uppercase', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with UPPERCASE.')
parser.add_argument('--variation-cap-lowercase', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with lowercase.')
parser.add_argument('--variation-cap-titlecase', choices=['on', 'off'], default='off', help='Default OFF. Capitalize words with TitleCase.')
parser.add_argument('--variation-chars-original', choices=['on', 'off'], default='off', help='Default OFF. Perform no filtering of special characters.')
parser.add_argument('--variation-chars-lettersonly', choices=['on', 'off'], default='off', help='Default OFF. Allow only letters A-Z.')
parser.add_argument('--variation-chars-lettersnumbers', choices=['on', 'off'], default='on', help='Default ON. Allow letters A-Z, numbers 0-9.')
parser.add_argument('--consecutive-words', type=int, default=2, help='Default 2. The maximum number of consecutive words to form combinations with.')
parser.add_argument('--consecutive-words-important', type=int, default=5, help='Default 5. The maximum number of consecutive words to form combinations with, when text is deemed to be especially "important" (e.g. link text).')
args = parser.parse_args()
args.variation_join_dash = args.variation_join_dash == 'on'
args.variation_join_underscore = args.variation_join_underscore == 'on'
args.variation_join_none = args.variation_join_none == 'on'
args.variation_cap_original = args.variation_cap_original == 'on'
args.variation_cap_camelcase = args.variation_cap_camelcase == 'on'
args.variation_cap_uppercase = args.variation_cap_uppercase == 'on'
args.variation_cap_lowercase = args.variation_cap_lowercase == 'on'
args.variation_cap_titlecase = args.variation_cap_titlecase == 'on'
args.variation_chars_original = args.variation_chars_original == 'on'
args.variation_chars_lettersonly = args.variation_chars_lettersonly == 'on'
args.variation_chars_lettersnumbers = args.variation_chars_lettersnumbers == 'on'
if args.consecutive_words_important < args.consecutive_words:
    args.consecutive_words_important = args.consecutive_words

# Open file
out_file = open(args.outfile, 'w')

# Debug stuff
debug_schema_file = open('schema.txt', 'w')
def debug_print(text):
    debug_schema_file.write(text)
    debug_schema_file.write('\n')


class WordlistGenerator:
    special_chars_functions = []
    if args.variation_chars_original:
        special_chars_functions.append(lambda text: text)
    if args.variation_chars_lettersonly:
        special_chars_functions.append(lambda text: ''.join(filter(lambda c: c.isalpha() or c.isspace(), text)))
    if args.variation_chars_lettersnumbers:
        special_chars_functions.append(lambda text: ''.join(filter(lambda c: c.isalnum() or c.isspace(), text)))
    
    capitalization_functions = []
    if args.variation_cap_original:
        capitalization_functions.append(lambda words: words)
    if args.variation_cap_camelcase:
        capitalization_functions.append(lambda words: (words[0].lower(), *[word.title() for word in words[1:]]))
    if args.variation_cap_uppercase:
        capitalization_functions.append(lambda words: (word.upper() for word in words))
    if args.variation_cap_lowercase:
        capitalization_functions.append(lambda words: (word.lower() for word in words))
    if args.variation_cap_titlecase:
        capitalization_functions.append(lambda words: (word.title() for word in words))
    
    join_functions = []
    if args.variation_join_none:
        join_functions.append(lambda words: ''.join(words))
    if args.variation_join_dash:
        join_functions.append(lambda words: '-'.join(words))
    if args.variation_join_underscore:
        join_functions.append(lambda words: '_'.join(words))

    def __init__(self):
        self.list = set()
        self.buffers = [] # There is one buffer for each filtering variation (original, lettersonly, lettersnumbers)
    
    def process_variations(self, words):
        variations = set()
        for c_func in self.capitalization_functions:
            c_words = c_func(words)
            for j_func in self.join_functions:
                variations.add(j_func(c_words))
        self.list |= variations # In-place union operator

    def continue_text_input(self, text):
        debug_print(text)
        # Special chars filtering: update buffer for each filtering variation
        for i in range(len(self.special_chars_functions)):
            words = self.special_chars_functions[i](text).split(' ')
            for word in words:
                self.buffers[i].append(word)
                self.buffers[i] = self.buffers[i][-args.consecutive_words:] # Trim buffer to args.consecutive_words length
                for buffer_index in range(len(self.buffers[i])):
                    self.process_variations(self.buffers[i][buffer_index])


wl = WordlistGenerator()

def wikicode_iterate(wikicode, debug_indent_level=0):
    if wikicode is None:
        debug_print('|  ' * debug_indent_level + '(nothing)')
        return
    for node in wikicode.nodes:
        debug_print('|  ' * debug_indent_level + type(node).__name__)
        if isinstance(node, mwparserfromhell.nodes.Tag):
            wikicode_iterate(node.contents, debug_indent_level + 1)
        elif isinstance(node, mwparserfromhell.nodes.Text):
            wl.continue_text_input(node.value)
        elif isinstance(node, mwparserfromhell.nodes.Wikilink):
            wikicode_iterate(node.text, debug_indent_level + 1)
            wikicode_iterate(node.title, debug_indent_level + 1)
        elif isinstance(node, mwparserfromhell.nodes.ExternalLink):
            wikicode_iterate(node.title, debug_indent_level + 1)
        elif isinstance(node, mwparserfromhell.nodes.Heading):
            wikicode_iterate(node.title, debug_indent_level + 1)
        else:
            debug_print('|  ' * debug_indent_level + '-Uh Oh! It was something else!')

def process_page(page):
    print(f'Processing page: {page.title()}')
    text = page.expand_text()
    parsed = mwparserfromhell.parse(text)
    wikicode_iterate(parsed)

print(f'Connecting to site: {args.url}')
site = pywikibot.Site(url=args.url)



if args.category or args.page:
    for cat_name in (args.category or []):
        for page in pywikibot.Category(site, cat_name).articles(recurse=True):
            process_page(page)
    for page_name in (args.page or []):
        process_page(pywikibot.Page(site, page_name))
else:
    try:
        input('Since no categories or pages were specified, the ENTIRE wiki will be downloaded. Press [Enter] to confirm. ')
    except KeyboardInterrupt:
        sys.exit(1)
    for page in pagegenerators.AllpagesPageGenerator(site):
        process_page(page)

out_file.close()
debug_schema_file.close()