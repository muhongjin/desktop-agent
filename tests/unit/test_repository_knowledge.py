from __future__ import annotations

from desktop_agent.domain.models import MessageRole
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository


def make_repository(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return database, Repository(database), workspace


def test_message_retrieval_roundtrip(tmp_path):
    database, repository, workspace = make_repository(tmp_path)
    try:
        session = repository.create_session("聊天", str(workspace))
        draft = repository.append_message(session.id, MessageRole.ASSISTANT, "回答")
        payload = {"query": "怎么申请", "hits": [{"n": 1, "doc_name": "新人指南"}]}
        updated = repository.set_message_retrieval(draft.id, payload)
        assert updated.retrieval == payload
        stored = repository.list_messages(session.id)[0]
        assert stored.retrieval["hits"][0]["doc_name"] == "新人指南"
    finally:
        database.close()


def test_session_knowledge_bases_roundtrip(tmp_path):
    database, repository, workspace = make_repository(tmp_path)
    try:
        session = repository.create_session("聊天", str(workspace))
        assert repository.get_session_knowledge_bases(session.id) == []
        saved = repository.set_session_knowledge_bases(session.id, ["kb-b", "kb-a", "kb-b"])
        assert saved == ["kb-b", "kb-a"]
        assert repository.get_session_knowledge_bases(session.id) == ["kb-b", "kb-a"]
        assert repository.set_session_knowledge_bases(session.id, []) == []
    finally:
        database.close()


def test_session_knowledge_bases_are_removed_with_session(tmp_path):
    database, repository, workspace = make_repository(tmp_path)
    try:
        session = repository.create_session("聊天", str(workspace))
        repository.set_session_knowledge_bases(session.id, ["kb-b"])
        repository.archive_session(session.id)
        repository.delete_session(session.id)
        assert repository.get_session_knowledge_bases(session.id) == []
    finally:
        database.close()
