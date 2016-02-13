#!/usr/bin/env python
import logging
import argparse

import requests
from PythonConfluenceAPI import ConfluenceAPI

__author__ = 'Grigory Chernyshev <systray@yandex.ru>'


class ConfluencePageCopier(object):
    def __init__(self, username='admin', password='admin', uri_base='http://localhost:1990/confluence'):
        self.log = logging.getLogger('confl-copier')
        self._client = ConfluenceAPI(username, password, uri_base)

    def _find_page(self, content_id=None, space_key=None, title=None):
        try:
            if content_id:
                self.log.debug("Searching page by id '{}'".format(content_id))
                content = self._client.get_content_by_id(
                    content_id=content_id,
                    expand='body.storage,space,ancestors'
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
                    expand='body.storage,space,ancestors'
                )

            self.log.debug('Found {} page(s)'.format(content['size']))
            if content['size'] == 0:
                return None
            elif content['size'] == 1:
                return content['results'][0]
            else:
                raise ValueError("Unexpected result count: {}".format(content['size']))
        except requests.exceptions.HTTPError as e:
            if 400 <= e.response.status_code < 500:
                return None
            raise

    def copy(self, src, dst_space_key=None, dst_title=None, force=False):
        source = self._find_page(**src)
        if not dst_space_key:
            src_space_key = source['space']['key']
            self.log.debug("Setting destination space key to source's '{}'".format(src_space_key))
            dst_space_key = src_space_key

        page_exists = self._find_page(space_key=dst_space_key, title=dst_title)
        if page_exists:
            if force:
                self.log.debug("Forcing removal of existing page '{space}/{title}'".format(
                    space=page_exists['space']['key'],
                    title=page_exists['title']
                ))
                self._client.delete_content_by_id(page_exists['id'])

            else:
                raise RuntimeError("Can't copy to '{space}/{title}' as it already exists!".format(
                    space=dst_space_key,
                    title=dst_title
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

    parser.add_argument('--force', action="store_true", default=False,
                        help='Force page creation: if the same page already exists it will be removed.')

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
        force=args.force
    )
