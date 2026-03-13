import argparse
import sys
import pywikibot
import mwparserfromhell
from pywikibot import pagegenerators
pywikibot.config.useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

parser = argparse.ArgumentParser(description='Create a wordlist from a MediaWiki site. ')
parser.add_argument('url', help='The URL of the MediaWiki api. Should end with /api.php.')
parser.add_argument('--category', action='append', help='Use pages that match this category. You can use this flag multiple times.')
parser.add_argument('--page', action='append', help='Use page with this name. You can use this flag multiple times.')
args = parser.parse_args()

debug_file = open('test.txt', 'w')

wordlist = []
def add_to_wordlist(text):
    global wordlist
    debug_file.write(text)
    debug_file.write('\n')
    

def wikicode_iterate(wikicode, debug_indent_level=0):
    if wikicode is None:
        print('|  ' * debug_indent_level + '(nothing)')
        return
    for node in wikicode.nodes:
        print('|  ' * debug_indent_level + type(node).__name__)
        if isinstance(node, mwparserfromhell.nodes.Tag):
            wikicode_iterate(node.contents, debug_indent_level + 1)
        elif isinstance(node, mwparserfromhell.nodes.Text):
            add_to_wordlist(node.value)
        elif isinstance(node, mwparserfromhell.nodes.Wikilink):
            wikicode_iterate(node.text, debug_indent_level + 1)
        elif isinstance(node, mwparserfromhell.nodes.ExternalLink):
            wikicode_iterate(node.title, debug_indent_level + 1)
        elif isinstance(node, mwparserfromhell.nodes.Heading):
            wikicode_iterate(node.title, debug_indent_level + 1)
        else:
            print('|  ' * debug_indent_level + '-Uh Oh! It was something else!')

print(f'Connecting to site: {args.url}')
site = pywikibot.Site(url=args.url)

if args.category or args.page:
    for category in (args.category or []):
        pass
    for page_name in (args.page or []):
        print(f'Processing page: {page_name}')
        page = pywikibot.Page(site, page_name)
        text = page.expand_text()
        parsed = mwparserfromhell.parse(text)
        wikicode_iterate(parsed)
else:
    try:
        input('Since no categories or pages were specified, the ENTIRE wiki will be downloaded. Press [Enter] to confirm. ')
    except KeyboardInterrupt:
        sys.exit(1)
    gen = pagegenerators.AllpagesPageGenerator(site)

debug_file.close()