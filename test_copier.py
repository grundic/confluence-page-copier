import unittest
import sys, os
from mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from copier import ConfluencePageCopier

class TestOverwrite(unittest.TestCase):

    @classmethod
    def _find_page(cls, **kwargs):
        return kwargs

    def setUp(self):
        self.source = {'title': 'source', 'content_id': 11, 'id': 2,'space': {'key': 'space'}}
        self.dst = {'title': 'title', 'space_key': 'space'}
        self.cp = ConfluencePageCopier('user','password','bah')
        self.cp._find_page = MagicMock(side_effect=TestOverwrite._find_page)
        self.cp._init_destination_page = MagicMock(return_value=[self.dst['space_key'], self.dst['title']])
        self.cp._client.get_content_children_by_type = MagicMock(return_value={})
        self.cp._overwrite_page = MagicMock()

    def test_dst_parent_id(self):
        ancestor = 3
        self.cp.copy(src=self.source, dst_parent_id=ancestor, dst_title_template='', overwrite=True,
                     skip_attachments=True, skip_labels=True)

        self.cp._overwrite_page.assert_called_with(self.source, ancestor, self.dst, self.dst['space_key'],
                                                   self.dst['title'])

    def test_ancesor_id_page(self):
        ancestor = 30
        self.source['ancestors'] = [{'id': ancestor+2}, {'id': ancestor+1}, {'id': ancestor}]
        self.cp.copy(src=self.source, dst_title_template='', overwrite=True,
                     skip_attachments=True, skip_labels=True)
        self.cp._overwrite_page.assert_called_with(self.source, ancestor, self.dst, self.dst['space_key'],
                                                   self.dst['title'])

if __name__ == '__main__':
    unittest.main()
