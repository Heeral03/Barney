import { SignJWT } from "jose";

/**
 * The only proof of identity the Barney back end accepts: a short-lived token signed with a secret that only this server
 * and the back end know. `sub` is "google:<id>" for an account or "guest:<id>" for a visitor who has not signed in.
 */
export async function backendToken(sub: string, email?: string | null): Promise<string> {
  const secret = process.env.BACKEND_JWT_SECRET;
  if (!secret || secret.length < 32) throw new Error("BACKEND_JWT_SECRET must be set to at least 32 characters");
  return new SignJWT(email ? { email } : {})
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(sub)
    .setIssuer("barney-web")
    .setAudience("barney-api")
    .setIssuedAt()
    .setExpirationTime("2m")
    .sign(new TextEncoder().encode(secret));
}
