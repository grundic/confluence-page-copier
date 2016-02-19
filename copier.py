#!/usr/bin/env python
import os
import re
import shutil
import logging
import tempfile
import argparse

import requests
from PythonConfluenceAPI import ConfluenceAPI

__author__ = 'Grigory Chernyshev <systray@yandex.ru>'


class ConfluenceAPIDryRunProxy(ConfluenceAPI):

    MOD_METH_RE = re.compile(r'^(create|update|convert|delete)_.*$')

    def __init__(self, username, password, uri_base, user_agent=ConfluenceAPI.DEFAULT_USER_AGENT, dry_run=False):
        super(ConfluenceAPIDryRunProxy, self).__init__(username, password, uri_base, user_agent)
        self._dry_run = dry_run
        self.log = logging.getLogger('api-proxy')

    def __getattribute__(self, name):
        attr = object.__getattribute__(self, name)
        is_dry = object.__getattribute__(self, '_dry_run')
        if is_dry and hasattr(attr, '__call__') and self.MOD_METH_RE.match(name):
            def dry_run(*args, **kwargs):
                func_args = list()
                if args:
                    func_args.extend(str(a) for a in args)
                if kwargs:
                    func_args.extend('%s=%s' % (k, v) for k, v in kwargs.items())

                self.log.info("[DRY-RUN] {name}({func_args})".format(name=name, func_args=', '.join(func_args)))

            return dry_run
        else:
            return attr


