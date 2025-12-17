"""
Bank Reconciliation Service - Auto-matching Algorithm

Matches external bank transactions (Plaid/Synctera) with internal ledger entries
to ensure books are balanced and detect discrepancies.

Algorithm:
1. Exact match (amount + date + description)
2. Fuzzy match (amount + date ± 2 days + partial description)
3. Manual review queue for unmatched
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from fuzzywuzzy import fuzz
import re


class ReconciliationService:
    """
    Automated bank reconciliation service.

    Matches transactions from multiple sources:
    - Plaid transactions (external banks)
    - Banking transactions (Synctera internal accounts)
    - Ledger entries (accounting system)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconcile_account(
        self,
        account_id: str,
        account_type: str,  # 'plaid' or 'synctera'
        start_date: datetime,
        end_date: datetime,
        auto_approve_threshold: float = 0.95
    ) -> Dict[str, Any]:
        """
        Reconcile an account for a date range.

        Args:
            account_id: Plaid account ID or Synctera account ID
            account_type: 'plaid' or 'synctera'
            start_date: Start of reconciliation period
            end_date: End of reconciliation period
            auto_approve_threshold: Confidence score to auto-match (0.0-1.0)

        Returns:
            {
                "matched": 45,
                "unmatched_bank": 5,
                "unmatched_ledger": 3,
                "confidence_scores": {
                    "exact": 30,
                    "high": 15,
                    "medium": 0,
                    "low": 0
                }
            }
        """
        # Fetch bank transactions
        bank_transactions = await self._get_bank_transactions(
            account_id, account_type, start_date, end_date
        )

        # Fetch ledger entries
        ledger_entries = await self._get_ledger_entries(
            account_id, account_type, start_date, end_date
        )

        # Match transactions
        matches = []
        unmatched_bank = []
        unmatched_ledger = list(ledger_entries)

        confidence_scores = {
            "exact": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        for bank_tx in bank_transactions:
            # Try to find a match
            best_match = await self._find_best_match(
                bank_tx, unmatched_ledger
            )

            if best_match and best_match['confidence'] >= auto_approve_threshold:
                # Auto-approve high confidence matches
                matches.append({
                    "bank_transaction_id": bank_tx['id'],
                    "ledger_entry_id": best_match['ledger_entry']['id'],
                    "confidence": best_match['confidence'],
                    "match_reason": best_match['reason'],
                })

                # Remove from unmatched
                unmatched_ledger = [
                    entry for entry in unmatched_ledger
                    if entry['id'] != best_match['ledger_entry']['id']
                ]

                # Categorize confidence
                if best_match['confidence'] == 1.0:
                    confidence_scores['exact'] += 1
                elif best_match['confidence'] >= 0.95:
                    confidence_scores['high'] += 1
                elif best_match['confidence'] >= 0.80:
                    confidence_scores['medium'] += 1
                else:
                    confidence_scores['low'] += 1

            else:
                # No match or low confidence
                unmatched_bank.append(bank_tx)

        # Store matches in database
        for match in matches:
            await self._record_match(
                account_type,
                match['bank_transaction_id'],
                match['ledger_entry_id'],
                match['confidence'],
                match['match_reason']
            )

        await self.db.commit()

        return {
            "matched": len(matches),
            "unmatched_bank": len(unmatched_bank),
            "unmatched_ledger": len(unmatched_ledger),
            "confidence_scores": confidence_scores,
            "unmatched_bank_transactions": unmatched_bank,
            "unmatched_ledger_entries": unmatched_ledger,
        }

    async def _get_bank_transactions(
        self,
        account_id: str,
        account_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch bank transactions for reconciliation."""
        if account_type == 'plaid':
            result = await self.db.execute(
                """
                SELECT
                    id, transaction_id, amount, date,
                    description, merchant_name, pending, reconciled
                FROM plaid_transaction
                WHERE account_id = :account_id
                  AND date BETWEEN :start_date AND :end_date
                  AND reconciled = false
                ORDER BY date ASC
                """,
                {
                    "account_id": account_id,
                    "start_date": start_date.date(),
                    "end_date": end_date.date(),
                }
            )
        else:  # synctera
            result = await self.db.execute(
                """
                SELECT
                    id, external_id as transaction_id, amount, posted_at as date,
                    description, merchant_name, status as pending, reconciled
                FROM banking_transaction
                WHERE account_id = :account_id
                  AND posted_at BETWEEN :start_date AND :end_date
                  AND reconciled = false
                ORDER BY posted_at ASC
                """,
                {
                    "account_id": account_id,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

        transactions = []
        for row in result.fetchall():
            transactions.append({
                "id": row[0],
                "transaction_id": row[1],
                "amount": float(row[2]),
                "date": row[3],
                "description": row[4] or "",
                "merchant_name": row[5] or "",
                "pending": row[6],
                "reconciled": row[7],
            })

        return transactions

    async def _get_ledger_entries(
        self,
        account_id: str,
        account_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch unreconciled ledger entries."""
        # Get company_id from account
        if account_type == 'plaid':
            account_result = await self.db.execute(
                "SELECT company_id, ledger_account_code FROM plaid_account WHERE id = :id",
                {"id": account_id}
            )
        else:
            account_result = await self.db.execute(
                "SELECT company_id FROM banking_account WHERE id = :id",
                {"id": account_id}
            )

        account_row = account_result.fetchone()
        if not account_row:
            return []

        company_id = account_row[0]
        ledger_account_code = account_row[1] if account_type == 'plaid' else None

        # Fetch ledger entries
        # Note: This assumes you have a ledger_entry table
        # Adjust the query based on your actual schema
        result = await self.db.execute(
            """
            SELECT
                id, amount, entry_date, description, reference_number
            FROM ledger_entry
            WHERE company_id = :company_id
              AND entry_date BETWEEN :start_date AND :end_date
              AND reconciled = false
            ORDER BY entry_date ASC
            """,
            {
                "company_id": company_id,
                "start_date": start_date.date(),
                "end_date": end_date.date(),
            }
        )

        entries = []
        for row in result.fetchall():
            entries.append({
                "id": row[0],
                "amount": float(row[1]),
                "date": row[2],
                "description": row[3] or "",
                "reference": row[4] or "",
            })

        return entries

    async def _find_best_match(
        self,
        bank_tx: Dict[str, Any],
        ledger_entries: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best matching ledger entry for a bank transaction.

        Matching algorithm:
        1. Exact amount match
        2. Date within ± 2 days
        3. Description similarity > 80%

        Returns:
            {
                "ledger_entry": {...},
                "confidence": 0.95,
                "reason": "Exact amount + date + high description match"
            }
        """
        if not ledger_entries:
            return None

        best_match = None
        best_confidence = 0.0

        for entry in ledger_entries:
            confidence = 0.0
            reasons = []

            # 1. Amount match (40% weight)
            amount_diff = abs(bank_tx['amount'] - entry['amount'])
            if amount_diff == 0:
                confidence += 0.40
                reasons.append("exact amount")
            elif amount_diff < 0.01:  # Within 1 cent
                confidence += 0.35
                reasons.append("near amount")

            # 2. Date match (30% weight)
            bank_date = bank_tx['date'] if isinstance(bank_tx['date'], datetime) else datetime.fromisoformat(str(bank_tx['date']))
            entry_date = entry['date'] if isinstance(entry['date'], datetime) else datetime.fromisoformat(str(entry['date']))

            date_diff = abs((bank_date - entry_date).days)
            if date_diff == 0:
                confidence += 0.30
                reasons.append("same date")
            elif date_diff <= 1:
                confidence += 0.25
                reasons.append("±1 day")
            elif date_diff <= 2:
                confidence += 0.15
                reasons.append("±2 days")

            # 3. Description similarity (30% weight)
            bank_desc = self._normalize_description(
                bank_tx['description'] or bank_tx.get('merchant_name', '')
            )
            ledger_desc = self._normalize_description(entry['description'])

            if bank_desc and ledger_desc:
                similarity = fuzz.ratio(bank_desc, ledger_desc) / 100.0
                confidence += similarity * 0.30

                if similarity > 0.9:
                    reasons.append("high description match")
                elif similarity > 0.7:
                    reasons.append("good description match")
                elif similarity > 0.5:
                    reasons.append("partial description match")

            # Update best match
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {
                    "ledger_entry": entry,
                    "confidence": confidence,
                    "reason": " + ".join(reasons) if reasons else "low match",
                }

        return best_match

    def _normalize_description(self, text: str) -> str:
        """
        Normalize transaction description for comparison.

        Removes common noise:
        - Transaction IDs
        - Dates
        - Extra whitespace
        - Special characters
        """
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove transaction IDs (patterns like #123456)
        text = re.sub(r'#\d+', '', text)

        # Remove dates (MM/DD/YYYY, YYYY-MM-DD)
        text = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', text)
        text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters except spaces
        text = re.sub(r'[^a-z0-9\s]', '', text)

        return text.strip()

    async def _record_match(
        self,
        account_type: str,
        bank_transaction_id: str,
        ledger_entry_id: str,
        confidence: float,
        reason: str
    ):
        """Record a successful match in the database."""
        now = datetime.utcnow()

        # Update bank transaction
        if account_type == 'plaid':
            await self.db.execute(
                """
                UPDATE plaid_transaction
                SET matched_ledger_entry_id = :ledger_id,
                    reconciled = true,
                    reconciled_at = :now
                WHERE id = :id
                """,
                {
                    "ledger_id": ledger_entry_id,
                    "now": now,
                    "id": bank_transaction_id,
                }
            )
        else:
            await self.db.execute(
                """
                UPDATE banking_transaction
                SET matched_ledger_entry_id = :ledger_id,
                    reconciled = true,
                    reconciled_at = :now
                WHERE id = :id
                """,
                {
                    "ledger_id": ledger_entry_id,
                    "now": now,
                    "id": bank_transaction_id,
                }
            )

        # Update ledger entry
        await self.db.execute(
            """
            UPDATE ledger_entry
            SET reconciled = true,
                reconciled_at = :now
            WHERE id = :id
            """,
            {
                "now": now,
                "id": ledger_entry_id,
            }
        )

    async def manual_match(
        self,
        account_type: str,
        bank_transaction_id: str,
        ledger_entry_id: str,
        user_id: str
    ):
        """
        Manually match a bank transaction to a ledger entry.

        Used when auto-matching fails or confidence is too low.
        """
        await self._record_match(
            account_type,
            bank_transaction_id,
            ledger_entry_id,
            confidence=1.0,  # Manual match = 100% confidence
            reason="Manual match by user"
        )

        # Log the manual match
        await self.db.execute(
            """
            UPDATE plaid_transaction
            SET reconciled_by = :user_id
            WHERE id = :id
            """ if account_type == 'plaid' else """
            UPDATE banking_transaction
            SET reconciled_by = :user_id
            WHERE id = :id
            """,
            {
                "user_id": user_id,
                "id": bank_transaction_id,
            }
        )

        await self.db.commit()

    async def unmatch(
        self,
        account_type: str,
        bank_transaction_id: str
    ):
        """
        Undo a reconciliation match.

        Useful when a match was incorrect.
        """
        # Get the ledger entry ID first
        if account_type == 'plaid':
            result = await self.db.execute(
                "SELECT matched_ledger_entry_id FROM plaid_transaction WHERE id = :id",
                {"id": bank_transaction_id}
            )
        else:
            result = await self.db.execute(
                "SELECT matched_ledger_entry_id FROM banking_transaction WHERE id = :id",
                {"id": bank_transaction_id}
            )

        row = result.fetchone()
        if not row or not row[0]:
            return  # Not matched

        ledger_entry_id = row[0]

        # Unmatch bank transaction
        if account_type == 'plaid':
            await self.db.execute(
                """
                UPDATE plaid_transaction
                SET matched_ledger_entry_id = NULL,
                    reconciled = false,
                    reconciled_at = NULL,
                    reconciled_by = NULL
                WHERE id = :id
                """,
                {"id": bank_transaction_id}
            )
        else:
            await self.db.execute(
                """
                UPDATE banking_transaction
                SET matched_ledger_entry_id = NULL,
                    reconciled = false,
                    reconciled_at = NULL
                WHERE id = :id
                """,
                {"id": bank_transaction_id}
            )

        # Unmatch ledger entry
        await self.db.execute(
            """
            UPDATE ledger_entry
            SET reconciled = false,
                reconciled_at = NULL
            WHERE id = :id
            """,
            {"id": ledger_entry_id}
        )

        await self.db.commit()

    async def get_reconciliation_summary(
        self,
        company_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get reconciliation summary for a company.

        Returns:
            {
                "total_bank_transactions": 100,
                "total_ledger_entries": 95,
                "matched": 90,
                "unmatched_bank": 10,
                "unmatched_ledger": 5,
                "match_rate": 0.90,
                "accounts": [
                    {
                        "account_name": "Operating Account",
                        "matched": 50,
                        "unmatched": 5
                    }
                ]
            }
        """
        # Count total bank transactions (Plaid + Synctera)
        plaid_result = await self.db.execute(
            """
            SELECT COUNT(*) FROM plaid_transaction pt
            JOIN plaid_account pa ON pa.id = pt.account_id
            WHERE pa.company_id = :company_id
              AND pt.date BETWEEN :start_date AND :end_date
            """,
            {
                "company_id": company_id,
                "start_date": start_date.date(),
                "end_date": end_date.date(),
            }
        )
        plaid_count = plaid_result.scalar()

        synctera_result = await self.db.execute(
            """
            SELECT COUNT(*) FROM banking_transaction bt
            JOIN banking_account ba ON ba.id = bt.account_id
            WHERE ba.company_id = :company_id
              AND bt.posted_at BETWEEN :start_date AND :end_date
            """,
            {
                "company_id": company_id,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        synctera_count = synctera_result.scalar()

        total_bank = plaid_count + synctera_count

        # Count matched
        plaid_matched = await self.db.execute(
            """
            SELECT COUNT(*) FROM plaid_transaction pt
            JOIN plaid_account pa ON pa.id = pt.account_id
            WHERE pa.company_id = :company_id
              AND pt.date BETWEEN :start_date AND :end_date
              AND pt.reconciled = true
            """,
            {
                "company_id": company_id,
                "start_date": start_date.date(),
                "end_date": end_date.date(),
            }
        )
        plaid_matched_count = plaid_matched.scalar()

        synctera_matched = await self.db.execute(
            """
            SELECT COUNT(*) FROM banking_transaction bt
            JOIN banking_account ba ON ba.id = bt.account_id
            WHERE ba.company_id = :company_id
              AND bt.posted_at BETWEEN :start_date AND :end_date
              AND bt.reconciled = true
            """,
            {
                "company_id": company_id,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        synctera_matched_count = synctera_matched.scalar()

        total_matched = plaid_matched_count + synctera_matched_count

        # Count ledger entries
        ledger_result = await self.db.execute(
            """
            SELECT COUNT(*) FROM ledger_entry
            WHERE company_id = :company_id
              AND entry_date BETWEEN :start_date AND :end_date
            """,
            {
                "company_id": company_id,
                "start_date": start_date.date(),
                "end_date": end_date.date(),
            }
        )
        total_ledger = ledger_result.scalar()

        match_rate = total_matched / total_bank if total_bank > 0 else 0.0

        return {
            "total_bank_transactions": total_bank,
            "total_ledger_entries": total_ledger,
            "matched": total_matched,
            "unmatched_bank": total_bank - total_matched,
            "unmatched_ledger": total_ledger - total_matched,
            "match_rate": match_rate,
        }
