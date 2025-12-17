"""
Transfer Service - Internal, ACH, and Wire Transfers

Handles all money movement operations:
- Internal transfers (instant between Synctera accounts)
- ACH transfers (1-3 business days)
- Wire transfers (same day, with fees)
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from enum import Enum
import uuid
import httpx


class TransferType(str, Enum):
    INTERNAL = "internal"
    ACH = "ach"
    WIRE = "wire"


class TransferStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransferService:
    """
    Service for managing all types of money transfers.

    Integrates with Synctera API for actual transfer execution.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.synctera_api_key = None  # Load from env
        self.synctera_base_url = "https://api.synctera.com/v0"

    async def create_internal_transfer(
        self,
        company_id: str,
        from_account_id: str,
        to_account_id: str,
        amount: float,
        description: str,
        user_id: str,
        scheduled_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create an internal transfer between two Synctera accounts.

        Internal transfers are:
        - Instant (processed immediately)
        - Free (no fees)
        - Between accounts owned by same company

        Args:
            company_id: Company making the transfer
            from_account_id: Source Synctera account ID
            to_account_id: Destination Synctera account ID
            amount: Transfer amount (USD)
            description: Transfer description/memo
            user_id: User initiating transfer
            scheduled_date: Optional future date to execute

        Returns:
            {
                "transfer_id": "trn_xxx",
                "status": "completed",
                "processed_at": "2025-12-16T10:00:00Z"
            }
        """
        # Validate accounts belong to company
        from_account = await self._get_account(from_account_id)
        to_account = await self._get_account(to_account_id)

        if from_account['company_id'] != company_id or to_account['company_id'] != company_id:
            raise ValueError("Cannot transfer between accounts of different companies")

        # Check sufficient balance
        if from_account['available_balance'] < amount:
            raise ValueError(f"Insufficient funds. Available: ${from_account['available_balance']:.2f}")

        # Create transfer record
        transfer_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Determine status
        if scheduled_date and scheduled_date > now:
            status = TransferStatus.PENDING
            processed_at = None
        else:
            status = TransferStatus.PROCESSING
            processed_at = now

        await self.db.execute(
            """
            INSERT INTO banking_transfer (
                id, company_id, transfer_type, status,
                from_account_id, to_account_id, amount, currency,
                description, initiated_by, scheduled_date, processed_at,
                created_at, updated_at
            ) VALUES (
                :id, :company_id, :transfer_type, :status,
                :from_account_id, :to_account_id, :amount, :currency,
                :description, :initiated_by, :scheduled_date, :processed_at,
                :now, :now
            )
            """,
            {
                "id": transfer_id,
                "company_id": company_id,
                "transfer_type": TransferType.INTERNAL,
                "status": status,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "amount": amount,
                "currency": "USD",
                "description": description,
                "initiated_by": user_id,
                "scheduled_date": scheduled_date,
                "processed_at": processed_at,
                "now": now,
            }
        )

        # If not scheduled, execute immediately
        if not scheduled_date or scheduled_date <= now:
            await self._execute_internal_transfer(
                transfer_id, from_account_id, to_account_id, amount, description
            )

        await self.db.commit()

        return {
            "transfer_id": transfer_id,
            "status": status,
            "processed_at": processed_at.isoformat() if processed_at else None,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
        }

    async def _execute_internal_transfer(
        self,
        transfer_id: str,
        from_account_id: str,
        to_account_id: str,
        amount: float,
        description: str
    ):
        """
        Execute an internal transfer via Synctera API.

        Calls Synctera's /transfers endpoint to move money instantly.
        """
        # Call Synctera API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.synctera_base_url}/transfers",
                    headers={
                        "Authorization": f"Bearer {self.synctera_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "source_account_id": from_account_id,
                        "destination_account_id": to_account_id,
                        "amount": int(amount * 100),  # Convert to cents
                        "currency": "USD",
                        "memo": description,
                    }
                )

                if response.status_code == 201:
                    synctera_transfer = response.json()

                    # Update transfer record
                    await self.db.execute(
                        """
                        UPDATE banking_transfer
                        SET status = :status,
                            external_id = :external_id,
                            processed_at = :now,
                            updated_at = :now
                        WHERE id = :id
                        """,
                        {
                            "status": TransferStatus.COMPLETED,
                            "external_id": synctera_transfer['id'],
                            "now": datetime.utcnow(),
                            "id": transfer_id,
                        }
                    )

                    # Create transaction records for both accounts
                    await self._create_transaction_records(
                        from_account_id, to_account_id, amount, description,
                        synctera_transfer['id']
                    )

                else:
                    # Transfer failed
                    await self.db.execute(
                        """
                        UPDATE banking_transfer
                        SET status = :status,
                            error_message = :error,
                            updated_at = :now
                        WHERE id = :id
                        """,
                        {
                            "status": TransferStatus.FAILED,
                            "error": f"Synctera API error: {response.status_code}",
                            "now": datetime.utcnow(),
                            "id": transfer_id,
                        }
                    )

        except Exception as e:
            # Transfer failed
            await self.db.execute(
                """
                UPDATE banking_transfer
                SET status = :status,
                    error_message = :error,
                    updated_at = :now
                WHERE id = :id
                """,
                {
                    "status": TransferStatus.FAILED,
                    "error": str(e),
                    "now": datetime.utcnow(),
                    "id": transfer_id,
                }
            )

    async def _create_transaction_records(
        self,
        from_account_id: str,
        to_account_id: str,
        amount: float,
        description: str,
        synctera_transfer_id: str
    ):
        """Create transaction records for both accounts."""
        now = datetime.utcnow()

        # Debit from source account
        await self.db.execute(
            """
            INSERT INTO banking_transaction (
                id, account_id, external_id, amount, currency,
                description, transaction_type, status, posted_at,
                created_at, updated_at
            ) VALUES (
                :id, :account_id, :external_id, :amount, :currency,
                :description, :transaction_type, :status, :posted_at,
                :now, :now
            )
            """,
            {
                "id": str(uuid.uuid4()),
                "account_id": from_account_id,
                "external_id": f"{synctera_transfer_id}_debit",
                "amount": -amount,  # Negative for debit
                "currency": "USD",
                "description": f"Transfer to account: {description}",
                "transaction_type": "transfer_out",
                "status": "posted",
                "posted_at": now,
                "now": now,
            }
        )

        # Credit to destination account
        await self.db.execute(
            """
            INSERT INTO banking_transaction (
                id, account_id, external_id, amount, currency,
                description, transaction_type, status, posted_at,
                created_at, updated_at
            ) VALUES (
                :id, :account_id, :external_id, :amount, :currency,
                :description, :transaction_type, :status, :posted_at,
                :now, :now
            )
            """,
            {
                "id": str(uuid.uuid4()),
                "account_id": to_account_id,
                "external_id": f"{synctera_transfer_id}_credit",
                "amount": amount,  # Positive for credit
                "currency": "USD",
                "description": f"Transfer from account: {description}",
                "transaction_type": "transfer_in",
                "status": "posted",
                "posted_at": now,
                "now": now,
            }
        )

    async def create_ach_transfer(
        self,
        company_id: str,
        from_account_id: str,
        recipient_name: str,
        recipient_routing_number: str,
        recipient_account_number: str,
        recipient_account_type: str,  # 'checking' or 'savings'
        amount: float,
        description: str,
        user_id: str,
        save_recipient: bool = False,
        recipient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an ACH transfer to an external bank account.

        ACH transfers:
        - Take 1-3 business days
        - Have daily/monthly limits
        - May have small fees ($0-3)

        Args:
            company_id: Company making the transfer
            from_account_id: Source Synctera account
            recipient_name: Recipient name
            recipient_routing_number: 9-digit routing number
            recipient_account_number: Account number
            recipient_account_type: 'checking' or 'savings'
            amount: Transfer amount
            description: Transfer memo
            user_id: User initiating
            save_recipient: Whether to save for future use
            recipient_id: Optional existing recipient ID

        Returns:
            {
                "transfer_id": "trn_xxx",
                "status": "pending",
                "estimated_completion": "2025-12-19"
            }
        """
        # Validate account
        from_account = await self._get_account(from_account_id)
        if from_account['company_id'] != company_id:
            raise ValueError("Account does not belong to company")

        # Check balance
        if from_account['available_balance'] < amount:
            raise ValueError("Insufficient funds")

        # Check ACH limits (example: $25,000/day)
        daily_ach = await self._get_daily_ach_total(from_account_id)
        if daily_ach + amount > 25000:
            raise ValueError(f"Daily ACH limit exceeded. Available: ${25000 - daily_ach:.2f}")

        # Save recipient if requested
        if save_recipient and not recipient_id:
            recipient_id = await self._save_ach_recipient(
                company_id,
                recipient_name,
                recipient_routing_number,
                recipient_account_number,
                recipient_account_type
            )

        # Create transfer record
        transfer_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # ACH transfers complete in 1-3 business days
        estimated_completion = self._calculate_ach_completion(now)

        await self.db.execute(
            """
            INSERT INTO banking_transfer (
                id, company_id, transfer_type, status,
                from_account_id, amount, currency, description,
                recipient_name, recipient_routing_number,
                recipient_account_number, recipient_account_type,
                recipient_id, initiated_by, estimated_completion_date,
                created_at, updated_at
            ) VALUES (
                :id, :company_id, :transfer_type, :status,
                :from_account_id, :amount, :currency, :description,
                :recipient_name, :recipient_routing_number,
                :recipient_account_number, :recipient_account_type,
                :recipient_id, :initiated_by, :estimated_completion_date,
                :now, :now
            )
            """,
            {
                "id": transfer_id,
                "company_id": company_id,
                "transfer_type": TransferType.ACH,
                "status": TransferStatus.PENDING,
                "from_account_id": from_account_id,
                "amount": amount,
                "currency": "USD",
                "description": description,
                "recipient_name": recipient_name,
                "recipient_routing_number": recipient_routing_number,
                "recipient_account_number": recipient_account_number,
                "recipient_account_type": recipient_account_type,
                "recipient_id": recipient_id,
                "initiated_by": user_id,
                "estimated_completion_date": estimated_completion,
                "now": now,
            }
        )

        # Submit to Synctera
        await self._execute_ach_transfer(transfer_id)

        await self.db.commit()

        return {
            "transfer_id": transfer_id,
            "status": TransferStatus.PENDING,
            "estimated_completion": estimated_completion.date().isoformat(),
        }

    async def _execute_ach_transfer(self, transfer_id: str):
        """
        Execute ACH transfer via Synctera API.

        Synctera handles ACH processing, NACHA compliance, and settlement.
        """
        # Get transfer details
        result = await self.db.execute(
            """
            SELECT from_account_id, amount, recipient_name,
                   recipient_routing_number, recipient_account_number,
                   recipient_account_type, description
            FROM banking_transfer
            WHERE id = :id
            """,
            {"id": transfer_id}
        )
        row = result.fetchone()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.synctera_base_url}/ach/transfers",
                    headers={
                        "Authorization": f"Bearer {self.synctera_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "source_account_id": row[0],
                        "amount": int(row[1] * 100),
                        "currency": "USD",
                        "recipient": {
                            "name": row[2],
                            "routing_number": row[3],
                            "account_number": row[4],
                            "account_type": row[5],
                        },
                        "memo": row[6],
                    }
                )

                if response.status_code == 201:
                    synctera_ach = response.json()

                    await self.db.execute(
                        """
                        UPDATE banking_transfer
                        SET status = :status,
                            external_id = :external_id,
                            updated_at = :now
                        WHERE id = :id
                        """,
                        {
                            "status": TransferStatus.PROCESSING,
                            "external_id": synctera_ach['id'],
                            "now": datetime.utcnow(),
                            "id": transfer_id,
                        }
                    )
                else:
                    await self.db.execute(
                        """
                        UPDATE banking_transfer
                        SET status = :status,
                            error_message = :error,
                            updated_at = :now
                        WHERE id = :id
                        """,
                        {
                            "status": TransferStatus.FAILED,
                            "error": f"Synctera ACH error: {response.status_code}",
                            "now": datetime.utcnow(),
                            "id": transfer_id,
                        }
                    )

        except Exception as e:
            await self.db.execute(
                """
                UPDATE banking_transfer
                SET status = :status, error_message = :error, updated_at = :now
                WHERE id = :id
                """,
                {
                    "status": TransferStatus.FAILED,
                    "error": str(e),
                    "now": datetime.utcnow(),
                    "id": transfer_id,
                }
            )

    async def create_wire_transfer(
        self,
        company_id: str,
        from_account_id: str,
        recipient_name: str,
        recipient_routing_number: str,
        recipient_account_number: str,
        recipient_bank_name: str,
        amount: float,
        description: str,
        user_id: str,
        wire_type: str = "domestic",  # 'domestic' or 'international'
        recipient_swift_code: Optional[str] = None,
        recipient_address: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a wire transfer (domestic or international).

        Wire transfers:
        - Same day (domestic) or 1-2 days (international)
        - Higher fees: $25 domestic, $45 international
        - Require additional verification

        Args:
            company_id: Company making transfer
            from_account_id: Source account
            recipient_name: Recipient name
            recipient_routing_number: Routing/ABA number
            recipient_account_number: Account number
            recipient_bank_name: Bank name
            amount: Transfer amount
            description: Wire purpose
            user_id: User initiating
            wire_type: 'domestic' or 'international'
            recipient_swift_code: SWIFT code (for international)
            recipient_address: Recipient address (for international)

        Returns:
            {
                "transfer_id": "trn_xxx",
                "status": "pending",
                "fee_amount": 25.00
            }
        """
        # Validate account
        from_account = await self._get_account(from_account_id)
        if from_account['company_id'] != company_id:
            raise ValueError("Account does not belong to company")

        # Calculate fee
        fee = 25.00 if wire_type == "domestic" else 45.00

        # Check balance (amount + fee)
        if from_account['available_balance'] < (amount + fee):
            raise ValueError(f"Insufficient funds. Need ${amount + fee:.2f} (including ${fee:.2f} fee)")

        # Create transfer record
        transfer_id = str(uuid.uuid4())
        now = datetime.utcnow()

        await self.db.execute(
            """
            INSERT INTO banking_transfer (
                id, company_id, transfer_type, status,
                from_account_id, amount, currency, fee_amount,
                description, recipient_name, recipient_routing_number,
                recipient_account_number, recipient_bank_name,
                wire_type, recipient_swift_code, recipient_address,
                initiated_by, created_at, updated_at
            ) VALUES (
                :id, :company_id, :transfer_type, :status,
                :from_account_id, :amount, :currency, :fee_amount,
                :description, :recipient_name, :recipient_routing_number,
                :recipient_account_number, :recipient_bank_name,
                :wire_type, :recipient_swift_code, :recipient_address,
                :initiated_by, :now, :now
            )
            """,
            {
                "id": transfer_id,
                "company_id": company_id,
                "transfer_type": TransferType.WIRE,
                "status": TransferStatus.PENDING,
                "from_account_id": from_account_id,
                "amount": amount,
                "currency": "USD",
                "fee_amount": fee,
                "description": description,
                "recipient_name": recipient_name,
                "recipient_routing_number": recipient_routing_number,
                "recipient_account_number": recipient_account_number,
                "recipient_bank_name": recipient_bank_name,
                "wire_type": wire_type,
                "recipient_swift_code": recipient_swift_code,
                "recipient_address": recipient_address,
                "initiated_by": user_id,
                "now": now,
            }
        )

        # Wire transfers often require manual approval
        # This would integrate with Synctera's wire API
        # For now, mark as pending approval

        await self.db.commit()

        return {
            "transfer_id": transfer_id,
            "status": TransferStatus.PENDING,
            "fee_amount": fee,
        }

    async def _get_account(self, account_id: str) -> Dict[str, Any]:
        """Get account details."""
        result = await self.db.execute(
            """
            SELECT id, company_id, current_balance, available_balance
            FROM banking_account
            WHERE id = :id
            """,
            {"id": account_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Account {account_id} not found")

        return {
            "id": row[0],
            "company_id": row[1],
            "current_balance": float(row[2] or 0),
            "available_balance": float(row[3] or 0),
        }

    async def _get_daily_ach_total(self, account_id: str) -> float:
        """Get total ACH transfers for today."""
        today = datetime.utcnow().date()

        result = await self.db.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM banking_transfer
            WHERE from_account_id = :account_id
              AND transfer_type = 'ach'
              AND DATE(created_at) = :today
              AND status != 'failed'
              AND status != 'cancelled'
            """,
            {
                "account_id": account_id,
                "today": today,
            }
        )

        return float(result.scalar())

    def _calculate_ach_completion(self, start_date: datetime) -> datetime:
        """Calculate estimated ACH completion date (skip weekends)."""
        # ACH typically takes 1-3 business days
        # Use 2 business days as estimate
        days_added = 0
        current_date = start_date

        while days_added < 2:
            current_date += timedelta(days=1)
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                days_added += 1

        return current_date

    async def _save_ach_recipient(
        self,
        company_id: str,
        name: str,
        routing_number: str,
        account_number: str,
        account_type: str
    ) -> str:
        """Save ACH recipient for future use."""
        recipient_id = str(uuid.uuid4())

        await self.db.execute(
            """
            INSERT INTO banking_ach_recipient (
                id, company_id, name, routing_number,
                account_number, account_type, created_at
            ) VALUES (
                :id, :company_id, :name, :routing_number,
                :account_number, :account_type, :now
            )
            """,
            {
                "id": recipient_id,
                "company_id": company_id,
                "name": name,
                "routing_number": routing_number,
                "account_number": account_number,
                "account_type": account_type,
                "now": datetime.utcnow(),
            }
        )

        return recipient_id

    async def get_transfer_history(
        self,
        company_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent transfer history for a company."""
        result = await self.db.execute(
            """
            SELECT
                id, transfer_type, status, amount, fee_amount,
                description, recipient_name, created_at, processed_at
            FROM banking_transfer
            WHERE company_id = :company_id
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {
                "company_id": company_id,
                "limit": limit,
            }
        )

        transfers = []
        for row in result.fetchall():
            transfers.append({
                "id": row[0],
                "type": row[1],
                "status": row[2],
                "amount": float(row[3]),
                "fee": float(row[4]) if row[4] else 0.0,
                "description": row[5],
                "recipient": row[6],
                "created_at": row[7].isoformat(),
                "processed_at": row[8].isoformat() if row[8] else None,
            })

        return transfers
