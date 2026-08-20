-- Brand ownership vs brand eligibility.
--
-- leads.brand           = the single owner. Drives attribution, cost and CAC.
--                         Exactly one value, always. Never make this an array.
-- leads.eligible_brands = who is ALLOWED to work the lead. One or both brands.
--
-- The telecaller queue filters on eligibility. Everything that reports money
-- keeps reading `brand` and needs no change.

BEGIN;

ALTER TABLE leads ADD COLUMN IF NOT EXISTS eligible_brands text[];
UPDATE leads SET eligible_brands = ARRAY[brand] WHERE eligible_brands IS NULL AND brand IS NOT NULL;
UPDATE leads SET eligible_brands = ARRAY['jobdrive'] WHERE eligible_brands IS NULL;
ALTER TABLE leads ALTER COLUMN eligible_brands SET NOT NULL;
ALTER TABLE leads ALTER COLUMN eligible_brands SET DEFAULT ARRAY['jobdrive'];

-- cardinality(), not array_length(). array_length('{}',1) returns NULL and a
-- CHECK passes on NULL, so an empty array slips through and makes the lead
-- invisible to every caller. This bit us once during the original migration.
ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_eligible_brands_chk;
ALTER TABLE leads ADD CONSTRAINT leads_eligible_brands_chk
  CHECK (eligible_brands <@ ARRAY['amatec','jobdrive']
         AND cardinality(eligible_brands) >= 1);

CREATE INDEX IF NOT EXISTS leads_eligible_brands_gin ON leads USING GIN (eligible_brands);

-- Which brand each caller works. NULL with role='admin' means see everything.
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS brand text;
UPDATE app_users SET brand = 'jobdrive' WHERE brand IS NULL AND role <> 'admin';
ALTER TABLE app_users DROP CONSTRAINT IF EXISTS app_users_brand_chk;
ALTER TABLE app_users ADD CONSTRAINT app_users_brand_chk
  CHECK (brand IS NULL OR brand IN ('amatec','jobdrive'));

COMMIT;
