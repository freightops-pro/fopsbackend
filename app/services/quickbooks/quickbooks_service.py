"""QuickBooks service for managing QuickBooks integrations and syncing data."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import CompanyIntegration
from app.services.quickbooks.quickbooks_client import QuickBooksAPIClient

logger = logging.getLogger(__name__)


class QuickBooksService:
    """Service for managing QuickBooks Online integrations."""

    def __init__(self, db: AsyncSession):
        """Initialize QuickBooks service."""
        self.db = db

    async def get_client(
        self, integration: CompanyIntegration, sandbox: bool = True
    ) -> QuickBooksAPIClient:
        """
        Get QuickBooks API client for an integration.

        Args:
            integration: CompanyIntegration instance
            sandbox: Whether to use sandbox environment

        Returns:
            QuickBooksAPIClient instance
        """
        if not integration.credentials:
            raise ValueError("Integration credentials not found")

        client_id = integration.credentials.get("client_id")
        client_secret = integration.credentials.get("client_secret")
        access_token = integration.credentials.get("access_token")
        refresh_token = integration.credentials.get("refresh_token")
        # Check both credentials and config for realm_id
        realm_id = integration.credentials.get("realm_id")
        if not realm_id and integration.config:
            realm_id = integration.config.get("realm_id")
        sandbox = integration.credentials.get("sandbox", True)

        if not client_id or not client_secret:
            raise ValueError("QuickBooks client credentials not configured")

        return QuickBooksAPIClient(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            realm_id=realm_id,
            sandbox=sandbox if isinstance(sandbox, bool) else True,
        )

    async def test_connection(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """
        Test QuickBooks connection by fetching company info.

        Args:
            integration: CompanyIntegration instance

        Returns:
            Connection test result
        """
        try:
            client = await self.get_client(integration)
            company_info = await client.get_company_info()
            return {
                "success": True,
                "company_name": company_info.get("CompanyInfo", {}).get("CompanyName"),
                "message": "Connection successful",
            }
        except Exception as e:
            logger.error(f"QuickBooks connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    async def sync_customers(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Sync customers from QuickBooks."""
        try:
            client = await self.get_client(integration)
            response = await client.get_customers(max_results=100)
            customers = response.get("QueryResponse", {}).get("Customer", [])
            
            # TODO: Map and store customers in local database
            # This would integrate with your Customer model
            
            return {
                "success": True,
                "count": len(customers) if isinstance(customers, list) else 1,
                "message": f"Synced {len(customers) if isinstance(customers, list) else 1} customers",
            }
        except Exception as e:
            logger.error(f"QuickBooks customer sync failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    async def sync_invoices(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Sync invoices from QuickBooks."""
        try:
            client = await self.get_client(integration)
            response = await client.get_invoices(max_results=100)
            invoices = response.get("QueryResponse", {}).get("Invoice", [])
            
            # TODO: Map and store invoices in local database
            # This would integrate with your Invoice model
            
            return {
                "success": True,
                "count": len(invoices) if isinstance(invoices, list) else 1,
                "message": f"Synced {len(invoices) if isinstance(invoices, list) else 1} invoices",
            }
        except Exception as e:
            logger.error(f"QuickBooks invoice sync failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    async def sync_payments(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Sync payments from QuickBooks."""
        try:
            client = await self.get_client(integration)
            response = await client.get_payments(max_results=100)
            payments = response.get("QueryResponse", {}).get("Payment", [])
            
            # TODO: Map and store payments in local database
            
            return {
                "success": True,
                "count": len(payments) if isinstance(payments, list) else 1,
                "message": f"Synced {len(payments) if isinstance(payments, list) else 1} payments",
            }
        except Exception as e:
            logger.error(f"QuickBooks payment sync failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    async def sync_accounts(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Sync accounts (Chart of Accounts) from QuickBooks."""
        try:
            client = await self.get_client(integration)
            response = await client.get_accounts(max_results=100)
            accounts = response.get("QueryResponse", {}).get("Account", [])
            
            # TODO: Map and store accounts in local database
            # This would integrate with your Chart of Accounts model
            
            return {
                "success": True,
                "count": len(accounts) if isinstance(accounts, list) else 1,
                "message": f"Synced {len(accounts) if isinstance(accounts, list) else 1} accounts",
            }
        except Exception as e:
            logger.error(f"QuickBooks account sync failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    async def sync_vendors(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Sync vendors from QuickBooks."""
        try:
            client = await self.get_client(integration)
            response = await client.get_vendors(max_results=100)
            vendors = response.get("QueryResponse", {}).get("Vendor", [])

            return {
                "success": True,
                "count": len(vendors) if isinstance(vendors, list) else 1,
                "data": vendors,
                "message": f"Synced {len(vendors) if isinstance(vendors, list) else 1} vendors",
            }
        except Exception as e:
            logger.error(f"QuickBooks vendor sync failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    async def sync_bills(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Sync bills (payables) from QuickBooks."""
        try:
            client = await self.get_client(integration)
            response = await client.get_bills(max_results=100)
            bills = response.get("QueryResponse", {}).get("Bill", [])

            return {
                "success": True,
                "count": len(bills) if isinstance(bills, list) else 1,
                "data": bills,
                "message": f"Synced {len(bills) if isinstance(bills, list) else 1} bills",
            }
        except Exception as e:
            logger.error(f"QuickBooks bill sync failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    async def full_sync(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Perform a full sync of all QuickBooks data."""
        results = {
            "success": True,
            "synced_at": datetime.utcnow().isoformat(),
            "entities": {},
            "errors": [],
        }

        # Sync all entity types
        sync_tasks = [
            ("customers", self.sync_customers),
            ("vendors", self.sync_vendors),
            ("invoices", self.sync_invoices),
            ("bills", self.sync_bills),
            ("payments", self.sync_payments),
            ("accounts", self.sync_accounts),
        ]

        for entity_name, sync_func in sync_tasks:
            try:
                result = await sync_func(integration)
                results["entities"][entity_name] = {
                    "success": result.get("success", False),
                    "count": result.get("count", 0),
                    "message": result.get("message", ""),
                }
                if not result.get("success"):
                    results["errors"].append(f"{entity_name}: {result.get('message')}")
            except Exception as e:
                results["entities"][entity_name] = {
                    "success": False,
                    "count": 0,
                    "message": str(e),
                }
                results["errors"].append(f"{entity_name}: {str(e)}")

        results["success"] = len(results["errors"]) == 0
        return results

    async def get_sync_summary(self, integration: CompanyIntegration) -> Dict[str, Any]:
        """Get summary of QuickBooks data for display."""
        try:
            client = await self.get_client(integration)

            # Get company info
            company_info = await client.get_company_info()
            company = company_info.get("CompanyInfo", {})

            # Get counts for each entity type
            customers_resp = await client.get_customers(max_results=1)
            invoices_resp = await client.get_invoices(max_results=1)
            vendors_resp = await client.get_vendors(max_results=1)
            bills_resp = await client.get_bills(max_results=1)

            return {
                "success": True,
                "company_name": company.get("CompanyName"),
                "company_country": company.get("Country"),
                "counts": {
                    "customers": customers_resp.get("QueryResponse", {}).get("totalCount", 0),
                    "invoices": invoices_resp.get("QueryResponse", {}).get("totalCount", 0),
                    "vendors": vendors_resp.get("QueryResponse", {}).get("totalCount", 0),
                    "bills": bills_resp.get("QueryResponse", {}).get("totalCount", 0),
                },
            }
        except Exception as e:
            logger.error(f"QuickBooks sync summary failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }

    # ========== PUSH TO QUICKBOOKS (Export from local system) ==========

    async def push_invoice_to_quickbooks(
        self, integration: CompanyIntegration, invoice_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Push/export an invoice from local system to QuickBooks.

        Args:
            integration: CompanyIntegration instance
            invoice_data: Local invoice data to push
                {
                    "customer_ref_id": "123",  # QuickBooks Customer ID
                    "invoice_date": "2024-01-15",
                    "due_date": "2024-02-15",
                    "line_items": [
                        {
                            "description": "Freight charge",
                            "amount": 1500.00,
                            "account_ref": "1"  # Income account
                        }
                    ],
                    "total_amount": 1500.00,
                    "quickbooks_invoice_id": None  # For updates
                }

        Returns:
            Result with QuickBooks invoice ID
        """
        try:
            client = await self.get_client(integration)

            # Map local invoice to QuickBooks format
            qb_invoice = {
                "CustomerRef": {"value": str(invoice_data["customer_ref_id"])},
                "TxnDate": invoice_data["invoice_date"],
                "DueDate": invoice_data.get("due_date"),
                "Line": []
            }

            # Add line items
            line_num = 1
            for item in invoice_data.get("line_items", []):
                qb_invoice["Line"].append({
                    "LineNum": line_num,
                    "Amount": item["amount"],
                    "DetailType": "SalesItemLineDetail",
                    "Description": item.get("description", ""),
                    "SalesItemLineDetail": {
                        "Qty": item.get("quantity", 1),
                        "UnitPrice": item.get("unit_price", item["amount"]),
                        "ItemRef": {"value": item.get("item_ref", "1")}  # Service item
                    }
                })
                line_num += 1

            # Create or update invoice
            if invoice_data.get("quickbooks_invoice_id"):
                # Update existing invoice
                qb_invoice["Id"] = str(invoice_data["quickbooks_invoice_id"])
                qb_invoice["SyncToken"] = invoice_data.get("sync_token", "0")
                result = await client.update_invoice(qb_invoice)
            else:
                # Create new invoice
                result = await client.create_invoice(qb_invoice)

            return {
                "success": True,
                "quickbooks_invoice_id": result.get("Invoice", {}).get("Id"),
                "sync_token": result.get("Invoice", {}).get("SyncToken"),
                "message": "Invoice pushed to QuickBooks successfully"
            }
        except Exception as e:
            logger.error(f"Failed to push invoice to QuickBooks: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e)
            }

    async def push_payment_to_quickbooks(
        self, integration: CompanyIntegration, payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record a payment in QuickBooks.

        Args:
            integration: CompanyIntegration instance
            payment_data: Payment information
                {
                    "customer_ref_id": "123",
                    "total_amount": 1500.00,
                    "payment_date": "2024-01-20",
                    "payment_method": "Check",
                    "reference_number": "CHK-001",
                    "linked_invoices": [
                        {"invoice_id": "456", "amount_paid": 1500.00}
                    ]
                }
        """
        try:
            client = await self.get_client(integration)

            qb_payment = {
                "CustomerRef": {"value": str(payment_data["customer_ref_id"])},
                "TotalAmt": payment_data["total_amount"],
                "TxnDate": payment_data["payment_date"],
            }

            if payment_data.get("payment_method"):
                # Get payment method ref (you may need to map this)
                qb_payment["PaymentMethodRef"] = {"value": payment_data["payment_method"]}

            if payment_data.get("reference_number"):
                qb_payment["PaymentRefNum"] = payment_data["reference_number"]

            # Link to invoices being paid
            if payment_data.get("linked_invoices"):
                qb_payment["Line"] = []
                for invoice in payment_data["linked_invoices"]:
                    qb_payment["Line"].append({
                        "Amount": invoice["amount_paid"],
                        "LinkedTxn": [{
                            "TxnId": str(invoice["invoice_id"]),
                            "TxnType": "Invoice"
                        }]
                    })

            result = await client.create_payment(qb_payment)

            return {
                "success": True,
                "quickbooks_payment_id": result.get("Payment", {}).get("Id"),
                "message": "Payment recorded in QuickBooks successfully"
            }
        except Exception as e:
            logger.error(f"Failed to push payment to QuickBooks: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e)
            }

    async def push_expense_to_quickbooks(
        self, integration: CompanyIntegration, expense_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create an expense record in QuickBooks (for fuel, etc.).

        Args:
            integration: CompanyIntegration instance
            expense_data: Expense information
                {
                    "vendor_ref_id": "789",  # Fuel vendor
                    "transaction_date": "2024-01-15",
                    "total_amount": 250.00,
                    "payment_method": "CreditCard",
                    "line_items": [
                        {
                            "description": "Diesel fuel",
                            "amount": 250.00,
                            "account_ref": "60"  # Fuel expense account
                        }
                    ]
                }
        """
        try:
            client = await self.get_client(integration)

            qb_expense = {
                "TxnDate": expense_data["transaction_date"],
                "TotalAmt": expense_data["total_amount"],
                "Line": []
            }

            if expense_data.get("vendor_ref_id"):
                qb_expense["EntityRef"] = {
                    "value": str(expense_data["vendor_ref_id"]),
                    "type": "Vendor"
                }

            if expense_data.get("payment_method"):
                qb_expense["PaymentType"] = expense_data["payment_method"]

            # Add expense line items
            for item in expense_data.get("line_items", []):
                qb_expense["Line"].append({
                    "Amount": item["amount"],
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Description": item.get("description", ""),
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": str(item.get("account_ref", "60"))}
                    }
                })

            result = await client.create_purchase(qb_expense)

            return {
                "success": True,
                "quickbooks_expense_id": result.get("Purchase", {}).get("Id"),
                "message": "Expense created in QuickBooks successfully"
            }
        except Exception as e:
            logger.error(f"Failed to push expense to QuickBooks: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e)
            }

    async def push_bill_to_quickbooks(
        self, integration: CompanyIntegration, bill_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a bill in QuickBooks.

        Args:
            integration: CompanyIntegration instance
            bill_data: Bill information
                {
                    "vendor_ref_id": "789",
                    "transaction_date": "2024-01-15",
                    "due_date": "2024-02-15",
                    "total_amount": 2500.00,
                    "line_items": [
                        {
                            "description": "Maintenance service",
                            "amount": 2500.00,
                            "account_ref": "65"  # Maintenance expense account
                        }
                    ],
                    "quickbooks_bill_id": None  # For updates
                }
        """
        try:
            client = await self.get_client(integration)

            qb_bill = {
                "VendorRef": {"value": str(bill_data["vendor_ref_id"])},
                "TxnDate": bill_data["transaction_date"],
                "DueDate": bill_data.get("due_date"),
                "Line": []
            }

            # Add line items
            for item in bill_data.get("line_items", []):
                qb_bill["Line"].append({
                    "Amount": item["amount"],
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Description": item.get("description", ""),
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {"value": str(item.get("account_ref", "65"))}
                    }
                })

            # Create or update bill
            if bill_data.get("quickbooks_bill_id"):
                qb_bill["Id"] = str(bill_data["quickbooks_bill_id"])
                qb_bill["SyncToken"] = bill_data.get("sync_token", "0")
                result = await client.update_bill(qb_bill)
            else:
                result = await client.create_bill(qb_bill)

            return {
                "success": True,
                "quickbooks_bill_id": result.get("Bill", {}).get("Id"),
                "sync_token": result.get("Bill", {}).get("SyncToken"),
                "message": "Bill pushed to QuickBooks successfully"
            }
        except Exception as e:
            logger.error(f"Failed to push bill to QuickBooks: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e)
            }

    async def push_batch_to_quickbooks(
        self, integration: CompanyIntegration, batch_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Push multiple items to QuickBooks in a batch.

        Args:
            integration: CompanyIntegration instance
            batch_data: Dictionary with lists of items to push
                {
                    "invoices": [...],
                    "payments": [...],
                    "expenses": [...],
                    "bills": [...]
                }

        Returns:
            Summary of push results
        """
        results = {
            "success": True,
            "pushed_at": datetime.utcnow().isoformat(),
            "entities": {},
            "errors": []
        }

        # Push invoices
        if batch_data.get("invoices"):
            invoice_results = []
            for invoice in batch_data["invoices"]:
                result = await self.push_invoice_to_quickbooks(integration, invoice)
                invoice_results.append(result)
                if not result["success"]:
                    results["errors"].append(f"Invoice: {result['message']}")

            results["entities"]["invoices"] = {
                "total": len(invoice_results),
                "successful": sum(1 for r in invoice_results if r["success"]),
                "failed": sum(1 for r in invoice_results if not r["success"])
            }

        # Push payments
        if batch_data.get("payments"):
            payment_results = []
            for payment in batch_data["payments"]:
                result = await self.push_payment_to_quickbooks(integration, payment)
                payment_results.append(result)
                if not result["success"]:
                    results["errors"].append(f"Payment: {result['message']}")

            results["entities"]["payments"] = {
                "total": len(payment_results),
                "successful": sum(1 for r in payment_results if r["success"]),
                "failed": sum(1 for r in payment_results if not r["success"])
            }

        # Push expenses
        if batch_data.get("expenses"):
            expense_results = []
            for expense in batch_data["expenses"]:
                result = await self.push_expense_to_quickbooks(integration, expense)
                expense_results.append(result)
                if not result["success"]:
                    results["errors"].append(f"Expense: {result['message']}")

            results["entities"]["expenses"] = {
                "total": len(expense_results),
                "successful": sum(1 for r in expense_results if r["success"]),
                "failed": sum(1 for r in expense_results if not r["success"])
            }

        # Push bills
        if batch_data.get("bills"):
            bill_results = []
            for bill in batch_data["bills"]:
                result = await self.push_bill_to_quickbooks(integration, bill)
                bill_results.append(result)
                if not result["success"]:
                    results["errors"].append(f"Bill: {result['message']}")

            results["entities"]["bills"] = {
                "total": len(bill_results),
                "successful": sum(1 for r in bill_results if r["success"]),
                "failed": sum(1 for r in bill_results if not r["success"])
            }

        results["success"] = len(results["errors"]) == 0
        return results

