"""Literal AP text: never interpret remote text as BOTW message commands."""
import unicodedata


# Existing dialogue buffer holds 2048 UTF-16 units including its terminator.
# This is a storage ceiling, not permission to open that dialogue in native mode.
MESSAGE_MAX_UNITS = 2047


def literal_text(text):
    """Keep printable Unicode and newlines; remove binary MSBT control codes.

    Braces are literal: the laboratory's markup parser must not process network
    messages. Unpaired surrogates can arrive through JSON and cannot be encoded
    in UTF-16/UTF-8 safely. Replace them before persistence or native encoding.
    """
    text = str(text).replace('\r\n', '\n').replace('\r', '\n')
    return ''.join(
        '\ufffd' if unicodedata.category(char) == 'Cs' else
        ' ' if unicodedata.category(char) == 'Cc' and char != '\n' else char
        for char in text)


def clip_units(text, units):
    """Bound literal text by UTF-16 units, without splitting a surrogate pair."""
    if units < 0:
        raise ValueError('UTF-16 capacity must be nonnegative')
    return literal_text(text).encode('utf-16-be')[:units * 2].decode(
        'utf-16-be', errors='ignore')


def literal_metadata(value):
    """Keep JSON node metadata serializable even for malformed Unicode input."""
    if isinstance(value, str):
        return literal_text(value)
    if isinstance(value, (list, tuple)):
        return [literal_metadata(entry) for entry in value]
    if isinstance(value, dict):
        return {literal_text(key): literal_metadata(entry)
                for key, entry in value.items()}
    return value


def queued_text(text):
    """Preserve message content until a display channel is chosen."""
    clean = literal_text(text).strip()
    if len(clean.encode('utf-16-be')) <= MESSAGE_MAX_UNITS * 2:
        return clean
    return clip_units(clean, MESSAGE_MAX_UNITS - 3).rstrip() + '...'
