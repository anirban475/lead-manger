ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS offer        text,
  ADD COLUMN IF NOT EXISTS trigger_type text,
  ADD COLUMN IF NOT EXISTS buyer_level  text,
  ADD COLUMN IF NOT EXISTS country      char(2);

ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_buyer_level_chk;
ALTER TABLE leads ADD CONSTRAINT leads_buyer_level_chk
  CHECK (buyer_level IS NULL OR buyer_level IN ('owner','head','individual'));
