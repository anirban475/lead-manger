import { Pool } from 'pg';

function getCoachingConnectionString(): string {
  if (process.env.COACHING_DATABASE_URL) {
    return process.env.COACHING_DATABASE_URL;
  }
  if (process.env.DATABASE_URL) {
    try {
      const url = new URL(process.env.DATABASE_URL);
      url.pathname = '/telecaller_coaching';
      return url.toString();
    } catch {
      return process.env.DATABASE_URL.replace(/\/[^/?]+(\?.*)?$/, '/telecaller_coaching$1');
    }
  }
  throw new Error('Neither COACHING_DATABASE_URL nor DATABASE_URL environment variable is set');
}

// Singleton pool — reused across hot reloads in dev, one per container in prod.
const g = globalThis as unknown as { _coachingPgPool?: Pool };

export const coachingPool: Pool =
  g._coachingPgPool ??
  new Pool({
    connectionString: getCoachingConnectionString(),
    max: 5,
    idleTimeoutMillis: 30_000,
  });

if (process.env.NODE_ENV !== 'production') g._coachingPgPool = coachingPool;

export async function coachingQuery<T = Record<string, unknown>>(
  text: string,
  params?: unknown[],
): Promise<T[]> {
  const res = await coachingPool.query(text, params as unknown[] | undefined);
  return res.rows as T[];
}
