-- Link telecaller coaching agents to lead cockpit app_users by email.
--
-- Enables lead-manger cockpit to query telecaller performance metrics
-- from the telecaller_coaching database using the existing leads_user role.

BEGIN;

ALTER TABLE agents ADD COLUMN IF NOT EXISTS app_user_email text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_app_user_email
  ON agents (app_user_email)
  WHERE app_user_email IS NOT NULL;

UPDATE agents SET app_user_email = 'anirban@amatec.in' WHERE folder_name = 'anirban_sinha';
UPDATE agents SET app_user_email = 'bhratti@amatec.in' WHERE folder_name = 'bhratti_raval';
UPDATE agents SET app_user_email = 'paherwarharsha@gmail.com' WHERE folder_name = 'harsha_ahir';

-- telecaller_app is the role the app actually connects as; leads_user is belt and braces.
GRANT CONNECT ON DATABASE telecaller_coaching TO telecaller_app;
GRANT USAGE ON SCHEMA public TO telecaller_app;
GRANT SELECT ON agents, calls, chat_messages TO telecaller_app;

GRANT CONNECT ON DATABASE telecaller_coaching TO leads_user;
GRANT USAGE ON SCHEMA public TO leads_user;
GRANT SELECT ON agents, calls, chat_messages TO leads_user;

COMMIT;
