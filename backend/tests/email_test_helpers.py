"""Shared fake SMTP client for email tests. Never touches a real network connection —
none of the tests using this import smtplib's real SMTP/SMTP_SSL classes.
"""


def make_fake_smtp_class(*, raise_on=None, exception=None, sent_store=None):
    """raise_on: None | "connect" | "starttls" | "login" | "send_message"."""

    class FakeSmtp:
        def __init__(self, host, port, timeout=None, context=None):
            self.host = host
            self.port = port
            if raise_on == "connect":
                raise exception

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context=None):
            if raise_on == "starttls":
                raise exception

        def login(self, username, password):
            if raise_on == "login":
                raise exception

        def send_message(self, message):
            if raise_on == "send_message":
                raise exception
            if sent_store is not None:
                sent_store.append(message)

    return FakeSmtp
