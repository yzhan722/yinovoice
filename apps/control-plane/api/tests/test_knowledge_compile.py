from yino_platform_api.services.knowledge_compile import (
    KNOWLEDGE_END,
    KNOWLEDGE_START,
    apply_knowledge_block,
    compile_knowledge_block,
)


def test_compile_wraps_documents_between_markers() -> None:
    block = compile_knowledge_block(
        [
            {"title": "热线", "body": "400-000-0000"},
            {"title": "地址", "body": "合成路 1 号"},
        ]
    )
    assert block.startswith(KNOWLEDGE_START)
    assert block.endswith(KNOWLEDGE_END)
    assert "## 热线" in block
    assert "合成路 1 号" in block


def test_apply_replaces_existing_knowledge_block() -> None:
    original = "营业时间每天 8:30-17:30\n\n" + compile_knowledge_block(
        [{"title": "旧", "body": "旧内容"}]
    )
    updated = apply_knowledge_block(
        original,
        compile_knowledge_block([{"title": "新", "body": "新内容"}]),
    )
    assert updated.count(KNOWLEDGE_START) == 1
    assert "新内容" in updated
    assert "旧内容" not in updated
    assert updated.startswith("营业时间每天 8:30-17:30")


def test_apply_appends_when_markers_missing() -> None:
    updated = apply_knowledge_block(
        "机构介绍",
        compile_knowledge_block([{"title": "补充", "body": "会员制就诊"}]),
    )
    assert updated.startswith("机构介绍")
    assert "会员制就诊" in updated
    assert KNOWLEDGE_START in updated
