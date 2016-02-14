#!/usr/bin/env python
import re
import logging
import argparse

import requests
from PythonConfluenceAPI import ConfluenceAPI

__author__ = 'Grigory Chernyshev <systray@yandex.ru>'


class ConfluencePageCopier(object):

    EXPAND_FIELDS = 'body.storage,space,ancestors,version'

    def __init__(self, username='admin', password='admin', uri_base='http://localhost:1990/confluence'):
        self.log = logging.getLogger('confl-copier')
        self._client = ConfluenceAPI(username, password, uri_base)

    def _find_page(self, content_id=None, space_key=None, title=None):
        try:
            if content_id:
                self.log.debug("Searching page by id '{}'".format(content_id))
                content = self._client.get_content_by_id(
                    content_id=content_id,
                    expand=self.EXPAND_FIELDS
                )
            else:
                assert space_key or title, "Can't search page without space key or title!"

                self.log.debug("Searching page by{space}{and_msg}{title}".format(
                    space=" space '%s'" % space_key if space_key else '',
                    and_msg=" and" if space_key and title else '',
                    title=" title '%s'" % title if title else ''
                ))
                content = self._client.get_content(
                    space_key=space_key, title=title,
                    expand=self.EXPAND_FIELDS
                )

            self.log.debug('Found {} page(s)'.format(content['size']))
            if content['size'] == 0:
                return None
            elif content['size'] == 1:
                return content['results'][0]
            else:
                spaces = set([r['space']['name'] for r in content['results']])
                raise ValueError(
                    "Unexpected result count: {count}, possibly you have to specify space to search in. "
                    "Results includes these spaces: {spaces}".format(
                        count=content['size'], spaces=', '.join(spaces)
                ))
        except requests.exceptions.HTTPError as e:
            if 400 <= e.response.status_code < 500:
                return None
            raise

    def _get_next_title(self, space_key, title):
        regex = re.compile("^{title}( \(\d+\))?$".format(title=re.escape(title)))
        matched_pages = list()
        search_results = self._client.search_content(cql_str='space = {space} and title ~ "{title}"'.format(
            space=space_key, title=title
        ))
        for result in search_results['results']:
            if regex.match(result['title']):
                matched_pages.append(result)

        total = len(matched_pages)
        if total == 0:
            self.log.warn('Failed to find suitable page to generate next title!')
            return None
        else:
            return "{title} ({counter})".format(title=title, counter=total)

    def copy(self, src, dst_space_key=None, dst_title=None, overwrite=False):
        source = self._find_page(**src)
        if not dst_space_key:
            src_space_key = source['space']['key']
            self.log.debug("Setting destination space key to source's value '{}'".format(src_space_key))
            dst_space_key = src_space_key
        if not dst_title:
            next_title = self._get_next_title(space_key=dst_space_key, title=source['title'])
            if next_title:
                self.log.debug("Setting destination title to calculated value '{}'".format(next_title))
                dst_title = next_title
            else:
                raise ValueError("Destination title is not given and could not be calculated!")

        existing_dst_page = self._find_page(space_key=dst_space_key, title=dst_title)
        if existing_dst_page:
            if overwrite:
                # Compare content and ancestors with existing before overwrite.
                if (
                    source['body']['storage']['value'] != existing_dst_page['body']['storage']['value']
                ) or (
                    source['ancestors'] != existing_dst_page['ancestors']
                ):
                    next_version = existing_dst_page['version']['number'] + 1
                    self.log.debug("Overwriting existing '{space}/{title}' with {version} version".format(
                        space=existing_dst_page['space']['key'],
                        title=existing_dst_page['title'],
                        version=next_version
                    ))

                    content_data = {
                        'id': existing_dst_page['id'],
                        'type': source['type'],
                        'space': {'key': dst_space_key},
                        'title': dst_title,
                        'body': {
                            'storage': {
                                'value': source['body']['storage']['value'],
                                'representation': 'storage'
                            }
                        },
                        'ancestors': source['ancestors'],
                        "version": {"number": next_version},
                    }
                    page_copy = self._client.update_content_by_id(
                        content_data=content_data,
                        content_id=existing_dst_page['id']
                    )
                else:
                    self.log.debug("Skipping '{space}/{title}' overwrite, as it's the same as original".format(
                        space=existing_dst_page['space']['key'],
                        title=existing_dst_page['title'],
                    ))
                    page_copy = existing_dst_page
            else:
                raise RuntimeError("Can't copy to '{space}/{title}' as it already exists!".format(
                    space=dst_space_key,
                    title=dst_title
                ))
        else:
            self.log.info("Copying '{src_space}/{src_title}' => '{dst_space}/{dst_title}'".format(
                src_space=source['space']['key'],
                src_title=source['title'],
                dst_space=dst_space_key,
                dst_title=dst_title,
            ))
            page_copy = self._client.create_new_content({
                'type': source['type'],
                'space': {'key': dst_space_key},
                'title': dst_title,
                'body': {
                    'storage': {
                        'value': source['body']['storage']['value'],
                        'representation': 'storage'
                    }
                },
                'ancestors': source['ancestors'],
            })

        labels = list()
        for label in self._client.get_content_labels(content_id=source['id'])['results']:
            labels.append({'prefix': label['prefix'], 'name': label['name']})
        self._client.create_new_label_by_content_id(content_id=page_copy['id'], label_names=labels)


def init_args():
    parser = argparse.ArgumentParser(description='Script for copying Confluence page')
    parser.add_argument('--log-level',
                        choices=filter(lambda item: type(item) is not int, logging._levelNames.values()),
                        default='DEBUG', help='Log level')

    parser.add_argument('--src-id', help='Source page id')
    parser.add_argument('--src-space', help='Source page space')
    parser.add_argument('--src-title', help='Source page title')

    parser.add_argument('--dst-space', help='Destination page space')
    parser.add_argument('--dst-title', help='Destination page title')

    parser.add_argument('--overwrite', action="store_true", default=False,
                        help='Overwrite page in case it already exists.')

    return parser.parse_args()


if __name__ == '__main__':
    args = init_args()
    logging.basicConfig(level=logging._levelNames.get(args.log_level))
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("PythonConfluenceAPI.api").setLevel(logging.WARNING)

    copier = ConfluencePageCopier()

    copier.copy(
        src={
            'title': args.src_title,
            'space_key': args.src_space,
            'content_id': args.src_id,
        },
        dst_space_key=args.dst_space,
        dst_title=args.dst_title,
        overwrite=args.overwrite
    )
