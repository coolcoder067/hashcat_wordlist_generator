import argparse
import sys
import mwparserfromhell
import pywikibot
from pywikibot import pagegenerators

pywikibot.config.useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

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

# Process arguments
parser = argparse.ArgumentParser(description='Create a wordlist from a MediaWiki site. ')
parser.add_argument('url', help='The URL of the MediaWiki api. Should end with /api.php.')
parser.add_argument('--outfile', '-o', default='wordlist.txt', help='File to store generated wordlist. Default wordlist.txt')
parser.add_argument('--category', action='append', help='Use pages with this category. You can use this flag multiple times.')
parser.add_argument('--page', action='append', help='Use page with this name. You can use this flag multiple times.')
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
parser.add_argument('--debug_schema', action='store_true', help='Output an additional file with an outline of the schema.')
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
args.variation_chars_alnum = args.variation_chars_alnum == 'on'
args.variation_chars_nopunctuation = args.variation_chars_nopunctuation == 'on'
if args.consecutive_words_important < args.consecutive_words:
    args.consecutive_words_important = args.consecutive_words

if args.debug_schema:
    debug_schema_file = open('debug_schema.txt', 'w')
def debug_print(indent_level, text):
    if args.debug_schema:
        debug_schema_file.write('|  ' * indent_level + text)
        debug_schema_file.write('\n')

def title_case(word):
    word = word.lower()
    return word[0].upper() + word[1:]

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
            # Process section by itself
            if len(words) <= args.consecutive_words_important:
                section_buffer = []
                for word in words:
                    section_buffer.append(word)
                    section_buffer = section_buffer[-args.consecutive_words_important:] # Trim buffer
                    for buffer_index in range(len(section_buffer)):
                        self.process_variations(section_buffer[buffer_index:])


wl = WordlistGenerator()

def wikicode_iterate(wikicode, debug_indent_level=0):
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
            wikicode_iterate(node.title, debug_indent_level + 1)
        elif isinstance(node, mwparserfromhell.nodes.Heading):
            wikicode_iterate(node.title, debug_indent_level + 1)
        else:
            debug_print(debug_indent_level, '(unrecognized element)')

def process_page(page):
    print(f'Processing page: {page.title()}')
    text = page.expand_text()
    parsed = mwparserfromhell.parse(text)
    wikicode_iterate(parsed)


# TODO replace this section with custom logic, not rely on pywikibot
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

# Write rules
with open(args.outfile, 'w') as out_file:
    for word in wl.list:
        out_file.write(word)
        out_file.write('\n')

# Close debug file
if args.debug_schema:
    debug_schema_file.close()