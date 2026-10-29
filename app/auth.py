"""Who is calling. The Next.js app signs a short-lived token for every request it forwards; this module checks it.

The browser never says who it is: the web app decides from the signed-in session (or, for visitors who have not signed in,
from a random id in an httpOnly cookie) and signs `sub` with a secret only the two servers share. So a user id can no
longer be guessed or typed into a request. `sub` is "google:<id>" for an account and "guest:<id>" for a visitor.
"""
import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException

ISSUER = "barney-web"
AUDIENCE = "barney-api"
MIN_SECRET = 32


@dataclass(frozen=True)
class Caller:
    id: str
    email: str = ""
    profile: str = ""  # which shopping profile ("Mom", ...) the page has selected; checked against the account before use

    @property
    def guest(self) -> bool:
        return self.id.startswith("guest:")


def _secret() -> str:
    secret = os.getenv("BACKEND_JWT_SECRET", "")
    if len(secret) < MIN_SECRET:  # refuse to run open: no secret means no way to trust any caller
        raise HTTPException(503, f"BACKEND_JWT_SECRET must be set to at least {MIN_SECRET} characters")
    return secret


def decode(token: str) -> Caller:
    try:
        claims = jwt.decode(token, _secret(), algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
                            options={"require": ["exp", "sub", "iss", "aud"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token") from None
    sub = str(claims["sub"])
    if not sub.startswith(("google:", "guest:")) or len(sub) < 8:
        raise HTTPException(401, "invalid subject")
    return Caller(sub, str(claims.get("email") or ""))


def current_user(authorization: str = Header(default=""), x_barney_profile: str = Header(default="")) -> Caller:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "missing bearer token")
    caller = decode(token)
    return Caller(caller.id, caller.email, x_barney_profile[:60])


def signed_in(me: Caller = Depends(current_user)) -> Caller:
    if me.guest:
        raise HTTPException(403, "sign in required")
    return me
