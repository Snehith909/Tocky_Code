/**
 * Vulnerable TypeScript test fixture for CodeGuard AI evaluation.
 * Demonstrates SQL injection in query builder.
 */

export class DatabaseService {
  private db: any;

  constructor(db: any) {
    this.db = db;
  }

  public async getUserAccount(userId: string): Promise<any> {
    // Vulnerability: SQL Injection via template string interpolation
    return this.db.query(`SELECT * FROM users WHERE id = ${userId}`);
  }
}
