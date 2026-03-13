import argparse
import sys
import pywikibot
from pywikibot import pagegenerators
pywikibot.config.useragent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

parser = argparse.ArgumentParser(description='Create a wordlist from a MediaWiki site. ')
parser.add_argument('url', help='The URL of the MediaWiki api. Should end with /api.php.')
parser.add_argument('--category', action='append', help='Use pages that match this category. You can use this flag multiple times.')
parser.add_argument('--page', action='append', help='Use page with this name. You can use this flag multiple times.')
args = parser.parse_args()

wordlist = []
def add_to_wordlist(text):
    global wordlist
    with open(f'test.txt', 'w') as file:
        file.write(text)

print(f'Connecting to site: {args.url}')
site = pywikibot.Site(url=args.url)

if args.category or args.page:
    for category in (args.category or []):
        pass
    for page_name in (args.page or []):
        print(f'Processing page: {page_name}')
        page = pywikibot.Page(site, page_name)
        add_to_wordlist(page.expand_text())

else:
    try:
        input('Since no categories or pages were specified, the ENTIRE wiki will be downloaded. Press [Enter] to confirm. ')
    except KeyboardInterrupt:
        sys.exit(1)
    gen = pagegenerators.AllpagesPageGenerator(site)
