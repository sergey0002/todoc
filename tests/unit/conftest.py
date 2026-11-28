import pytest
from todoc.config import init_dataset

@pytest.fixture
def kb(tmp_path):
    root=tmp_path/'kb';root.mkdir();init_dataset(root)
    for d in ('inbox','notes','other'):(root/d).mkdir()
    (root/'inbox/a.md').write_text('---\nid: doc:inbox/a.md\ndoc_type: note\nupdated: 2020-01-01\n---\n# A\n\n## Суть\n\nText.\n\n## Part\nText.\n')
    return root

