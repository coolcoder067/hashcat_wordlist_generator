# Hashcat wordlist generator

## Setup

MacOS / Linux:

```
git clone https://github.com/coolcoder067/hashcat_wordlist_generator
cd hashcat_wordlist_generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```
usage: generate.py [-h] [--outfile OUTFILE] [--infile INFILE] [--mw-source MW_SOURCE] [--mw-category MW_CATEGORY] [--mw-page MW_PAGE] [--mw-url MW_URL]
                   [--variation-join-space {on,off}] [--variation-join-dash {on,off}] [--variation-join-underscore {on,off}] [--variation-join-none {on,off}]
                   [--variation-cap-original {on,off}] [--variation-cap-camelcase {on,off}] [--variation-cap-uppercase {on,off}] [--variation-cap-lowercase {on,off}]
                   [--variation-cap-titlecase {on,off}] [--variation-chars-original {on,off}] [--variation-chars-lettersonly {on,off}] [--variation-chars-alnum {on,off}]
                   [--variation-chars-nopunctuation {on,off}] [--consecutive-words CONSECUTIVE_WORDS] [--consecutive-words-important CONSECUTIVE_WORDS_IMPORTANT] [--debug-schema]

Create a wordlist from a MediaWiki site.

options:
  -h, --help            show this help message and exit
  --outfile, -o OUTFILE
                        File to store generated wordlist. Default wordlist.txt
  --infile, -i INFILE   Text file input
  --mw-source MW_SOURCE
                        The URL of the MediaWiki api endpoint. You can use this flag multiple times.
  --mw-category MW_CATEGORY
                        Category name for the preceding --mw-source. You can use this flag multiple times.
  --mw-page MW_PAGE     Page name for the preceding --mw-source. You can use this flag multiple times.
  --mw-url MW_URL       A standalone MediaWiki url to scrape. You can use this flag multiple times.
  --variation-join-space {on,off}
                        Default ON. Join words with spaces.
  --variation-join-dash {on,off}
                        Default OFF. Join words with dashes.
  --variation-join-underscore {on,off}
                        Default OFF. Join words with underscores.
  --variation-join-none {on,off}
                        Default OFF. Join words without seperator.
  --variation-cap-original {on,off}
                        Default OFF. Capitalize words with oRiGiNalCaPiTiLiZaTiOn.
  --variation-cap-camelcase {on,off}
                        Default OFF. Capitalize words with camelCase.
  --variation-cap-uppercase {on,off}
                        Default OFF. Capitalize words with UPPERCASE.
  --variation-cap-lowercase {on,off}
                        Default OFF. Capitalize words with lowercase.
  --variation-cap-titlecase {on,off}
                        Default ON. Capitalize words with TitleCase.
  --variation-chars-original {on,off}
                        Default OFF. Allow all ASCII characters.
  --variation-chars-lettersonly {on,off}
                        Default OFF. Allow only letters A-Z.
  --variation-chars-alnum {on,off}
                        Default ON. Allow letters A-Z, numbers 0-9.
  --variation-chars-nopunctuation {on,off}
                        Default ON. Allow all ASCII characters but ,.?!:;
  --consecutive-words CONSECUTIVE_WORDS
                        Default 2. The maximum number of consecutive words to form combinations with.
  --consecutive-words-important CONSECUTIVE_WORDS_IMPORTANT
                        Default 5. The maximum number of consecutive words to form combinations with, when text is deemed to be especially "important" (e.g. link text).
  --debug-schema        Output an additional file with an outline of the schema.
```