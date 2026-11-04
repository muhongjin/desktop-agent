from __future__ import annotations

from desktop_agent.agent.prompt import PromptComposer


def test_extra_system_messages_follow_prompt_layers():
    request = PromptComposer("全局提示词").compose(
        [], workspace="C:/tmp", extra_system_messages=("参考资料 A", "  ", "参考资料 B")
    )
    contents = [message["content"] for message in request.messages]
    assert contents[0] == request.kernel
    assert contents[1] == "全局提示词"
    assert contents[2] == "参考资料 A"
    assert contents[3] == "参考资料 B"


def test_without_extra_messages_layout_is_unchanged():
    request = PromptComposer("").compose([], workspace="C:/tmp")
    assert [message["role"] for message in request.messages] == ["system", "system"]