class ConfluencePageCopier(object):
    EXPAND_FIELDS = 'body.storage,space,ancestors,version'
    TITLE_FIELD = '{title}'
    COUNTER_FIELD = '{counter}'
    DEFAULT_TEMPLATE = '{t} ({c})'.format(t=TITLE_FIELD, c=COUNTER_FIELD)

    def __init__(self, username='admin', password='admin', uri_base='http://localhost:1990/confluence', dry_run=False):
        self.log = logging.getLogger('confl-copier')
        self._dry_run = dry_run
        self._client = ConfluenceAPIDryRunProxy(
            username=username,
            password=password,
            uri_base=uri_base,
            dry_run=dry_run
        )

    def copy(
        self,
        src,
        dst_space_key=None,
        dst_title_template=None,
        ancestor_id=None,
        overwrite=False,
        skip_labels=False,
        skip_attachments=False
    ):
        source = self._find_page(**src)
        dst_space_key, dst_title_template = self._init_destination_page(source, dst_space_key, dst_title_template)
        dst_title = dst_title_template.format(title=source['title'])

        # ancestor_id determines parent of the page being copied. If it's not provided, we take it from source page.
        # If source page doesn't have ancestors, that means that it's root page, so we will copy to the root as well.
        if not ancestor_id:
            if source['ancestors']:
                self.log.debug('Setting ancestor id to {}'.format(source['ancestors'][0]['id']))
                ancestor_id = source['ancestors'][0]['id']
            else:
                ancestor_id = None

        # check if page in selected space and with specific title already exists.
        existing_dst_page = self._find_page(space_key=dst_space_key, title=dst_title)
        if existing_dst_page:
            if overwrite:
                page_copy = self._overwrite_page(source, ancestor_id, existing_dst_page, dst_space_key, dst_title)
            else:
                raise RuntimeError("Can't copy to '{space}/{title}' as it already exists!".format(
                    space=dst_space_key,
                    title=dst_title
                ))
        else:
            page_copy = self._copy_page(source, ancestor_id, dst_space_key, dst_title)

        if self._dry_run:
            page_copy_id = -1
        else:
            page_copy_id = page_copy['id']

        if not skip_labels:
            # copy labels
            self._copy_labels(source, page_copy_id)

        if not skip_attachments:
            # copy attachments
            self._copy_attachments(source, page_copy_id)

        # recursively copy children
        children = self._client.get_content_children_by_type(content_id=source['id'], child_type='page')
        if children and children.get('results'):
            for child in children['results']:
                self.copy(
                    src={'content_id': child['id']},
                    dst_space_key=dst_space_key,
                    dst_title_template=dst_title_template,
                    ancestor_id=page_copy_id,
                    overwrite=overwrite
                )

    def _find_page(self, content_id=None, space_key=None, title=None):
        try:
            if content_id:
                self.log.debug("Searching page by id '{}'".format(content_id))
                content = self._client.get_content_by_id(
                    content_id=content_id,
                    expand=self.EXPAND_FIELDS
                )
                return content
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
                            count=content['size'], spaces=', '.join(spaces))
                    )
        except requests.exceptions.HTTPError as e:
            if 400 <= e.response.status_code < 500:
                return None
            raise

    def _init_destination_page(self, source, dst_space_key, title_template):
        if not dst_space_key:
            src_space_key = source['space']['key']
            self.log.debug("Setting destination space key to source's value '{}'".format(src_space_key))
            dst_space_key = src_space_key
        if not title_template:
            # if no value is provided for template - use default one
            title_template = self.DEFAULT_TEMPLATE
        elif self.TITLE_FIELD not in title_template:
            # if there is no title in template - treat the value as a suffix
            self.log.info("Can't find '{title}' in title template '{template}', treating it as suffix.".format(
                title=self.TITLE_FIELD, template=title_template
            ))
            title_template = self.TITLE_FIELD + title_template

        if self.COUNTER_FIELD in title_template:
            counter = self._get_title_counter(space_key=dst_space_key, title=source['title'], template=title_template)
            # can't use `format` here, because there are other fields that should not be formatted yet ({title})
            title_template = title_template.replace(self.COUNTER_FIELD, str(counter))

        return dst_space_key, title_template

    def _get_title_counter(self, space_key, title, template):
        counter = 0
        template = template.replace(self.TITLE_FIELD, title)
        template = re.escape(template)
        template = template.replace(re.escape(self.COUNTER_FIELD), '\d+')
        regex = re.compile("^{template}$".format(template=template))
        search_results = self._client.search_content(cql_str='space = {space} and title ~ "{title}"'.format(
            space=space_key, title=title
        ))
        for result in search_results['results']:
            if regex.match(result['title']):
                counter += 1

        return counter + 1

    def _overwrite_page(self, source, ancestor_id, existing_dst_page, dst_space_key, dst_title):
        is_page_equal = True
        is_page_equal = is_page_equal and (
            source['body']['storage']['value'] == existing_dst_page['body']['storage']['value']
        )
        # TODO: https://answers.atlassian.com/questions/5278993/answers/11442314
        is_page_equal = is_page_equal and ancestor_id == existing_dst_page['ancestors'][-1]['id']

        if is_page_equal:
            self.log.info("Skipping '{space}/{title}' overwrite, as it's the same as original".format(
                space=existing_dst_page['space']['key'],
                title=existing_dst_page['title'],
            ))
            return existing_dst_page

        next_version = existing_dst_page['version']['number'] + 1
        self.log.info("Overwriting existing '{space}/{title}' with {version} version".format(
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
            'ancestors': [] if not ancestor_id else [{'id': ancestor_id}],
            "version": {"number": next_version},
        }
        page_copy = self._client.update_content_by_id(
            content_data=content_data,
            content_id=existing_dst_page['id']
        )

        return page_copy

    def _copy_page(self, source, ancestor_id, dst_space_key, dst_title):
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
            'ancestors': [{'id': ancestor_id}],
        })

        return page_copy

    def _copy_labels(self, source, page_copy_id):
        labels = list()
        for label in self._client.get_content_labels(content_id=source['id'])['results']:
            labels.append({'prefix': label['prefix'], 'name': label['name']})
        if labels:
            self.log.info("Copying {} label(s)".format(len(labels)))
            self._client.create_new_label_by_content_id(content_id=page_copy_id, label_names=labels)

    def _copy_attachments(self, source, page_copy_id):
        src_attachments = self._client.get_content_attachments(content_id=source['id'])['results']
        if not src_attachments:
            return

        if self._dry_run:
            dst_attachments = list()
        else:
            dst_attachments = self._client.get_content_attachments(content_id=page_copy_id)['results']

        self.log.info("Copying {} attachment(s)".format(len(src_attachments)))
        temp_dir = tempfile.mkdtemp()
        try:
            for attachment in src_attachments:
                self.log.debug("Downloading '{name}' attachment".format(name=attachment['title']))
                content = self._client._service_get_request(sub_uri=attachment['_links']['download'][1:], raw=True)
                filename = os.path.join(temp_dir, attachment['title'])
                with open(filename, 'wb') as f:
                    f.write(content)

                for attach in dst_attachments:
                    if attachment['title'] == attach['title']:
                        self.log.debug("Updating existing attachment '{name}'".format(name=attachment['title']))
                        with open(filename, 'rb') as f:
                            self._client.update_attachment(
                                content_id=page_copy_id,
                                attachment_id=attach['id'],
                                attachment={'file': f}
                            )
                        break
                else:
                    self.log.debug("Creating new attachment '{name}'".format(name=attachment['title']))
                    with open(filename, 'rb') as f:
                        self._client.create_new_attachment_by_content_id(
                            content_id=page_copy_id,
                            attachments={'file': f}
                        )
        finally:
            self.log.debug("Removing temp directory '{}'".format(temp_dir))
            shutil.rmtree(temp_dir)


