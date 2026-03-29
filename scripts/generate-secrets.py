#!/usr/bin/env python3
"""Generate strong application secrets for DFAS environment files."""

import secrets


def emit(label):
    print(f"{label}={secrets.token_urlsafe(48)}")


def main():
    for name in (
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "SESSION_SIGNING_KEY",
    ):
        emit(name)


if __name__ == "__main__":
    main()
