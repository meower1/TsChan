from __future__ import annotations


class MelodifyError(Exception):
    pass


class MelodifyAuthError(MelodifyError):
    pass


class MelodifyNotFoundError(MelodifyError):
    pass


class TS3AudioBotError(Exception):
    pass
