"""Tests for the Telegram allowlist (B209, 2026-10-14).

Until B209 the allowlist matched the CHAT id only, so in an allowlisted group chat any member's "yes" fired a pending
act. The sender (`message.from.id`) must now be an allowed USER on every message, and a group chat is admitted only
when it is listed separately. In a private chat `chat.id == from.id`, so an existing private-chat entry keeps working.
A message with no sender (a channel post) or sent as an anonymous group admin (`sender_chat`) is refused: no person,
no authority.
"""
import pytest

import ingress

ME = 111111111          # a private chat: chat.id == from.id
STRANGER = 222222222
GROUP = -1001234567890  # supergroup ids are negative


@pytest.fixture(autouse=True)
def allowlist(monkeypatch):
    monkeypatch.setattr(ingress, "_USERS", {str(ME)})
    monkeypatch.setattr(ingress, "_CHATS", {str(GROUP)})


def _msg(chat_id, chat_type, from_id=None, **extra):
    m = {"chat": {"id": chat_id, "type": chat_type}, "text": "yes", **extra}
    if from_id is not None:
        m["from"] = {"id": from_id, "is_bot": False}
    return m


def test_an_allowed_user_in_their_private_chat_is_admitted():
    assert ingress._sender(_msg(ME, "private", ME)) == ME


def test_a_stranger_in_their_own_private_chat_is_refused():
    assert ingress._sender(_msg(STRANGER, "private", STRANGER)) is None


def test_a_stranger_in_an_allowed_group_is_refused():
    # The B209 hole: the chat is allowed, the person is not. Their "yes" must not confirm an act.
    assert ingress._sender(_msg(GROUP, "supergroup", STRANGER)) is None


def test_an_allowed_user_in_an_allowed_group_is_admitted():
    assert ingress._sender(_msg(GROUP, "supergroup", ME)) == ME


def test_an_allowed_user_in_a_group_that_is_not_listed_is_refused():
    assert ingress._sender(_msg(-1009999999999, "group", ME)) is None


def test_a_message_with_no_sender_is_refused():
    assert ingress._sender(_msg(GROUP, "supergroup")) is None


def test_an_anonymous_group_admin_is_refused_even_with_an_allowed_from():
    # Telegram sets from = the GroupAnonymousBot and sender_chat = the group for anonymous admins: no person to check.
    assert ingress._sender(_msg(GROUP, "supergroup", ME, sender_chat={"id": GROUP})) is None


def test_an_old_style_private_chat_entry_still_works_as_a_user_id():
    # Before B209 the allowlist held chat ids. A private chat's id IS the user's id, so the same entry admits them.
    assert ingress._sender(_msg(ME, "private", ME)) == ME
    assert ingress._sender(_msg(ME, "private", STRANGER)) is None   # a spoofed chat id with another sender
