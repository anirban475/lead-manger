import { query } from './db';

export type AppUser = {
  id: number;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
};

export async function listUsers(): Promise<AppUser[]> {
  return query<AppUser>(
    'SELECT id, email, display_name, role, is_active, created_at::text AS created_at FROM app_users ORDER BY id ASC',
  );
}
