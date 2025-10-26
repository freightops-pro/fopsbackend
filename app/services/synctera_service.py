import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

class SyncteraService:
    def __init__(self):
        self.base_url = settings.SYNCTERA_BASE_URL
        self.api_key = settings.SYNCTERA_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if not self.api_key:
            logger.warning("SYNCTERA_API_KEY not found in environment variables")
        else:
            # Sanity check: log first few chars of the key
            logger.info(f"Synctera API key configured: {self.api_key[:8]}...")
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to Synctera API"""
        if not self.api_key:
            raise Exception("Synctera API key not configured")
        
        url = f"{self.base_url}{endpoint}"
        logger.info(f"Making {method} request to: {url}")
        logger.info(f"Using API key: {self.api_key[:8]}...")
        logger.info(f"Headers: {self.headers}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError as e:
                logger.error(f"Connection error to Synctera API: {str(e)}")
                raise Exception(f"Failed to connect to Synctera API: {str(e)}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Synctera API error: {e.response.status_code} - {e.response.text}")
                logger.error(f"Request URL: {url}")
                logger.error(f"Request headers: {self.headers}")
                raise Exception(f"Synctera API error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"Synctera API request failed: {str(e)}")
                raise
    
    async def create_person(self, business_data: Dict[str, Any]) -> str:
        """Create a person in Synctera for KYB"""
        endpoint = "/persons"
        
        # Format business data for Synctera
        person_data = {
            "legal_names": [business_data["control_person_name"]],  # Use control person name, not business name
            "address": {
                "line1": business_data["business_address"],
                "city": business_data["business_city"],
                "state": business_data["business_state"],
                "postal_code": business_data["business_zip_code"],
                "country": "US"
            },
            "status": "ACTIVE",
            "is_customer": False,  # The business is the customer, not the individual
            "is_controller": True,  # This person controls the business
            "is_beneficial_owner": True,  # Assuming control person is beneficial owner
            "is_authorized_signer": True  # Assuming control person can sign
        }
        
        # Only add optional fields if they are provided and not None/empty
        if business_data.get("email") and business_data["email"].strip():
            person_data["email"] = business_data["email"]
        if business_data.get("phone") and business_data["phone"].strip():
            person_data["phone_number"] = business_data["phone"]
        if business_data.get("ssn"):
            person_data["ssn"] = business_data["ssn"]
        if business_data.get("date_of_birth"):
            person_data["date_of_birth"] = business_data["date_of_birth"]
        
        response = await self._make_request("POST", endpoint, person_data)
        return response["id"]
    
    async def create_business(self, business_data: Dict[str, Any], person_id: str) -> str:
        """Create a business entity in Synctera"""
        endpoint = "/customers"
        
        business_entity_data = {
            "type": "BUSINESS",
            "legal_names": [business_data["legal_name"]],
            "address": {
                "line1": business_data["business_address"],
                "city": business_data["business_city"],
                "state": business_data["business_state"],
                "postal_code": business_data["business_zip_code"],
                "country": "US"
            },
            "ein": business_data["ein"],
            "formation_state": business_data["business_state"],
            "structure": "LLC",  # Default to LLC, can be made configurable
            "status": "ACTIVE"
        }
        
        # Add optional fields if provided
        if business_data.get("email"):
            business_entity_data["email"] = business_data["email"]
        if business_data.get("phone"):
            business_entity_data["phone_number"] = business_data["phone"]
        if business_data.get("website"):
            business_entity_data["website"] = business_data["website"]
        
        response = await self._make_request("POST", endpoint, business_entity_data)
        return response["id"]
    
    async def create_person_business_relationship(self, person_id: str, business_id: str, ownership_percentage: int = 100) -> str:
        """Create a relationship between person and business for KYB"""
        endpoint = "/relationships"
        
        relationship_data = {
            "from_person_id": person_id,
            "to_business_id": business_id,
            "relationship_type": "BENEFICIAL_OWNER_OF",
            "ownership_percentage": ownership_percentage,
            "additional_data": {
                "ownership_percentage": ownership_percentage
            }
        }
        
        response = await self._make_request("POST", endpoint, relationship_data)
        return response["id"]
    
    async def submit_kyb_application(self, business_id: str, person_id: str) -> str:
        """Submit KYB application for business verification"""
        # First, create the relationship between person and business
        await self.create_person_business_relationship(person_id, business_id)
        
        # Then submit KYB verification
        endpoint = "/verifications/verify"
        
        kyb_data = {
            "customer_consent": True,
            "customer_ip_address": "203.0.113.10",  # Default IP, can be made configurable
            "business_id": business_id
        }
        
        response = await self._make_request("POST", endpoint, kyb_data)
        return response["id"]
    
    async def get_kyb_status(self, business_id: str) -> Dict[str, Any]:
        """Get KYB verification status"""
        endpoint = f"/customers/{business_id}"
        
        response = await self._make_request("GET", endpoint)
        return response
    
    async def create_account(self, business_id: str, account_type: str = "checking") -> str:
        """Create a bank account for the business"""
        endpoint = "/accounts"
        
        account_data = {
            "type": "DEPOSITORY",
            "subtype": "CHECKING" if account_type == "checking" else "SAVINGS",
            "currency": "USD",
            "status": "ACTIVE",
            "customer_id": business_id,
            "account_holder": {
                "type": "BUSINESS",
                "customer_id": business_id
            }
        }
        
        response = await self._make_request("POST", endpoint, account_data)
        return response["id"]
    
    async def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        """Get account balance information"""
        endpoint = f"/accounts/{account_id}/balances"
        
        response = await self._make_request("GET", endpoint)
        return response
    
    async def create_card(self, account_id: str, card_type: str = "virtual") -> str:
        """Create a card for the account"""
        endpoint = "/cards"
        
        card_data = {
            "type": "PHYSICAL" if card_type == "physical" else "VIRTUAL",
            "status": "ACTIVE",
            "account_id": account_id,
            "currency": "USD"
        }
        
        response = await self._make_request("POST", endpoint, card_data)
        return response["id"]
    
    async def get_card_details(self, card_id: str) -> Dict[str, Any]:
        """Get card details (masked for security)"""
        endpoint = f"/cards/{card_id}"
        
        response = await self._make_request("GET", endpoint)
        return response
    
    async def update_card_status(self, card_id: str, status: str) -> Dict[str, Any]:
        """Update card status (active, suspended, etc.)"""
        endpoint = f"/cards/{card_id}"
        
        card_data = {
            "status": status.upper()
        }
        
        response = await self._make_request("PATCH", endpoint, card_data)
        return response
    
    async def get_account_transactions(self, account_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get account transactions"""
        endpoint = f"/accounts/{account_id}/transactions"
        
        params = {
            "limit": limit,
            "order": "desc"
        }
        
        response = await self._make_request("GET", endpoint, params=params)
        return response.get("transactions", [])
    
    async def create_transfer(self, from_account_id: str, to_account_id: str, amount: float, description: str = "") -> str:
        """Create a transfer between accounts"""
        endpoint = "/transfers"
        
        transfer_data = {
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": int(amount * 100),  # Convert to cents
            "currency": "USD",
            "description": description,
            "type": "ACH"
        }
        
        response = await self._make_request("POST", endpoint, transfer_data)
        return response["id"]
    
    async def get_transfer_status(self, transfer_id: str) -> Dict[str, Any]:
        """Get transfer status"""
        endpoint = f"/transfers/{transfer_id}"
        
        response = await self._make_request("GET", endpoint)
        return response
    
    async def create_ach_transfer(self, account_id: str, amount: float, recipient_data: Dict[str, Any]) -> str:
        """Create an ACH transfer to external account"""
        endpoint = "/transfers"
        
        transfer_data = {
            "from_account_id": account_id,
            "amount": int(amount * 100),  # Convert to cents
            "currency": "USD",
            "type": "ACH",
            "ach_details": {
                "routing_number": recipient_data["routing_number"],
                "account_number": recipient_data["account_number"],
                "account_type": "CHECKING",
                "description": recipient_data.get("description", "")
            }
        }
        
        response = await self._make_request("POST", endpoint, transfer_data)
        return response["id"]
    
    async def get_business_details(self, business_id: str) -> Dict[str, Any]:
        """Get business details"""
        endpoint = f"/customers/{business_id}"
        
        response = await self._make_request("GET", endpoint)
        return response
    
    async def update_business_details(self, business_id: str, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update business details"""
        endpoint = f"/customers/{business_id}"
        
        response = await self._make_request("PATCH", endpoint, business_data)
        return response
    
    async def list_accounts(self, business_id: str) -> List[Dict[str, Any]]:
        """List all accounts for a business"""
        endpoint = "/accounts"
        
        params = {
            "customer_id": business_id,
            "status": "ACTIVE"
        }
        
        response = await self._make_request("GET", endpoint, params=params)
        return response.get("accounts", [])
    
    async def list_cards(self, account_id: str) -> List[Dict[str, Any]]:
        """List all cards for an account"""
        endpoint = "/cards"
        
        params = {
            "account_id": account_id,
            "status": "ACTIVE"
        }
        
        response = await self._make_request("GET", endpoint, params=params)
        return response.get("cards", [])

# Global instance
synctera_service = SyncteraService()

