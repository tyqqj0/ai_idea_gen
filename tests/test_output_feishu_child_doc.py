from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock

from backend.services.outputs.feishu_child_doc import FeishuChildDocOutputHandler
from backend.services.outputs.base import SourceDoc
from backend.core.manager import ProcessContext
from backend.services.processors.base import ProcessorResult


class TestFeishuChildDocOutputHandler(unittest.IsolatedAsyncioTestCase):
    async def test_wiki_path_with_space_id_skips_get_node(self) -> None:
        feishu = Mock()
        feishu.create_wiki_child_doc = AsyncMock(
            return_value={"obj_token": "doxc_child_obj", "node_token": "wikcn_child"}
        )
        feishu.write_doc_content = AsyncMock()
        feishu.append_reference_block = AsyncMock()
        feishu.send_card = AsyncMock()
        feishu.get_wiki_node_by_token = AsyncMock()

        handler = FeishuChildDocOutputHandler(feishu_client=feishu)
        ctx = ProcessContext(
            doc_token="doxc_source",
            user_id="ou_xxx",
            mode="idea_expand",
            trigger_source="unit_test",
            wiki_node_token="wikcn_parent",
            wiki_space_id="spc_123",
        )
        source = SourceDoc(doc_token="doxc_source", title="src-title", parent_token=None)
        pr = ProcessorResult(title="child-title", content_md="# hi", summary="s")

        out = await handler.handle(ctx=ctx, source_doc=source, processor_result=pr)

        feishu.get_wiki_node_by_token.assert_not_called()
        feishu.create_wiki_child_doc.assert_awaited_once()
        feishu.write_doc_content.assert_awaited_once_with("doxc_child_obj", "# hi")
        feishu.append_reference_block.assert_awaited_once()
        self.assertEqual(out.child_doc_token, "doxc_child_obj")
        self.assertEqual(out.child_doc_url, "https://feishu.cn/wiki/wikcn_child")

    async def test_wiki_path_without_space_id_calls_get_node(self) -> None:
        feishu = Mock()
        feishu.get_wiki_node_by_token = AsyncMock(return_value={"space_id": "spc_abc"})
        feishu.create_wiki_child_doc = AsyncMock(
            return_value={"obj_token": "doxc_child_obj", "node_token": "wikcn_child"}
        )
        feishu.write_doc_content = AsyncMock()
        feishu.append_reference_block = AsyncMock()
        feishu.send_card = AsyncMock()

        handler = FeishuChildDocOutputHandler(feishu_client=feishu)
        ctx = ProcessContext(
            doc_token="doxc_source",
            user_id="ou_xxx",
            mode="idea_expand",
            trigger_source="unit_test",
            wiki_node_token="wikcn_parent",
            wiki_space_id=None,
        )
        source = SourceDoc(doc_token="doxc_source", title="src-title", parent_token=None)
        pr = ProcessorResult(title="child-title", content_md="# hi", summary="s")

        out = await handler.handle(ctx=ctx, source_doc=source, processor_result=pr)

        feishu.get_wiki_node_by_token.assert_awaited_once_with(node_token="wikcn_parent")
        feishu.create_wiki_child_doc.assert_awaited_once()
        self.assertEqual(out.child_doc_url, "https://feishu.cn/wiki/wikcn_child")

    async def test_drive_path_uses_create_child_doc(self) -> None:
        feishu = Mock()
        feishu.create_child_doc = AsyncMock(return_value="doxc_child")
        feishu.write_doc_content = AsyncMock()
        feishu.append_reference_block = AsyncMock()
        feishu.send_card = AsyncMock()

        handler = FeishuChildDocOutputHandler(feishu_client=feishu)
        ctx = ProcessContext(
            doc_token="doxc_source",
            user_id="ou_xxx",
            mode="idea_expand",
            trigger_source="unit_test",
            wiki_node_token=None,
            wiki_space_id=None,
        )
        source = SourceDoc(doc_token="doxc_source", title="src-title", parent_token="fld_123")
        pr = ProcessorResult(title="child-title", content_md="# hi", summary="s")

        out = await handler.handle(ctx=ctx, source_doc=source, processor_result=pr)

        feishu.create_child_doc.assert_awaited_once_with(folder_token="fld_123", title="child-title")
        feishu.write_doc_content.assert_awaited_once_with("doxc_child", "# hi")
        self.assertEqual(out.child_doc_url, "https://feishu.cn/docx/doxc_child")


if __name__ == "__main__":
    unittest.main()



