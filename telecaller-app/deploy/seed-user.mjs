// Generate an app_users upsert with a bcrypt-hashed password.
// Usage: node deploy/seed-user.mjs <email> "<Display Name>" "<password>"
// Pipe the printed SQL into psql (as the leads owner / admin), e.g.
//   node deploy/seed-user.mjs bhratti@amatec.in "Bhratti" "s3cret" \
//     | docker exec -i shared-postgres psql -U admin -d leads
import bcrypt from 'bcryptjs';

const [, , email, name, password] = process.argv;
if (!email || !name || !password) {
  console.error('usage: node deploy/seed-user.mjs <email> "<Display Name>" "<password>"');
  process.exit(1);
}

const hash = bcrypt.hashSync(password, 10);
const esc = (s) => s.replace(/'/g, "''");
console.log(
  `INSERT INTO app_users (email, password_hash, display_name, role) VALUES ` +
    `('${esc(email.toLowerCase())}', '${hash}', '${esc(name)}', 'caller') ` +
    `ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, display_name = EXCLUDED.display_name;`,
);
