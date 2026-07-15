import { cookies } from 'next/headers';
import crypto from 'node:crypto';
import bcrypt from 'bcryptjs';
import { query } from './db';

const COOKIE = 'tc_session';
const MAX_AGE = 60 * 60 * 12; // 12 hours

export type Session = { email: string; displayName: string; role: string };
type TokenPayload = Session & { exp: number };

function secret(): string {
  const s = process.env.AUTH_SECRET;
  if (!s) throw new Error('AUTH_SECRET is not set');
  return s;
}

function sign(data: string): string {
  return crypto.createHmac('sha256', secret()).update(data).digest('base64url');
}

function encode(payload: TokenPayload): string {
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  return `${body}.${sign(body)}`;
}

function decode(token: string): TokenPayload | null {
  const [body, sig] = token.split('.');
  if (!body || !sig) return null;
  const expected = sign(body);
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try {
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString()) as TokenPayload;
    if (typeof payload.exp !== 'number' || payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}

export async function verifyCredentials(email: string, password: string): Promise<Session | null> {
  const rows = await query<{
    email: string;
    password_hash: string;
    display_name: string | null;
    role: string | null;
  }>('SELECT email, password_hash, display_name, role FROM app_users WHERE email = $1', [
    email.toLowerCase().trim(),
  ]);
  const u = rows[0];
  if (!u) return null;
  const ok = await bcrypt.compare(password, u.password_hash);
  if (!ok) return null;
  return { email: u.email, displayName: u.display_name || u.email, role: u.role || 'caller' };
}

export async function createSession(session: Session): Promise<void> {
  const exp = Math.floor(Date.now() / 1000) + MAX_AGE;
  const token = encode({ ...session, exp });
  const store = await cookies();
  store.set(COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: MAX_AGE,
  });
}

export async function destroySession(): Promise<void> {
  const store = await cookies();
  store.delete(COOKIE);
}

export async function getSession(): Promise<Session | null> {
  const store = await cookies();
  const token = store.get(COOKIE)?.value;
  if (!token) return null;
  const payload = decode(token);
  if (!payload) return null;
  return { email: payload.email, displayName: payload.displayName, role: payload.role };
}
