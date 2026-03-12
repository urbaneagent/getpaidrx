import pool from './db.js';

export async function initDb(): Promise<void> {
  if (!pool) {
    console.log('No DATABASE_URL — running in in-memory mode (no database)');
    return;
  }

  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        name VARCHAR(255) NOT NULL,
        pharmacy_name VARCHAR(255),
        plan VARCHAR(20) DEFAULT 'free',
        claims_used INTEGER DEFAULT 0,
        comparisons_used INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS claims (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES users(id),
        claim_data JSONB NOT NULL,
        analysis_result JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
      )
    `);

    console.log('✅ Database schema ready');
  } catch (err) {
    console.error('Database initialization error:', err);
    throw err;
  } finally {
    client.release();
  }
}
