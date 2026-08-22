import { register } from 'node:module';
import { execSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

// Resolve environment variables if running outside container
if (!process.env.COACHING_DATABASE_URL && !process.env.DATABASE_URL) {
  try {
    const raw = execSync("docker inspect telecaller-app --format '{{json .Config.Env}}'", { encoding: 'utf8' });
    const envs = JSON.parse(raw);
    const dbEntry = envs.find((e) => e.startsWith('DATABASE_URL='));
    if (dbEntry) {
      const url = new URL(dbEntry.slice('DATABASE_URL='.length));
      url.hostname = '127.0.0.1';
      process.env.DATABASE_URL = url.toString();
    }
  } catch (err) {
    // Let coachingDb handle missing env
  }
} else {
  for (const varName of ['DATABASE_URL', 'COACHING_DATABASE_URL']) {
    if (process.env[varName]) {
      try {
        const u = new URL(process.env[varName]);
        if (u.hostname === 'shared-postgres') {
          try {
            execSync('getent hosts shared-postgres', { stdio: 'ignore' });
          } catch {
            u.hostname = '127.0.0.1';
            process.env[varName] = u.toString();
          }
        }
      } catch {}
    }
  }
}

// Module loader hook to allow Node ESM to resolve .ts files and extensionless imports
register(
  'data:text/javascript,' +
    encodeURIComponent(`
  import path from 'node:path';
  import fs from 'node:fs';

  export async function resolve(specifier, context, defaultResolve) {
    try {
      return await defaultResolve(specifier, context);
    } catch (err) {
      if (err.code === 'ERR_MODULE_NOT_FOUND' || err.code === 'ERR_UNSUPPORTED_DIR_IMPORT') {
        const parentDir = context.parentURL ? path.dirname(new URL(context.parentURL).pathname) : process.cwd();
        for (const ext of ['.ts', '.js', '.mjs', '/index.ts', '/index.js']) {
          const candidate = path.resolve(parentDir, specifier + ext);
          if (fs.existsSync(candidate)) {
            return defaultResolve(specifier + ext, context);
          }
        }
      }
      throw err;
    }
  }
`),
  import.meta.url,
);

async function run() {
  let currentStep = 'import lib/coachingQueries';
  try {
    const {
      listAgents,
      getAgentByEmail,
      getScorecard,
      getDailySeries,
      getLeaderboard,
      getTopCalls,
      getBottomCalls,
      getIssueCounts,
    } = await import('../lib/coachingQueries.ts');

    const to = new Date();
    const from = new Date(to.getTime() - 90 * 24 * 60 * 60 * 1000);

    console.log(`=== Telecaller Performance Data Layer Acceptance Check ===`);
    console.log(`Date window: 90 days (${from.toISOString().slice(0, 10)} to ${to.toISOString().slice(0, 10)})\n`);

    // 1. listAgents
    currentStep = 'listAgents';
    const agents = await listAgents();
    console.log(`--- 1. listAgents() ---`);
    console.log(JSON.stringify(agents, null, 2));
    console.log();

    // 2. getAgentByEmail
    currentStep = 'getAgentByEmail';
    const bhratti = await getAgentByEmail('bhratti@amatec.in');
    console.log(`--- 2. getAgentByEmail('bhratti@amatec.in') ---`);
    console.log(JSON.stringify(bhratti, null, 2));
    console.log();

    if (!bhratti || !bhratti.id) {
      throw new Error(`Agent with app_user_email = 'bhratti@amatec.in' not found`);
    }
    const bhrattiId = bhratti.id;

    // 3. getScorecard
    currentStep = 'getScorecard (All Agents)';
    const scorecardAll = await getScorecard(null, from, to);
    console.log(`--- 3. getScorecard(null, from, to) [All Agents] ---`);
    console.log(JSON.stringify(scorecardAll, null, 2));
    console.log();

    currentStep = 'getScorecard (Bhratti Raval)';
    const scorecardBhratti = await getScorecard(bhrattiId, from, to);
    console.log(`--- 4. getScorecard(${bhrattiId}, from, to) [Bhratti Raval] ---`);
    console.log(JSON.stringify(scorecardBhratti, null, 2));
    console.log();

    // 4. getDailySeries
    currentStep = 'getDailySeries (All Agents)';
    const dailyAll = await getDailySeries(null, from, to);
    console.log(`--- 5. getDailySeries(null, from, to) [All Agents, total days: ${dailyAll.length}] ---`);
    console.log(JSON.stringify(dailyAll.slice(0, 5), null, 2));
    console.log('... (showing first 5 days)');
    console.log();

    currentStep = 'getDailySeries (Bhratti Raval)';
    const dailyBhratti = await getDailySeries(bhrattiId, from, to);
    console.log(`--- 6. getDailySeries(${bhrattiId}, from, to) [Bhratti Raval, total days: ${dailyBhratti.length}] ---`);
    console.log(JSON.stringify(dailyBhratti.slice(0, 5), null, 2));
    console.log('... (showing first 5 days)');
    console.log();

    // 5. getLeaderboard
    currentStep = 'getLeaderboard';
    const leaderboard = await getLeaderboard(from, to);
    console.log(`--- 7. getLeaderboard(from, to) ---`);
    console.log(JSON.stringify(leaderboard, null, 2));
    console.log();

    // 6. getTopCalls
    currentStep = 'getTopCalls (All Agents)';
    const topCallsAll = await getTopCalls(null, from, to, 3);
    console.log(`--- 8. getTopCalls(null, from, to, 3) [All Agents] ---`);
    console.log(JSON.stringify(topCallsAll, null, 2));
    console.log();

    currentStep = 'getTopCalls (Bhratti Raval)';
    const topCallsBhratti = await getTopCalls(bhrattiId, from, to, 3);
    console.log(`--- 9. getTopCalls(${bhrattiId}, from, to, 3) [Bhratti Raval] ---`);
    console.log(JSON.stringify(topCallsBhratti, null, 2));
    console.log();

    // 7. getBottomCalls
    currentStep = 'getBottomCalls (All Agents)';
    const bottomCallsAll = await getBottomCalls(null, from, to, 3);
    console.log(`--- 10. getBottomCalls(null, from, to, 3) [All Agents] ---`);
    console.log(JSON.stringify(bottomCallsAll, null, 2));
    console.log();

    currentStep = 'getBottomCalls (Bhratti Raval)';
    const bottomCallsBhratti = await getBottomCalls(bhrattiId, from, to, 3);
    console.log(`--- 11. getBottomCalls(${bhrattiId}, from, to, 3) [Bhratti Raval] ---`);
    console.log(JSON.stringify(bottomCallsBhratti, null, 2));
    console.log();

    // 8. getIssueCounts
    currentStep = 'getIssueCounts (All Agents)';
    const issuesAll = await getIssueCounts(null, from, to, 5);
    console.log(`--- 12. getIssueCounts(null, from, to, 5) [All Agents] ---`);
    console.log(JSON.stringify(issuesAll, null, 2));
    console.log();

    currentStep = 'getIssueCounts (Bhratti Raval)';
    const issuesBhratti = await getIssueCounts(bhrattiId, from, to, 5);
    console.log(`--- 13. getIssueCounts(${bhrattiId}, from, to, 5) [Bhratti Raval] ---`);
    console.log(JSON.stringify(issuesBhratti, null, 2));
    console.log();

    // Acceptance condition validation
    const topPerformer = leaderboard.find((r) => r.calls > 900);
    if (!topPerformer) {
      console.error(`ERROR: Leaderboard does not contain any agent with >900 calls in the 90-day window.`);
      process.exit(1);
    }

    console.log(`=== Acceptance Criteria Verified ===`);
    console.log(`Top agent: ${topPerformer.name} with ${topPerformer.calls} calls (avg score: ${topPerformer.avg_score}).`);
    console.log(`All queries executed successfully.`);
    process.exit(0);
  } catch (err) {
    console.error(`FAILED: ${currentStep}: ${err.message}`);
    process.exit(1);
  }
}

run();
