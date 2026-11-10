"""
Storage manager extensions for MCP server integration.
Adds methods for retrieving findings by ID and recording patch applications.
"""

from typing import Optional, Dict, Any, List
from codeguard.storage import StorageManager as BaseStorageManager


class MCPStorageManager(BaseStorageManager):
    """Extended storage manager with MCP-specific methods."""
    
    def get_finding_by_id(self, finding_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific finding by its ID."""
        if not self.conn:
            return None
        
        cursor = self.conn.execute(
            """
            SELECT * FROM findings 
            WHERE id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
            """,
            (finding_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row[1],
            "tool": row[2],
            "rule_id": row[3],
            "language": row[4],
            "file": row[5],
            "start_line": row[6],
            "end_line": row[7],
            "severity": row[8],
            "message": row[9],
            "evidence": row[10],
            "fingerprint": row[11],
            "status": row[12],
            "cwe": row[13] if len(row) > 13 else None
        }
    
    def get_recent_findings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent findings from the last scan."""
        if not self.conn:
            return []
        
        cursor = self.conn.execute(
            """
            SELECT * FROM findings 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (limit,)
        )
        
        findings = []
        for row in cursor.fetchall():
            findings.append({
                "id": row[1],
                "tool": row[2],
                "rule_id": row[3],
                "language": row[4],
                "file": row[5],
                "start_line": row[6],
                "end_line": row[7],
                "severity": row[8],
                "message": row[9],
                "evidence": row[10],
                "fingerprint": row[11],
                "status": row[12],
                "cwe": row[13] if len(row) > 13 else None
            })
        
        return findings
    
    def record_patch_application(self, vulnerability_id: str, file_path: str, status: str):
        """Record that a patch was applied for a vulnerability."""
        if not self.conn:
            return
        
        try:
            self.conn.execute(
                """
                INSERT INTO patch_applications (vulnerability_id, file_path, status, timestamp)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (vulnerability_id, file_path, status)
            )
            self.conn.commit()
        except Exception:
            # Table might not exist, create it
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS patch_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vulnerability_id TEXT,
                    file_path TEXT,
                    status TEXT,
                    timestamp TEXT
                )
                """
            )
            self.conn.execute(
                """
                INSERT INTO patch_applications (vulnerability_id, file_path, status, timestamp)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (vulnerability_id, file_path, status)
            )
            self.conn.commit()
    
    def record_verification_result(self, vulnerability_id: str, result: Dict[str, Any]):
        """Record the result of a verification check."""
        if not self.conn:
            return
        
        try:
            self.conn.execute(
                """
                INSERT INTO verification_results (vulnerability_id, status, details, timestamp)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (vulnerability_id, result['status'], str(result))
            )
            self.conn.commit()
        except Exception:
            # Table might not exist, create it
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vulnerability_id TEXT,
                    status TEXT,
                    details TEXT,
                    timestamp TEXT
                )
                """
            )
            self.conn.execute(
                """
                INSERT INTO verification_results (vulnerability_id, status, details, timestamp)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (vulnerability_id, result['status'], str(result))
            )
            self.conn.commit()
