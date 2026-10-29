import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Google sign-in. The session is a signed cookie (no database); `session.user.id` is Google's stable id for the person.
// Reads AUTH_SECRET, AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET from the environment.
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
  callbacks: {
    session({ session, token }) {
      if (token.sub) session.user.id = token.sub;
      return session;
    },
  },
});
