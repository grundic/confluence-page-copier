# Confluence page copier
Python script for creating a copy of a tree of Confluence pages.

## Description
This script will help you to create duplicates of Confluence pages and their children.
By default script will create a copy of page, labels and attachments. Default title of copied page would be
`"{title} ({counter})"` -- that means that would be used title of original page and counter will be set to size+1
from number of pages with original title. Counter calculated only once for root page, so all descendats will have
same number in title. You can set arbitrary title from command line and set prefixes/suffixes for new pages.

Also it's a good idea firstly use `--dry-run` flag which prevent any creations of new pages, so you can safely run
script and examine it's output.

If you don't need to copy page's children, you can set `--recursion-limit` parameter to `0`. Obviously, you can use
this parameter to control recursion limit of children pages that you wish to copy.x

## Install
pip install -r requirements.txt

## Examples
```bash
python copier.py --src-space=SPACE --src-title="Simple Page" --dst-title-template="Prefix {title} Suffix"
```
This command will create recursive copy of all pages starting from "Simple Page". Resulting pages will have name
corresponding to template, e.g.: "Prefix Simple Page Suffix". If the same pages already exists script will
throw an error. If you wish you can use `--overwrite` flag to overwrite existing page.

```bash
python copier.py --src-id=12345 --dst-title-template="{title} ({counter})"
```
This command will create a copy of page with id `12345` and add a counter to the title of copied page. This way you can
create multiple copies without warring about conflicts in names.

## Similar software
 * [Copy Page Tree](https://marketplace.atlassian.com/plugins/com.nurago.confluence.plugins.treecopy/cloud/overview): Confluence AddOn that adds a "Page Tree Copy" action to copy an entire page tree/hierarchy.
 * [Confluence Command Line Interface](https://bobswift.atlassian.net/wiki/display/CSOAP/Reference#Reference-copyPage): A command line interface (CLI) for remotely accessing Confluence.


# License
### MIT
