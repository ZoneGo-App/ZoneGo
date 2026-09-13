"""What a merchant calls their store, kept off chain and signed by the merchant.

The vault holds a reward, a cap, a geohash and a radius — nothing a person
walking down the street would recognise. Putting a name in the contract would
mean redeploying it underneath campaigns that are already funded, so the name
lives here instead, and campaigns borrow it on the way out.

Off chain is not the same as unauthenticated. A profile is only accepted with a
signature from the wallet it describes, which is the rule the rest of ZoneGo
already runs on: the merchant signs, and nobody speaks for them. Without it,
anyone could rename somebody else's store — or send people away from it — with
one request.
"""

import os
import re
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass

from eth_account import Account
from eth_account.messages import encode_defunct

from api.config import get_config

NAME_MAX = 120
DESCRIPTION_MAX = 400

# The signed message is built line by line, so a line break in the name could
# move text between two fields under the same signature: a name ending in
# "\nDescription: ..." would read back as a different split of the same bytes.
#
# The description is allowed them. The merchant types it into a multi-line box,
# and refusing Enter there failed every save silently. It is safe: the name is
# now pinned to its own line, and the timestamp that follows the description is
# an integer that cannot contain a line break, so no two sets of values produce
# the same message.
_LINE_BREAK = re.compile(r"[\r\n]")


class ProfileError(ValueError):
    """The request is well formed but cannot be accepted. Maps to a 4xx."""

    status = 422


class SignatureRejected(ProfileError):
    status = 401


class StaleProfile(ProfileError):
    status = 409


@dataclass(frozen=True)
class Profile:
    wallet: str
    name: str
    description: str
    issued_at: int


_write_lock = threading.Lock()


def message(*, wallet: str, name: str, description: str, issued_at: int) -> str:
    """The exact text the merchant's wallet signs.

    The frontend has to build this character for character. The wallet is
    lowercased on both sides so a checksummed address and a plain one describe
    the same message.
    """
    return (
        "ZoneGo merchant profile\n"
        f"Wallet: {wallet.lower()}\n"
        f"Name: {name}\n"
        f"Description: {description}\n"
        f"Issued at: {issued_at}"
    )


def _path() -> str:
    configured = get_config().merchant_profiles_path
    return configured or os.path.join(tempfile.gettempdir(), "zonego_merchant_profiles.db")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_path())
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_profiles (
            wallet      TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT NOT NULL,
            issued_at   INTEGER NOT NULL
        )
        """
    )
    return connection


def _validate(*, name: str, description: str) -> None:
    if not name.strip():
        raise ProfileError("name cannot be empty")
    if len(name) > NAME_MAX:
        raise ProfileError(f"name is longer than {NAME_MAX} characters")
    if len(description) > DESCRIPTION_MAX:
        raise ProfileError(f"description is longer than {DESCRIPTION_MAX} characters")
    if _LINE_BREAK.search(name):
        raise ProfileError("name must be a single line")


def save(*, wallet: str, name: str, description: str, issued_at: int, signature: str) -> Profile:
    """Store a profile, if the wallet it names is the one that signed it."""
    _validate(name=name, description=description)

    window = get_config().merchant_profile_signature_window_seconds
    if abs(int(time.time()) - issued_at) > window:
        raise SignatureRejected("signature timestamp is too old or in the future; sign again")

    signed = encode_defunct(
        text=message(wallet=wallet, name=name, description=description, issued_at=issued_at)
    )
    try:
        signer = Account.recover_message(signed, signature=signature)
    except Exception as exc:  # noqa: BLE001 — any malformed signature is the same answer
        raise SignatureRejected("signature could not be read") from exc

    if signer.lower() != wallet.lower():
        raise SignatureRejected("signature is not from this wallet")

    key = wallet.lower()
    with _write_lock:
        connection = _connect()
        try:
            row = connection.execute(
                "SELECT issued_at FROM merchant_profiles WHERE wallet = ?", (key,)
            ).fetchone()
            # A signed profile stays valid for the whole window, so without this
            # an old one captured earlier could be sent again to put back a name
            # the merchant has since changed.
            if row is not None and issued_at <= row[0]:
                raise StaleProfile("a newer profile is already saved for this wallet")

            connection.execute(
                """
                INSERT INTO merchant_profiles (wallet, name, description, issued_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(wallet) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    issued_at = excluded.issued_at
                """,
                (key, name, description, issued_at),
            )
            connection.commit()
        finally:
            connection.close()

    return Profile(wallet=key, name=name, description=description, issued_at=issued_at)


def get(wallet: str) -> Profile | None:
    """A merchant's profile, or None.

    Read on every campaign in every search, so it never raises. A storage
    failure means the store shows its generic name, which is a worse page and
    not a broken one — search is the front door and must not go down over a
    label.
    """
    try:
        connection = _connect()
    except sqlite3.Error:
        return None
    try:
        row = connection.execute(
            "SELECT wallet, name, description, issued_at FROM merchant_profiles WHERE wallet = ?",
            (wallet.lower(),),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connection.close()

    return Profile(*row) if row else None


def labels(merchant: str) -> tuple[str, str]:
    """What to call a store, and what it says it sells — in one read.

    Its own name if the merchant gave one, a shortened address if not. The
    description is what search matches on, so a store that says it sells
    sneakers is found by somebody typing "sneakers" even though nothing on
    chain has ever mentioned a shoe.
    """
    profile = get(merchant)
    if profile is not None:
        return profile.name, profile.description
    return f"Merchant {merchant[:6]}…{merchant[-4:]}", ""
