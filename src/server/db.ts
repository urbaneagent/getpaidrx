import { Pool } from 'pg';

// Pool is null when DATABASE_URL is not set (local dev / test environment)
const pool: Pool | null = process.env.DATABASE_URL
  ? new Pool({
      connectionString: process.env.DATABASE_URL,
      ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
    })
  : null;

export default pool;
