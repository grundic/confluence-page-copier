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

Here how output from script could look like:
```
DEBUG:confl-copier:Searching page by title 'Page tree -- one'
DEBUG:confl-copier:Found 1 page(s)
DEBUG:confl-copier:Searching page by space 'TWO' and title 'Page tree -- one (4)'
DEBUG:confl-copier:Found 0 page(s)
DEBUG:confl-copier:Searching page by id '753678'
DEBUG:confl-copier:Searching page by id '753736'
INFO:confl-copier:Copying [ONE]:'First space Home'/'Page tree -- one' => [TWO]:'Simple page (2)'/'Page tree -- one (4)'
DEBUG:confl-copier:Searching page by id '753684'
DEBUG:confl-copier:Searching page by space 'TWO' and title 'Страничка с русскими символами (4)'
DEBUG:confl-copier:Found 0 page(s)
DEBUG:confl-copier:Searching page by id '753747'
INFO:confl-copier:Copying [ONE]:'First space Home'/'Страничка с русскими символами' => [TWO]:'Page tree -- one (4)'/'Страничка с русскими символами (4)'
DEBUG:confl-copier:Searching page by id '753686'
DEBUG:confl-copier:Searching page by space 'TWO' and title 'WTF?!@#$%^&*()_+`1234567890-=\/ (4)'
DEBUG:confl-copier:Found 0 page(s)
DEBUG:confl-copier:Searching page by id '753748'
INFO:confl-copier:Copying [ONE]:'First space Home'/'WTF?!@#$%^&*()_+`1234567890-=\/' => [TWO]:'Страничка с русскими символами (4)'/'WTF?!@#$%^&*()_+`1234567890-=\/ (4)'
INFO:confl-copier:Copying 1 attachment(s)
DEBUG:confl-copier:Downloading 'corpus-example.txt' attachment
DEBUG:confl-copier:Creating new attachment 'corpus-example.txt'
DEBUG:confl-copier:Removing temp directory '/var/folders/sd/ztpl1rh170542b20sd94dw4d5qz_tc/T/tmpLQUsPI'
```

## Parameters
* `--log-level`: change log level of the script. Could be one of `DEBUG`, `INFO`, `WARN`, `ERROR`.
* `--username`: username for Confluence server.
* `--password`: password for Confluence server.
* `--endpoint`: Confluence root endpoint. By default is configured to `http://localhost:1990/confluence`.
* `--src-id`: Source page id. Using this parameter precisely determines the page (if it exists). In case this parameter is set, `--src-space` and `--src-title` parameters are ignored.
* `--src-space`: Source page space. This parameter is optional. If it's not given, then script will try to find page by title only.
* `--src-title`: Source page title. Should unambiguously determine the page.
* `--dst-space`: Destination page space. Optional. If not set, then source space will be used (after root page for copying would be found).
* `--dst-title-template`: Destination page title template. This parameter supports meta variables: `{title}` and `{counter}`. You can use this parameter to set various suffixes/prefixes for resulting pages. Also, `{counter}` parameter allows you to create multiple copies of the same page incrementing counter in title.
* `--dst-parent-id`: ID of destination parent page. Setting this parameter would make script put original page tree under specified page. This parameter has precedence over `--dst-parent-title`.
* `--dst-parent-title`: Title of destination parent page. Setting this parameter would make script put original page tree under specified page. Should unambiguously determine single page.
* `--overwrite`: Overwrite page in case it already exists. Otherwise script will raise an exception.
* `--dry-run`: Using this flag would just log all actions without actually copying anything.
* `--skip-labels`: Use this flag to skip labels copying.
* `--skip-attachments`: Use this flag to skip attachments copying.
* `--recursion-limit`: Set recursion limit for copying pages. Setting thin parameter you can choose how deep should script go when copying pages. By default limit is not set and all children are copied. Setting zero would result in copying only one page without any children. Setting to 1 will copy only direct pages etc.

## Similar software
 * [Copy Page Tree](https://marketplace.atlassian.com/plugins/com.nurago.confluence.plugins.treecopy/cloud/overview): Confluence AddOn that adds a "Page Tree Copy" action to copy an entire page tree/hierarchy.
 * [Confluence Command Line Interface](https://bobswift.atlassian.net/wiki/display/CSOAP/Reference#Reference-copyPage): A command line interface (CLI) for remotely accessing Confluence.


# License
### MIT