def init_args():
    parser = argparse.ArgumentParser(description='Script for smart copying Confluence pages.')
    parser.add_argument('--log-level',
                        choices=filter(lambda item: type(item) is not int, logging._levelNames.values()),
                        default='DEBUG', help='Log level')

    parser.add_argument(
        '--src-id',
        help=(
            'Source page id. Using this parameter precisely determines the page (if it exists). '
            'In case this parameter is set, `--src-space` and `--src-title` parameters are ignored.'
        )
    )
    parser.add_argument(
        '--src-space',
        help='Source page space. This parameter could be skipped, then script will try to find page by title only.'
    )
    parser.add_argument(
        '--src-title',
        help='Source page title. Should unambiguously determine page.'
    )

    parser.add_argument(
        '--dst-space',
        help='Destination page space. If not set, then source space will be used (after it will be found).')
    parser.add_argument(
        '--dst-title-template',
        default=ConfluencePageCopier.DEFAULT_TEMPLATE,
        help=(
            "Destination page title template. "
            "This parameter supports meta variables: '{title}' and '{counter}'. "
            "You can use this parameter to set various suffixes/prefixes for resulting pages. "
            "Also, '{counter}' parameter allows you to create multiple copies of the same page "
            "incrementing counter in title.".format(
                title=ConfluencePageCopier.TITLE_FIELD, counter=ConfluencePageCopier.COUNTER_FIELD
            )
        )
    )

    parser.add_argument('--overwrite', action="store_true", default=False,
                        help='Overwrite page in case it already exists. Otherwise script will raise an exception.')

    parser.add_argument('--dry-run', action="store_true", default=False,
                        help='Using this flag would just log all actions without actually copying anything.')

    parser.add_argument('--skip-labels', action="store_true", default=False,
                        help='Use this flag to skip labels copying.')

    parser.add_argument('--skip-attachments', action="store_true", default=False,
                        help='Use this flag to skip attachments copying.')

    return parser.parse_args()


if __name__ == '__main__':
    args = init_args()
    logging.basicConfig(level=logging._levelNames.get(args.log_level))
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("PythonConfluenceAPI.api").setLevel(logging.WARNING)

    copier = ConfluencePageCopier(dry_run=args.dry_run)

    copier.copy(
        src={
            'title': args.src_title,
            'space_key': args.src_space,
            'content_id': args.src_id,
        },
        dst_space_key=args.dst_space,
        dst_title_template=args.dst_title_template,
        overwrite=args.overwrite,
        skip_labels=args.skip_labels,
        skip_attachments=args.skip_attachments,
    )
