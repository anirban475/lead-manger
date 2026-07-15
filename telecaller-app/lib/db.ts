import { Pool } from 'pg';

// Singleton pool — reused across hot reloads in dev, one per container in prod.
const g = globalThis as unknown as { _pgPool?: Pool };

export const pool: Pool =
  g._pgPool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 5,
    idleTimeoutMillis: 30_000,
  });

if (process.env.NODE_ENV !== 'production') g._pgPool = pool;

export async function query<T = Record<string, unknown>>(
  text: string,
  params?: unknown[],
): Promise<T[]> {
  const res = await pool.query(text, params as unknown[] | undefined);
  return res.rows as T[];
}
