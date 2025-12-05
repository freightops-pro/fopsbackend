"""Motive API client for interacting with api.gomotive.com."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MotiveAPIClient:
    """Client for interacting with Motive API (api.gomotive.com)."""

    BASE_URL = "https://api.gomotive.com"
    OAUTH_TOKEN_URL = "https://api.gomotive.com/v1/auth/token"

    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize Motive API client.

        Args:
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None

    async def _get_access_token(self) -> str:
        """Get or refresh access token using OAuth 2.0 client credentials flow."""
        if self._access_token:
            return self._access_token

        async with httpx.AsyncClient() as client:
            try:
                # OAuth 2.0 client credentials flow
                response = await client.post(
                    self.OAUTH_TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                self._access_token = data.get("access_token")
                if not self._access_token:
                    raise ValueError("No access_token in response")
                return self._access_token
            except httpx.HTTPError as e:
                logger.error(f"Motive auth error: {str(e)}")
                raise

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Motive API."""
        token = await self._get_access_token()
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    params=params,
                    json=json_data,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Motive API error {e.response.status_code}: {e.response.text}")
                raise
            except httpx.HTTPError as e:
                logger.error(f"Motive request error: {str(e)}")
                raise

    async def get_vehicles(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        List all the vehicles of a company.

        Use this API to fetch a list of all vehicles belonging to your company.

        Args:
            limit: Maximum number of vehicles to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing:
            - vehicles: Array of vehicle objects, each containing:
                - id: Unique identifier for the vehicle
                - company_id: ID of the company that owns the vehicle
                - number: The vehicle's assigned number or name
                - status: Current status of the vehicle (e.g., "active")
                - ifta: Indicates whether the vehicle is IFTA-registered
                - vin: The Vehicle Identification Number (VIN)
                - make: The make of the vehicle
                - model: The model of the vehicle
                - year: The manufacturing year of the vehicle
                - license_plate_state: The state where the vehicle's license plate is registered
                - license_plate_number: The vehicle's license plate number
                - metric_units: Indicates if the vehicle uses metric units
                - fuel_type: The type of fuel used by the vehicle
                - group_ids: List of group IDs associated with the vehicle
                - created_at: The timestamp when the vehicle was created
                - updated_at: The timestamp when the vehicle was last updated
                - eld_device: Information about the vehicle's ELD device
                - current_driver: Information about the vehicle's current driver
                - external_ids: List of external system IDs associated with the vehicle
                - availability_details: Availability details object

        Reference:
            https://developer.gomotive.com/reference/list-all-the-company-vehicles
        """
        return await self._request(
            "GET",
            "/v1/vehicles",
            params={"limit": limit, "offset": offset},
        )

    async def get_assets(
        self,
        name: Optional[str] = None,
        status: Optional[str] = None,
        exact_match: bool = False,
        per_page: int = 25,
        page_no: int = 1,
    ) -> Dict[str, Any]:
        """
        Get list of assets (trailers, reefers, etc.).

        Args:
            name: Optional asset name to filter by
            status: Optional status filter (active, deactivated)
            exact_match: If True, search with exact casing of name
            per_page: Number of records per page (default: 25)
            page_no: Page number (default: 1)

        Returns:
            Response containing assets list
        """
        params = {
            "exact_match": str(exact_match).lower(),
            "per_page": per_page,
            "page_no": page_no,
        }
        if name:
            params["name"] = name
        if status:
            params["status"] = status

        return await self._request("GET", "/v1/assets", params=params)

    async def lookup_asset_by_external_id(
        self, external_id: str, integration_name: str
    ) -> Dict[str, Any]:
        """
        Lookup an asset using its external ID.

        Args:
            external_id: The external identifier for the asset
            integration_name: The name of the integration with which the external ID is associated

        Returns:
            Asset details

        Reference:
            https://developer.gomotive.com/reference/lookup-an-asset-using-an-external-id
        """
        return await self._request(
            "GET",
            "/v1/assets/lookup_by_external_id",
            params={
                "external_id": external_id,
                "integration_name": integration_name,
            },
        )

    async def create_asset(
        self,
        name: str,
        asset_type: str,
        make: str,
        model: str,
        year: str,
        external_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a new asset in Motive.

        Required fields: name, type, make, model, year

        Args:
            name: Asset name
            asset_type: Type of asset (e.g., "flatbed", "reefer", "lowboy", "auto_hauler")
            make: Manufacturer of the asset
            model: Model of the asset
            year: Year the asset was manufactured
            external_id: Optional external ID to link with external systems
            integration_name: Name of integration for external ID (e.g., "freightops")
            **kwargs: Additional optional fields (vin, license_plate_state, license_plate_number,
                     axle, weight_metric_units, length_metric_units, leased, notes, length,
                     gvwr, gawr, custom_type, etc.)

        Returns:
            Created asset details

        Reference:
            https://developer.gomotive.com/reference/create-a-new-asset
        """
        payload: Dict[str, Any] = {
            "name": name,
            "type": asset_type,
            "make": make,
            "model": model,
            "year": year,
        }

        # Add external ID if provided
        if external_id and integration_name:
            payload["external_ids_attributes"] = [
                {
                    "external_id": external_id,
                    "integration_name": integration_name,
                }
            ]

        # Add any additional fields
        payload.update(kwargs)

        return await self._request("POST", "/v1/assets", json_data=payload)

    async def update_asset(
        self,
        asset_id: str,
        external_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        status: Optional[str] = None,
        group_ids: Optional[List[int]] = None,
        availability_status: Optional[str] = None,
        out_of_service_reason: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update an existing asset in Motive.

        Allows updating:
        - External ID attributes
        - Status
        - Group IDs
        - Lease information
        - Corresponding Gateway ID
        - VIN
        - Availability Details

        Args:
            asset_id: Motive asset ID
            external_id: Optional external ID to add/update
            integration_name: Name of integration for external ID (required if external_id provided)
            status: Asset status (e.g., "active", "deactivated")
            group_ids: List of group IDs to assign to the asset
            availability_status: Availability status ("in_service" or "out_of_service")
            out_of_service_reason: Reason for being out of service
            **kwargs: Additional fields to update (name, type, make, model, year, vin,
                     license_plate_state, license_plate_number, leased, notes, length,
                     gvwr, gawr, custom_type, asset_gateway_id, etc.)

        Returns:
            Updated asset details

        Reference:
            https://developer.gomotive.com/reference/update-an-existing-asset
        """
        payload: Dict[str, Any] = {}

        # Add external ID if provided
        if external_id and integration_name:
            payload["external_ids_attributes"] = [
                {
                    "external_id": external_id,
                    "integration_name": integration_name,
                }
            ]

        # Add status if provided
        if status:
            payload["status"] = status

        # Add group IDs if provided
        if group_ids:
            payload["group_ids"] = group_ids

        # Add availability details if provided
        if availability_status:
            availability_details: Dict[str, Any] = {
                "availability_status": availability_status,
            }
            if out_of_service_reason:
                availability_details["out_of_service_reason"] = out_of_service_reason
            payload["availability_details"] = availability_details

        # Add any additional fields
        payload.update(kwargs)

        return await self._request("PUT", f"/v1/assets/{asset_id}", json_data=payload)

    async def get_vehicle(self, vehicle_id: str) -> Dict[str, Any]:
        """
        List the details of a vehicle (ID).

        Use this API to fetch the details of a vehicle using a unique vehicle ID. This API
        is useful when you have the vehicle ID and need complete vehicle information.

        Args:
            vehicle_id: Motive vehicle ID

        Returns:
            Response containing:
            - vehicle: Vehicle object with complete details including:
                - id: Unique identifier for the vehicle
                - company_id: ID of the company that owns the vehicle
                - number: The vehicle's assigned number or name
                - status: Current status of the vehicle (e.g., "active")
                - ifta: Indicates whether the vehicle is IFTA-registered
                - vin: The Vehicle Identification Number (VIN)
                - make: The make of the vehicle
                - model: The model of the vehicle
                - year: The manufacturing year of the vehicle
                - license_plate_state: The state where the vehicle's license plate is registered
                - license_plate_number: The vehicle's license plate number
                - metric_units: Indicates if the vehicle uses metric units
                - fuel_type: The type of fuel used by the vehicle
                - prevent_auto_odometer_entry: Indicates if auto-odometer entry is disabled
                - group_ids: List of group IDs associated with the vehicle
                - created_at: The timestamp when the vehicle was created
                - updated_at: The timestamp when the vehicle was last updated
                - eld_device: Information about the vehicle's ELD device
                - current_driver: Information about the vehicle's current driver
                - external_ids: List of external system IDs associated with the vehicle
                - availability_details: Availability details object

        Reference:
            https://developer.gomotive.com/reference/list-the-details-of-a-vehicle-id
        """
        return await self._request("GET", f"/v1/vehicles/{vehicle_id}")

    async def lookup_vehicle_by_number(self, number: str) -> Dict[str, Any]:
        """
        Lookup a vehicle by its number.

        Use this API to search for a vehicle using its number that is assigned in the Motive
        system. The endpoint will fetch details of that particular vehicle such as:
        - status
        - license number
        - make
        - fuel type used
        - vehicle gateway details (if assigned)
        - driver details

        Args:
            number: Vehicle number assigned in the Motive system

        Returns:
            Response containing:
            - vehicle: Vehicle object with complete details including:
                - id: The unique identifier for the vehicle
                - company_id: The unique identifier for the company associated with the vehicle
                - number: The name or number of the vehicle
                - status: The current status of the vehicle (e.g., "active")
                - ifta: Indicates whether the vehicle is subject to IFTA
                - vin: The Vehicle Identification Number
                - make: The make of the vehicle
                - model: The model of the vehicle
                - year: The year of manufacture of the vehicle
                - license_plate_state: The state where the vehicle's license plate is registered
                - license_plate_number: The license plate number of the vehicle
                - metric_units: Indicates whether the vehicle uses metric units
                - fuel_type: The type of fuel used by the vehicle (e.g., "diesel")
                - prevent_auto_odometer_entry: Indicates whether automatic odometer entries are prevented
                - created_at: The timestamp when the vehicle was created
                - updated_at: The timestamp when the vehicle details were last updated
                - eld_device: Contains details about the vehicle gateway associated with the vehicle:
                    - id: The unique identifier for the vehicle gateway
                    - identifier: The identifier of the vehicle gateway
                    - model: The model of the vehicle gateway
                - current_driver: Contains details about the current driver of the vehicle:
                    - id: The unique identifier for the driver
                    - first_name: The first name of the driver
                    - last_name: The last name of the driver
                    - username: The username of the driver
                    - email: The email address of the driver (if available)
                    - driver_company_id: The unique identifier for the company associated with the driver (if available)
                    - status: The current status of the driver (e.g., "active")
                    - role: The role of the current user (e.g., "driver")
                - external_ids: An array of external identifiers associated with the vehicle
                - availability_details: Availability details object

        Reference:
            https://developer.gomotive.com/reference/lookup-a-vehicle-by-its-number
        """
        params = {"number": number}
        return await self._request("GET", "/v1/vehicles/lookup", params=params)

    async def lookup_vehicle_by_external_id(
        self,
        external_id: str,
        integration_name: str,
    ) -> Dict[str, Any]:
        """
        Lookup a vehicle by external identifier.

        Use this API to search for a vehicle using its external identifier that is assigned
        by a third-party system. An external ID is associated with an integration. You must
        mention both the `external_id` and the `integration_name`, as the system will use
        the information to pull out the relevant vehicle details.

        This endpoint will fetch the details of the vehicle such as:
        - status
        - license number
        - make
        - fuel type used
        - vehicle gateway details (if assigned)
        - driver details

        Args:
            external_id: External identifier assigned by a third-party system
            integration_name: Name of the integration associated with the external ID

        Returns:
            Response containing:
            - vehicle: Vehicle object with complete details including:
                - id: The unique identifier for the vehicle
                - company_id: The unique identifier for the company associated with the vehicle
                - number: The name or number of the vehicle
                - status: The current status of the vehicle (e.g., "active")
                - ifta: Indicates whether the vehicle is subject to IFTA
                - vin: The Vehicle Identification Number
                - make: The make of the vehicle
                - model: The model of the vehicle
                - year: The year of manufacture of the vehicle
                - license_plate_state: The state where the vehicle's license plate is registered
                - license_plate_number: The license plate number of the vehicle
                - metric_units: Indicates whether the vehicle uses metric units
                - fuel_type: The type of fuel used by the vehicle (e.g., "diesel")
                - prevent_auto_odometer_entry: Indicates whether automatic odometer entries are prevented
                - created_at: The timestamp when the vehicle was created
                - updated_at: The timestamp when the vehicle details were last updated
                - eld_device: Contains details about the vehicle gateway associated with the vehicle:
                    - id: The unique identifier for the vehicle gateway
                    - identifier: The identifier of the vehicle gateway
                    - model: The model of the vehicle gateway
                - current_driver: Contains details about the current driver of the vehicle:
                    - id: The unique identifier for the driver
                    - first_name: The first name of the driver
                    - last_name: The last name of the driver
                    - username: The username of the driver
                    - email: The email address of the driver (if available)
                    - driver_company_id: The unique identifier for the company associated with the driver (if available)
                    - status: The current status of the driver (e.g., "active")
                    - role: The role of the current user (e.g., "driver")
                - external_ids: An array of external identifiers associated with the vehicle

        Reference:
            https://developer.gomotive.com/reference/lookup-a-vehicle-by-external-identifier
        """
        params = {
            "external_id": external_id,
            "integration_name": integration_name,
        }
        return await self._request("GET", "/v1/vehicles/lookup_by_external_id", params=params)

    async def create_vehicle(
        self,
        number: str,
        status: str = "active",
        ifta: Optional[bool] = None,
        vin: Optional[str] = None,
        make: Optional[str] = None,
        model: Optional[str] = None,
        year: Optional[str] = None,
        license_plate_state: Optional[str] = None,
        license_plate_number: Optional[str] = None,
        metric_units: Optional[bool] = None,
        fuel_type: Optional[str] = None,
        notes: Optional[str] = None,
        group_ids: Optional[List[int]] = None,
        eld_device: Optional[Dict[str, Any]] = None,
        current_driver: Optional[Dict[str, Any]] = None,
        external_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        availability_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new vehicle.

        Use this API to create a new vehicle in your company. You can specify various
        attributes including vehicle identification, ELD device assignment, current driver,
        and external IDs for integration with external systems.

        Args:
            number: Fleet number assigned to the vehicle (required)
            status: Status of the vehicle (default: "active")
            ifta: Optional - indicates whether the vehicle is subject to IFTA reporting
            vin: Optional Vehicle Identification Number (VIN)
            make: Optional manufacturer of the vehicle (e.g., "Ford")
            model: Optional model of the vehicle (e.g., "Expedition")
            year: Optional year the vehicle was manufactured (e.g., "2024")
            license_plate_state: Optional state of the vehicle's license plate
            license_plate_number: Optional license plate number
            metric_units: Optional - indicates whether the vehicle's measurements are in metric units
            fuel_type: Optional type of fuel the vehicle uses (e.g., "diesel")
            notes: Optional notes about the vehicle
            group_ids: Optional list of group IDs to assign the vehicle to
            eld_device: Optional ELD device information:
                - id: ID of the vehicle gateway
                - identifier: Unique identifier of the vehicle gateway
                - model: Model of the vehicle gateway
            current_driver: Optional current driver information:
                - id: Unique identifier of the driver
                - first_name: First name of the driver
                - last_name: Last name of the driver
                - username: Username assigned to the driver
                - email: Email address of the driver
                - driver_company_id: ID of the driver assigned by the company
                - status: Status of the driver (e.g., "active")
                - role: Role of the user (e.g., "driver")
            external_id: Optional external ID for tracking this vehicle in external systems
            integration_name: Optional name of the integration for external ID (required if external_id provided)
            availability_details: Optional availability details:
                - availability_status: "out_of_service" or "in_service"
                - out_of_service_reason: Reason for being out of service
                - additional_note: Comments or notes
                - custom_driver_app_warning_prompt: Prompt message for drivers

        Returns:
            Response containing:
            - vehicle: Created vehicle object with all details including:
                - id: Unique identifier assigned to the vehicle
                - company_id: Unique identifier of the company
                - number: Fleet number assigned to the vehicle
                - status: Status of the vehicle
                - ifta: Indicates whether the vehicle is subject to IFTA reporting
                - vin: Vehicle Identification Number
                - make: Manufacturer of the vehicle
                - model: Model of the vehicle
                - year: Year the vehicle was manufactured
                - license_plate_state: State of the vehicle's license plate
                - license_plate_number: License plate number
                - metric_units: Indicates whether the vehicle's measurements are in metric units
                - fuel_type: Type of fuel the vehicle uses
                - group_ids: List of group IDs assigned to the vehicle
                - created_at: Timestamp when the vehicle was created
                - updated_at: Timestamp when the vehicle was last updated
                - eld_device: ELD device associated with the vehicle
                - current_driver: Current driver of the vehicle
                - external_ids: List of external identifiers associated with the vehicle
                - availability_details: Availability details object

        Reference:
            https://developer.gomotive.com/reference/create-a-vehicle
        """
        payload: Dict[str, Any] = {
            "number": number,
            "status": status,
        }

        if ifta is not None:
            payload["ifta"] = ifta
        if vin:
            payload["vin"] = vin
        if make:
            payload["make"] = make
        if model:
            payload["model"] = model
        if year:
            payload["year"] = year
        if license_plate_state:
            payload["license_plate_state"] = license_plate_state
        if license_plate_number:
            payload["license_plate_number"] = license_plate_number
        if metric_units is not None:
            payload["metric_units"] = metric_units
        if fuel_type:
            payload["fuel_type"] = fuel_type
        if notes:
            payload["notes"] = notes
        if group_ids:
            payload["group_ids"] = group_ids
        if eld_device:
            payload["eld_device"] = eld_device
        if current_driver:
            payload["current_driver"] = current_driver
        if external_id and integration_name:
            payload["external_ids_attributes"] = [
                {
                    "external_id": external_id,
                    "integration_name": integration_name,
                }
            ]
        if availability_details:
            payload["availability_details"] = availability_details

        return await self._request("POST", "/v1/vehicles", json_data=payload)

    async def update_vehicle(
        self,
        vehicle_id: str,
        number: Optional[str] = None,
        status: Optional[str] = None,
        ifta: Optional[bool] = None,
        vin: Optional[str] = None,
        make: Optional[str] = None,
        model: Optional[str] = None,
        year: Optional[str] = None,
        license_plate_state: Optional[str] = None,
        license_plate_number: Optional[str] = None,
        metric_units: Optional[bool] = None,
        fuel_type: Optional[str] = None,
        notes: Optional[str] = None,
        group_ids: Optional[List[int]] = None,
        prevent_auto_odometer_entry: Optional[bool] = None,
        eld_device: Optional[Dict[str, Any]] = None,
        current_driver: Optional[Dict[str, Any]] = None,
        external_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        external_id_id: Optional[str] = None,
        availability_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing vehicle.

        Use this API to update an existing vehicle in your company. You can update various
        attributes including vehicle identification, ELD device assignment, current driver,
        and external IDs for integration with external systems.

        Args:
            vehicle_id: Motive vehicle ID to update
            number: Optional fleet number assigned to the vehicle
            status: Optional status of the vehicle
            ifta: Optional - indicates whether the vehicle is subject to IFTA reporting
            vin: Optional Vehicle Identification Number (VIN)
            make: Optional manufacturer of the vehicle
            model: Optional model of the vehicle
            year: Optional year the vehicle was manufactured
            license_plate_state: Optional state of the vehicle's license plate
            license_plate_number: Optional license plate number
            metric_units: Optional - indicates whether the vehicle's measurements are in metric units
            fuel_type: Optional type of fuel the vehicle uses
            notes: Optional notes about the vehicle
            group_ids: Optional list of group IDs to assign the vehicle to
            prevent_auto_odometer_entry: Optional - indicates if auto-odometer entry is disabled
            eld_device: Optional ELD device information:
                - id: ID of the vehicle gateway
                - identifier: Unique identifier of the vehicle gateway
                - model: Model of the vehicle gateway
            current_driver: Optional current driver information:
                - id: Unique identifier of the driver
                - first_name: First name of the driver
                - last_name: Last name of the driver
                - username: Username assigned to the driver
                - email: Email address of the driver
                - driver_company_id: ID of the driver assigned by the company
                - status: Status of the driver (e.g., "active")
                - role: Role of the user (e.g., "driver")
            external_id: Optional external ID for tracking this vehicle in external systems
            integration_name: Optional name of the integration for external ID (required if external_id provided)
            external_id_id: Optional ID of existing external ID to update (required when updating existing external ID)
            availability_details: Optional availability details:
                - availability_status: "out_of_service" or "in_service"
                - out_of_service_reason: Reason for being out of service
                - additional_note: Comments or notes
                - custom_driver_app_warning_prompt: Prompt message for drivers

        Returns:
            Response containing:
            - vehicle: Updated vehicle object with all details including:
                - id: Unique identifier for the vehicle
                - company_id: ID of the company that owns the vehicle
                - number: The vehicle's assigned number or name
                - status: Current status of the vehicle
                - ifta: Indicates whether the vehicle is IFTA-registered
                - vin: The Vehicle Identification Number (VIN)
                - make: The make of the vehicle
                - model: The model of the vehicle
                - year: The manufacturing year of the vehicle
                - license_plate_state: The state where the vehicle's license plate is registered
                - license_plate_number: The vehicle's license plate number
                - metric_units: Indicates if the vehicle uses metric units
                - fuel_type: The type of fuel used by the vehicle
                - group_ids: List of group IDs associated with the vehicle
                - prevent_auto_odometer_entry: Indicates if auto-odometer entry is disabled
                - created_at: The timestamp when the vehicle was created
                - updated_at: The timestamp when the vehicle was last updated
                - eld_device: Information about the vehicle gateway
                - current_driver: Information about the vehicle's current driver
                - external_ids: List of external system IDs associated with the vehicle
                - availability_details: Availability details object

        Reference:
            https://developer.gomotive.com/reference/update-an-existing-vehicle
        """
        payload: Dict[str, Any] = {}

        if number is not None:
            payload["number"] = number
        if status is not None:
            payload["status"] = status
        if ifta is not None:
            payload["ifta"] = ifta
        if vin is not None:
            payload["vin"] = vin
        if make is not None:
            payload["make"] = make
        if model is not None:
            payload["model"] = model
        if year is not None:
            payload["year"] = year
        if license_plate_state is not None:
            payload["license_plate_state"] = license_plate_state
        if license_plate_number is not None:
            payload["license_plate_number"] = license_plate_number
        if metric_units is not None:
            payload["metric_units"] = metric_units
        if fuel_type is not None:
            payload["fuel_type"] = fuel_type
        if notes is not None:
            payload["notes"] = notes
        if group_ids is not None:
            payload["group_ids"] = group_ids
        if prevent_auto_odometer_entry is not None:
            payload["prevent_auto_odometer_entry"] = prevent_auto_odometer_entry
        if eld_device is not None:
            payload["eld_device"] = eld_device
        if current_driver is not None:
            payload["current_driver"] = current_driver
        if external_id and integration_name:
            external_id_attr: Dict[str, Any] = {
                "external_id": external_id,
                "integration_name": integration_name,
            }
            if external_id_id:
                external_id_attr["id"] = external_id_id
            payload["external_ids_attributes"] = [external_id_attr]
        if availability_details is not None:
            payload["availability_details"] = availability_details

        return await self._request("PUT", f"/v1/vehicles/{vehicle_id}", json_data=payload)

    async def get_fault_codes(
        self,
        vehicle_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch a list of all vehicle fault codes.

        Fault codes derived from the Vehicle Gateways are diagnostic trouble codes that are
        generated by a vehicle's onboard computer. These codes indicate various problems such
        as engine malfunctions, emissions, system failures, or sensor issues.

        Use this report to monitor vehicle health, perform preventive maintenance, and ensure
        vehicle safety and compliance.

        Args:
            vehicle_id: Optional vehicle ID to filter fault codes
            status: Optional status filter (e.g., "open", "closed")
            limit: Maximum number of fault codes to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing fault codes with:
            - id: Unique identifier for the fault code
            - code: The fault code as reported by the vehicle
            - code_label: Label associated with the fault code
            - code_description: Description of the fault code
            - source_address_label: Label for the source address
            - status: Status of the fault code (e.g., "open", "closed")
            - first_observed_at: Date and time when the fault code was first observed
            - last_observed_at: Date and time when the fault code was last observed
            - type: Type of the fault code (e.g., "constant")
            - fmi: Failure Mode Identifier, providing additional detail about the fault
            - fmi_description: Description of the Failure Mode Identifier
            - occurrence_count: Number of times the fault code has occurred
            - num_observations: The number of observations of the fault code
            - sum_num_observations: The cumulative number of observations for the fault code
            - source_address_name: Name associated with the source address
            - source_address: Source address from which the fault code originated
            - is_sid: Indicates whether the code is a System Identification Number (SID)
            - dtc_status: Status of the Diagnostic Trouble Code
            - dtc_severity: Severity of the Diagnostic Trouble Code
            - functional_grp_id: Functional group identifier
            - ftb: Fault code Trouble Board identifier
            - network: Network through which the fault code was communicated (e.g., "obdii")
            - vehicle_gateway: Vehicle Gateway details:
                - id: Unique identifier for the Vehicle Gateway
                - identifier: The identifier of the Vehicle Gateway
                - model: The model of the Vehicle Gateway
            - vehicle: Vehicle details associated with the fault code:
                - id: Unique identifier for the vehicle
                - number: The vehicle number
                - year: The manufacturing year of the vehicle
                - make: The make of the vehicle
                - model: The model of the vehicle
                - vin: The VIN (Vehicle Identification Number) of the vehicle
                - metric_units: Indicates if the vehicle uses metric units

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-vehicles-fault-codes
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if status:
            params["status"] = status

        return await self._request("GET", "/v1/fault_codes", params=params)

    async def get_users(
        self,
        driver_status: Optional[str] = None,
        user_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List all the users of a company.

        Use this API to fetch a list of all the users that belong to your company. The users
        can be having any of the following roles:
        - Driver
        - Fleet User
        - Admin

        If you are looking for driver info, you can also narrow the search by specifying the
        driver status or the user status in the query parameters.

        Args:
            driver_status: Optional driver status to filter by (e.g., "active", "inactive")
            user_status: Optional user status to filter by (e.g., "active", "inactive")
            limit: Maximum number of users to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing:
            - users: Array of user objects, each containing:
                - id: Unique identifier of the user
                - email: Email address of the user
                - first_name: User's first name
                - last_name: User's last name
                - company_reference_id: Reference ID for the company associated with the user
                - phone: Phone number of the user
                - phone_ext: Phone extension of the user
                - time_zone: Time zone of the user
                - carrier_name: Name of the carrier company
                - carrier_street: Street address of the carrier company
                - carrier_city: City where the carrier company is located
                - carrier_state: State where the carrier company is located
                - carrier_zip: ZIP code of the carrier company
                - violation_alerts: Frequency of violation alerts (e.g., "1_hour")
                - terminal_street: Street address of the terminal
                - terminal_city: City where the terminal is located
                - terminal_state: State where the terminal is located
                - terminal_zip: ZIP code of the terminal
                - exception_24_hour_restart: Indicates if the 24-hour restart exception is applied
                - exception_8_hour_break: Indicates if the 8-hour break exception is applied
                - exception_wait_time: Indicates if the wait time exception is applied
                - exception_short_haul: Indicates if the short haul exception is applied
                - exception_ca_farm_school_bus: Indicates if the CA farm school bus exception is applied
                - cycle2: Second cycle of the user
                - exception_24_hour_restart2: Indicates if the 24-hour restart exception is applied to the second cycle
                - exception_8_hour_break2: Indicates if the 8-hour break exception is applied to the second cycle
                - exception_wait_time2: Indicates if the wait time exception is applied to the second cycle
                - exception_short_haul2: Indicates if the short haul exception is applied to the second cycle
                - exception_ca_farm_school_bus2: Indicates if the CA farm school bus exception is applied to the second cycle
                - export_combined: Indicates if the data export is combined
                - export_recap: Indicates if the recap data is exported
                - export_odometers: Indicates if odometer readings are exported
                - metric_units: Indicates if metric units are used
                - username: Username of the user
                - cycle: Cycle type of the user (e.g., "70_8")
                - driver_company_id: Company ID of the driver
                - minute_logs: Indicates if minute logs are enabled
                - duty_status: Current duty status of the user (e.g., "off_duty")
                - eld_mode: The mode of the Vehicle Gateway (e.g., "logs")
                - drivers_license_number: Driver's license number of the user
                - drivers_license_state: State of the user's driver's license
                - yard_moves_enabled: Indicates if yard moves are enabled
                - personal_conveyance_enabled: Indicates if personal conveyance is enabled
                - mobile_last_active_at: Timestamp when the user was last active on mobile
                - mobile_current_sign_in_at: Timestamp when the user last signed in on mobile
                - mobile_last_sign_in_at: Timestamp when the user last signed in on mobile
                - web_last_active_at: Timestamp when the user was last active on the web (ISO 8601 format)
                - role: Role of the user (e.g., "driver")
                - status: Status of the user (e.g., "active")
                - web_current_sign_in_at: Timestamp when the user last signed in on the web
                - web_last_sign_in_at: Timestamp when the user last signed in on the web
                - created_at: Timestamp when the user was created
                - updated_at: Timestamp when the user was last updated
                - external_ids: Array of external ID objects, each containing:
                    - external_id: External ID of the user
                    - integration_name: Name of the integration associated with the external ID (e.g., "generic_tms")

        Reference:
            https://developer.gomotive.com/reference/list-all-the-users-of-a-company
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if driver_status:
            params["driver_status"] = driver_status
        if user_status:
            params["user_status"] = user_status

        return await self._request("GET", "/v1/users", params=params)

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch a specific user using an ID.

        Use this API to fetch the complete details of a particular user. You must specify
        the ID of the user whose details you want to view. The API response will fetch
        important details such as the following:
        - Name
        - Email
        - Phone
        - Timezone
        - Violation info
        - Sign-in details

        Args:
            user_id: Motive user ID

        Returns:
            Response containing:
            - user: User object with complete details including:
                - id: Unique identifier of the user
                - email: Email address of the user
                - first_name: User's first name
                - last_name: User's last name
                - company_reference_id: Reference ID for the company associated with the user
                - phone: Phone number of the user
                - phone_ext: Phone extension of the user
                - time_zone: Time zone of the user
                - metric_units: Denotes if the metric units are used
                - carrier_name: Name of the carrier company
                - carrier_street: Street address of the carrier company
                - carrier_city: City where the carrier company is located
                - carrier_state: State where the carrier company is located
                - carrier_zip: ZIP code of the carrier company
                - violation_alerts: Frequency of violation alerts (e.g., "1_hour")
                - terminal_street: Street address of the terminal
                - terminal_city: City where the terminal is located
                - terminal_state: State where the terminal is located
                - terminal_zip: ZIP code of the terminal
                - exception_24_hour_restart: Indicates if the 24-hour restart exception is applied
                - exception_8_hour_break: Indicates if the 8-hour break exception is applied
                - exception_wait_time: Indicates if the wait time exception is applied
                - exception_short_haul: Indicates if the short haul exception is applied
                - exception_ca_farm_school_bus: Indicates if the CA farm school bus exception is applied
                - cycle2: Second cycle of the user
                - exception_24_hour_restart2: Indicates if the 24-hour restart exception is applied to the second cycle
                - exception_8_hour_break2: Indicates if the 8-hour break exception is applied to the second cycle
                - exception_wait_time2: Indicates if the wait time exception is applied to the second cycle
                - exception_short_haul2: Indicates if the short haul exception is applied to the second cycle
                - exception_ca_farm_school_bus2: Indicates if the CA farm school bus exception is applied to the second cycle
                - export_combined: Indicates if the data export is combined
                - export_recap: Indicates if the recap data is exported
                - export_odometers: Indicates if odometer readings are exported
                - username: Username of the user
                - cycle: Cycle type of the user (e.g., "70_8")
                - driver_company_id: Company ID of the driver
                - minute_logs: Indicates if minute logs are enabled
                - duty_status: Current duty status of the user (e.g., "off_duty")
                - eld_mode: The mode of the Vehicle Gateway (e.g., "logs")
                - drivers_license_number: Driver's license number of the user
                - drivers_license_state: State of the user's driver's license
                - yard_moves_enabled: Indicates if yard moves are enabled
                - personal_conveyance_enabled: Indicates if personal conveyance is enabled
                - mobile_last_active_at: Timestamp when the user was last active on mobile
                - mobile_current_sign_in_at: Timestamp when the user last signed in on mobile
                - mobile_last_sign_in_at: Timestamp when the user last signed in on mobile
                - web_last_active_at: Timestamp when the user was last active on the web (ISO 8601 format)
                - role: Role of the user (e.g., "driver")
                - status: Status of the user (e.g., "active")
                - web_current_sign_in_at: Timestamp when the user last signed in on the web
                - web_last_sign_in_at: Timestamp when the user last signed in on the web
                - created_at: Timestamp when the user was created
                - updated_at: Timestamp when the user was last updated
                - external_ids: Array of external ID objects, each containing:
                    - id: ID assigned to the external identifier
                    - external_id: External ID of the user
                    - integration_name: Name of the integration associated with the external ID (e.g., "generic_tms")

        Reference:
            https://developer.gomotive.com/reference/fetch-a-specific-user-using-an-id
        """
        return await self._request("GET", f"/v1/users/{user_id}")

    async def create_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        role: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        phone: Optional[str] = None,
        phone_country_code: Optional[str] = None,
        phone_ext: Optional[str] = None,
        time_zone: Optional[str] = None,
        carrier_name: Optional[str] = None,
        carrier_street: Optional[str] = None,
        carrier_city: Optional[str] = None,
        carrier_state: Optional[str] = None,
        carrier_zip: Optional[str] = None,
        violation_alerts: Optional[str] = None,
        terminal_street: Optional[str] = None,
        terminal_city: Optional[str] = None,
        terminal_state: Optional[str] = None,
        terminal_zip: Optional[str] = None,
        exception_24_hour_restart: Optional[bool] = None,
        exception_8_hour_break: Optional[bool] = None,
        exception_wait_time: Optional[bool] = None,
        exception_short_haul: Optional[bool] = None,
        exception_ca_farm_school_bus: Optional[bool] = None,
        exception_adverse_driving: Optional[bool] = None,
        export_combined: Optional[bool] = None,
        export_recap: Optional[bool] = None,
        export_odometers: Optional[bool] = None,
        metric_units: Optional[bool] = None,
        cycle: Optional[str] = None,
        driver_company_id: Optional[str] = None,
        minute_logs: Optional[bool] = None,
        duty_status: Optional[str] = None,
        eld_mode: Optional[str] = None,
        drivers_license_number: Optional[str] = None,
        drivers_license_state: Optional[str] = None,
        yard_moves_enabled: Optional[bool] = None,
        personal_conveyance_enabled: Optional[bool] = None,
        manual_driving_enabled: Optional[bool] = None,
        status: Optional[str] = None,
        dot_id: Optional[str] = None,
        time_tracking_mode: Optional[str] = None,
        group_ids: Optional[List[int]] = None,
        group_visibility: Optional[str] = None,
        custom_user_role: Optional[Dict[str, Any]] = None,
        external_id: Optional[str] = None,
        integration_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new user.

        Use this API to create a new user in your company. The user can be a driver, fleet user,
        or admin. You can specify various attributes including contact information, HOS exceptions,
        and role-specific settings.

        To add a driver to groups, include the list of group IDs in the `group_ids` attribute.
        For fleet users, you can restrict visibility to specific groups using `group_visibility`
        and `custom_user_role`.

        Args:
            email: User's email address
            first_name: User's first name
            last_name: User's last name
            role: Role of the user (e.g., "driver", "fleet_user", "admin")
            username: Optional username for the user
            password: Optional password for the user
            phone: Optional phone number of the user
            phone_country_code: Optional country code for phone number (e.g., "+1" for USA, "+52" for Mexico)
            phone_ext: Optional phone extension
            time_zone: Optional time zone of the user
            carrier_name: Optional name of the carrier company
            carrier_street: Optional street address of the carrier
            carrier_city: Optional city of the carrier
            carrier_state: Optional state of the carrier
            carrier_zip: Optional ZIP code of the carrier
            violation_alerts: Optional frequency of violation alerts (e.g., "1_hour", "2_hours")
            terminal_street: Optional street address of the terminal
            terminal_city: Optional city of the terminal
            terminal_state: Optional state of the terminal
            terminal_zip: Optional ZIP code of the terminal
            exception_24_hour_restart: Optional - indicates if the 24-hour restart exception is enabled
            exception_8_hour_break: Optional - indicates if the 8-hour break exception is enabled
            exception_wait_time: Optional - indicates if the wait time exception is enabled
            exception_short_haul: Optional - indicates if the short haul exception is enabled
            exception_ca_farm_school_bus: Optional - indicates if the CA farm school bus exception is enabled
            exception_adverse_driving: Optional - indicates if the adverse driving exception is enabled
            export_combined: Optional - indicates if the combined export option is enabled
            export_recap: Optional - indicates if the recap export option is enabled
            export_odometers: Optional - indicates if the odometer export option is enabled
            metric_units: Optional - indicates if metric units are used
            cycle: Optional cycle type associated with the user
            driver_company_id: Optional driver's company ID
            minute_logs: Optional - indicates if minute logs are enabled
            duty_status: Optional current duty status of the user
            eld_mode: Optional mode of the vehicle gateway (e.g., "none", "logs")
            drivers_license_number: Optional driver's license number
            drivers_license_state: Optional state where the driver's license was issued
            yard_moves_enabled: Optional - indicates if yard moves are enabled
            personal_conveyance_enabled: Optional - indicates if personal conveyance is enabled
            manual_driving_enabled: Optional - indicates if manual driving is enabled
            status: Optional status of the user (e.g., "active")
            dot_id: Optional DOT ID associated with the user
            time_tracking_mode: Optional time tracking mode (e.g., "logs", "timecards")
            group_ids: Optional list of group IDs to add the driver to
            group_visibility: Optional visibility setting for fleet users (e.g., "limited")
            custom_user_role: Optional custom user role configuration for fleet users:
                - user_role_id: ID of the user role
                - group_ids: List of group IDs the user can access
            external_id: Optional external ID for tracking this user in external systems
            integration_name: Optional name of the integration for external ID (required if external_id provided)

        Returns:
            Response containing:
            - user: Created user object with all details including:
                - id: Unique identifier for the user
                - email: User's email address
                - first_name: User's first name
                - last_name: User's last name
                - company_reference_id: Reference ID for the company
                - phone: User's phone number
                - phone_country_code: Country code associated with the user's phone number
                - phone_ext: Extension associated with the user's phone number
                - time_zone: Time zone of the user
                - carrier_name: Carrier name associated with the user
                - carrier_street: Street address of the carrier
                - carrier_city: City of the carrier
                - carrier_state: State of the carrier
                - carrier_zip: ZIP code of the carrier
                - violation_alerts: Frequency of violation alerts
                - terminal_street: Street address of the terminal
                - terminal_city: City of the terminal
                - terminal_state: State of the terminal
                - terminal_zip: ZIP code of the terminal
                - exception_24_hour_restart: Indicates if the 24-hour restart exception is enabled
                - exception_8_hour_break: Indicates if the 8-hour break exception is enabled
                - exception_wait_time: Indicates if the wait time exception is enabled
                - exception_short_haul: Indicates if the short haul exception is enabled
                - exception_ca_farm_school_bus: Indicates if the CA farm school bus exception is enabled
                - exception_adverse_driving: Indicates if the adverse driving exception is enabled
                - export_combined: Indicates if the combined export option is enabled
                - export_recap: Indicates if the recap export option is enabled
                - export_odometers: Indicates if the odometer export option is enabled
                - metric_units: Indicates if metric units are used
                - username: Username of the user
                - cycle: Cycle type associated with the user
                - driver_company_id: Driver's company ID
                - minute_logs: Indicates if minute logs are enabled
                - duty_status: Current duty status of the user
                - eld_mode: The mode of the vehicle gateway
                - drivers_license_number: Driver's license number
                - drivers_license_state: State where the driver's license was issued
                - yard_moves_enabled: Indicates if yard moves are enabled
                - personal_conveyance_enabled: Indicates if personal conveyance is enabled
                - manual_driving_enabled: Indicates if manual driving is enabled
                - role: Role of the user
                - status: Status of the user
                - created_at: Timestamp when the user was created
                - updated_at: Timestamp when the user was last updated
                - external_ids: Array of external IDs associated with the user
                - dot_id: DOT ID associated with the user

        Reference:
            https://developer.gomotive.com/reference/create-a-new-user
        """
        payload: Dict[str, Any] = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
        }

        # Add optional fields
        if username:
            payload["username"] = username
        if password:
            payload["password"] = password
        if phone:
            payload["phone"] = phone
        if phone_country_code:
            payload["phone_country_code"] = phone_country_code
        if phone_ext:
            payload["phone_ext"] = phone_ext
        if time_zone:
            payload["time_zone"] = time_zone
        if carrier_name:
            payload["carrier_name"] = carrier_name
        if carrier_street:
            payload["carrier_street"] = carrier_street
        if carrier_city:
            payload["carrier_city"] = carrier_city
        if carrier_state:
            payload["carrier_state"] = carrier_state
        if carrier_zip:
            payload["carrier_zip"] = carrier_zip
        if violation_alerts:
            payload["violation_alerts"] = violation_alerts
        if terminal_street:
            payload["terminal_street"] = terminal_street
        if terminal_city:
            payload["terminal_city"] = terminal_city
        if terminal_state:
            payload["terminal_state"] = terminal_state
        if terminal_zip:
            payload["terminal_zip"] = terminal_zip
        if exception_24_hour_restart is not None:
            payload["exception_24_hour_restart"] = exception_24_hour_restart
        if exception_8_hour_break is not None:
            payload["exception_8_hour_break"] = exception_8_hour_break
        if exception_wait_time is not None:
            payload["exception_wait_time"] = exception_wait_time
        if exception_short_haul is not None:
            payload["exception_short_haul"] = exception_short_haul
        if exception_ca_farm_school_bus is not None:
            payload["exception_ca_farm_school_bus"] = exception_ca_farm_school_bus
        if exception_adverse_driving is not None:
            payload["exception_adverse_driving"] = exception_adverse_driving
        if export_combined is not None:
            payload["export_combined"] = export_combined
        if export_recap is not None:
            payload["export_recap"] = export_recap
        if export_odometers is not None:
            payload["export_odometers"] = export_odometers
        if metric_units is not None:
            payload["metric_units"] = metric_units
        if cycle:
            payload["cycle"] = cycle
        if driver_company_id:
            payload["driver_company_id"] = driver_company_id
        if minute_logs is not None:
            payload["minute_logs"] = minute_logs
        if duty_status:
            payload["duty_status"] = duty_status
        if eld_mode:
            payload["eld_mode"] = eld_mode
        if drivers_license_number:
            payload["drivers_license_number"] = drivers_license_number
        if drivers_license_state:
            payload["drivers_license_state"] = drivers_license_state
        if yard_moves_enabled is not None:
            payload["yard_moves_enabled"] = yard_moves_enabled
        if personal_conveyance_enabled is not None:
            payload["personal_conveyance_enabled"] = personal_conveyance_enabled
        if manual_driving_enabled is not None:
            payload["manual_driving_enabled"] = manual_driving_enabled
        if status:
            payload["status"] = status
        if dot_id:
            payload["dot_id"] = dot_id
        if time_tracking_mode:
            payload["time_tracking_mode"] = time_tracking_mode
        if group_ids:
            payload["group_ids"] = group_ids
        if group_visibility:
            payload["group_visibility"] = group_visibility
        if custom_user_role:
            payload["custom_user_role"] = custom_user_role
        if external_id and integration_name:
            payload["external_ids_attributes"] = [
                {
                    "external_id": external_id,
                    "integration_name": integration_name,
                }
            ]

        return await self._request("POST", "/v1/users", json_data=payload)

    async def search_user(
        self,
        email: Optional[str] = None,
        username: Optional[str] = None,
        driver_company_id: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for a specific user.

        Use this API to search for a specific user and see their information. This API
        requires you to specify any one of the following as a query parameter:
        - Email
        - User Name
        - Driver's Company ID
        - Phone

        Args:
            email: Optional email address to search by
            username: Optional username to search by
            driver_company_id: Optional driver's company ID to search by
            phone: Optional phone number to search by

        Returns:
            Response containing user object with details including:
            - id: Unique identifier for the user
            - email: User's email address
            - first_name: User's first name
            - last_name: User's last name
            - phone: User's phone number
            - phone_ext: Phone extension
            - time_zone: Time zone of the user
            - metric_units: Indicates if metric units are used
            - carrier_name: Name of the carrier
            - carrier_street: Street address of the carrier
            - carrier_city: City of the carrier
            - carrier_state: State of the carrier
            - carrier_zip: ZIP code of the carrier
            - violation_alerts: Frequency of violation alerts (e.g., "1_hour", "2_hours")
            - terminal_street: Street address of the terminal
            - terminal_city: City of the terminal
            - terminal_state: State of the terminal
            - terminal_zip: ZIP code of the terminal
            - cycle: Cycle type associated with the user
            - exception_24_hour_restart: Indicates if the 24-hour restart exception is enabled
            - exception_8_hour_break: Indicates if the 8-hour break exception is enabled
            - exception_wait_time: Indicates if the wait time exception is enabled
            - exception_short_haul: Indicates if the short haul exception is enabled
            - exception_ca_farm_school_bus: Indicates if the CA farm school bus exception is enabled
            - cycle2: Secondary cycle type
            - exception_24_hour_restart2: Indicates if the 24-hour restart exception is enabled (secondary)
            - exception_8_hour_break2: Indicates if the 8-hour break exception is enabled (secondary)
            - exception_wait_time2: Indicates if the wait time exception is enabled (secondary)
            - exception_short_haul2: Indicates if the short haul exception is enabled (secondary)
            - exception_ca_farm_school_bus2: Indicates if the CA farm school bus exception is enabled (secondary)
            - export_combined: Indicates if combined export is enabled
            - export_recap: Indicates if recap export is enabled
            - export_odometers: Indicates if odometer export is enabled
            - username: Username of the user
            - driver_company_id: Driver's company ID
            - minute_logs: Indicates if minute logs are enabled
            - duty_status: Current duty status of the user
            - eld_mode: ELD mode of the user
            - drivers_license_number: Driver's license number
            - drivers_license_state: State where the driver's license was issued
            - yard_moves_enabled: Indicates if yard moves are enabled
            - personal_conveyance_enabled: Indicates if personal conveyance is enabled
            - manual_driving_enabled: Indicates if manual driving is enabled
            - role: Role of the user (e.g., "driver")
            - status: Status of the user (e.g., "active")
            - created_at: Timestamp when the user was created
            - updated_at: Timestamp when the user was last updated
            - external_ids: Array of external IDs associated with the user

        Reference:
            https://developer.gomotive.com/reference/search-for-a-specific-user
        """
        params: Dict[str, Any] = {}
        if email:
            params["email"] = email
        if username:
            params["username"] = username
        if driver_company_id:
            params["driver_company_id"] = driver_company_id
        if phone:
            params["phone"] = phone

        if not params:
            raise ValueError("At least one search parameter (email, username, driver_company_id, or phone) must be provided")

        return await self._request("GET", "/v1/users/lookup", params=params)

    async def search_user_by_external_id(
        self,
        external_id: str,
        integration_name: str,
    ) -> Dict[str, Any]:
        """
        Search for a user using an external ID.

        Use this API to search for user using an external ID. It is important to note that
        an `external_id` & `integration_name` are unique.

        Args:
            external_id: External ID of the user
            integration_name: Name of the integration associated with the external ID

        Returns:
            Response containing user object with details including:
            - id: Unique identifier for the user
            - email: User's email address
            - first_name: User's first name
            - last_name: User's last name
            - phone: User's phone number
            - phone_ext: Phone extension
            - time_zone: Time zone of the user
            - metric_units: Indicates if metric units are used
            - carrier_name: Name of the carrier
            - carrier_street: Street address of the carrier
            - carrier_city: City of the carrier
            - carrier_state: State of the carrier
            - carrier_zip: ZIP code of the carrier
            - violation_alerts: Frequency of violation alerts (e.g., "1_hour", "2_hours")
            - terminal_street: Street address of the terminal
            - terminal_city: City of the terminal
            - terminal_state: State of the terminal
            - terminal_zip: ZIP code of the terminal
            - cycle: Cycle type associated with the user
            - exception_24_hour_restart: Indicates if the 24-hour restart exception is enabled
            - exception_8_hour_break: Indicates if the 8-hour break exception is enabled
            - exception_wait_time: Indicates if the wait time exception is enabled
            - exception_short_haul: Indicates if the short haul exception is enabled
            - exception_ca_farm_school_bus: Indicates if the CA farm school bus exception is enabled
            - cycle2: Secondary cycle type
            - exception_24_hour_restart2: Indicates if the 24-hour restart exception is enabled (secondary)
            - exception_8_hour_break2: Indicates if the 8-hour break exception is enabled (secondary)
            - exception_wait_time2: Indicates if the wait time exception is enabled (secondary)
            - exception_short_haul2: Indicates if the short haul exception is enabled (secondary)
            - exception_ca_farm_school_bus2: Indicates if the CA farm school bus exception is enabled (secondary)
            - export_combined: Indicates if combined export is enabled
            - export_recap: Indicates if recap export is enabled
            - export_odometers: Indicates if odometer export is enabled
            - username: Username of the user
            - driver_company_id: Driver's company ID
            - minute_logs: Indicates if minute logs are enabled
            - duty_status: Current duty status of the user
            - eld_mode: ELD mode of the user
            - drivers_license_number: Driver's license number
            - drivers_license_state: State where the driver's license was issued
            - yard_moves_enabled: Indicates if yard moves are enabled
            - personal_conveyance_enabled: Indicates if personal conveyance is enabled
            - manual_driving_enabled: Indicates if manual driving is enabled
            - role: Role of the user (e.g., "driver")
            - status: Status of the user (e.g., "active")
            - created_at: Timestamp when the user was created
            - updated_at: Timestamp when the user was last updated
            - external_ids: Array of external IDs associated with the user

        Reference:
            https://developer.gomotive.com/reference/use-external-id-to-search-for-a-user
        """
        params = {
            "external_id": external_id,
            "integration_name": integration_name,
        }
        return await self._request("GET", "/v1/users/lookup_by_external_id", params=params)

    async def update_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        phone_country_code: Optional[str] = None,
        phone_ext: Optional[str] = None,
        time_zone: Optional[str] = None,
        carrier_name: Optional[str] = None,
        carrier_street: Optional[str] = None,
        carrier_city: Optional[str] = None,
        carrier_state: Optional[str] = None,
        carrier_zip: Optional[str] = None,
        violation_alerts: Optional[str] = None,
        terminal_street: Optional[str] = None,
        terminal_city: Optional[str] = None,
        terminal_state: Optional[str] = None,
        terminal_zip: Optional[str] = None,
        exception_24_hour_restart: Optional[bool] = None,
        exception_8_hour_break: Optional[bool] = None,
        exception_wait_time: Optional[bool] = None,
        exception_short_haul: Optional[bool] = None,
        exception_ca_farm_school_bus: Optional[bool] = None,
        exception_adverse_driving: Optional[bool] = None,
        export_combined: Optional[bool] = None,
        export_recap: Optional[bool] = None,
        export_odometers: Optional[bool] = None,
        metric_units: Optional[bool] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        cycle: Optional[str] = None,
        driver_company_id: Optional[str] = None,
        minute_logs: Optional[bool] = None,
        duty_status: Optional[str] = None,
        eld_mode: Optional[str] = None,
        drivers_license_number: Optional[str] = None,
        drivers_license_state: Optional[str] = None,
        yard_moves_enabled: Optional[bool] = None,
        personal_conveyance_enabled: Optional[bool] = None,
        manual_driving_enabled: Optional[bool] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        dot_id: Optional[str] = None,
        time_tracking_mode: Optional[str] = None,
        group_ids: Optional[List[int]] = None,
        group_visibility: Optional[str] = None,
        custom_user_role: Optional[Dict[str, Any]] = None,
        external_id: Optional[str] = None,
        integration_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing user.

        Use this API to update an existing user in your company. You can update various
        attributes including contact information, HOS exceptions, and role-specific settings.

        Args:
            user_id: Motive user ID to update
            email: Optional email address
            first_name: Optional first name
            last_name: Optional last name
            phone: Optional phone number
            phone_country_code: Optional country code for phone number
            phone_ext: Optional phone extension
            time_zone: Optional time zone
            carrier_name: Optional name of the carrier company
            carrier_street: Optional street address of the carrier
            carrier_city: Optional city of the carrier
            carrier_state: Optional state of the carrier
            carrier_zip: Optional ZIP code of the carrier
            violation_alerts: Optional frequency of violation alerts
            terminal_street: Optional street address of the terminal
            terminal_city: Optional city of the terminal
            terminal_state: Optional state of the terminal
            terminal_zip: Optional ZIP code of the terminal
            exception_24_hour_restart: Optional - indicates if the 24-hour restart exception is enabled
            exception_8_hour_break: Optional - indicates if the 8-hour break exception is enabled
            exception_wait_time: Optional - indicates if the wait time exception is enabled
            exception_short_haul: Optional - indicates if the short haul exception is enabled
            exception_ca_farm_school_bus: Optional - indicates if the CA farm school bus exception is enabled
            exception_adverse_driving: Optional - indicates if the adverse driving exception is enabled
            export_combined: Optional - indicates if the combined export option is enabled
            export_recap: Optional - indicates if the recap export option is enabled
            export_odometers: Optional - indicates if the odometer export option is enabled
            metric_units: Optional - indicates if metric units are used
            username: Optional username
            password: Optional password
            cycle: Optional cycle type
            driver_company_id: Optional driver's company ID
            minute_logs: Optional - indicates if minute logs are enabled
            duty_status: Optional current duty status
            eld_mode: Optional mode of the vehicle gateway
            drivers_license_number: Optional driver's license number
            drivers_license_state: Optional state where the driver's license was issued
            yard_moves_enabled: Optional - indicates if yard moves are enabled
            personal_conveyance_enabled: Optional - indicates if personal conveyance is enabled
            manual_driving_enabled: Optional - indicates if manual driving is enabled
            role: Optional role of the user
            status: Optional status of the user
            dot_id: Optional DOT ID
            time_tracking_mode: Optional time tracking mode
            group_ids: Optional list of group IDs
            group_visibility: Optional visibility setting for fleet users
            custom_user_role: Optional custom user role configuration
            external_id: Optional external ID for tracking this user in external systems
            integration_name: Optional name of the integration for external ID

        Returns:
            Response containing updated user object with all details

        Reference:
            https://developer.gomotive.com/reference/update-an-existing-user
        """
        payload: Dict[str, Any] = {}

        # Add optional fields
        if email is not None:
            payload["email"] = email
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        if phone is not None:
            payload["phone"] = phone
        if phone_country_code is not None:
            payload["phone_country_code"] = phone_country_code
        if phone_ext is not None:
            payload["phone_ext"] = phone_ext
        if time_zone is not None:
            payload["time_zone"] = time_zone
        if carrier_name is not None:
            payload["carrier_name"] = carrier_name
        if carrier_street is not None:
            payload["carrier_street"] = carrier_street
        if carrier_city is not None:
            payload["carrier_city"] = carrier_city
        if carrier_state is not None:
            payload["carrier_state"] = carrier_state
        if carrier_zip is not None:
            payload["carrier_zip"] = carrier_zip
        if violation_alerts is not None:
            payload["violation_alerts"] = violation_alerts
        if terminal_street is not None:
            payload["terminal_street"] = terminal_street
        if terminal_city is not None:
            payload["terminal_city"] = terminal_city
        if terminal_state is not None:
            payload["terminal_state"] = terminal_state
        if terminal_zip is not None:
            payload["terminal_zip"] = terminal_zip
        if exception_24_hour_restart is not None:
            payload["exception_24_hour_restart"] = exception_24_hour_restart
        if exception_8_hour_break is not None:
            payload["exception_8_hour_break"] = exception_8_hour_break
        if exception_wait_time is not None:
            payload["exception_wait_time"] = exception_wait_time
        if exception_short_haul is not None:
            payload["exception_short_haul"] = exception_short_haul
        if exception_ca_farm_school_bus is not None:
            payload["exception_ca_farm_school_bus"] = exception_ca_farm_school_bus
        if exception_adverse_driving is not None:
            payload["exception_adverse_driving"] = exception_adverse_driving
        if export_combined is not None:
            payload["export_combined"] = export_combined
        if export_recap is not None:
            payload["export_recap"] = export_recap
        if export_odometers is not None:
            payload["export_odometers"] = export_odometers
        if metric_units is not None:
            payload["metric_units"] = metric_units
        if username is not None:
            payload["username"] = username
        if password is not None:
            payload["password"] = password
        if cycle is not None:
            payload["cycle"] = cycle
        if driver_company_id is not None:
            payload["driver_company_id"] = driver_company_id
        if minute_logs is not None:
            payload["minute_logs"] = minute_logs
        if duty_status is not None:
            payload["duty_status"] = duty_status
        if eld_mode is not None:
            payload["eld_mode"] = eld_mode
        if drivers_license_number is not None:
            payload["drivers_license_number"] = drivers_license_number
        if drivers_license_state is not None:
            payload["drivers_license_state"] = drivers_license_state
        if yard_moves_enabled is not None:
            payload["yard_moves_enabled"] = yard_moves_enabled
        if personal_conveyance_enabled is not None:
            payload["personal_conveyance_enabled"] = personal_conveyance_enabled
        if manual_driving_enabled is not None:
            payload["manual_driving_enabled"] = manual_driving_enabled
        if role is not None:
            payload["role"] = role
        if status is not None:
            payload["status"] = status
        if dot_id is not None:
            payload["dot_id"] = dot_id
        if time_tracking_mode is not None:
            payload["time_tracking_mode"] = time_tracking_mode
        if group_ids is not None:
            payload["group_ids"] = group_ids
        if group_visibility is not None:
            payload["group_visibility"] = group_visibility
        if custom_user_role is not None:
            payload["custom_user_role"] = custom_user_role
        if external_id and integration_name:
            payload["external_ids_attributes"] = [
                {
                    "external_id": external_id,
                    "integration_name": integration_name,
                }
            ]

        return await self._request("PUT", f"/v1/users/{user_id}", json_data=payload)

    async def get_user_permissions(
        self,
        name: str,
        status: str,
    ) -> Dict[str, Any]:
        """
        View the permissions of a user role.

        Use this API to view all the available permissions pertaining to a user's role such
        as an admin, or a fleet manager, or a driver. This API will list out all the
        available permissions to that particular user role.

        Note: You must specify the `name` and the `status` of the role to view its
        associated permissions in the Query Parameters.

        Args:
            name: Name of the user role
            status: Status of the user role (e.g., "active")

        Returns:
            Response containing:
            - id: The unique identifier for the user role
            - name: The name of the user role
            - permissions: Array of strings - list of permissions granted to the user role
            - status: The status of the user role (e.g., "active")
            - created_at: The date and time when the user role was created (DateTime)
            - updated_at: The date and time when the user role was last updated (DateTime)
            - last_edited_by: Object containing information about the user who last edited the role:
                - id: The unique identifier of the user who last edited
                - first_name: The first name of the user who last edited
                - last_name: The last name of the user who last edited
            - is_editable: Indicates whether the user role can be edited
            - type: The type of the user role (e.g., "default" or "custom")
            - assigned_users_count: The number of users assigned to this role

        Reference:
            https://developer.gomotive.com/reference/view-the-permissions-of-a-user-role
        """
        params = {
            "name": name,
            "status": status,
        }
        return await self._request("GET", "/v1/user_roles", params=params)

    async def get_locations(
        self,
        vehicle_ids: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get vehicle locations.

        Args:
            vehicle_ids: Optional list of vehicle IDs to filter
            start_time: ISO 8601 start time
            end_time: ISO 8601 end time

        Returns:
            Response containing location data
        """
        params = {}
        if vehicle_ids:
            params["vehicle_ids"] = ",".join(vehicle_ids)
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/locations", params=params)

    async def get_vehicle_locations_v3(
        self,
        vehicle_id: Optional[str] = None,
        vehicle_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all the vehicles and their locations (v3).

        This API is only meant for vehicles with the Motive Vehicle Gateway. For others,
        you may use the V1 or V2 API. Use this API to fetch a list of all the company
        vehicles, and their information such as assigned drivers, their location, fuel
        type, and etc. The response will list out all the vehicles of your company with
        the corresponding details.

        Note: Use the query parameters only if you want to fetch the details of a
        particular vehicle and its corresponding info. Otherwise, ignore the parameters
        to fetch all the vehicle information of the company.

        Args:
            vehicle_id: Optional vehicle ID to filter for a specific vehicle
            vehicle_status: Optional vehicle status to filter (e.g., "active", "inactive")

        Returns:
            Response containing vehicles with:
            - vehicles: Array of vehicle objects, each containing:
                - id: Unique identifier assigned to the vehicle
                - number: Name or number assigned to the vehicle
                - year: Model year of the vehicle
                - make: Manufacturer or brand of the vehicle
                - model: Model name of the vehicle
                - vin: Vehicle Identification Number
                - aux_status: Statuses of auxiliary equipment installed in the vehicle:
                    - AUX1/AUX2: Information about specific auxiliary inputs:
                        - present: Indicates if the auxiliary equipment is installed
                        - start_time: Timestamp when the auxiliary input was engaged
                        - end_time: Timestamp when the auxiliary input was disengaged
                        - is_engaged: Indicates whether the auxiliary input is currently engaged
                        - aux_equipment_type: Type of auxiliary equipment (e.g., "PTO", "Generators")
                - current_location: Real-time or last known location data:
                    - lat: Latitude coordinate of the vehicle's location
                    - lon: Longitude coordinate of the vehicle's location
                    - bearing: Compass direction the vehicle is facing (null if not available)
                    - located_at: Timestamp of the most recent known location
                    - city: City in which the vehicle is located
                    - state: State in which the vehicle is located
                    - rg_km: Distance from a geofence or region in kilometers
                    - rg_brg: Bearing from a geofence or region in degrees
                    - rg_match: Indicates whether the vehicle matched a geofence region
                    - kph: Current speed of the vehicle in kilometers per hour
                    - vehicle_state: Indicates whether the vehicle is "on" or "off"
                    - current_location: Human-readable location address of the vehicle

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-vehicles-and-their-locations-v3
        """
        params: Dict[str, Any] = {}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if vehicle_status:
            params["vehicle_status"] = vehicle_status

        return await self._request("GET", "/v3/vehicle_locations", params=params)

    async def get_vehicle_location_by_id_v3(
        self,
        vehicle_id: str,
        start_date: str,
        end_date: str,
        updated_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a vehicle's location using its ID (v3).

        Use this API to fetch the location of a particular vehicle using its ID. You must
        specify the date range for which you want to check the information of the vehicle.

        Important Notes:
        - This is the v3 of the "Fetch the location of a vehicle using its ID" endpoint
        - The duration between start_date and end_date must not exceed 3 months
        - This endpoint has a limit of 10 simultaneous requests at a time
        - For accurate odometer tracking, use true_odometer instead of odometer
        - For accurate engine hours, use true_engine_hours instead of engine_hours

        Args:
            vehicle_id: The unique identifier for the vehicle
            start_date: Start date from which you want to check the location history
                (format: YYYY-MM-DD)
            end_date: End date for when you want to check the location history
                (format: YYYY-MM-DD)
                IMPORTANT: The duration between start_date and end_date must not exceed 3 months
            updated_after: Optional date after which the location records have been updated
                (format: YYYY-MM-DD)

        Returns:
            Response containing vehicle location history with:
            - id: Unique identifier for the vehicle location
            - located_at: Timestamp of when the vehicle was located
            - lat: Latitude value of the vehicle's location
            - lon: Longitude value of the vehicle's location
            - bearing: Direction the vehicle is heading in degrees
            - battery_voltage: Voltage of the vehicle's battery at the time of location
            - engine_hours: Virtual engine hours at the time of location
            - type: Type of location data (e.g., "vehicle_moving")
            - description: Textual description of the vehicle's location
            - speed: Speed of the vehicle at the time of location in miles per hour (mph)
            - odometer: Virtual odometer readings captured by the Vehicle Gateway
            - fuel: Fuel level of the vehicle in gallons at the time of location
            - fuel_primary_remaining_percentage: Percentage of fuel remaining in primary fuel tank
            - fuel_secondary_remaining_percentage: Percentage of fuel remaining in secondary fuel tank
            - true_odometer: Accurate odometer readings (recommended for third-party maintenance tools)
            - true_engine_hours: Accurate engine hour readings (recommended for third-party maintenance tools)
            - veh_range: Remaining range of the vehicle based on current fuel levels
            - hvb_state_of_charge: State of charge of the High Voltage Battery (HVB) as a percentage
            - hvb_charge_status: Charge status of the High Voltage Battery (HVB)
            - hvb_charge_source: Source of charge for the High Voltage Battery (HVB)
            - hvb_lifetime_energy_output: Lifetime energy output of the High Voltage Battery (HVB)
            - driver: Details of the driver associated with the vehicle:
                - id: Unique identifier for the driver
                - first_name: First name of the driver
                - last_name: Last name of the driver
                - username: Username associated with the driver
                - email: Email address of the driver
                - driver_company_id: Company identifier associated with the driver
                - status: Status of the driver (e.g., "active")
                - role: Role of the driver (e.g., "driver")
            - vehicle_gateway: Details of the ELD device:
                - id: Unique identifier for the ELD device
                - identifier: Identifier of the ELD device
                - model: Model of the ELD device

        Reference:
            https://developer.gomotive.com/reference/fetch-a-vehicles-location-using-its-id-v3
        """
        params: Dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
        }
        if updated_after:
            params["updated_after"] = updated_after

        return await self._request(
            "GET", f"/v3/vehicle_locations/{vehicle_id}", params=params
        )

    async def get_driver_locations(
        self,
        per_page: int = 25,
        page_no: int = 1,
    ) -> Dict[str, Any]:
        """
        List the drivers with location and vehicle info.

        Use this API to fetch a list of all the existing drivers of your company. This API
        will also fetch details such as existing location and the vehicle that the driver is
        using. This is helpful if you want an overview of all the drivers and their driven
        vehicles.

        Args:
            per_page: Number of results per page (default: 25)
            page_no: Current page number (default: 1)

        Returns:
            Response containing drivers with location and vehicle info:
            - users: Array of user objects, each containing:
                - id: Unique identifier for the user
                - first_name: First name of the user
                - last_name: Last name of the user
                - username: Username of the user
                - email: Email address of the user
                - driver_company_id: ID of the company associated with the driver
                - status: Status of the user (e.g., "deactivated")
                - role: Role of the user, such as "driver"
                - current_location: Current location details of the user:
                    - id: Unique identifier for the location
                    - lat: Latitude of the user's current location
                    - lon: Longitude of the user's current location
                    - description: Textual description of the user's current location
                    - located_at: Timestamp of when the location was recorded
                - current_vehicle: Current vehicle details associated with the user:
                    - id: Unique identifier for the vehicle
                    - number: Fleet number assigned to the vehicle
                    - year: Year the vehicle was manufactured
                    - make: Manufacturer of the vehicle
                    - model: Model of the vehicle
                    - vin: Vehicle Identification Number (VIN) of the vehicle
            - pagination: Pagination details for the response:
                - per_page: Number of results per page
                - page_no: Current page number
                - total: Total number of results available

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-drivers-with-location-and-vehicle-info
        """
        params: Dict[str, Any] = {
            "per_page": per_page,
            "page_no": page_no,
        }

        return await self._request("GET", "/v1/driver_locations", params=params)

    async def get_asset_locations(
        self,
        per_page: int = 25,
        page_no: int = 1,
    ) -> Dict[str, Any]:
        """
        List all the assets and their locations.

        Use this API to fetch a list of all the assets of your company along with their
        current location information. This provides an overview of all assets and where
        they are currently located.

        Args:
            per_page: Number of results per page (default: 25)
            page_no: Current page number (default: 1)

        Returns:
            Response containing assets with location info:
            - assets: Array of asset objects, each containing:
                - id: Unique identifier for the asset
                - name: Name or number of the asset
                - type: Type of asset (e.g., "trailer", "container")
                - make: Make of the asset
                - model: Model of the asset
                - year: Year of manufacture
                - status: Status of the asset (e.g., "active", "deactivated")
                - current_location: Current location details of the asset:
                    - id: Unique identifier for the location
                    - lat: Latitude of the asset's current location
                    - lon: Longitude of the asset's current location
                    - description: Textual description of the asset's current location
                    - located_at: Timestamp of when the location was recorded
                - metric_units: Indicates if the asset uses metric units
            - pagination: Pagination details for the response:
                - per_page: Number of results per page
                - page_no: Current page number
                - total: Total number of results available

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-assets-and-their-locations
        """
        params: Dict[str, Any] = {
            "per_page": per_page,
            "page_no": page_no,
        }

        return await self._request("GET", "/v1/asset_locations", params=params)

    async def get_asset_location_by_id(
        self,
        asset_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List the location details of an asset.

        Use this API to fetch the location details of a particular asset using its ID.
        Optionally, you can also use the query parameters to view the location details
        within a particular date range.

        Important Note:
        - The date range between the start_time and end_time should not exceed more than 3 months.

        Args:
            asset_id: The unique identifier for the asset
            start_time: Optional start time (YYYY-MM-DD format) to filter location history
            end_time: Optional end time (YYYY-MM-DD format) to filter location history
                IMPORTANT: The duration between start_time and end_time must not exceed 3 months

        Returns:
            Response containing asset location details with:
            - asset: Details of the asset:
                - id: Unique identifier for the asset
                - name: Name assigned to the asset
                - status: Current status of the asset (e.g., "active")
                - type: Type of asset (e.g., "low_boy")
                - vin: Vehicle Identification Number (VIN) of the asset
                - license_plate_state: State where the asset's license plate was issued
                - license_plate_number: License plate number of the asset
                - make: Manufacturer of the asset
                - model: Model of the asset
                - year: Year the asset was manufactured
                - axle: Axle details of the asset
                - weight_metric_units: Indicates whether the asset's weight is measured in metric units
                - length_metric_units: Indicates whether the asset's length is measured in metric units
                - leased: Indicates whether the asset is leased
                - notes: Additional notes about the asset
                - length: Length of the asset
                - gvwr: Gross Vehicle Weight Rating (GVWR) of the asset
                - gawr: Gross Axle Weight Rating (GAWR) of the asset
                - asset_gateway: Details about the asset's gateway:
                    - id: Unique identifier for the asset's gateway
                    - identifier: Identifier for the asset's gateway
                    - active: Indicates whether the asset's gateway is active
            - breadcrumbs: Array of breadcrumb locations for the asset:
                - uuid: Unique identifier for the breadcrumb
                - lat: Latitude of the breadcrumb location
                - lon: Longitude of the breadcrumb location
                - bearing: Bearing (direction) of the asset at the time of the breadcrumb
                - speed: Speed of the asset at the time of the breadcrumb
                - motion_description: Description of the asset's motion at the time of the breadcrumb
                - moving: Indicates whether the asset was moving at the time of the breadcrumb
                - address: Address of the breadcrumb location
                - located_at: Timestamp when the asset was located at the breadcrumb location

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-assets-and-their-locations-using-their-ids
        """
        params: Dict[str, Any] = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request(
            "GET", f"/v1/asset_locations/{asset_id}", params=params
        )

    async def get_freight_visibility_vehicle_locations(self) -> Dict[str, Any]:
        """
        Fetch the location of all subscribed vehicles.

        This endpoint provides important details of subscribed vehicles such as driver info,
        latitude and longitude coordinates, initial stop, final stop, and current location.
        This is part of the Freight Visibility API for tracking vehicles that have been
        subscribed to location tracking.

        Returns:
            Response containing vehicle details with:
            - data: Object containing vehicle details and pagination information
                - vehicle_details: Array of vehicle detail objects, each containing:
                    - start_time: The start time of the vehicle details (DateTime)
                    - end_time: The end time of the vehicle details (DateTime)
                    - load_id: The ID of the load associated with the vehicle (if applicable)
                    - load_details: Additional information about the load
                    - total_distance: The total distance traveled by the vehicle:
                        - unit: The unit of distance (e.g., "mi", "km")
                        - value: The numeric value of the total distance
                    - initial_stop: The initial stop location coordinates:
                        - lat: Latitude of the initial stop
                        - lon: Longitude of the initial stop
                    - final_stop: The final stop location coordinates:
                        - lat: Latitude of the final stop
                        - lon: Longitude of the final stop
                    - vehicle_location: Details about the vehicle's current location:
                        - lat: Latitude of the vehicle's location
                        - lon: Longitude of the vehicle's location
                        - located_at: Time when the vehicle was located (DateTime)
                        - description: A textual description of the vehicle's location
                    - current_driver: Information about the current driver:
                        - id: The ID of the driver
                        - first_name: The first name of the driver
                        - last_name: The last name of the driver
                        - email: The email of the driver
                        - status: The status of the driver
                        - role: The role of the driver
                    - vehicle_id: The unique identifier of the vehicle
                    - vehicle_name: The name of the vehicle
                    - company_id: The company associated with the vehicle
                    - dot_ids: List of DOT IDs associated with the vehicle
                    - trailer_id: The trailer ID attached to the vehicle
                    - tracking_subscription_id: The tracking subscription ID

        Reference:
            https://developer.gomotive.com/reference/fetch-the-location-of-all-subscribed-vehicles
        """
        return await self._request("GET", "/v1/freight_visibility/vehicle_locations")

    async def subscribe_to_location(
        self,
        entity_type: str,
        entity_id: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """
        Subscribe to the location of a vehicle or an asset.

        When you subscribe to the location of an asset or a vehicle, you are essentially
        tracking the location of that object. You must specify how long you want to subscribe
        to the location (how long you want to track the location) using start_time and end_time.

        Important Requirements:
        1. For vehicles:
           - Vehicle must be owned by a company
           - Vehicle status must be 'active', not 'deactivated'
        2. For assets:
           - Asset status must be 'active', not 'deactivated'
           - Every asset must have an asset gateway assigned to it
        3. This endpoint does not allow overlapping of tracking instances
        4. start_time must be less than 2 weeks from the current date
        5. Minimum difference between start_time and end_time: 1 hour
        6. Maximum difference between start_time and end_time: 5 days

        Args:
            entity_type: Type of entity to track ("vehicle" or "asset")
            entity_id: ID of the vehicle or asset to track
            start_time: ISO 8601 start time for tracking (must be < 2 weeks from now)
            end_time: ISO 8601 end time for tracking
                - Must be at least 1 hour after start_time
                - Must be at most 5 days after start_time

        Returns:
            Response containing:
            - tracking_subscription_id: ID for tracking the location of the asset or vehicle

        Raises:
            HTTPException: If requirements are not met (overlapping subscription, invalid
                          entity status, time constraints violated, etc.)

        Reference:
            https://developer.gomotive.com/reference/subscribe-to-the-location-of-a-vehicle-or-an-asset
        """
        if entity_type not in ["vehicle", "asset"]:
            raise ValueError("entity_type must be 'vehicle' or 'asset'")

        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "start_time": start_time,
            "end_time": end_time,
        }

        return await self._request("POST", "/v1/freight_visibility/subscribe", json_data=payload)

    async def modify_subscription_duration(
        self,
        tracking_subscription_id: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """
        Modify the duration of a tracking subscription.

        Use this API to modify the duration of the start_time and end_time for a tracking
        subscription that was created earlier. You must specify the tracking subscription ID
        and provide the new start time and end time.

        Modification Requirements:
        1. start_time must be less than 2 weeks from the current date
        2. Minimum difference between start_time and end_time: 1 hour
        3. Maximum difference between start_time and end_time: 5 days
        4. New start_time must be earlier than the previous date
        5. New end_time must be later than the previous date
        6. This endpoint does not allow overlapping of tracking instances
        7. For vehicles:
           - Vehicle must be owned by a company
           - Vehicle status must be 'active', not 'deactivated'
        8. For assets:
           - Asset status must be 'active', not 'deactivated'
           - Every asset must have an asset gateway assigned to it

        Args:
            tracking_subscription_id: ID of the tracking subscription to modify
            start_time: New ISO 8601 start time for tracking
                - Must be less than 2 weeks from current date
                - Must be earlier than the previous start_time
            end_time: New ISO 8601 end time for tracking
                - Must be at least 1 hour after start_time
                - Must be at most 5 days after start_time
                - Must be later than the previous end_time

        Returns:
            Response containing:
            - success: Boolean indicating if the modification was successful
                - Mostly "true" if successful
                - Status 400 if requirements are not met

        Raises:
            HTTPException: If requirements are not met (overlapping subscription, invalid
                          time constraints, entity status issues, etc.)

        Reference:
            https://developer.gomotive.com/reference/modify-the-duration-of-a-subscription
        """
        params = {
            "start_time": start_time,
            "end_time": end_time,
        }

        return await self._request(
            "PUT",
            f"/v1/freight_visibility/subscribe/{tracking_subscription_id}",
            params=params,
        )

    async def cancel_subscription(
        self,
        tracking_subscription_id: str,
    ) -> Dict[str, Any]:
        """
        Cancel the subscription to location tracking.

        Use this API to cancel the subscription to track either a vehicle or an asset.
        When you first subscribe to this feature, you will be provided a
        `tracking_subscription_id`. You must specify the same ID to cancel the subscription.
        This will delete the subscription to the tracking of that particular vehicle or asset.

        Important Notes:
        1. Billing: When you initially subscribe to location tracking, you will be billed
           for the entire duration (start_time & end_time). When you cancel the subscription,
           even if you have some days pending for the duration to complete, you will be billed
           for the entire duration. There will not be any pro-rata billing for the duration.
        2. Cancellation Window: You cannot cancel a subscription that has already ended.
           Since the duration has already passed, you will be billed for the complete duration.
           Only subscriptions that are not ended (the end_date is yet to come) can be cancelled.
        3. Dashboard Tracking: If you cancel a subscription, it does not mean that you will
           not be able to track your vehicles or assets. The Motive Dashboard will still show
           you the tracking of the vehicles or assets as usual, irrespective of your subscription
           to the location tracking feature.
        4. Location Information: When pulling the location information of a vehicle or an asset,
           the user will not see the subscription information. This info will be removed.

        Args:
            tracking_subscription_id: ID of the tracking subscription to cancel
                (provided when the subscription was created)

        Returns:
            Response containing:
            - success: Boolean indicating if the subscription was deleted successfully
                - Mostly "true" if successful
                - Status 400 if the subscription cannot be cancelled (e.g., already ended)

        Raises:
            HTTPException: If the subscription cannot be cancelled (e.g., already ended,
                          invalid subscription ID, etc.)

        Reference:
            https://developer.gomotive.com/reference/cancel-the-subscription-to-location-tracking
        """
        return await self._request(
            "DELETE",
            f"/v1/freight_visibility/subscribe/{tracking_subscription_id}",
        )

    async def get_companies_that_allow_tracking(self) -> Dict[str, Any]:
        """
        List the companies that allow vehicle tracking.

        Usually, a vehicle location or tracking information can be shared with third-parties,
        brokers, or stakeholders for regular monitoring as well as to provide certain services.
        This location sharing is done for a limited time period.

        This endpoint is mostly used by brokers or third-party agents who want to know which
        companies allow the sharing of vehicle tracking information.

        Returns:
            Response containing company information with:
            - data: Object containing information about companies
                - companies: Array of company detail objects, each containing:
                    - name: The name of the company
                    - company_id: Unique identifier for the company
                    - dot_ids: List of DOT IDs associated with the company
                    - street: Street address of the company
                    - city: City where the company is located
                    - state: State where the company is located
                    - zip: ZIP code of the company address

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-companies-that-allow-vehicle-tracking
        """
        return await self._request("GET", "/v1/freight_visibility/companies")

    async def check_carrier_consent(self) -> Dict[str, Any]:
        """
        Check if your company is associated with a carrier and has necessary permissions.

        Use this API to find out if your company is associated with the carrier and has all
        the necessary permissions to fetch their data. This endpoint is primarily used by
        brokers or third-party agents to determine if they have the consent of the carriers
        for data sharing. This ensures alignment with proper data-sharing agreements and
        legal compliances.

        Important Note:
        - If the response is `true`, then you have the consent of the carrier for data-sharing.
        - If the response is `false`, then you do not have the required permissions.
        - It is recommended to procure the permissions first and then proceed to data fetching
          or data sharing.

        Returns:
            Response containing:
            - company_associated: Boolean indicating if your company is associated with the carrier
                - `true`: You have the consent of the carrier for data-sharing
                - `false`: You do not have the required permissions

        Reference:
            https://developer.gomotive.com/reference/check-a-carriers-consent
        """
        return await self._request("GET", "/v1/freight_visibility/company_associated")

    async def get_nearby_vehicles(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location: Optional[str] = None,
        radius: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a list of all vehicles that are nearby to your specified location.

        Use this API to find vehicles that are nearby to a specified location. For example,
        if you have a pickup at Walnut Creek and want to know which vehicles are available
        for a service, this API will fetch all the nearby vehicles to Walnut Creek as well
        as their details and current location.

        Args:
            latitude: Optional latitude coordinate for the search location
            longitude: Optional longitude coordinate for the search location
            location: Optional location name or address (e.g., "Walnut Creek")
            radius: Optional search radius in kilometers or miles

        Returns:
            Response containing nearby vehicles with:
            - List of vehicles near the specified location
            - Vehicle details and current location information
            - Vehicle availability status

        Reference:
            https://developer.gomotive.com/reference/fetch-all-the-nearby-vehicles-as-per-the-specified-location
        """
        params: Dict[str, Any] = {}
        if latitude is not None:
            params["latitude"] = latitude
        if longitude is not None:
            params["longitude"] = longitude
        if location:
            params["location"] = location
        if radius is not None:
            params["radius"] = radius

        return await self._request("GET", "/v1/freight_visibility/vehicle_association", params=params)

    # Alias for backward compatibility
    async def get_vehicle_association(self) -> Dict[str, Any]:
        """
        Get vehicle association information for freight visibility.
        
        This is an alias for get_nearby_vehicles().
        """
        return await self.get_nearby_vehicles()

    async def get_nearby_vehicles_v2(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        destination_latitude: Optional[float] = None,
        destination_longitude: Optional[float] = None,
        expected_time: Optional[str] = None,
        location: Optional[str] = None,
        radius: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a list of all vehicles nearby to your specified location (v2 with scoring system).

        This is version 2 of the nearby vehicles endpoint that uses an intelligent scoring system
        to rank vehicles based on multiple criteria. Vehicles are sorted by score, with the highest
        scoring vehicles appearing first.

        Scoring System:
        The endpoint calculates a score (0.0 to 1.0) based on three parameters:

        1. **Vehicle Proximity**: Vehicles that can arrive quickly to the location within the
           expected time receive higher scores. For example, if the current time is 7:00 PM and
           you set expected_time as 9:00 PM, vehicles that can arrive fastest within the expected
           time will be given preference and awarded a higher score.

        2. **Hours of Service (HOS)**: The endpoint calculates the Hours of Service of all drivers
           who are nearby and can reach fast. Drivers who have remaining Hours of Service that is
           within the expected time will receive additional scoring.

        3. **Vehicle Direction**: The endpoint observes the direction of vehicles towards the
           provided destination's latitude and longitude. It assigns higher scores to vehicles
           that are heading towards the direction of the destination.

        Scores are calculated in decimals from 0.0 to 1.0:
        - 0.0 (lowest): None of the parameters were met
        - 1.0 (highest): All parameters were met
        - Multiple vehicles may have a 1.0 score

        Args:
            latitude: Optional latitude coordinate for the search location
            longitude: Optional longitude coordinate for the search location
            destination_latitude: Optional destination latitude for direction scoring
            destination_longitude: Optional destination longitude for direction scoring
            expected_time: Optional ISO 8601 datetime for expected arrival time
                (used for proximity and HOS scoring)
            location: Optional location name or address
            radius: Optional search radius in kilometers or miles

        Returns:
            Response containing nearby vehicles sorted by matching score with:
            - data: Object containing company and vehicle details:
                - company_id: Unique identifier for the company
                - dot_ids: List of DOT IDs associated with the company
                - integration_status: Current integration status of the company
                - vehicle_details: Array of vehicle detail objects, each containing:
                    - vehicle_id: Unique ID of the vehicle
                    - vehicle_name: Name or identifier of the vehicle
                    - eld_device_id: ID of the ELD device installed in the vehicle
                    - eld_identifier: Unique identifier of the ELD device
                    - trailer_id: Identifier for the trailer attached to the vehicle
                    - driver: Driver information:
                        - id: Unique identifier for the driver
                        - first_name: First name of the driver
                        - last_name: Last name of the driver
                    - located_at: Timestamp of when the vehicle was last located
                    - description: Description of the vehicle's current location
                    - distance_origin: Distance of the vehicle from the origin:
                        - value: The distance value
                        - unit: Unit of the distance (e.g., "miles")
                    - matching_score: Score (0.0 to 1.0) representing how well the vehicle
                      matches the criteria (proximity, HOS, direction)

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-nearby-vehicles-v2
        """
        params: Dict[str, Any] = {}
        if latitude is not None:
            params["latitude"] = latitude
        if longitude is not None:
            params["longitude"] = longitude
        if destination_latitude is not None:
            params["destination_latitude"] = destination_latitude
        if destination_longitude is not None:
            params["destination_longitude"] = destination_longitude
        if expected_time:
            params["expected_time"] = expected_time
        if location:
            params["location"] = location
        if radius is not None:
            params["radius"] = radius

        return await self._request("GET", "/v2/freight_visibility/vehicle_association", params=params)

    async def get_active_subscriptions(
        self,
        vehicle_id: Optional[str] = None,
        vehicle_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a list of all active vehicle subscriptions.

        Use this API to fetch a list of all the active vehicle subscriptions. If you want to
        narrow down the results, you may enter the ID of the vehicle or the name of the vehicle,
        to view if you are subscribed to it or not.

        Args:
            vehicle_id: Optional vehicle ID to filter subscriptions
            vehicle_name: Optional vehicle name to filter subscriptions

        Returns:
            Response containing active subscriptions with:
            - data: Object containing company and subscription details:
                - company_id: Unique identifier for the company
                - dot_ids: List of Department of Transportation (DOT) IDs associated with the company
                - vehicle_subscriptions: Array of vehicle subscription objects, each containing:
                    - vehicle_id: The unique ID of the vehicle
                    - vehicle_name: The name or identifier of the vehicle
                    - subscriptions: Array of subscription detail objects:
                        - tracking_subscription_id: The unique ID of the tracking subscription
                        - start_time: Timestamp indicating when the tracking subscription started
                        - end_time: Timestamp indicating when the tracking subscription ended

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-active-subscriptions
        """
        params: Dict[str, Any] = {}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if vehicle_name:
            params["vehicle_name"] = vehicle_name

        return await self._request("GET", "/v1/freight_visibility/vehicle_subscriptions", params=params)

    async def subscribe_to_location_with_stops(
        self,
        entity_type: str,
        entity_id: str,
        start_time: str,
        end_time: str,
        initial_stop: Optional[str] = None,
        final_stop: Optional[str] = None,
        total_distance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Subscribe to the location of a vehicle or an asset with stop and distance information.

        This is an alternative version of the subscribe endpoint that allows specifying
        initial stop, final stop, and total distance as query parameters.

        Args:
            entity_type: Type of entity to track ("vehicle" or "asset")
            entity_id: ID of the vehicle or asset to track
            start_time: ISO 8601 start time for tracking
            end_time: ISO 8601 end time for tracking
            initial_stop: Optional initial stop location
            final_stop: Optional final stop location
            total_distance: Optional total distance for the route

        Returns:
            Response containing tracking subscription details

        Reference:
            Motive API - Freight Visibility Subscribe with Stops
        """
        if entity_type not in ["vehicle", "asset"]:
            raise ValueError("entity_type must be 'vehicle' or 'asset'")

        params: Dict[str, Any] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "start_time": start_time,
            "end_time": end_time,
        }
        if initial_stop:
            params["initial_stop"] = initial_stop
        if final_stop:
            params["final_stop"] = final_stop
        if total_distance:
            params["total_distance"] = total_distance

        return await self._request("POST", "/v1/freight_visibility/subscribe", params=params)

    async def get_subscription_details(
        self,
        tracking_subscription_id: str,
    ) -> Dict[str, Any]:
        """
        Get details of a specific tracking subscription.

        Args:
            tracking_subscription_id: ID of the tracking subscription

        Returns:
            Response containing subscription details

        Reference:
            Motive API - Freight Visibility Get Subscription Details
        """
        return await self._request(
            "GET",
            f"/v1/freight_visibility/subscribe/{tracking_subscription_id}",
        )

    async def get_vehicle_locations_details(
        self,
        vehicle_id: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """
        Fetch recent location details of a specific vehicle (within 24 hours).

        Use this API to fetch the recent location details of a specific vehicle. It is important
        to note that you can only view the location history of the past 24 hours or less.

        Important Requirements:
        1. The start_time and end_time must be within the past 24 hours or less. This endpoint
           will not fetch historical location data beyond 24 hours.
        2. You must have an active tracking subscription for the vehicle.
        3. The vehicle must not be deactivated.
        4. The start_time and end_time must match or be within the start_time and end_time of
           the vehicle subscription.

        Args:
            vehicle_id: ID of the vehicle to fetch location details for
            start_time: ISO 8601 start time for location history
                - Must be within the past 24 hours
                - Must match or be within the subscription's start_time
            end_time: ISO 8601 end time for location history
                - Must be within the past 24 hours
                - Must match or be within the subscription's end_time

        Returns:
            Response containing vehicle location details with:
            - data: Object containing vehicle location information:
                - vehicle_locations: Array of vehicle location objects, each containing:
                    - id: Unique identifier for the vehicle location event
                    - located_at: Timestamp of when the vehicle location was recorded
                    - lat: Latitude of the vehicle's location
                    - lon: Longitude of the vehicle's location
                    - description: Descriptive location of the vehicle (e.g., city, state)
                    - bearing: The vehicle's directional bearing in degrees
                    - engine_hours: Number of engine hours recorded
                    - type: Type of vehicle event (e.g., "vehicle moving")
                    - speed: Speed of the vehicle in miles per hour
                    - fuel: The amount of fuel remaining in gallons
                    - odometer: The vehicle's odometer reading in miles

        Raises:
            HTTPException: If requirements are not met (no active subscription, vehicle deactivated,
                          time range outside 24 hours, time range outside subscription window, etc.)

        Reference:
            https://developer.gomotive.com/reference/fetch-recent-location-details-of-a-vehicle-within-24-hours
        """
        params = {
            "vehicle_id": vehicle_id,
            "start_time": start_time,
            "end_time": end_time,
        }

        return await self._request("GET", "/v1/freight_visibility/vehicle_locations/details", params=params)

    async def get_asset_association(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List location of company assets based on proximity.

        Use this API to fetch a list of all the company assets. The response of this endpoint
        sorts the assets based on their proximity to your location or the location of interest.

        Important Note:
        - This endpoint does not list assets that do not have an asset gateway assigned or installed.

        Args:
            latitude: Optional latitude coordinate for proximity sorting
            longitude: Optional longitude coordinate for proximity sorting
            location: Optional location name or address for proximity sorting

        Returns:
            Response containing assets sorted by proximity with:
            - data: Object containing asset and company details:
                - asset_details: Array of asset detail objects, each containing:
                    - name: The name of the asset
                    - status: The current status of the asset (e.g., "active")
                    - type: The type of the asset (e.g., "dry_box", "low_boy")
                    - vin: Vehicle Identification Number (VIN) of the asset, if applicable
                    - license_plate_state: State of the license plate associated with the asset
                    - license_plate_number: License plate number of the asset
                    - make: The manufacturer of the asset
                    - model: The model of the asset
                    - year: The year the asset was manufactured
                    - axle: Number of axles on the asset
                    - weight_metric_units: Indicates whether weight is measured in metric units
                    - length_metric_units: Indicates whether length is measured in metric units
                    - leased: Indicates whether the asset is leased
                    - notes: Additional notes associated with the asset
                    - length: Length of the asset, if available
                    - gvwr: Gross Vehicle Weight Rating (GVWR) of the asset
                    - gawr: Gross Axle Weight Rating (GAWR) of the asset
                    - asset_gateway: Gateway details for the asset:
                        - id: Unique identifier of the asset gateway
                        - identifier: Identifier of the asset gateway
                        - active: Indicates whether the asset gateway is active
                    - asset_id: Unique identifier for the asset
                    - trailer_id: Trailer ID associated with the asset, if applicable
                    - located_at: Timestamp of when the asset location was recorded
                    - lat: Latitude of the asset's location
                    - lon: Longitude of the asset's location
                    - distance_origin: Distance of the asset from the provided location, in kilometers
                    - description: Descriptive text of the asset's current location and distance from the origin
                - company_id: Unique identifier for the company
                - dot_ids: List of DOT (Department of Transportation) IDs associated with the company
                - integration_status: Status of the company's integration

        Reference:
            https://developer.gomotive.com/reference/fetch-location-of-company-assets-based-on-proximity
        """
        params: Dict[str, Any] = {}
        if latitude is not None:
            params["latitude"] = latitude
        if longitude is not None:
            params["longitude"] = longitude
        if location:
            params["location"] = location

        return await self._request("GET", "/v1/freight_visibility/asset_association", params=params)

    async def get_asset_locations(self) -> Dict[str, Any]:
        """
        List the locations of all the subscribed assets.

        Use this API to fetch the locations of all the assets that you've subscribed to.
        This endpoint provides comprehensive asset information including load details,
        location data, and asset specifications.

        Returns:
            Response containing subscribed asset locations with:
            - data: Object containing asset and company details:
                - asset_details: Array of asset detail objects, each containing:
                    - start_time: Start time of asset activity
                    - end_time: End time of asset activity
                    - load_id: Load ID associated with the asset
                    - load_details: Additional details regarding the load
                    - total_distance: Total distance traveled by the asset
                    - initial_stop: Initial stop location of the asset
                    - final_stop: Final stop location of the asset
                    - asset: Asset-related details:
                        - id: Unique identifier for the asset
                        - name: Name of the asset
                        - status: Status of the asset (e.g., "active")
                        - type: Type of the asset (e.g., "dry_box")
                        - vin: Vehicle Identification Number (VIN) for the asset
                        - license_plate_state: State where the license plate is registered
                        - license_plate_number: License plate number of the asset
                        - make: Manufacturer of the asset
                        - model: Model of the asset
                        - year: Manufacturing year of the asset
                        - axle: Number of axles on the asset
                        - weight_metric_units: Indicates whether weight is measured in metric units
                        - length_metric_units: Indicates whether length is measured in metric units
                        - leased: Indicates if the asset is leased
                        - notes: Additional notes about the asset
                        - length: Length of the asset
                        - gvwr: Gross Vehicle Weight Rating (GVWR) of the asset
                        - gawr: Gross Axle Weight Rating (GAWR) of the asset
                    - asset_gateway: Details of the asset's gateway:
                        - id: Unique identifier for the asset gateway
                        - identifier: Identifier of the asset gateway
                        - active: Indicates whether the asset gateway is active
                    - last_location: The most recent location details of the asset:
                        - address: Address of the asset's last location
                        - bearing: Direction in which the asset was moving, in degrees
                        - lat: Latitude of the asset's last location
                        - lon: Longitude of the asset's last location
                        - located_at: Timestamp of when the last location was recorded
                        - ground_speed_kph: Ground speed of the asset in kilometers per hour
                        - battery_capacity: Battery capacity of the asset in percentage
                        - uuid: Unique identifier for the location entry
                        - moving: Indicates if the asset was moving at the time
                        - formatted_address: Formatted address of the asset's last location
                    - company_id: Unique identifier of the company
                    - dot_ids: List of DOT (Department of Transportation) IDs associated with the company
                    - trailer_id: Identifier of the trailer associated with the asset
                    - tracking_subscription_id: Tracking subscription ID for the asset

        Reference:
            https://developer.gomotive.com/reference/fetch-the-locations-of-all-the-subscribed-assets
        """
        return await self._request("GET", "/v1/freight_visibility/asset_locations")

    async def get_fuel_purchases(
        self,
        vehicle_id: Optional[str] = None,
        driver_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        fuel_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch all fuel purchases of your company.

        Use this API to view all the fuel purchases done by your drivers or fleet admins
        in your company. This allows you to view and monitor the fuel purchases and at
        the same time prepare necessary data for tax filings.

        Args:
            vehicle_id: Optional vehicle ID to filter purchases
            driver_id: Optional driver ID to filter purchases
            start_date: Optional start date (ISO 8601 format) to filter purchases
            end_date: Optional end date (ISO 8601 format) to filter purchases
            jurisdiction: Optional jurisdiction (state or region code) to filter purchases
            fuel_type: Optional fuel type to filter purchases (e.g., "diesel")
            limit: Maximum number of purchases to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing fuel purchases with:
            - Array of fuel purchase objects, each containing:
                - id: Unique identifier for the fuel purchase
                - offline_id: The offline identifier associated with the fuel purchase
                - purchased_at: Date and time when the fuel was purchased (DateTime)
                - jurisdiction: The jurisdiction where the fuel purchase occurred (e.g., state or region code)
                - fuel_type: The type of fuel purchased (e.g., "diesel")
                - ref_no: The reference number for the fuel purchase
                - vendor: The vendor from whom the fuel was purchased
                - total_cost: The total cost of the fuel purchase
                - currency: The currency used for the purchase (e.g., "USD")
                - fuel: The amount of fuel purchased
                - fuel_unit: The unit of measurement for the fuel (e.g., "gal")
                - odometer: The odometer reading at the time of fuel purchase
                - odometer_unit: The unit of measurement for the odometer (e.g., "mi")
                - receipt_upload_url: The URL where the receipt can be downloaded
                - receipt_filename: The filename of the receipt
                - uploader: Information about the person who uploaded the fuel purchase:
                    - id: Unique identifier of the uploader
                    - first_name: First name of the uploader
                    - last_name: Last name of the uploader
                    - email: Email address of the uploader
                    - role: Role of the uploader
                    - deactivated_at: Date and time when the uploader was deactivated (if applicable)
                - vehicle: Information about the vehicle associated with the fuel purchase:
                    - id: Unique identifier of the vehicle
                    - number: Vehicle number
                    - year: Year of the vehicle
                    - make: Make of the vehicle
                    - model: Model of the vehicle
                    - vin: Vehicle Identification Number
                    - metric_units: Indicates if the vehicle uses metric units
                - driver: Information about the driver associated with the fuel purchase:
                    - id: Unique identifier of the driver
                    - first_name: First name of the driver
                    - last_name: Last name of the driver
                    - username: Username of the driver
                    - email: Email address of the driver
                    - driver_company_id: ID of the driver's company (if applicable)
                    - status: Status of the driver (e.g., "active")
                    - role: Role of the driver

        Reference:
            https://developer.gomotive.com/reference/fetch-all-the-fuel-purchases-of-your-company
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if driver_id:
            params["driver_id"] = driver_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        if fuel_type:
            params["fuel_type"] = fuel_type

        return await self._request("GET", "/v1/fuel_purchases", params=params)

    async def get_fuel_purchase_by_id(self, fuel_purchase_id: str) -> Dict[str, Any]:
        """
        View a specific fuel purchase by its ID.

        Use this API to find out the fuel purchase details by entering its ID. You must
        specify the ID of the fuel purchase transaction as a path parameter.

        Args:
            fuel_purchase_id: The unique identifier for the fuel purchase

        Returns:
            Response containing fuel purchase details with:
            - id: Unique identifier for the fuel purchase
            - offline_id: The offline identifier associated with the fuel purchase
            - purchased_at: Date and time when the fuel was purchased (DateTime)
            - jurisdiction: The jurisdiction where the fuel purchase occurred (e.g., state or region code)
            - fuel_type: The type of fuel purchased (e.g., "diesel")
            - ref_no: The reference number for the fuel purchase
            - vendor: The vendor from whom the fuel was purchased
            - total_cost: The total cost of the fuel purchase
            - currency: The currency used for the purchase (e.g., "USD")
            - fuel: The amount of fuel purchased
            - fuel_unit: The unit of measurement for the fuel (e.g., "gal")
            - odometer: The odometer reading at the time of fuel purchase
            - odometer_unit: The unit of measurement for the odometer (e.g., "mi")
            - receipt_upload_url: The URL where the receipt can be downloaded
            - receipt_filename: The filename of the receipt
            - uploader: Information about the person who uploaded the fuel purchase:
                - id: Unique identifier of the uploader
                - first_name: First name of the uploader
                - last_name: Last name of the uploader
                - email: Email address of the uploader
                - role: Role of the uploader
                - deactivated_at: Date and time when the uploader was deactivated (if applicable)
            - vehicle: Information about the vehicle associated with the fuel purchase:
                - id: Unique identifier of the vehicle
                - number: Vehicle number
                - year: Year of the vehicle
                - make: Make of the vehicle
                - model: Model of the vehicle
                - vin: Vehicle Identification Number
                - metric_units: Indicates if the vehicle uses metric units
            - driver: Information about the driver associated with the fuel purchase:
                - id: Unique identifier of the driver
                - first_name: First name of the driver
                - last_name: Last name of the driver
                - username: Username of the driver
                - email: Email address of the driver
                - driver_company_id: ID of the driver's company (if applicable)
                - status: Status of the driver (e.g., "active")
                - role: Role of the driver

        Reference:
            https://developer.gomotive.com/reference/view-the-fuel-purchases-by-an-id
        """
        return await self._request("GET", f"/v1/fuel_purchases/{fuel_purchase_id}")

    async def get_motive_card_transactions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        transaction_status: Optional[str] = None,
        per_page: int = 25,
        page_no: int = 1,
    ) -> Dict[str, Any]:
        """
        List of all the Motive Card transactions.

        Use this API to fetch a list of all the Motive card transactions that happened at
        your organisation. This API fetches the details of the transactions by the drivers,
        as well as other employees who use the Motive card for their daily expenses.

        Important Note:
        - The query parameters `start_date` and `end_date` must be used together.
          They are not mutually exclusive.

        Args:
            start_date: Optional start date (YYYY-MM-DD format) to filter transactions
                Must be used together with end_date
            end_date: Optional end date (YYYY-MM-DD format) to filter transactions
                Must be used together with start_date
            driver_id: Optional driver ID to filter transactions
            vehicle_id: Optional vehicle ID to filter transactions
            transaction_status: Optional transaction status to filter (e.g., "posted")
            per_page: Number of results per page (default: 25)
            page_no: Current page number (default: 1)

        Returns:
            Response containing Motive Card transactions with:
            - transactions: Array of transaction objects, each containing:
                - id: Unique identifier for the transaction
                - transaction_status: Status of the transaction (e.g., "posted")
                - transaction_time: Timestamp when the transaction occurred
                - posted_at: Timestamp when the transaction was posted
                - updated_at: Timestamp when the transaction was last updated
                - transaction_dispute: Dispute status of the transaction, if any
                - driver_id: ID of the driver associated with the transaction
                - vehicle_id: ID of the vehicle associated with the transaction (null if not applicable)
                - last_four_digits: Last four digits of the card used in the transaction
                - invoice_number: Invoice number for the transaction
                - authorized_amount_in_micros: Authorized amount in micros (1 micro = 0.000001 currency unit)
                - total_rebate_in_micros: Total rebate amount applied to the transaction in micros
                - total_amount_before_rebate_in_micros: Total amount before applying the rebate, in micros
                - total_amount_after_rebate_in_micros: Total amount after applying the rebate, in micros
                - merchant_info: Information about the merchant where the transaction occurred:
                    - name: Name of the merchant
                    - city: City where the merchant is located
                    - state: State where the merchant is located
                    - street: Street address of the merchant
                    - country: Country where the merchant is located
                    - zip_code: ZIP code of the merchant's location
                    - address: Full address of the merchant
                    - full_address: Full formatted address of the merchant
                - decline_reason_code: Code indicating the reason for transaction decline, if applicable
                - decline_reason: Description of the reason for transaction decline, if applicable
                - transaction_reversed_time: Timestamp when the transaction was reversed, if applicable
                - pre_transaction_metadata: Pre-transaction metadata
                - line_items: Array of line items in the transaction:
                    - id: Unique identifier for the line item
                    - description: Description of the item
                    - quantity: Quantity of the item
                    - unit_price: Unit price of the item
                    - gross_amount: Gross amount of the item in micros
                    - product_type: Type of the product (e.g., "Cash", "ATM fee", "Maintenance", "Gasoline", "Diesel", "Food", etc.)
                    - unit_of_measure: Unit of measurement for the item
                    - rebate_amount_in_micros: Rebate amount applied to the item in micros
                - currency: Currency used in the transaction (e.g., "USD")

        Supported Product Types:
            - Maintenance: Automotive Glass, Brake Fluid, Motor Oil, TBA, etc.
            - Gasoline: Various grades of gasoline and ethanol blends
            - Tires: Tire purchases
            - Miscellaneous Fuel: Aviation Fuel, Biodiesel, CNG, Electric Vehicle Charge, etc.
            - Cash: Cash Advance
            - DEF: Diesel Exhaust Fluid
            - Reefer Fuel: Dyed Diesel, Reefer
            - Food: Restaurant, Soda, Beer/Wine, etc.
            - Diesel: Biodiesel, Diesel, Diesel Premium, ULSD
            - Other: Various other categories
            - Parking and Tolls: Tiedown and Hangar
            - Car Washes
            - Towing

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-motive-card-transactions
        """
        params: Dict[str, Any] = {
            "per_page": per_page,
            "page_no": page_no,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if driver_id:
            params["driver_id"] = driver_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if transaction_status:
            params["transaction_status"] = transaction_status

        return await self._request("GET", "/motive_card/v1/transactions", params=params)

    async def get_motive_card_transactions_v2(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        transaction_status: Optional[str] = None,
        transaction_type: Optional[str] = None,
        per_page: int = 25,
        page_no: int = 1,
    ) -> Dict[str, Any]:
        """
        List all the Motive Card transactions (v2).

        The Motive Cards – List all transactions (v2) endpoint returns a paginated collection
        of card transactions across your fleet, enabling finance and operations teams to
        audit spend, reconcile charges, and monitor usage in real time.

        Args:
            start_date: Optional start date (YYYY-MM-DD format) to filter transactions
            end_date: Optional end date (YYYY-MM-DD format) to filter transactions
            driver_id: Optional driver ID to filter transactions
            vehicle_id: Optional vehicle ID to filter transactions
            transaction_status: Optional transaction status to filter (e.g., "posted")
            transaction_type: Optional transaction type to filter (e.g., "purchase", "fee", "credit", "adjustment")
            per_page: Number of results per page (default: 25)
            page_no: Current page number (default: 1)

        Returns:
            Response containing Motive Card transactions (v2 format) with:
            - company_id: Unique identifier of the company
            - transactions: Array of transaction objects, each containing:
                - id: Unique identifier for the transaction
                - transaction_status: Status of the transaction (e.g., "posted")
                - transaction_type: Type of the transaction (e.g., "purchase", "fee", "credit", "adjustment")
                - transaction_time: Timestamp when the transaction occurred
                - posted_at: Timestamp when the transaction was posted
                - updated_at: Timestamp when the transaction was last updated
                - transaction_reversed_time: Timestamp when the transaction was reversed, if applicable
                - driver_id: ID of the driver associated with the transaction
                - vehicle_id: ID of the vehicle associated with the transaction (null if not applicable)
                - last_four_digits: Last four digits of the card used in the transaction
                - card_id: Unique identifier of the card used in the transaction
                - invoice_number: Invoice number for the transaction
                - authorized_amount: Authorized amount in dollars
                - total_rebate: Total rebate amount applied to the transaction in dollars
                - total_amount_before_rebate: Total amount before applying the rebate, in dollars
                - total_amount: Total amount after applying the rebate, in dollars. In the case of
                    a fee, credit, or adjustment, the impacted amount is surfaced in this field
                - decline_reason_code: Code indicating the reason for transaction decline, if applicable
                - decline_reason: Description of the reason for transaction decline, if applicable
                - currency: Currency used in the transaction (e.g., "USD")
                - order_items: Array of items involved in the transaction:
                    - quantity: Quantity of the item
                    - unit_price: Unit price of the item
                    - gross_amount: Gross amount of the item in dollars
                    - product_type: Type of the product (e.g., "Cash", "ATM fee")
                    - unit_of_measure: Unit of measurement for the item
                - rebate_items: Array of rebate details for items in the transaction:
                    - product_type: Type of the product that is considered under the rebate
                    - rebate_amount: Rebate amount applied to the product type in dollars
                - merchant_info: Information about the merchant where the transaction occurred:
                    - name: Name of the merchant
                    - city: City where the merchant is located
                    - state: State where the merchant is located
                    - street: Street address of the merchant
                    - country: Country where the merchant is located
                    - zip_code: ZIP code of the merchant's location
                    - address: Full address of the merchant
                    - full_address: Full formatted address of the merchant
                - pre_transaction_metadata: Metadata before the transaction occurred:
                    - odometer_reading: Odometer reading before the transaction
                    - odometer_unit: Unit of the odometer reading (e.g., "km")
                    - custom_info: Custom metadata associated with the transaction
                - post_transaction_metadata: Metadata after the transaction occurred:
                    - receipt_available: Whether a receipt is available for the transaction
                    - comment: Additional comments related to the transaction
                - transaction_dispute: Dispute details, if applicable

        Reference:
            https://developer.gomotive.com/reference/list-all-the-motive-card-transactions-v2
        """
        params: Dict[str, Any] = {
            "per_page": per_page,
            "page_no": page_no,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if driver_id:
            params["driver_id"] = driver_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if transaction_status:
            params["transaction_status"] = transaction_status
        if transaction_type:
            params["transaction_type"] = transaction_type

        return await self._request("GET", "/motive_card/v2/transactions", params=params)

    async def get_motive_cards(
        self,
        proximity_based_decline: Optional[bool] = None,
        transaction_requirements: Optional[str] = None,
        mobile_based_unlock: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        List the Motive Cards of your company.

        View a list of all the available Motive Cards for your company. This endpoint allows
        you to see all of the assigned cards, their statuses, to whom they are assigned, and
        also the spend control profile of each of the cards.

        Args:
            proximity_based_decline: Optional filter for cards with vehicle proximity-based
                decline settings enabled/disabled
            transaction_requirements: Optional filter for transaction requirements
            mobile_based_unlock: Optional filter for cards with mobile-based unlock enabled/disabled

        Returns:
            Response containing Motive Cards with:
            - cards: Array of card objects, each containing:
                - id: Unique identifier of the card (UUID)
                - last_four_digits: Last four digits of the card number
                - display_card_id: Display-friendly identifier for the card
                - name_line_1: First line of the cardholder's name (e.g., driver name)
                - name_line_2: Second line of the cardholder's name (e.g., company name)
                - status: Current status of the card (e.g., "active")
                - created_at: Timestamp indicating when the card was created
                - updated_at: Timestamp indicating when the card information was last updated
                - assigned_to: Information about the entity to whom the card is assigned:
                    - entity_type: Type of entity (e.g., "driver")
                    - entity_id: Unique identifier of the assigned entity
                    - entity_name: Name of the assigned entity
                - security_settings: Security-related settings for the card:
                    - status: Security status of the card (e.g., "active")
                    - is_locked: Indicates if the card is currently locked
                    - unlocked_till: Time until which the card remains unlocked, if applicable
                    - vehicle_proximity_based_decline_settings: Whether vehicle proximity-based
                        declines are enabled or not
                - spend_control_profile: Spending control profile details for the card:
                    - id: Unique identifier of the spend control profile (UUID)
                    - name: Name of the spend control profile
                    - is_default: Indicates if this profile is the default profile
                    - created_at: Timestamp when the profile was created
                    - updated_at: Timestamp when the profile was last updated
                    - spend_limits: Detailed spending limits set within the profile:
                        - daily_limit_in_cents: Daily spending limit in cents (null if not set)
                        - weekly_limit_in_cents: Weekly spending limit in cents (null if not set)
                        - monthly_limit_in_cents: Monthly spending limit in cents (null if not set)
                        - transaction_limit_in_cents: Per-transaction spending limit in cents (null if not set)
                        - billing_cycle_spend_limit_in_cents: Spending limit for current billing cycle in cents (null if not set)
                        - daily_withdrawal_limit_in_cents: Daily withdrawal limit in cents (null if not set)
                        - weekly_withdrawal_limit_in_cents: Weekly withdrawal limit in cents (null if not set)
                        - atm_withdrawal_enabled: Indicates whether ATM withdrawals are allowed
                        - enable_days: Days of the week when the card can be used (e.g., ["mon", "tue", ...])
                        - enable_start_time: Start time (24-hour format) from which card usage is enabled
                        - enable_end_time: End time (24-hour format) until which card usage is enabled
                        - created_by: ID of the user who created these spend limits (null if not applicable)
                    - spend_categories: Spending categories for this profile (e.g., ["Fuel pump"])

        Reference:
            https://developer.gomotive.com/reference/fetch-all-the-motive-cards
        """
        params: Dict[str, Any] = {}
        if proximity_based_decline is not None:
            params["proximity_based_decline"] = proximity_based_decline
        if transaction_requirements:
            params["transaction_requirements"] = transaction_requirements
        if mobile_based_unlock is not None:
            params["mobile_based_unlock"] = mobile_based_unlock

        return await self._request("GET", "/motive_card/v1/cards", params=params)

    async def get_motive_card_by_id(self, card_id: str) -> Dict[str, Any]:
        """
        Fetch the details of a Motive Card.

        View detailed info of a particular Motive Card. This endpoint fetches details such
        as display_card_id, status, last_transaction_performed_at, security_settings,
        spend_control_profile, and vehicle_proximity_based_decline_settings.

        Args:
            card_id: The unique identifier (UUID) of the Motive Card

        Returns:
            Response containing card details with:
            - cards: Array containing the card object:
                - id: Unique identifier of the card (UUID)
                - last_four_digits: Last four digits of the card number
                - display_card_id: Display-friendly identifier for the card
                - name_line_1: First line of the cardholder's name (e.g., driver name)
                - name_line_2: Second line of the cardholder's name (e.g., company name)
                - status: Current status of the card (e.g., "active")
                - created_at: Timestamp indicating when the card was created
                - updated_at: Timestamp indicating when the card information was last updated
                - last_transaction_performed_at: Timestamp of the last transaction performed
                - assigned_to: Information about the entity to whom the card is assigned:
                    - entity_type: Type of entity (e.g., "driver")
                    - entity_id: Unique identifier of the assigned entity
                    - entity_name: Name of the assigned entity
                - security_settings: Security-related settings for the card:
                    - status: Security status of the card (e.g., "active")
                    - is_locked: Indicates if the card is currently locked
                    - unlocked_till: Time until which the card remains unlocked, if applicable
                    - vehicle_proximity_based_decline_settings: Whether vehicle proximity-based
                        declines are enabled or not
                - spend_control_profile: Spending control profile details for the card:
                    - id: Unique identifier of the spend control profile (UUID)
                    - name: Name of the spend control profile
                    - is_default: Indicates if this profile is the default profile
                    - created_at: Timestamp when the profile was created
                    - updated_at: Timestamp when the profile was last updated
                    - spend_limits: Detailed spending limits set within the profile:
                        - daily_limit_in_cents: Daily spending limit in cents (null if not set)
                        - weekly_limit_in_cents: Weekly spending limit in cents (null if not set)
                        - monthly_limit_in_cents: Monthly spending limit in cents (null if not set)
                        - transaction_limit_in_cents: Per-transaction spending limit in cents (null if not set)
                        - billing_cycle_spend_limit_in_cents: Spending limit for current billing cycle in cents (null if not set)
                        - daily_withdrawal_limit_in_cents: Daily withdrawal limit in cents (null if not set)
                        - weekly_withdrawal_limit_in_cents: Weekly withdrawal limit in cents (null if not set)
                        - atm_withdrawal_enabled: Indicates whether ATM withdrawals are allowed
                        - enable_days: Days of the week when the card can be used (e.g., ["mon", "tue", ...])
                        - enable_start_time: Start time (24-hour format) from which card usage is enabled
                        - enable_end_time: End time (24-hour format) until which card usage is enabled
                        - created_by: ID of the user who created these spend limits (null if not applicable)
                    - spend_categories: Spending categories for this profile (e.g., ["Fuel pump"])

        Reference:
            https://developer.gomotive.com/reference/fetch-the-details-of-a-specific-motive-card
        """
        return await self._request("GET", f"/motive_card/v1/cards/{card_id}")

    async def take_motive_card_action(
        self,
        card_id: str,
        action: str,
        reason_code: Optional[str] = None,
        custom_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Take action on your user's Motive Card.

        Use this endpoint to take one of the following actions on the Motive Card:
        - Freeze: Put a temporary freeze on the Motive Card
        - Unfreeze: Unfreeze a Motive Card that is already frozen
        - Deactivate: Deactivate a Motive Card (permanent action)

        Important Note:
        - Deactivating a card is a permanent action
        - When deactivating, you must provide both reason_code and custom_reason

        Args:
            card_id: The unique identifier (UUID) of the Motive Card
            action: Action to take on the card ("freeze", "unfreeze", or "deactivate")
            reason_code: Required when action is "deactivate" - reason code for deactivation
            custom_reason: Required when action is "deactivate" - custom reason description

        Returns:
            Response containing action result:
            - success: Boolean indicating if the action was successful
            - message: Message describing the result

        Raises:
            ValueError: If action is "deactivate" but reason_code or custom_reason is missing

        Reference:
            https://developer.gomotive.com/reference/take-action-on-your-users-motive-card
        """
        if action == "deactivate":
            if not reason_code or not custom_reason:
                raise ValueError(
                    "reason_code and custom_reason are required when action is 'deactivate'"
                )

        payload: Dict[str, Any] = {"action": action}
        if reason_code:
            payload["reason_code"] = reason_code
        if custom_reason:
            payload["custom_reason"] = custom_reason

        return await self._request(
            "POST", f"/motive_card/v1/cards/{card_id}/actions", json_data=payload
        )

    async def get_spend_profiles(
        self,
        default_first: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        List all the spend profiles of your company.

        Use this endpoint to view a list of all the spend profiles of the users in your company.
        This endpoint provides important details such as daily, weekly, and monthly spend limits,
        spend categories, and the default status of the user.

        You can also use the optional query parameter that will list all the default profiles
        in the beginning and non-default profiles at the end.

        Args:
            default_first: Optional parameter to list default profiles first, then non-default profiles

        Returns:
            Response containing spend profiles with:
            - spend_control_profiles: Array of spend control profile objects, each containing:
                - id: Unique identifier of the spend control profile (UUID)
                - name: Name of the spend control profile
                - is_default: Indicates if this profile is the default profile
                - created_at: Timestamp when the profile was created
                - updated_at: Timestamp when the profile was last updated
                - spend_limits: Spending limits associated with the profile:
                    - daily_limit_in_cents: Daily spending limit in cents
                    - weekly_limit_in_cents: Weekly spending limit in cents
                    - monthly_limit_in_cents: Monthly spending limit in cents
                    - transaction_limit_in_cents: Per-transaction spending limit in cents
                    - billing_cycle_spend_limit_in_cents: Spending limit for current billing cycle in cents
                    - daily_withdrawal_limit_in_cents: Daily withdrawal limit in cents (e.g., for ATM withdrawals)
                    - weekly_withdrawal_limit_in_cents: Weekly withdrawal limit in cents
                    - atm_withdrawal_enabled: Indicates whether ATM withdrawals are allowed
                    - enable_days: Days of the week when the card can be used (e.g., ["sun", "mon", ...])
                    - enable_start_time: Start time (24-hour format) from which card usage is enabled
                    - enable_end_time: End time (24-hour format) until which card usage is enabled
                    - created_by: ID of the user who created these spend limits
                - spend_categories: Allowed spending categories for this profile (e.g., ["Fuel pump"])

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-spend-profiles-of-your-company
        """
        params: Dict[str, Any] = {}
        if default_first is not None:
            params["default_first"] = default_first

        return await self._request("GET", "/motive_card/v1/spend_profiles", params=params)

    async def get_spend_profile_by_id(self, spend_profile_id: str) -> Dict[str, Any]:
        """
        Fetch a particular spend profile.

        Use this endpoint to view the details of a particular spend profile of a user. This
        endpoint provides important details such as daily, weekly, and monthly spend limits,
        spend categories, and the default status of the user.

        Args:
            spend_profile_id: The unique identifier (UUID) of the spend control profile

        Returns:
            Response containing spend profile details with:
            - spend_control_profiles: Array containing the profile object:
                - id: Unique identifier of the spend control profile (UUID)
                - name: Name of the spend control profile
                - created_at: Timestamp when the profile was created
                - updated_at: Timestamp when the profile was last updated
                - is_default: Indicates if this profile is the default profile
                - spend_limits: Spending limits associated with the profile:
                    - daily_limit_in_cents: Daily spending limit in cents
                    - weekly_limit_in_cents: Weekly spending limit in cents
                    - monthly_limit_in_cents: Monthly spending limit in cents
                    - transaction_limit_in_cents: Per-transaction spending limit in cents
                    - billing_cycle_spend_limit_in_cents: Spending limit for current billing cycle in cents
                    - daily_withdrawal_limit_in_cents: Daily withdrawal limit in cents (e.g., for ATM withdrawals)
                    - weekly_withdrawal_limit_in_cents: Weekly withdrawal limit in cents
                    - atm_withdrawal_enabled: Indicates whether ATM withdrawals are allowed
                    - enable_days: Days of the week when the card can be used (e.g., ["sun", "mon", ...])
                    - enable_start_time: Start time (24-hour format) from which card usage is enabled
                    - enable_end_time: End time (24-hour format) until which card usage is enabled
                    - created_by: ID of the user who created these spend limits
                - spend_categories: Allowed spending categories for this profile (e.g., ["Fuel pump"])

        Reference:
            https://developer.gomotive.com/reference/fetch-a-particular-spend-profile
        """
        return await self._request(
            "GET", f"/motive_card/v1/spend_profiles/{spend_profile_id}"
        )

    async def update_motive_card_spend_profile(
        self,
        card_id: str,
        spend_profile_id: str,
    ) -> Dict[str, Any]:
        """
        Update the spend profile of a user's Motive Card.

        Use this endpoint to update the spend control profile of a particular user's card.
        You must specify the ID (UUID) of the card as a path parameter and the ID of the
        spend control profile that you want to update in the body of the endpoint.

        Args:
            card_id: The unique identifier (UUID) of the Motive Card
            spend_profile_id: The unique identifier (UUID) of the spend control profile
                to assign to the card

        Returns:
            Response containing updated card details with the new spend control profile

        Reference:
            https://developer.gomotive.com/reference/update-the-spend-profile-of-a-users-motive-card
        """
        payload: Dict[str, Any] = {
            "spend_control_profile_id": spend_profile_id,
        }

        return await self._request(
            "PATCH", f"/motive_card/v1/cards/{card_id}", json_data=payload
        )

    async def lock_motive_card(self, card_id: str) -> Dict[str, Any]:
        """
        Lock a driver's Motive card.

        Use this endpoint to lock the Motive card of a driver. Locking a Motive card allows
        companies to prevent misuse of the card in case of theft or loss. It also prevents
        any unauthorized or fraudulent use of the card.

        Important Notes:
        - A Motive card can only be locked by Fleet Managers/Dispatchers or users with
          admin permissions or access to the group to which the card belongs
        - Drivers cannot lock a Motive Card
        - A Motive card that is still not yet "active", cannot be locked
        - A Motive card that is currently "frozen", cannot be locked. You must unfreeze
          the card first, then proceed to lock the card
        - A Motive card that is "deactivated", cannot be locked

        Args:
            card_id: The unique identifier (UUID) of the Motive Card

        Returns:
            Response containing:
            - success: Boolean indicating if the card was locked successfully
            - message: Message describing the result

        Reference:
            https://developer.gomotive.com/reference/lock-a-users-motive-card
        """
        return await self._request("POST", f"/motive_card/v1/cards/{card_id}/lock")

    async def unlock_motive_card(self, card_id: str) -> Dict[str, Any]:
        """
        Unlock a driver's Motive card.

        Use this endpoint to unlock the Motive card for a default duration of 30 minutes.
        Temporary unlocking (for 30 minutes) allows controlled usage by the cardholder,
        reducing the risk of prolonged exposure to misuse.

        Lock and unlock features support workflows where cards should only be usable at
        specific times or for specific purposes, aligning with fleet management best practices.

        Important Notes:
        - The action of "unlocking" a Motive card can be performed by both dispatchers
          or drivers via the Driver's app
        - To allow drivers to unlock the Motive card from mobile devices, you must enable
          the Mobile-based card unlock feature
        - Unlocking provides temporary access for 30 minutes

        Args:
            card_id: The unique identifier (UUID) of the Motive Card

        Returns:
            Response containing:
            - success: Boolean indicating if the card was unlocked successfully
            - message: Message describing the result
            - unlocked_till: Timestamp indicating when the unlock period expires

        Reference:
            https://developer.gomotive.com/reference/unlock-a-drivers-motive-card
        """
        return await self._request("POST", f"/motive_card/v1/cards/{card_id}/unlock")

    async def get_geofences(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List the locations with Geofences.

        Use this API to fetch a list of all the available Geofences. You must specify
        the category of the geofence. The category is nothing but the location where the
        Geofence has been configured (e.g., "Fuel Station").

        Args:
            category: Optional category of the geofence (e.g., "Fuel Station")
                - This is the location where the Geofence has been configured
            status: Optional status filter (e.g., "active")
            limit: Maximum number of geofences to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing geofences with:
            - Array of geofence objects, each containing:
                - id: Unique identifier for the geofence
                - name: The name of the geofence
                - category: The category of the geofence (e.g., "Fuel Station")
                - status: The status of the geofence (e.g., "active")
                - address: The physical address associated with the geofence
                - location_points: Array of geographical points that define the boundaries:
                    - lat: Latitude of a location point in the geofence
                    - lon: Longitude of a location point in the geofence

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-the-locations-with-geofences
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if category:
            params["category"] = category
        if status:
            params["status"] = status

        return await self._request("GET", "/v1/geofences", params=params)

    async def get_geofence_by_id(self, geofence_id: str) -> Dict[str, Any]:
        """
        Fetch a Geofence information using its ID.

        Use this API to search for a specific Geofence by using its ID.

        Args:
            geofence_id: The unique identifier for the geofence

        Returns:
            Response containing geofence details with:
            - id: Unique identifier for the geofence
            - name: The name of the geofence
            - category: The category of the geofence (e.g., "Fuel Station")
            - status: The status of the geofence (e.g., "active")
            - address: The physical address associated with the geofence
            - location_points: Array of geographical points that define the boundaries:
                - lat: Latitude of a location point in the geofence
                - lon: Longitude of a location point in the geofence

        Reference:
            https://developer.gomotive.com/reference/fetch-a-geofence-information-using-its-id
        """
        return await self._request("GET", f"/v1/geofences/{geofence_id}")

    async def create_circular_geofence(
        self,
        name: str,
        category: str,
        centre_lat: float,
        centre_lon: float,
        radius_in_meters: int,
        status: str = "active",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new circular Geofence.

        Use this API to create a new Geofence. You must provide information such as name,
        location coordinates (latitude and longitude), as well as status information in
        the request body.

        Args:
            name: Name of the geofence
            category: Category of the geofence (e.g., "Fuel Station")
            centre_lat: Latitude of the center point of the circular geofence
            centre_lon: Longitude of the center point of the circular geofence
            radius_in_meters: Radius of the geofence in meters
            status: Status of the geofence (default: "active")
            description: Optional brief note or description with respect to the Geofence

        Returns:
            Response containing created geofence details with:
            - id: Unique identifier for the geofence
            - name: The name of the geofence
            - category: The category of the geofence (e.g., "Fuel Station")
            - status: The status of the geofence (e.g., "active")
            - address: The physical address associated with the geofence
            - description: Brief note or description with respect to the Geofence
            - radius_in_meters: Measurement of the radius of the Geofence in meters
            - center_lat: The latitude of a central point in the geofence
            - center_lon: The longitude of a central point in the geofence

        Reference:
            https://developer.gomotive.com/reference/create-a-new-geofence-polygon-copy
        """
        payload: Dict[str, Any] = {
            "name": name,
            "category": category,
            "centre_lat": str(centre_lat),
            "centre_lon": str(centre_lon),
            "radius_in_meters": str(radius_in_meters),
            "status": status,
        }
        if description:
            payload["description"] = description

        return await self._request("POST", "/v1/geofences/circular", json_data=payload)

    async def get_geofence_events(
        self,
        geofence_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List the Geofence events.

        Use this API to view the events of your existing Geofences. This API allows you to
        check out the following information:
        - Geofence Event ID
        - Start time of the event
        - Vehicle in the Geofence event
        - Event starting driver details
        - Event ending driver details

        Args:
            geofence_id: Optional geofence ID to filter events
            vehicle_id: Optional vehicle ID to filter events
            start_time: Optional ISO 8601 start time to filter events
            end_time: Optional ISO 8601 end time to filter events
            limit: Maximum number of events to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing geofence events with:
            - Array of geofence event objects, each containing:
                - id: Unique identifier for the geofence event
                - geofence_id: Unique identifier for the geofence associated with the event
                - start_time: The start time of the geofence event
                - end_time: The end time of the geofence event
                - duration: The duration of the geofence event in seconds
                - vehicle: Details about the vehicle involved in the geofence event:
                    - id: Unique identifier for the vehicle
                    - number: The vehicle's number
                    - year: The year the vehicle was manufactured
                    - make: The make of the vehicle
                    - model: The model of the vehicle
                    - vin: The vehicle identification number (VIN) of the vehicle
                    - metric_units: Indicates if the vehicle uses metric units
                - start_driver: Details about the driver at the start of the geofence event:
                    - id: Unique identifier for the start driver
                    - first_name: First name of the start driver
                    - last_name: Last name of the start driver
                    - username: Username of the start driver
                    - email: Email address of the start driver
                    - driver_company_id: Company ID associated with the start driver
                    - status: Status of the start driver
                    - role: Assigned role of the user - driver
                - end_driver: Details about the driver at the end of the geofence event:
                    - id: Unique identifier for the end driver
                    - first_name: First name of the end driver
                    - last_name: Last name of the end driver
                    - username: Username of the end driver
                    - email: Email address of the end driver
                    - driver_company_id: Company ID associated with the end driver
                    - status: Status of the end driver
                    - role: Assigned role of the user - driver

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-geofence-events
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if geofence_id:
            params["geofence_id"] = geofence_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/geofences/events", params=params)

    async def get_asset_geofence_events(
        self,
        geofence_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List all the asset Geofence events.

        Use this API to view all the Geofence events pertaining to your assets.

        Args:
            geofence_id: Optional geofence ID to filter events
            asset_id: Optional asset ID to filter events
            start_time: Optional ISO 8601 start time to filter events
            end_time: Optional ISO 8601 end time to filter events
            limit: Maximum number of events to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing asset geofence events with:
            - Array of geofence event objects, each containing:
                - id: Unique identifier for the geofence event
                - geofence_id: Unique identifier for the geofence associated with the event
                - start_time: The start time of the geofence event
                - end_time: The end time of the geofence event
                - duration: The duration of the geofence event in seconds
                - asset: Details about the asset involved in the geofence event:
                    - id: Unique identifier for the asset
                    - name: The name of the asset
                    - status: The status of the asset
                    - type: The type of asset
                    - vin: The vehicle identification number (VIN) of the asset, if applicable
                    - license_plate_state: The state of the license plate of the asset, if applicable
                    - license_plate_number: The license plate number of the asset, if applicable
                    - make: The make of the asset
                    - model: The model of the asset
                    - year: The year the asset was manufactured
                    - axle: The number of axles on the asset, if applicable
                    - weight_metric_units: Indicates if the asset's weight is measured in metric units
                    - length_metric_units: Indicates if the asset's length is measured in metric units
                    - leased: Indicates if the asset is leased
                    - notes: Additional notes about the asset
                    - length: The length of the asset, if applicable
                    - gvwr: The gross vehicle weight rating (GVWR) of the asset
                    - gawr: The gross axle weight rating (GAWR) of the asset
                    - asset_gateway: Details about the asset's gateway:
                        - id: Unique identifier for the asset gateway
                        - identifier: The identifier of the asset gateway
                        - active: Indicates if the asset gateway is active
                    - external_ids: Array of external identifiers associated with the asset

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-company-asset-geofence-events
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if geofence_id:
            params["geofence_id"] = geofence_id
        if asset_id:
            params["asset_id"] = asset_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/geofences/asset_events", params=params)

    async def get_drivers_with_available_time(self) -> Dict[str, Any]:
        """
        Fetch a list of all drivers with available time.

        Use this API to fetch a list of all the drivers with available time. Getting to know
        your driver's available time allows you to perform better scheduling and plan their
        routes more efficiently. Also, you can control labor costs by optimizing the driver
        schedules, thereby improving customer service.

        Returns:
            Response containing drivers with available time, each user object containing:
            - duty_status: Current duty status of the user (e.g., "on_duty")
            - id: Unique identifier for the user
            - first_name: First name of the user
            - last_name: Last name of the user
            - username: Username of the user
            - email: Email address of the user
            - driver_company_id: ID of the driver's company (if applicable)
            - status: Status of the user (e.g., "active")
            - role: Role of the user (e.g., "driver")
            - available_time: Time availability breakdown for the user:
                - cycle: Total cycle time available in seconds
                - shift: Total shift time available in seconds
                - drive: Total drive time available in seconds
                - break: Total break time available in seconds
            - recap: Summary of duty and driving durations:
                - on_duty_duration: Array of on-duty durations by date:
                    - date: Date of the recorded duration
                    - duration: Duration of on-duty time in seconds
                - driving_duration: Array of driving durations by date:
                    - date: Date of the recorded duration
                    - duration: Duration of driving time in seconds
                - seconds_available: Total available time in seconds
                - seconds_tomorrow: Available time for the following day in seconds
            - last_hos_status: Most recent HOS status:
                - status: Current HOS status of the user (e.g., "on_duty")
                - time: Timestamp of the last HOS status update
            - last_cycle_reset: Information about the last cycle reset:
                - type: Type of cycle reset (e.g., "34_hour")
                - start_time: Start time of the last cycle reset
                - end_time: End time of the last cycle reset

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-drivers-with-available-time
        """
        return await self._request("GET", "/v1/available_time")

    async def get_company_drivers_hos(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        driver_id: Optional[str] = None,
        per_page: int = 100,
        page_no: int = 1,
    ) -> Dict[str, Any]:
        """
        List company drivers with Hours of Service (HOS).

        Use this API to fetch a list of all the company drivers and their corresponding
        Hours of Service (HOS). This allows you to view all the drivers with their HOS
        details so that you can optimize planning and scheduling of the drivers more
        efficiently and effectively.

        Important Note:
        - Please provide either `start_date` or an `end_date` for the API call.

        Args:
            start_date: Optional start date (ISO 8601 format) for HOS records
                - Must provide either start_date or end_date
            end_date: Optional end date (ISO 8601 format) for HOS records
                - Must provide either start_date or end_date
            driver_id: Optional driver ID to filter records
            per_page: Number of records per page (default: 100)
            page_no: Current page number (default: 1)

        Returns:
            Response containing HOS records with:
            - hours_of_services: Array of hours of service record objects, each containing:
                - id: Unique identifier for the hours of service record
                - date: Date of the hours of service record
                - off_duty_duration: Duration of off-duty time in seconds
                - on_duty_duration: Duration of on-duty time in seconds
                - sleeper_duration: Duration of sleeper time in seconds
                - driving_duration: Duration of driving time in seconds
                - waiting_duration: Duration of waiting time in seconds
                - driver: Details of the driver associated with the HOS record:
                    - id: Unique identifier for the driver
                    - first_name: First name of the driver
                    - last_name: Last name of the driver
                    - username: Username of the driver
                    - email: Email address of the driver
                    - driver_company_id: ID of the driver's company
                    - status: Status of the driver (e.g., "active")
                    - role: Role of the driver (e.g., "driver")
            - pagination: Pagination details for the response:
                - per_page: Number of records per page
                - page_no: Current page number
                - total: Total number of records available

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-company-drivers-with-hours-of-service-hos
        """
        if not start_date and not end_date:
            raise ValueError("Either start_date or end_date must be provided")

        params: Dict[str, Any] = {"per_page": per_page, "page_no": page_no}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if driver_id:
            params["driver_id"] = driver_id

        return await self._request("GET", "/v1/hours_of_service", params=params)

    async def get_hos_violations(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        driver_id: Optional[str] = None,
        violation_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List the drivers with Hours of Service (HOS) violations.

        Use this API to pull out a list of all the drivers with Hours of Service (HOS) violations.
        Hours of Service or HOS is mandated by governments to reduce the driving hours of the
        driver, and allows the drivers to have a stress-free and fatigue-free job. Ensuring
        drivers adhere to HOS regulations is vital for maintaining compliance with legal and
        regulatory requirements. Frequent violations can lead to disruptions, such as fines or
        penalties, and affect operational efficiency.

        Args:
            start_date: Optional start date (ISO 8601 format) to filter violations
            end_date: Optional end date (ISO 8601 format) to filter violations
            driver_id: Optional driver ID to filter violations for a specific driver
            violation_type: Optional violation type to filter (e.g., "us_driving_11", "us_duty_14")

        Returns:
            Response containing HOS violations with:
            - hos_violations: Array of HOS violation objects, each containing:
                - id: Unique identifier for the HOS violation
                - type: The type of HOS violation (e.g., "us_driving_11", "us_duty_14", "us_break_30")
                - start_time: The start time of the HOS violation in ISO 8601 format
                - end_time: The end time of the HOS violation in ISO 8601 format (if applicable)
                - name: The name or description of the HOS violation
                - user: Details of the driver associated with the HOS violation:
                    - id: Unique identifier for the driver
                    - first_name: The first name of the driver
                    - last_name: The last name of the driver
                    - username: The username of the driver
                    - email: The email address of the driver
                    - driver_company_id: The ID of the driver's company
                    - status: The status of the driver (e.g., "active", "deactivated")
                    - role: The role of the driver (e.g., "driver", "admin")

        Common Violation Types:
            US Regulations:
            - us_driving_11: Maximum of 11 hours driving time
            - us_duty_14: Maximum of 14 hours on-duty time
            - us_break_30: Required 30-minute break
            - us_cycle_60: 60-hour/7-day cycle limit
            - us_cycle_70: 70-hour/8-day cycle limit
            - us_cycle_80: 80-hour/8-day cycle limit
            - us_break_10: Required 10-hour off-duty break
            - us_break_34: Required 34-hour restart break

            Canada Regulations:
            - canada_driving_13: Maximum of 13 hours driving time
            - canada_duty_14: Maximum of 14 hours on-duty time
            - canada_break_10: 10-hour daily off-duty break
            - canada_cycle_70: 70-hour/7-day cycle limit
            - canada_cycle_80: 80-hour/7-day cycle limit
            - canada_cycle_120: 120-hour/14-day cycle limit

            State-Specific:
            - ca_*: California regulations
            - tx_*: Texas regulations
            - ak_*: Alaska regulations

            Short-Haul Operations:
            - short_haul_*: Short-haul specific violations

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-drivers-with-hours-of-service-hos-violations
        """
        params: Dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if driver_id:
            params["driver_id"] = driver_id
        if violation_type:
            params["violation_type"] = violation_type

        return await self._request("GET", "/v1/hos_violations", params=params)

    async def get_hos_logs(
        self,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List the Hours of Service (HOS) logs of the drivers.

        Use this API to fetch detailed HOS logs for drivers, including events, violations,
        vehicles, co-drivers, remarks, cycle restarts, and inspection reports. This provides
        comprehensive visibility into driver activity and compliance.

        Args:
            user_id: Optional user/driver ID to filter logs for a specific driver
            start_time: Optional ISO 8601 start time to filter logs
            end_time: Optional ISO 8601 end time to filter logs

        Returns:
            Response containing HOS logs with:
            - hos_logs: Array of HOS log objects, each containing:
                - id: Unique identifier for the HOS log
                - driver: Details of the driver associated with the log:
                    - id: Unique identifier for the driver
                    - first_name: First name of the driver
                    - last_name: Last name of the driver
                    - username: Username of the driver
                    - email: Email address of the driver
                    - driver_company_id: ID of the driver's company
                    - status: Status of the driver (e.g., "active")
                    - role: Role of the driver (e.g., "driver")
                - vehicles: Array of vehicles associated with the log:
                    - id: Unique identifier for the vehicle
                    - number: Vehicle number
                    - year: Year of the vehicle
                    - make: Make of the vehicle
                    - model: Model of the vehicle
                    - vin: Vehicle Identification Number (VIN)
                    - metric_units: Indicates if metric units are used
                - co_drivers: Array of co-drivers associated with the log:
                    - id: Unique identifier for the co-driver
                    - first_name: Co-driver's first name
                    - last_name: Co-driver's last name
                    - username: Co-driver's username
                    - email: Co-driver's email address
                    - driver_company_id: Co-driver's company ID
                    - status: Co-driver's status (e.g., "active")
                - remarks: Array of remarks associated with the log:
                    - id: Unique identifier for the remark
                    - time: Timestamp of the remark
                    - notes: Notes associated with the remark
                    - location: Location associated with the remark
                - cycle_restarts: Array of cycle restarts associated with the log:
                    - id: Unique identifier for the cycle restart
                    - start_time: Start time of the cycle restart
                    - end_time: End time of the cycle restart
                    - type: Type of cycle restart (e.g., "34_hour")
                    - name: Name of the cycle restart
                - shipping_docs: Shipping document numbers associated with the log
                - form_and_manner_errors: Array of form and manner errors (if any)
                - hos_violations: Array of HOS violations associated with the log:
                    - id: Unique identifier for the HOS violation
                    - type: Type of HOS violation
                    - name: Name of the HOS violation
                    - start_time: Start time of the HOS violation
                    - end_time: End time of the HOS violation
                - events: Array of events associated with the log:
                    - id: Unique identifier for the event
                    - type: Type of event (e.g., "driving", "sleeper")
                    - notes: Notes associated with the event
                    - location: Location of the event
                    - start_time: Start time of the event
                    - end_time: End time of the event
                    - is_manual: Indicates if the event was manually entered
                - inspection_reports: Array of inspection reports associated with the log:
                    - id: Unique identifier for the inspection report
                    - date: Date of the inspection
                    - time: Time of the inspection
                    - odometer: Odometer reading at the time of the inspection
                    - carrier_name: Carrier's name
                    - vehicle_number: Vehicle number associated with the inspection
                    - trailer_nums: Array of trailer numbers associated with the inspection
                    - location: Location of the inspection
                    - city: City of the inspection
                    - state: State of the inspection
                    - status: Status of the inspection (e.g., "corrected")
                    - mechanic_signed_at: Timestamp when the mechanic signed the inspection report
                    - mechanic_signature_url: URL to the mechanic's signature
                    - driver_signed_at: Timestamp when the driver signed the inspection report
                    - driver_signature_url: URL to the driver's signature
                    - reviewer_signed_at: Timestamp when the reviewer signed the inspection report
                    - reviewer_signature_url: URL to the reviewer's signature
                    - defects: Array of defects identified during the inspection:
                        - id: Unique identifier for the defect
                        - area: Area of the vehicle where the defect was found
                        - category: Category of the defect
                        - notes: Additional notes about the defect
                    - entries: Array of additional entries in the inspection report:
                        - name: Name of the entry
                        - value: Value of the entry
                        - position: Position of the entry in the inspection report

        Reference:
            https://developer.gomotive.com/reference/list-the-hours-of-service-hos-logs-of-the-drivers
        """
        params: Dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/hos_logs", params=params)

    async def get_hos_logs_v2(
        self,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List the Hours of Service (HOS) logs of the drivers (v2).

        This is the v2 version of the HOS logs endpoint, providing enhanced functionality
        and improved data structure. Use this API to fetch detailed HOS logs for drivers,
        including events, violations, vehicles, co-drivers, remarks, cycle restarts, and
        inspection reports. This provides comprehensive visibility into driver activity and
        compliance.

        Args:
            user_id: Optional user/driver ID to filter logs for a specific driver
            start_time: Optional ISO 8601 start time to filter logs
            end_time: Optional ISO 8601 end time to filter logs

        Returns:
            Response containing HOS logs (v2 format) with:
            - hos_logs: Array of HOS log objects, each containing:
                - id: Unique identifier for the HOS log
                - driver: Details of the driver associated with the log:
                    - id: Unique identifier for the driver
                    - first_name: First name of the driver
                    - last_name: Last name of the driver
                    - username: Username of the driver
                    - email: Email address of the driver
                    - driver_company_id: ID of the driver's company
                    - status: Status of the driver (e.g., "active")
                    - role: Role of the driver (e.g., "driver")
                - vehicles: Array of vehicles associated with the log:
                    - id: Unique identifier for the vehicle
                    - number: Vehicle number
                    - year: Year of the vehicle
                    - make: Make of the vehicle
                    - model: Model of the vehicle
                    - vin: Vehicle Identification Number (VIN)
                    - metric_units: Indicates if metric units are used
                - co_drivers: Array of co-drivers associated with the log:
                    - id: Unique identifier for the co-driver
                    - first_name: Co-driver's first name
                    - last_name: Co-driver's last name
                    - username: Co-driver's username
                    - email: Co-driver's email address
                    - driver_company_id: Co-driver's company ID
                    - status: Co-driver's status (e.g., "active")
                - remarks: Array of remarks associated with the log:
                    - id: Unique identifier for the remark
                    - time: Timestamp of the remark
                    - notes: Notes associated with the remark
                    - location: Location associated with the remark
                - cycle_restarts: Array of cycle restarts associated with the log:
                    - id: Unique identifier for the cycle restart
                    - start_time: Start time of the cycle restart
                    - end_time: End time of the cycle restart
                    - type: Type of cycle restart (e.g., "34_hour")
                    - name: Name of the cycle restart
                - shipping_docs: Shipping document numbers associated with the log
                - form_and_manner_errors: Array of form and manner errors (if any)
                - hos_violations: Array of HOS violations associated with the log:
                    - id: Unique identifier for the HOS violation
                    - type: Type of HOS violation
                    - name: Name of the HOS violation
                    - start_time: Start time of the HOS violation
                    - end_time: End time of the HOS violation
                - events: Array of events associated with the log:
                    - id: Unique identifier for the event
                    - type: Type of event (e.g., "driving", "sleeper")
                    - notes: Notes associated with the event
                    - location: Location of the event
                    - start_time: Start time of the event
                    - end_time: End time of the event
                    - is_manual: Indicates if the event was manually entered
                - inspection_reports: Array of inspection reports associated with the log:
                    - id: Unique identifier for the inspection report
                    - date: Date of the inspection
                    - time: Time of the inspection
                    - odometer: Odometer reading at the time of the inspection
                    - carrier_name: Carrier's name
                    - vehicle_number: Vehicle number associated with the inspection
                    - trailer_nums: Array of trailer numbers associated with the inspection
                    - location: Location of the inspection
                    - city: City of the inspection
                    - state: State of the inspection
                    - status: Status of the inspection (e.g., "corrected")
                    - mechanic_signed_at: Timestamp when the mechanic signed the inspection report
                    - mechanic_signature_url: URL to the mechanic's signature
                    - driver_signed_at: Timestamp when the driver signed the inspection report
                    - driver_signature_url: URL to the driver's signature
                    - reviewer_signed_at: Timestamp when the reviewer signed the inspection report
                    - reviewer_signature_url: URL to the reviewer's signature
                    - defects: Array of defects identified during the inspection:
                        - id: Unique identifier for the defect
                        - area: Area of the vehicle where the defect was found
                        - category: Category of the defect
                        - notes: Additional notes about the defect
                    - entries: Array of additional entries in the inspection report:
                        - name: Name of the entry
                        - value: Value of the entry
                        - position: Position of the entry in the inspection report

        Reference:
            https://developer.gomotive.com/reference/list-the-hours-of-service-hos-logs-of-the-drivers-copy
        """
        params: Dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/hos_logs/v2", params=params)

    async def get_log_suggestions(
        self,
        driver_id: Optional[str] = None,
        log_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        View all log suggestions.

        Log suggestions are automated recommendations provided by Motive to help drivers
        maintain accurate and compliant records of their duty status and driving activities.
        These suggestions are typically generated based on data collected by the system,
        such as vehicle movement, GPS location, and other sensor inputs. Drivers or fleet
        managers can then either approve or reject such recommendations or suggestions.

        Args:
            driver_id: Optional driver ID to filter suggestions for a specific driver
            log_id: Optional log ID to filter suggestions for a specific log
            status: Optional status to filter suggestions (e.g., "suggested", "approved")

        Returns:
            Response containing log suggestions with:
            - log_suggestions: Array of log suggestion objects, each containing:
                - id: Unique identifier for the log suggestion
                - driver_ids: List of driver IDs associated with the suggestion
                - log_ids: List of log IDs associated with the suggestion
                - status: Status of the suggestion (e.g., "suggested", "approved")
                - suggested_at: Timestamp of when the suggestion was made
                - reason: Reason for the suggestion (if provided)
                - driver: Details of the driver associated with the suggestion:
                    - id: Unique identifier for the driver
                    - first_name: First name of the driver
                    - last_name: Last name of the driver
                    - driver_company_id: Company ID associated with the driver
                    - eld_mode: The vehicle gateway mode present in the logs
                - dispatcher: Details of the dispatcher (if applicable):
                    - id: Unique identifier for the dispatcher
                    - first_name: First name of the dispatcher
                    - last_name: Last name of the dispatcher
                - suggested_changes: List of changes suggested to the log:
                    - field_name: The field that is suggested to be changed
                    - old_value: The old value of the field before the suggestion
                    - new_value: The new value suggested for the field

        Reference:
            https://developer.gomotive.com/reference/view-all-log-suggestions
        """
        params: Dict[str, Any] = {}
        if driver_id:
            params["driver_id"] = driver_id
        if log_id:
            params["log_id"] = log_id
        if status:
            params["status"] = status

        return await self._request("GET", "/v1/log_suggestions", params=params)

    async def get_ifta_trips(
        self,
        vehicle_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List of company vehicle's IFTA trips.

        Use this API to fetch a list of the company vehicle's IFTA trip reports. The trip
        report consists of details such as miles travelled in each jurisdiction, fuel
        purchased, and vehicle's odometer readings. These reports are required for compliance
        with the IFTA regulations in multiple jurisdictions in the United States and in Canada.
        These reports ensure that fuel taxes are fairly distributed among the states and
        provinces where the vehicles operate. The trip reports are then used to calculate
        tax liabilities.

        Note:
            The API response contains fields `calibrated_start_odometer` and
            `calibrated_end_odometer` that are available as a feature.

        Args:
            vehicle_id: Optional vehicle ID to filter trips for a specific vehicle
            start_date: Optional start date (YYYY-MM-DD format) to filter trips
            end_date: Optional end date (YYYY-MM-DD format) to filter trips
            jurisdiction: Optional jurisdiction code to filter trips by jurisdiction

        Returns:
            Response containing IFTA trip reports with:
            - ifta_trips: Array of IFTA trip objects, each containing:
                - id: Unique identifier for the IFTA trip
                - date: The date of the IFTA trip in YYYY-MM-DD format
                - jurisdiction: The jurisdiction where the trip took place, represented
                    by the jurisdiction code
                - vehicle: Information about the vehicle associated with the IFTA trip:
                    - id: Unique identifier for the vehicle
                    - number: The vehicle's number
                    - year: The year the vehicle was manufactured
                    - make: The make of the vehicle
                    - model: The model of the vehicle
                    - vin: The vehicle identification number (VIN) of the vehicle
                    - metric_units: Indicates whether the vehicle's units are metric
                        (true) or imperial (false)
                - start_odometer: The odometer reading at the start of the trip
                - end_odometer: The odometer reading at the end of the trip
                - calibrated_start_odometer: The calibrated odometer reading at the
                    start of the trip (feature available)
                - calibrated_end_odometer: The calibrated odometer reading at the end
                    of the trip (feature available)
                - start_lat: The latitude coordinate at the start of the trip
                - start_lon: The longitude coordinate at the start of the trip
                - end_lat: The latitude coordinate at the end of the trip
                - end_lon: The longitude coordinate at the end of the trip
                - distance: The total distance traveled during the trip
                - time_zone: The time zone in which the trip occurred

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-companys-ifta-trip-reports
        """
        params: Dict[str, Any] = {}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if jurisdiction:
            params["jurisdiction"] = jurisdiction

        return await self._request("GET", "/v1/ifta/trips", params=params)

    async def get_ifta_mileage_summary(
        self,
        vehicle_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List mileage summary of vehicles.

        Use this endpoint to fetch a mileage summary of all the company's vehicles. This
        allows you to view, consolidate, and summarize the fuel and mileage data for each
        vehicle in a fleet that operates across multiple jurisdictions. The summary report
        simplifies the tax filing process, thereby ensuring accurate and fair distribution
        of fuel taxes among the jurisdictions where the vehicle was driven.

        Args:
            vehicle_id: Optional vehicle ID to filter summary for a specific vehicle
            start_date: Optional start date (YYYY-MM-DD format) to filter summary
            end_date: Optional end date (YYYY-MM-DD format) to filter summary
            jurisdiction: Optional jurisdiction code to filter summary by jurisdiction

        Returns:
            Response containing IFTA mileage summary with:
            - mileage_summary: Array of mileage summary objects, each containing:
                - jurisdiction: The jurisdiction (state or province) where the IFTA trip occurred
                - vehicle: Information about the vehicle:
                    - id: The unique identifier for the vehicle associated with the IFTA trip
                    - number: The number assigned to the vehicle
                    - year: The year of the vehicle's manufacture
                    - make: The manufacturer of the vehicle
                    - model: The model of the vehicle
                    - vin: The Vehicle Identification Number (VIN) of the vehicle
                    - metric_units: Indicates whether the vehicle uses metric units for
                        measurements (e.g., kilometers, liters)
                - distance: The distance traveled during the IFTA trip, measured in the units
                    specified by metric_units
                - time_zone: The time zone in which the IFTA trip occurred

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-the-company-vehicles-mileage-summary
        """
        params: Dict[str, Any] = {}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if jurisdiction:
            params["jurisdiction"] = jurisdiction

        return await self._request("GET", "/v1/ifta/summary", params=params)

    async def get_inspection_reports(
        self,
        vehicle_id: str,
        per_page: int = 25,
        page_no: int = 1,
    ) -> Dict[str, Any]:
        """
        List vehicle's inspection reports.

        Use this API to fetch a list of inspection reports for a specific vehicle. Inspection
        reports contain detailed information about vehicle inspections, including defects found,
        signatures from mechanics, drivers, and reviewers, and compliance status.

        Args:
            vehicle_id: Required vehicle ID to fetch inspection reports for
            per_page: Number of records per page (default: 25)
            page_no: Current page number (default: 1)

        Returns:
            Response containing inspection reports with:
            - inspection_reports: Array of inspection report objects, each containing:
                - id: Unique identifier for the inspection report
                - log_id: Identifier for the log associated with the inspection
                - date: Date of the inspection report (YYYY-MM-DD format)
                - time: Time of the inspection report (ISO 8601 format)
                - odometer: Odometer reading at the time of the inspection (null if not available)
                - carrier_name: Name of the carrier
                - vehicle_number: Vehicle number
                - trailer_nums: List of trailer numbers
                - location: Location of the inspection
                - city: City where the inspection occurred
                - state: State where the inspection occurred
                - status: Status of the inspection report (e.g., "corrected")
                - mechanic_signed_at: Timestamp when the mechanic signed the report
                - mechanic_signature_url: URL of the mechanic's signature image
                - driver_signed_at: Timestamp when the driver signed the report
                - driver_signature_url: URL of the driver's signature image
                - reviewer_signed_at: Timestamp when the reviewer signed the report
                - reviewer_signature_url: URL of the reviewer's signature image
                - defects: Array of defects found during the inspection:
                    - id: Unique identifier for the defect
                    - area: Area of the vehicle where the defect was found (e.g., "tractor")
                    - category: Category of the defect (e.g., "Mirrors")
                    - notes: Additional notes about the defect (null if not applicable)
                - vehicle: Information about the vehicle:
                    - id: Unique identifier for the vehicle
                    - number: Vehicle number
                    - year: Vehicle year
                    - make: Vehicle make
                    - model: Vehicle model
                    - vin: Vehicle identification number
                    - metric_units: Whether the vehicle uses metric units
                - mechanic: Information about the mechanic who signed the report:
                    - id: Unique identifier for the mechanic
                    - first_name: Mechanic's first name
                    - last_name: Mechanic's last name
                    - username: Mechanic's username (null if not applicable)
                    - email: Mechanic's email address
                    - driver_company_id: Mechanic's company ID (null if not applicable)
                    - status: Mechanic's status (e.g., "active")
                    - role: Mechanic's role (e.g., "admin")
                - driver: Information about the driver who signed the report:
                    - id: Unique identifier for the driver
                    - first_name: Driver's first name
                    - last_name: Driver's last name
                    - username: Driver's username
                    - email: Driver's email address (null if not applicable)
                    - driver_company_id: Driver's company ID (null if not applicable)
                    - status: Driver's status (e.g., "active")
                    - role: Driver's role (e.g., "driver")
                - reviewer: Information about the reviewer of the report:
                    - id: Unique identifier for the reviewer
                    - first_name: Reviewer's first name
                    - last_name: Reviewer's last name
                    - username: Reviewer's username (null if not applicable)
                    - email: Reviewer's email address
                    - driver_company_id: Reviewer's company ID (null if not applicable)
                    - status: Reviewer's status (e.g., "active")
                    - role: Reviewer's role (e.g., "driver")
                - external_ids: Array of external IDs associated with the inspection report:
                    - external_id: External ID value
                    - integration_name: Integration name associated with the external ID
                - entries: Array of entries related to the inspection report:
                    - name: Name of the entry (e.g., "Tractor Plate #")
                    - value: Value of the entry (e.g., "2743186")
                    - position: Position of the entry in the list
            - pagination: Pagination details:
                - per_page: Number of records per page
                - page_no: Current page number
                - total: Total number of records

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-the-company-vehicles-inspection-reports
        """
        params: Dict[str, Any] = {
            "vehicle_id": vehicle_id,
            "per_page": per_page,
            "page_no": page_no,
        }

        return await self._request("GET", "/v1/inspection_reports", params=params)

    async def get_inspection_report_by_external_id(
        self,
        external_id: str,
        integration_name: str,
    ) -> Dict[str, Any]:
        """
        Fetch a report by an external ID.

        Use this API to fetch an inspection report using an external ID and integration name.
        This is useful when you need to retrieve inspection reports that have been associated
        with external identifiers from other systems.

        Args:
            external_id: The external ID associated with the inspection report
            integration_name: The name of the integration associated with the external ID
                (e.g., "generic_tms")

        Returns:
            Response containing inspection report with:
            - inspection_reports: Array of inspection report objects, each containing:
                - id: Unique identifier for the inspection report
                - log_id: Identifier for the log associated with the inspection
                - date: Date of the inspection report (YYYY-MM-DD format)
                - time: Time of the inspection report (ISO 8601 format)
                - odometer: Odometer reading at the time of the inspection (null if not available)
                - carrier_name: Name of the carrier
                - vehicle_number: Vehicle number
                - trailer_nums: List of trailer numbers
                - location: Location of the inspection
                - city: City where the inspection occurred
                - state: State where the inspection occurred
                - status: Status of the inspection report (e.g., "corrected")
                - mechanic_signed_at: Timestamp when the mechanic signed the report
                - mechanic_signature_url: URL of the mechanic's signature image
                - driver_signed_at: Timestamp when the driver signed the report
                - driver_signature_url: URL of the driver's signature image
                - reviewer_signed_at: Timestamp when the reviewer signed the report
                - reviewer_signature_url: URL of the reviewer's signature image
                - defects: Array of defects found during the inspection:
                    - id: Unique identifier for the defect
                    - area: Area of the vehicle where the defect was found (e.g., "tractor")
                    - category: Category of the defect (e.g., "Mirrors")
                    - notes: Additional notes about the defect (null if not applicable)
                - vehicle: Information about the vehicle:
                    - id: Unique identifier for the vehicle
                    - number: Vehicle number
                    - year: Vehicle year
                    - make: Vehicle make
                    - model: Vehicle model
                    - vin: Vehicle identification number
                    - metric_units: Whether the vehicle uses metric units
                - mechanic: Information about the mechanic who signed the report:
                    - id: Unique identifier for the mechanic
                    - first_name: Mechanic's first name
                    - last_name: Mechanic's last name
                    - username: Mechanic's username (null if not applicable)
                    - email: Mechanic's email address
                    - driver_company_id: Mechanic's company ID (null if not applicable)
                    - status: Mechanic's status (e.g., "active")
                    - role: Mechanic's role (e.g., "admin")
                - driver: Information about the driver who signed the report:
                    - id: Unique identifier for the driver
                    - first_name: Driver's first name
                    - last_name: Driver's last name
                    - username: Driver's username
                    - email: Driver's email address (null if not applicable)
                    - driver_company_id: Driver's company ID (null if not applicable)
                    - status: Driver's status (e.g., "active")
                    - role: Driver's role (e.g., "driver")
                - reviewer: Information about the reviewer of the report:
                    - id: Unique identifier for the reviewer
                    - first_name: Reviewer's first name
                    - last_name: Reviewer's last name
                    - username: Reviewer's username (null if not applicable)
                    - email: Reviewer's email address
                    - driver_company_id: Reviewer's company ID (null if not applicable)
                    - status: Reviewer's status (e.g., "active")
                    - role: Reviewer's role (e.g., "driver")
                - external_ids: Array of external IDs associated with the inspection report:
                    - id: The unique identifier that is assigned to the external ID
                    - external_id: External ID value
                    - integration_name: Integration name associated with the external ID
                - entries: Array of entries related to the inspection report:
                    - name: Name of the entry (e.g., "Tractor Plate #")
                    - value: Value of the entry (e.g., "2743186")
                    - position: Position of the entry in the list
            - pagination: Pagination details:
                - per_page: Number of records per page
                - page_no: Current page number
                - total: Total number of records

        Reference:
            https://developer.gomotive.com/reference/fetch-a-report-by-an-external-id
        """
        params: Dict[str, Any] = {
            "external_id": external_id,
            "integration_name": integration_name,
        }

        return await self._request("GET", "/v1/inspection_reports", params=params)

    async def get_inspection_report_by_external_id_v2(
        self,
        external_id: str,
        integration_name: str,
    ) -> Dict[str, Any]:
        """
        Fetch a report by an external ID (v2).

        Use this API to fetch an inspection report using an external ID and integration name.
        This is the v2 version which includes enhanced fields such as entity information,
        inspection type, declaration, and detailed part inspection data.

        Args:
            external_id: The external ID associated with the inspection report
            integration_name: The name of the integration associated with the external ID
                (e.g., "generic_tms")

        Returns:
            Response containing inspection report (v2 format) with:
            - inspection_reports: Array of inspection report objects, each containing:
                - id: Unique identifier for the inspection report
                - log_id: Identifier for the log associated with the inspection
                - date: Date of the inspection report (YYYY-MM-DD format)
                - time: Time of the inspection report (ISO 8601 format)
                - odometer: Odometer reading at the time of the inspection
                - carrier_name: Name of the carrier responsible for the vehicle
                - location: Location where the inspection took place
                - status: Status of the inspection (e.g., "corrected")
                - mechanic_signed_at: Timestamp when the mechanic signed the report
                - mechanic_signature_url: URL of the mechanic's signature image
                - driver_signed_at: Timestamp when the driver signed the report
                - driver_signature_url: URL of the driver's signature image
                - reviewer_signed_at: Timestamp when the reviewer signed the report
                - reviewer_signature_url: URL of the reviewer's signature image
                - entity_num: Entity number associated with the report (only present for
                    assets or vehicles not available on Motive platform, NULL for registered entities)
                - entity_type: Type of entity being inspected (e.g., "vehicle")
                - is_rejected: Indicates if the inspection report was rejected
                - inspection_type: Type of inspection (e.g., "pre-trip")
                - declaration: Declaration made by the inspector
                - inspected_parts: Array of parts that were inspected:
                    - id: Unique identifier of the inspected part
                    - category: Category of the inspected part (e.g., "Mirrors")
                    - notes: Any notes regarding the inspected part
                    - type: Type of defect found (e.g., "major")
                    - picture_url: URL of the picture showing the defect
                - not_inspected_parts: Array of parts that were not inspected:
                    - category: Category of the part that was not inspected
                - vehicle: Details of the vehicle being inspected:
                    - id: Unique identifier of the vehicle
                    - number: Number or name of the vehicle
                    - year: Year of manufacture
                    - make: Make of the vehicle
                    - model: Model of the vehicle
                    - vin: Vehicle Identification Number (VIN)
                    - metric_units: Indicates if the vehicle uses metric units
                - asset: Details of the asset inspected (if applicable):
                    - id: Unique identifier of the asset
                    - make: Make of the asset
                    - model: Model of the asset
                    - name: Name or number of the asset
                    - year: Year of manufacture of the asset
                    - metric_units: Indicates if the asset uses metric units
                - mechanic: Details of the mechanic who signed the report:
                    - id: Unique identifier of the mechanic
                    - first_name: Mechanic's first name
                    - last_name: Mechanic's last name
                    - email: Mechanic's email address
                - driver: Details of the driver associated with the report:
                    - id: Unique identifier of the driver
                    - first_name: Driver's first name
                    - last_name: Driver's last name
                    - username: Driver's username
                    - email: Driver's email address (null if not available)
                - reviewer: Details of the reviewer associated with the report:
                    - id: Unique identifier of the reviewer
                    - first_name: Reviewer's first name
                    - last_name: Reviewer's last name
                    - email: Reviewer's email address
                - external_ids: Array of external identifiers associated with the report:
                    - external_id: External ID value
                    - integration_name: Integration name associated with the external ID
                - entries: Array of additional entries associated with the report:
                    - name: Name of the entry (e.g., "Tractor Plate #")
                    - value: Value of the entry (e.g., "2743186")
                    - position: Position of the entry
            - pagination: Pagination details:
                - per_page: Number of records per page
                - page_no: Current page number
                - total: Total number of records

        Reference:
            https://developer.gomotive.com/reference/fetch-a-report-by-an-external-id-copy
        """
        params: Dict[str, Any] = {
            "external_id": external_id,
            "integration_name": integration_name,
        }

        return await self._request("GET", "/v1/inspection_reports/v2", params=params)

    async def get_driving_periods(
        self,
        vehicle_id: Optional[str] = None,
        driver_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch a list of all driving periods for the company's vehicles.

        This report includes information on driving hours, start and stop times, rest periods,
        distances traveled, and compliance with regulations like HOS (Hours of Service). It's
        often used by fleet managers to monitor driver behavior, ensure compliance, and optimize
        fleet operations.

        Note: The API response contains a "source" attribute that indicates the source of the
        driving period:
        - 1: Driving period recorded by the Vehicle Gateway
        - 2: An edit performed by an authenticated user other than the driver
        - 3: Driving period assumed from the unidentified driver profile

        Args:
            vehicle_id: Optional vehicle ID to filter periods
            driver_id: Optional driver ID to filter periods
            start_time: Optional ISO 8601 start time
            end_time: Optional ISO 8601 end time
            limit: Maximum number of periods to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing driving periods with:
            - driving_periods: Array of driving period objects, each containing:
                - id: Unique identifier for the driving period
                - start_time: Start time of the driving period
                - end_time: End time of the driving period
                - duration: Duration of the driving period in seconds
                - status: Status of the driving period (if available)
                - type: Type of the driving period (e.g., "driving")
                - annotation_status: Annotation status (if available)
                - notes: Any notes associated with the driving period
                - start_kilometers: Odometer reading at the start in kilometers
                - end_kilometers: Odometer reading at the end in kilometers
                - start_hvb_state_of_charge: High-voltage battery state of charge at start
                - end_hvb_state_of_charge: High-voltage battery state of charge at end
                - start_hvb_lifetime_energy_output: Lifetime energy output at start
                - end_hvb_lifetime_energy_output: Lifetime energy output at end
                - origin: Starting location of the driving period
                - origin_lat: Latitude of the origin location
                - origin_lon: Longitude of the origin location
                - destination: Destination location of the driving period
                - destination_lat: Latitude of the destination location
                - destination_lon: Longitude of the destination location
                - distance: Distance covered during the driving period
                - source: Source of the driving period data (1=Vehicle Gateway, 2=User edit, 3=Unidentified driver)
                - driver: Driver details associated with the period:
                    - id: Unique identifier for the driver
                    - first_name: Driver's first name
                    - last_name: Driver's last name
                    - username: Driver's username (if available)
                    - email: Driver's email address
                    - driver_company_id: Company ID associated with the driver
                    - status: Status of the driver (e.g., "active")
                    - role: Role of the driver (e.g., "driver")
                - vehicle: Vehicle details associated with the period:
                    - id: Unique identifier for the vehicle
                    - number: Vehicle number
                    - year: Year of manufacture
                    - make: Vehicle make
                    - model: Vehicle model
                    - vin: Vehicle Identification Number (VIN)
                    - metric_units: Whether metric units are used

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-the-vehicles-driving-periods
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if driver_id:
            params["driver_id"] = driver_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/driving_periods", params=params)

    async def get_driver_performance_events(
        self,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch all driver performance events.

        Tracking performance events such as hard braking, rapid acceleration, and speeding
        helps identify risky driving behaviors that may lead to accidents. Monitoring such
        events allows you to be compliant with regulatory requirements, as well as maintain
        healthy Hours of Service (HOS). Continuous monitoring also provides data that can be
        used for constructive feedback and coaching.

        Args:
            driver_id: Optional driver ID to filter events
            vehicle_id: Optional vehicle ID to filter events
            event_type: Optional event type filter (e.g., "hard_brake")
            start_time: Optional ISO 8601 start time
            end_time: Optional ISO 8601 end time
            limit: Maximum number of events to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing driver performance events with:
            - driver_performance_event: Array of event objects, each containing:
                - id: Unique identifier of the event
                - type: Type of event (e.g., "hard_brake")
                - acceleration: Acceleration recorded during the event
                - duration: Duration of the event in seconds
                - start_time: Timestamp when the event started
                - end_time: Timestamp when the event ended
                - start_speed: Speed at the start of the event
                - end_speed: Speed at the end of the event
                - start_bearing: Bearing at the start of the event in degrees
                - end_bearing: Bearing at the end of the event in degrees
                - lat: Latitude where the event occurred
                - lon: Longitude where the event occurred
                - location: Description of the event location
                - intensity: Intensity of the event (e.g., "-10.3 kph/s")
                - coaching_status: Coaching status (e.g., "pending_review")
                - m_gps_lat: Array of latitude values recorded during the event
                - m_gps_lon: Array of longitude values recorded during the event
                - m_gps_heading: Array of GPS heading data during the event
                - m_veh_spd: Array of vehicle speed values recorded during the event
                - m_gps_spd: Array of GPS speed values recorded during the event
                - m_veh_odo: Odometer reading (if available)
                - driver: Driver details associated with the event (if available)
                - vehicle: Vehicle details involved in the event
                - eld_device: ELD device details used during the event

        Reference:
            https://developer.gomotive.com/reference/fetch-all-the-drivers-performance-events
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if driver_id:
            params["driver_id"] = driver_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if event_type:
            params["event_type"] = event_type
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/driver_performance_events", params=params)

    async def get_driver_performance_events_v2(
        self,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch driver performance events (v2) with enhanced data including camera media.

        This is an enhanced version of the driver performance events endpoint that includes
        additional details such as camera media, comprehensive metadata, and contextual
        information for better event analysis and coaching.

        Args:
            driver_id: Optional driver ID to filter events
            vehicle_id: Optional vehicle ID to filter events
            event_type: Optional event type filter (e.g., "hard_brake")
            start_time: Optional ISO 8601 start time
            end_time: Optional ISO 8601 end time
            limit: Maximum number of events to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing driver performance events (v2) with enhanced data:
            - driver_performance_event: Array of event objects, each containing:
                - id: Unique identifier of the event
                - type: Type of event (e.g., "hard_brake")
                - start_time: Timestamp when the event started
                - end_time: Timestamp when the event ended
                - duration: Duration of the event in seconds
                - lat: Latitude where the event occurred
                - lon: Longitude where the event occurred
                - location: Description of the event location
                - intensity: Intensity of the event
                - coaching_status: Coaching status (e.g., "pending_review")
                - coached_at: Timestamp when the event was coached
                - coachable_behaviors: Array of coachable behaviors (e.g., "hard_brake")
                - coached_behaviors: Coached behaviors for the event
                - primary_behavior: Array of primary behaviors (e.g., "cell_phone")
                - secondary_behaviors: Array of secondary behaviors
                - max_speed: Maximum speed during the event in km/h
                - min_speed: Minimum speed during the event in km/h
                - event_intensity: Intensity details (name, value, unit_type)
                - m_gps_spd: Array of GPS speeds during the event
                - edited_by_fm: Whether the event was edited by a fleet manager
                - driver: Enhanced driver details (id, first_name, last_name, email, phone,
                         external_id, mcleod_id, status, role)
                - vehicle: Enhanced vehicle details (id, number, year, make, model, vin,
                          metric_units, mcleod_id)
                - eld_device: ELD device details (id, identifier, model)
                - camera_media: Camera media associated with the event:
                    - id: Unique identifier of the camera media
                    - available: Whether the camera media is available
                    - cam_positions: Array of camera positions (e.g., "front_facing", "driver_facing")
                    - cam_type: Type of camera (e.g., "dc54")
                    - uploaded_at: Timestamp when the media was uploaded
                    - start_time: Timestamp when the media recording started
                    - duration: Duration of the media in seconds
                    - downloadable_videos: URLs for downloadable videos:
                        - front_facing_enhanced_url
                        - front_facing_enhanced_ai_viz_url
                        - dual_facing_enhanced_url
                        - dual_facing_enhanced_ai_viz_url
                        - front_facing_plain_url
                        - driver_facing_plain_url
                    - auto_transcode_status: Status of the auto-transcoding process
                    - downloadable_images: URLs for downloadable images:
                        - front_facing_jpg_url
                        - driver_facing_jpg_url
                - metadata: Additional metadata for the event:
                    - severity: Severity of the event
                    - trigger: Trigger for the event
                    - additional_context: Contextual details (slope, lighting, road_type,
                                          lane_spacing, tpv_behavior, road_geometry,
                                          vehicle_speed, sensitive_zone, road_conditions,
                                          road_visibility, traffic_density, driving_visibility,
                                          traffic_conditions, traffic_violations)
                    - annotation_tags: Array of annotation tags (e.g., "delayed_response",
                                      "seat_belt_violation")

        Reference:
            https://developer.gomotive.com/reference/fetch-the-drivers-performance-events-v2
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if driver_id:
            params["driver_id"] = driver_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if event_type:
            params["event_type"] = event_type
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v2/driver_performance_events", params=params)

    async def get_speeding_events(
        self,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch all speeding events for the company's drivers.

        Tracking speeding events helps identify risky driving behaviors that may lead to
        accidents. Monitoring such events allows you to be compliant with regulatory
        requirements, as well as maintain healthy Hours of Service (HOS).

        Args:
            driver_id: Optional driver ID to filter events
            vehicle_id: Optional vehicle ID to filter events
            start_time: Optional ISO 8601 start time
            end_time: Optional ISO 8601 end time
            limit: Maximum number of events to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing speeding events with:
            - speeding_event: Array of event objects, each containing:
                - id: Unique identifier of the speeding event
                - type: Type of speeding event (e.g., "posted")
                - duration: Duration of the speeding event in seconds
                - start_time: Timestamp when the speeding event started
                - end_time: Timestamp when the speeding event ended
                - start_lat: Latitude where the speeding event started
                - start_lon: Longitude where the speeding event started
                - end_lat: Latitude where the speeding event ended
                - end_lon: Longitude where the speeding event ended
                - speeding_distance_in_km: Distance traveled while speeding in kilometers
                - max_over_speed_in_kph: Maximum speed over the posted limit during the event in km/h
                - avg_over_speed_in_kph: Average speed over the posted limit during the event in km/h
                - min_posted_speed_limit_in_kph: Minimum posted speed limit during the event in km/h
                - max_posted_speed_limit_in_kph: Maximum posted speed limit during the event in km/h
                - avg_vehicle_speed: Average vehicle speed during the event in km/h
                - min_vehicle_speed: Minimum vehicle speed during the event in km/h
                - max_vehicle_speed: Maximum vehicle speed during the event in km/h
                - coaching_status: Coaching status of the event (e.g., "coachable")
                - status: Status of the event (e.g., "invalid")
                - driver: Driver details involved in the event
                - vehicle: Vehicle details involved in the event
                - eld_device: ELD device details used during the event
                - metadata: Metadata related to the speeding event
                    - severity: Severity of the event (e.g., "critical")
                    - trigger: Trigger for the event (e.g., "speeding")
                    - is_manually_changed: Indicates if the event was manually changed

        Reference:
            https://developer.gomotive.com/reference/fetch-the-companys-speeding-events
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if driver_id:
            params["driver_id"] = driver_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/speeding_events", params=params)

    async def get_events(
        self,
        vehicle_id: Optional[str] = None,
        driver_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get vehicle/driver events.

        Args:
            vehicle_id: Optional vehicle ID to filter
            driver_id: Optional driver ID to filter
            event_type: Optional event type filter
            start_time: ISO 8601 start time
            end_time: ISO 8601 end time

        Returns:
            Response containing events
        """
        params = {}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if driver_id:
            params["driver_id"] = driver_id
        if event_type:
            params["event_type"] = event_type
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/events", params=params)

    async def get_reefer_activity_report(
        self,
        asset_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get reefer activity report showing location, temperatures, battery voltage, fuel level, etc.

        Args:
            asset_id: Optional asset ID to filter by
            start_time: Optional ISO 8601 start time
            end_time: Optional ISO 8601 end time

        Returns:
            Response containing reefer activity data with:
            - datetime: Unix timestamp
            - location: Location of the reefer
            - battery_voltage: Battery voltage of Thermo King unit
            - fuel_level: Fuel level of Thermo King unit
            - ambient_air_deg_c: Ambient air temperature in Celsius
            - mode: Operational mode
            - zone_number: Zone identifier
            - status: Current status
            - setpoint_deg_c: Temperature setpoint in Celsius
            - return_deg_c: Return air temperature in Celsius
            - discharge_deg_c: Discharge air temperature in Celsius
            - coil_deg_c: Coil temperature in Celsius
            - door_status: Door status

        Reference:
            https://developer.gomotive.com/reference/fetch-an-activity-report-of-a-reefer
        """
        params = {}
        if asset_id:
            params["asset_id"] = asset_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/reefer_activity_reports", params=params)

    async def locate_asset(self, asset_id: str) -> Dict[str, Any]:
        """
        Locate an asset by triggering an immediate location ping.

        This endpoint pings the asset's gateway to fetch its exact current location,
        instead of relying on the 12-hour scheduled location updates.

        Important Notes:
        - Response is asynchronous and takes 5-15 minutes
        - 15-minute cooldown period between requests
        - Only one locate request can be in progress at a time
        - Frequent requests will impact Asset Gateway battery
        - Response depends on cellular coverage and GPS fix

        Args:
            asset_id: Motive asset ID

        Returns:
            Response containing:
            - asset_id: ID of the asset
            - locate_status: Status of location retrieval
            - last_location: Retrieved location (latitude, longitude, timestamp)
            - message: Message from Asset Gateway (appears when status is "in_progress")

        Raises:
            HTTPStatusError: 429 if request sent within cooldown period

        Reference:
            https://developer.gomotive.com/reference/locate-your-asset
        """
        return await self._request("PUT", f"/v1/assets/{asset_id}/locate")

    async def get_reefer_sensor_samples(
        self,
        asset_ids: List[str],
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """
        Get sensor samples for one or more reefer assets within a time range.

        This is a read-only POST endpoint that returns all available sensor samples
        for the requested assets. POST is used to accommodate large request bodies
        (e.g., hundreds of asset IDs) that could exceed URL length limits.

        Note: Unknown asset IDs are ignored; only known assets are included in the response.

        Args:
            asset_ids: List of asset IDs to get samples for
            start_time: ISO 8601 start time for the sample range
            end_time: ISO 8601 end time for the sample range

        Returns:
            Response containing:
            - assets: Array of asset entries, each with:
              - asset: Asset metadata (id, name)
              - asset_gateway: Gateway information (id, identifier)
              - reefer_samples: Array of sensor sample groups, each with:
                - sensor_id: Unique sensor identifier
                - zone_number: Zone number within reefer
                - zone_location: Zone placement label (front, middle, back)
                - samples_count: Count of sample records
                - samples: Array of individual samples with:
                  - created_at: Unix timestamp
                  - temperature_deg_c: Temperature in Celsius
                  - humidity_pct: Relative humidity percentage
                  - sampled_at_location: Location object (address, lat, lon)

        Reference:
            https://developer.gomotive.com/reference/list-sensor-samples-for-reefers
        """
        payload = {
            "asset_ids": asset_ids,
            "start_time": start_time,
            "end_time": end_time,
        }
        return await self._request("POST", "/v1/reefers/samples", json_data=payload)

    async def get_company_info(self) -> Dict[str, Any]:
        """
        Identify a company using its access token.

        Returns the company details associated with the access token, including:
        - Company ID and name
        - Address information
        - DOT IDs
        - HOS cycle and exception settings
        - Time zone and unit preferences
        - Subscription plan

        Returns:
            Response containing:
            - companies: Array of company objects, each with:
              - id: Unique identifier
              - company_id: System-generated or custom identifier
              - name: Company name
              - street, city, state, zip: Address information
              - dot_ids: Array of DOT IDs
              - cycle: HOS cycle setting
              - time_zone: Company time zone
              - exception_*: Various HOS exception flags
              - metric_units: Whether company uses metric units
              - minute_logs: Whether company uses minute-by-minute logging
              - subscription_plan: Subscription plan name

        Reference:
            https://developer.gomotive.com/reference/identify-a-company-using-its-access-token
        """
        return await self._request("GET", "/v1/companies")

    # Webhook Management Methods
    async def list_webhooks(self) -> Dict[str, Any]:
        """
        List all company webhooks.

        Returns:
            Response containing:
            - company_webhooks: Array of webhook objects, each with:
              - id: Unique identifier
              - url: Webhook URL endpoint
              - secret: Secret key for authentication
              - format: Data format (e.g., "json")
              - actions: Array of action strings that trigger the webhook
              - enabled: Whether webhook is enabled

        Reference:
            https://developer.gomotive.com/reference/list-the-companys-webhooks
        """
        return await self._request("GET", "/v1/company_webhooks")

    async def get_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Get webhook details by ID.

        Args:
            webhook_id: Webhook ID (path parameter)

        Returns:
            Webhook details containing:
            - id: Unique identifier (Integer)
            - url: URL to which webhook sends data
            - secret: Secret key for webhook authentication
            - format: Data format (e.g., "json")
            - actions: Array of action strings that trigger the webhook
            - enabled: Whether webhook is enabled

        Reference:
            https://developer.gomotive.com/reference/fetch-a-webhook-using-its-id
        """
        return await self._request("GET", f"/v1/company_webhooks/{webhook_id}")

    async def create_webhook(
        self,
        url: str,
        secret: str,
        actions: List[str],
        format: str = "json",
        enabled: bool = True,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new company webhook.

        Required parameters:
        - URL: Webhook URL endpoint
        - Secret: Secret key for webhook authentication
        - Format: Data format (e.g., "json")
        - Actions: List of actions that trigger the webhook
        - Enabled: Whether webhook is enabled

        Args:
            url: Webhook URL endpoint
            secret: Secret key for webhook authentication
            actions: List of webhook actions to subscribe to (e.g., ["vehicle.created", "driver.updated"])
            format: Webhook data format (default: "json")
            enabled: Whether webhook is enabled (default: True)
            name: Optional webhook name

        Returns:
            Created webhook details containing:
            - id: Unique identifier
            - url: Webhook URL
            - secret: Secret key
            - format: Data format
            - actions: Array of action strings
            - enabled: Enabled status

        Reference:
            https://developer.gomotive.com/reference/create-a-new-company-webhook
        """
        payload = {
            "url": url,
            "secret": secret,
            "actions": actions,
            "format": format,
            "enabled": enabled,
        }
        if name:
            payload["name"] = name

        return await self._request("POST", "/v1/company_webhooks", json_data=payload)

    async def update_webhook(
        self,
        webhook_id: str,
        url: str,
        secret: str,
        actions: List[str],
        format: str,
        enabled: bool,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing webhook.

        Note: All parameters (URL, Secret, Format, Actions, Enabled) must be provided
        in the request body when updating a webhook.

        Args:
            webhook_id: Webhook ID (path parameter)
            url: Webhook URL endpoint
            secret: Secret key for webhook authentication
            actions: List of actions that trigger the webhook
            format: Data format (e.g., "json")
            enabled: Whether webhook is enabled
            name: Optional webhook name

        Returns:
            Updated webhook details containing:
            - id: Unique identifier
            - url: Webhook URL
            - secret: Secret key
            - format: Data format
            - actions: Array of action strings
            - enabled: Enabled status

        Reference:
            https://developer.gomotive.com/reference/update-an-existing-webhook
        """
        payload: Dict[str, Any] = {
            "url": url,
            "secret": secret,
            "actions": actions,
            "format": format,
            "enabled": enabled,
        }
        if name:
            payload["name"] = name

        return await self._request("PUT", f"/v1/company_webhooks/{webhook_id}", json_data=payload)

    async def get_webhook_requests(
        self,
        webhook_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get all webhook request history for the company.

        Args:
            webhook_id: Optional webhook ID to filter by
            limit: Maximum number of requests to return
            offset: Pagination offset

        Returns:
            Response containing webhook request history with:
            - id: Unique identifier for the webhook request
            - company_webhook_id: ID of the associated webhook
            - action: Action that triggered the webhook request
            - url: URL to which the request was sent
            - secret: Secret key for authentication
            - format: Data format (e.g., "json")
            - payload: Payload data sent with the request
            - response_code: HTTP response code received
            - num_failures: Number of times the request failed
            - posted_at: ISO 8601 datetime when request was sent

        Reference:
            https://developer.gomotive.com/reference/fetch-all-the-webhook-requests
        """
        params = {"limit": limit, "offset": offset}
        if webhook_id:
            params["webhook_id"] = webhook_id

        return await self._request("GET", "/v1/company_webhook_requests", params=params)

    async def retry_webhook_request(self, request_id: str) -> Dict[str, Any]:
        """
        Retry a failed webhook request.

        Webhooks may fail due to network issues or invalid responses. This method
        allows you to retry failed webhook requests by their ID to ensure critical
        webhook events are successfully delivered.

        Args:
            request_id: Webhook request ID to retry

        Returns:
            Response containing:
            - success: Boolean indicating if the webhook request was retried successfully

        Reference:
            https://developer.gomotive.com/reference/retry-webhook-requests
        """
        payload = {"request_id": request_id}
        return await self._request("POST", "/v1/company_webhook_requests/retry", json_data=payload)

    async def get_reefer_thresholds(self) -> Dict[str, Any]:
        """
        Fetch the reefer temperature thresholds for the company.

        This endpoint provides company-level configuration for reefer temperature
        thresholds that the webhook system uses to decide when to emit temperature-breach
        events (below minimum or above maximum).

        The threshold checks power the webhook events for temperature below minimum
        and temperature above maximum, in addition to general telematics change events.

        Returns:
            Response containing:
            - reefer_thresholds: Object with temperature thresholds
                - min_temp_deg_c: Minimum allowable temperature in degrees Celsius
                - max_temp_deg_c: Maximum allowable temperature in degrees Celsius

        Reference:
            https://developer.gomotive.com/reference/fetch-the-reefer-thresholds
        """
        return await self._request("GET", "/v1/company_webhooks/reefer_thresholds")

    async def update_reefer_thresholds(
        self,
        min_temp_deg_c: Optional[float] = None,
        max_temp_deg_c: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Update the reefer temperature thresholds for the company.

        Updates company-level reefer temperature thresholds used by the webhooks to
        determine when to emit temperature-breach events (below minimum / above maximum).

        Values are stored in company preferences and read by the webhooks during
        reefer telemetry handling to drive temperature threshold webhook events.

        Args:
            min_temp_deg_c: Optional minimum allowable temperature in degrees Celsius.
                          Supplying this updates only the minimum value; omitted field remains unchanged.
            max_temp_deg_c: Optional maximum allowable temperature in degrees Celsius.
                          Supplying this updates only the maximum value; omitted field remains unchanged.

        Returns:
            Updated reefer thresholds configuration containing:
            - reefer_thresholds: Object with temperature thresholds
                - min_temp_deg_c: Minimum allowable temperature in degrees Celsius
                - max_temp_deg_c: Maximum allowable temperature in degrees Celsius

        Reference:
            https://developer.gomotive.com/reference/update-the-reefer-temperature-thresholds
        """
        payload: Dict[str, Any] = {}
        if min_temp_deg_c is not None:
            payload["min_temp_deg_c"] = min_temp_deg_c
        if max_temp_deg_c is not None:
            payload["max_temp_deg_c"] = max_temp_deg_c

        return await self._request("POST", "/v1/company_webhooks/reefer_thresholds", json_data=payload)

    async def get_driver_worked_hours(
        self,
        user_ids: Optional[List[int]] = None,
        time_tracking_mode: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a driver's total worked hours.

        Use this API to retrieve the total seconds worked per day per driver. This endpoint
        enables organisations to gather specific information based on user IDs, time tracking
        modes (logs or timecards), start and end dates. By leveraging these filters, businesses
        can focus on the driver data for an in-depth analysis of the total worked hours per driver.

        Args:
            user_ids: Optional list of user IDs to filter by
            time_tracking_mode: Optional time tracking mode (e.g., "timecards", "logs")
            start_date: Optional start date for filtering (format: YYYY-MM-DD)
            end_date: Optional end date for filtering (format: YYYY-MM-DD)

        Returns:
            Response containing:
            - entries: Array of work entries tracking time and associated user information, each containing:
                - date: The specific date for the time entry (e.g., "2023-07-17")
                - time_tracking_mode: The mode used for tracking time (e.g., "timecards")
                - worked_time: The total time worked on the specific date, in minutes (e.g., 1440)
                - id: Unique identifier for the user (e.g., 1033954)
                - first_name: The first name of the user (e.g., "Erik")
                - last_name: The last name of the user (e.g., "Mclaughlin")
                - username: The username associated with the user (e.g., "e.mclaughlin")
                - email: The email address of the user

        Reference:
            https://developer.gomotive.com/reference/fetch-a-drivers-total-worked-hours
        """
        params: Dict[str, Any] = {}
        if user_ids:
            params["user_ids"] = user_ids
        if time_tracking_mode:
            params["time_tracking_mode"] = time_tracking_mode
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self._request("GET", "/v1/time_tracking/worked_time", params=params)

    async def get_timecard_entries(
        self,
        user_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch a list of the timecard entries per driver.

        Use this API to retrieve timecard entries for drivers. This endpoint allows you to
        filter by user ID and date range to get specific timecard information.

        Args:
            user_id: Optional user ID to filter by
            start_date: Optional start date for filtering (format: YYYY-MM-DD)
            end_date: Optional end date for filtering (format: YYYY-MM-DD)
            limit: Maximum number of entries to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing timecard entries with details such as:
            - id: Unique identifier for the timecard entry
            - user_id: ID of the user/driver
            - clock_in: Clock-in timestamp
            - clock_out: Clock-out timestamp
            - date: Date of the timecard entry
            - worked_time: Total time worked in minutes
            - status: Status of the timecard entry

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-the-timecard-entries-per-driver
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if user_id:
            params["user_id"] = user_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self._request("GET", "/v1/time_tracking/timecard_entries", params=params)

    async def create_timecard_entry(
        self,
        user_id: int,
        clock_in: str,
        clock_out: Optional[str] = None,
        date: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new timecard entry.

        Use this API to create a new timecard entry for a driver. This endpoint allows external
        systems to add timecard (workforce time tracking) entries for Motive users, such as drivers,
        from third-party HR, payroll, or time and attendance solutions.

        You can synchronise clock-in and clock-outs of the drivers automatically with external
        systems without any manual intervention.

        Args:
            user_id: ID of the user/driver
            clock_in: Clock-in timestamp (ISO 8601 format)
            clock_out: Optional clock-out timestamp (ISO 8601 format)
            date: Optional date for the timecard entry (format: YYYY-MM-DD). Defaults to today.
            external_id: Optional external ID for tracking this entry in external systems

        Returns:
            Response containing:
            - id: Unique identifier for the created timecard entry
            - user_id: ID of the user/driver
            - clock_in: Clock-in timestamp
            - clock_out: Clock-out timestamp (if provided)
            - date: Date of the timecard entry
            - worked_time: Total time worked in minutes
            - status: Status of the timecard entry

        Reference:
            https://developer.gomotive.com/reference/create-a-new-timecard-entry
        """
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "clock_in": clock_in,
        }
        if clock_out:
            payload["clock_out"] = clock_out
        if date:
            payload["date"] = date
        if external_id:
            payload["external_id"] = external_id

        return await self._request("POST", "/v1/time_tracking/timecard_entries", json_data=payload)

    async def update_timecard_entries(
        self,
        timecard_entries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update timecard entries of a driver.

        This endpoint allows external systems to update timecard (workforce time tracking) entries
        for Motive users, such as drivers, from third-party HR, payroll, or time and attendance
        solutions.

        You can synchronise clock-in and clock-outs of the drivers automatically with external
        systems without any manual intervention.

        Args:
            timecard_entries: List of timecard entry objects to update. Each entry should contain:
                - id: Unique identifier for the timecard entry (required for updates)
                - user_id: ID of the user/driver
                - clock_in: Clock-in timestamp (ISO 8601 format)
                - clock_out: Optional clock-out timestamp (ISO 8601 format)
                - date: Optional date for the timecard entry (format: YYYY-MM-DD)
                - external_id: Optional external ID for tracking this entry in external systems

        Returns:
            Response containing:
            - success: Boolean denoting if the timecard was updated or not. In most cases,
                      the bool value will be "true".

        Reference:
            https://developer.gomotive.com/reference/update-timecard-entries-of-a-driver
        """
        payload = {"timecard_entries": timecard_entries}
        return await self._request("PUT", "/v1/time_tracking/timecard_entries", json_data=payload)

    async def get_scorecard_summaries(
        self,
        vehicle_ids: Optional[List[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetch a list of the scorecard summaries of the company's vehicles.

        Use this API to retrieve scorecard summaries for vehicles. Scorecard summaries provide
        performance metrics and safety scores for vehicles, helping fleet managers monitor and
        improve fleet performance.

        Args:
            vehicle_ids: Optional list of vehicle IDs to filter by
            start_date: Optional start date for filtering (format: YYYY-MM-DD)
            end_date: Optional end date for filtering (format: YYYY-MM-DD)
            limit: Maximum number of summaries to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing scorecard summaries with details such as:
            - id: Unique identifier for the scorecard summary
            - vehicle_id: ID of the vehicle
            - vehicle_name: Name of the vehicle
            - safety_score: Safety score for the vehicle
            - performance_score: Performance score for the vehicle
            - total_events: Total number of events
            - speeding_events: Number of speeding events
            - harsh_braking_events: Number of harsh braking events
            - harsh_acceleration_events: Number of harsh acceleration events
            - harsh_cornering_events: Number of harsh cornering events
            - period_start: Start date of the reporting period
            - period_end: End date of the reporting period

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-the-scorecard-summaries-of-the-companys-vehicles
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if vehicle_ids:
            params["vehicle_ids"] = vehicle_ids
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self._request("GET", "/v1/scorecard_summary", params=params)

    async def get_vehicle_utilization(self) -> Dict[str, Any]:
        """
        Fetch the utilization of a vehicle.

        Use this API to view a summary of the vehicle utilization for your vehicles. A Vehicle
        Utilization Summary provides a report or data overview that tracks how efficiently and
        effectively vehicles within a fleet are being utilized. This summary typically includes
        metrics that help assess the productivity, efficiency, and overall usage of each vehicle
        in the fleet.

        Returns:
            Response containing:
            - vehicle_idle_rollups: Array of vehicle idle rollup objects, each containing:
                - vehicle_idle_rollup: Detailed utilization and idle data for a specific vehicle:
                    - vehicle: Information about the vehicle:
                        - id: Unique identifier for the vehicle
                        - number: Vehicle number or identifier (e.g., "F335ca_00776623")
                        - year: Year of the vehicle's manufacture (if available)
                        - make: Manufacturer of the vehicle (e.g., "Ford")
                        - model: Model of the vehicle
                        - vin: Vehicle Identification Number (VIN)
                        - metric_units: Indicates whether metric units are used (e.g., false for imperial units)
                    - utilization: The utilization rate of the vehicle as a percentage (e.g., 81.42)
                    - idle_time: Total idle time in seconds (e.g., 25,480 seconds)
                    - idle_fuel: Fuel consumed during idle time in liters (e.g., 49.23 litres)
                    - driving_time: Total driving time in seconds (e.g., 111,687 seconds)
                    - driving_fuel: Fuel consumed during driving time in liters (e.g., 721.17 litres)

        Reference:
            https://developer.gomotive.com/reference/fetch-the-utilization-of-a-vehicle
        """
        return await self._request("GET", "/v1/vehicle_utilization")

    async def get_idle_events(
        self,
        vehicle_id: Optional[int] = None,
        driver_id: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        View the idle events of your drivers.

        Use this API to view the idle time or idle events of the drivers in your fleet.

        Args:
            vehicle_id: Optional vehicle ID to filter idle events
            driver_id: Optional driver ID to filter idle events
            start_time: Optional ISO 8601 start time for filtering
            end_time: Optional ISO 8601 end time for filtering
            limit: Maximum number of idle events to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing:
            - idle_event: Array of idle event objects, each containing:
                - id: Unique identifier for the idle event (e.g., 35040)
                - start_time: The start time of the idle event in ISO 8601 format (e.g., "2018-05-29T09:53:57Z")
                - end_time: The end time of the idle event in ISO 8601 format (e.g., "2018-05-29T09:58:10Z")
                - veh_fuel_start: The vehicle's fuel level at the start of the idle event (e.g., 323326.5 liters)
                - veh_fuel_end: The vehicle's fuel level at the end of the idle event (e.g., 323326.8091 liters)
                - lat: Latitude coordinate of the vehicle during the idle event (e.g., 42.9744623)
                - lon: Longitude coordinate of the vehicle during the idle event (e.g., -78.9293763)
                - city: City where the idle event took place (e.g., "Tonawanda")
                - state: State where the idle event took place (e.g., "NY")
                - rg_brg: Registration bearing during the idle event (e.g., 226.923888332155)
                - rg_km: Registration kilometers during the idle event (e.g., 6.4759410773022 km)
                - rg_match: Indicates if the registration matches (e.g., true)
                - end_type: The reason why the idle event ended (e.g., "vehicle_moving")
                - driver: Information about the driver during the idle event (null if not applicable)
                - vehicle: Information about the vehicle involved in the idle event:
                    - id: Unique identifier for the vehicle (e.g., 4052)
                    - number: Vehicle number or identifier (e.g., "F335ca_00795348")
                    - year: Year of the vehicle's manufacture (if available)
                    - make: Manufacturer of the vehicle (e.g., "Ford")
                    - model: Model of the vehicle
                    - vin: Vehicle Identification Number (VIN)
                    - metric_units: Indicates whether metric units are used (e.g., false for imperial units)
                - eld_device: Information about the vehicle gateway associated with the idle event:
                    - id: Unique identifier for the vehicle gateway (e.g., 21186)
                    - identifier: Identifier for the vehicle gateway (e.g., "00795348")
                    - model: Model of the vehicle gateway (e.g., "lbb-3.35ca")
                - location: Description of the location where the idle event occurred (e.g., "Tonawanda, NY")

        Reference:
            https://developer.gomotive.com/reference/view-the-idle-events-of-your-drivers
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if driver_id:
            params["driver_id"] = driver_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/idle_events", params=params)

    async def get_vehicle_gateways(self) -> Dict[str, Any]:
        """
        List vehicle gateways of an organization.

        This endpoint fetches all the available vehicle gateways (ELD devices) that are
        assigned to your company or organization. It is important to note that your company
        must have vehicle gateways and those must be assigned to a vehicle as well as must
        be installed in those vehicles.

        Returns:
            Response containing:
            - eld_devices: Array of ELD device objects, each containing:
                - eld_devices: Information pertaining to the ELD device:
                    - id: Denotes the ID of the ELD device that is assigned to the vehicle
                    - identifier: Denotes the unique identifier of the ELD device
                    - model: Denotes the model name or the number of the ELD device
                - vehicles: Vehicle information that is associated with the ELD device:
                    - id: Denotes the unique identifier of the organization's vehicle to which
                          this ELD device is assigned to
                    - number: Denotes the number of the vehicle to which the ELD device is
                             assigned to
                    - year: Denotes the manufacturing year of the organization's vehicle
                    - make: Denotes the name of the manufacturer of the organization's vehicle
                    - model: Denotes the name of the model of the vehicle
                    - vin: Denotes the VIN number of the vehicle
                    - metric_units: Denotes if the vehicle uses the metric units for measuring
                                   its data or not (TRUE: uses metric units, FALSE: does not)
                    - mcleod_id: Denotes the McLeod ID of the vehicle (NOTE: This ID appears
                                only if the McLeod integration is enabled and active for an
                                account. Otherwise, you will not see this parameter appear
                                in the response)

        Reference:
            https://developer.gomotive.com/reference/fetch-the-eld-devices-of-an-organization
        """
        return await self._request("GET", "/v1/eld_devices")

    async def get_vehicle_gateway_disconnects(
        self,
        vehicle_id: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List vehicle gateway disconnect events.

        This endpoint provides information about Vehicle Gateway disconnect events. It details
        when a Vehicle Gateway went offline, where the disconnect occurred, which driver and
        vehicle were involved, and when/if it reconnected. This information can be used for
        auditing, ensuring Hours of Service (HOS) compliance, and investigating potential
        connectivity issues.

        Args:
            vehicle_id: Optional vehicle ID to filter disconnect events
            start_time: Optional ISO 8601 start time for filtering
            end_time: Optional ISO 8601 end time for filtering
            limit: Maximum number of disconnect events to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing:
            - eld_disconnects: Array of Vehicle Gateway disconnect event objects, each containing:
                - eld_disconnect: Details about a single Vehicle Gateway disconnect event:
                    - id: The unique identifier of the Vehicle Gateway disconnect event
                    - offline_id: The offline ID for the Vehicle Gateway disconnect
                    - start_time: The timestamp when the Vehicle Gateway went offline (DateTime)
                    - vehicle: Information about the vehicle at the time of disconnect:
                        - id: The unique identifier of the vehicle
                        - number: The number (or name) assigned to the vehicle
                    - previous_driver: The driver who was operating the vehicle before the
                                      Vehicle Gateway disconnected:
                        - id: The unique identifier of the previous driver
                        - first_name: The first name of the previous driver
                        - last_name: The last name of the previous driver
                        - driver_company_id: The company ID associated with the previous driver (if any)
                    - next_driver: The driver who takes over after the Vehicle Gateway reconnects
                                 (if applicable):
                        - id: The unique identifier of the next driver
                        - first_name: The first name of the next driver
                        - last_name: The last name of the next driver
                        - driver_company_id: The company ID associated with the next driver (if any)
                    - notes: Array of strings - any notes or comments related to the Vehicle
                            Gateway disconnect
                    - disconnect_location: The location where the Vehicle Gateway was disconnected
                    - reconnect_location: The location where the Vehicle Gateway was reconnected
                                        (if applicable)
                    - end_time: The timestamp when the Vehicle Gateway was reconnected
                               (if applicable, DateTime)

        Reference:
            https://developer.gomotive.com/reference/view-all-the-vehicle-gateway-disconnect-events
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self._request("GET", "/v1/eld_disconnects", params=params)

    async def add_external_id(
        self,
        external_id: str,
        integration_name: str,
        external_id_holder_id: int,
        external_id_holder_type: str,
    ) -> Dict[str, Any]:
        """
        Add External ID Info for an Entity.

        Use this endpoint to add the external integration details of an entity. For example,
        if you have an existing ADP integration for running the payroll of your users, this
        endpoint allows you to add critical info such as the integration name, and external ID,
        for mapping your users between ADP and Motive. This provides for a seamless integration
        between the two systems.

        Args:
            external_id: The external ID assigned by the integration partner
            integration_name: The name of the third-party integration that provided this external ID
            external_id_holder_id: The unique identifier assigned to the entity such as a user,
                                 vehicle, asset, or a group. If your entity is a user, then enter
                                 the user ID here. If a vehicle, enter the vehicle ID. Similarly
                                 for asset (asset ID), and group (group ID).
            external_id_holder_type: Specify the type of the holder or the entity. Allowed values
                                    are "User", "Vehicle", "Asset", or "Group"

        Returns:
            Response containing:
            - id: The unique identifier assigned to this external ID record
            - external_id: The external ID assigned by the integration partner
            - integration_name: The name of the third-party integration that provided this external ID
            - external_id_holder_id: The unique identifier assigned to the entity such as a user,
                                   vehicle, asset, or a group
            - external_id_holder_type: The type of the holder or the entity (User, Vehicle, Asset, or Group)

        Reference:
            https://developer.gomotive.com/reference/add-external-id-info-for-an-entity
        """
        payload = {
            "external_id": external_id,
            "integration_name": integration_name,
            "external_id_holder_id": external_id_holder_id,
            "external_id_holder_type": external_id_holder_type,
        }
        return await self._request("POST", "/v1/external_ids", json_data=payload)

    async def update_external_id(
        self,
        external_id_id: int,
        external_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        external_id_holder_id: Optional[int] = None,
        external_id_holder_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the External ID of an Entity.

        Use this endpoint to update the external integration info of an entity.

        Note: For updating the external integration details of entities such as users, vehicles,
        assets, or groups, you will require a Motive generated 'id'. This can be obtained by
        passing the GET v1/{entity}/:id endpoint. For example, if you are updating the external
        integration info for a user, pass the GET v1/user/:<user_id>. This endpoint will return
        the external_ids array with the id value that should be used in the path parameter.

        Args:
            external_id_id: The Motive-generated unique identifier for the external ID record
                          (obtained from GET v1/{entity}/:id endpoint)
            external_id: Optional - the external ID assigned by the integration partner
            integration_name: Optional - the name of the third-party integration that provided
                            this external ID
            external_id_holder_id: Optional - the unique identifier assigned to the entity such
                                 as a user, vehicle, asset, or a group
            external_id_holder_type: Optional - specify the type of the holder or the entity.
                                    Allowed values are "User", "Vehicle", "Asset", or "Group"

        Returns:
            Response containing:
            - id: The unique identifier assigned to this external ID record
            - external_id: The external ID assigned by the integration partner
            - integration_name: The name of the third-party integration that provided this external ID
            - external_id_holder_id: The unique identifier assigned to the entity such as a user,
                                   vehicle, asset, or a group
            - external_id_holder_type: The type of the holder or the entity (User, Vehicle, Asset, or Group)

        Reference:
            https://developer.gomotive.com/reference/update-the-external-id-of-an-entity
        """
        payload: Dict[str, Any] = {}
        if external_id is not None:
            payload["external_id"] = external_id
        if integration_name is not None:
            payload["integration_name"] = integration_name
        if external_id_holder_id is not None:
            payload["external_id_holder_id"] = external_id_holder_id
        if external_id_holder_type is not None:
            payload["external_id_holder_type"] = external_id_holder_type

        return await self._request("PUT", f"/v1/external_ids/{external_id_id}", json_data=payload)

    async def delete_external_id(self, external_id_id: int) -> Dict[str, Any]:
        """
        Delete External ID for an Entity.

        Use this endpoint to delete the external integration ID for an entity. For example,
        if you were earlier using a third-party integration for managing your users, and no
        longer require it, you can go ahead and call this endpoint to remove the association
        of your users with the third-party software inside Motive.

        Note: For deleting the external integration details of entities such as users, vehicles,
        assets, or groups, you will require a Motive generated 'id'. This can be obtained by
        passing the GET v1/{entity}/:id endpoint. For example, if you are deleting the external
        integration info for a user, pass the GET v1/user/:<user_id>. This endpoint will return
        the external_ids array with the id value that should be used in the path parameter.

        Args:
            external_id_id: The Motive-generated unique identifier for the external ID record
                          (obtained from GET v1/{entity}/:id endpoint)

        Returns:
            Response containing:
            - success: Denotes if the entity and third-party association was successfully
                      deleted or not

        Reference:
            https://developer.gomotive.com/reference/delete-external-id-for-an-entity
        """
        return await self._request("DELETE", f"/v1/external_ids/{external_id_id}")

    async def get_reefer_activity_data(
        self,
        asset_ids: Optional[List[int]] = None,
        reefer_state: Optional[str] = None,
        updated_after: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        View Reefer Activity Data.

        This endpoint returns the most recent reefer activity for one or many assets, combining
        asset/location details with OEM and sensor telemetry (e.g., power state, control mode,
        zone temperatures, fuel level, battery), with optional filters for asset_ids, reefer_state,
        and updated_after (defaults to last 7 days); responses are paginated and sorted by updated_at.

        Args:
            asset_ids: Optional list of asset IDs to filter by
            reefer_state: Optional reefer state to filter by
            updated_after: Optional ISO 8601 timestamp to filter by (defaults to last 7 days)
            limit: Maximum number of records to return (default: 100)
            offset: Pagination offset (default: 0)

        Returns:
            Response containing:
            - asset: Array of asset objects, each containing:
                - id: Unique identifier for the asset
                - make: Manufacturer of the asset
                - model: Model number of the asset
                - type: Type of the asset (e.g., "reefer", "trailer", etc.)
                - status: Current operational status of the asset
                - name: Asset name or identifier
                - source: Source of the asset data
                - location: Contains real-time GPS and address details for the asset's last known position:
                    - read_id: Identifier for the location read event
                    - oem_entity_id: OEM-specific entity identifier for the asset
                    - asset_name: Name of the associated asset
                    - asset_id: Internal identifier for the asset location record
                    - lat: Latitude coordinate of the asset
                    - lon: Longitude coordinate of the asset
                    - state: State where the asset is located
                    - city: City name
                    - zip: ZIP code of the location
                    - street: Street name of the location
                    - country: Country code (ISO)
                    - house_number: Street address number
                    - located_at: Timestamp of when the location was recorded (ISO 8601)
                    - address: Human-readable address format
                - sensor_data: Contains telemetry and sensor data from the Carrier system:
                    - carrier_overall: General reefer system metrics and status information:
                        - battery_voltage: Battery voltage reading
                        - fuel_level: Current fuel level percentage
                        - total_engine_hours: Total accumulated engine run time in hours
                        - control_mode: Current reefer control mode
                        - power_status: Indicates whether the reefer is powered on or off
                        - door_open: Indicates if the reefer door is open
                        - alarms: List of active alarms (if any)
                        - last_updated_at: Last update timestamp for reefer data (ISO 8601)
                    - zones: Array of objects representing the individual temperature zones of the
                            reefer and their configurations:
                        - zone_number: Zone identifier
                        - set_point_deg_c: Desired setpoint temperature in °C (Float or Null)
                        - return_air_deg_c: Return air temperature in °C (Float or Null)
                        - supply_air_deg_c: Supply air temperature in °C (Float or Null)
                        - probe_temp_deg_c: Probe temperature reading in °C (Float or Null)
                        - operating_mode: Current mode of the compartment

        Reference:
            https://developer.gomotive.com/reference/view-reefer-activity-data
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if asset_ids:
            params["asset_ids"] = asset_ids
        if reefer_state:
            params["reefer_state"] = reefer_state
        if updated_after:
            params["updated_after"] = updated_after

        return await self._request("GET", "/v1/reefer_activity_data", params=params)

    async def get_dispatch_locations(
        self,
        per_page: Optional[int] = None,
        page_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        List all dispatch locations.

        Args:
            per_page: Number of results per page
            page_no: Page number

        Returns:
            Response containing dispatch locations

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-company-dispatches
        """
        params: Dict[str, Any] = {}
        if per_page:
            params["per_page"] = per_page
        if page_no:
            params["page_no"] = page_no

        return await self._request("GET", "/v1/dispatch_locations", params=params)

    async def create_dispatch_location(
        self,
        location_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new dispatch location.

        Args:
            location_data: Dispatch location data

        Returns:
            Created dispatch location

        Reference:
            https://developer.gomotive.com/reference/create-a-dispatch-location
        """
        return await self._request("POST", "/v1/dispatch_locations", json_data=location_data)

    async def update_dispatch_location(
        self,
        location_id: str,
        location_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing dispatch location.

        Args:
            location_id: Dispatch location ID
            location_data: Updated dispatch location data

        Returns:
            Updated dispatch location

        Reference:
            https://developer.gomotive.com/reference/update-an-existing-dispatch-location
        """
        return await self._request("PUT", f"/v1/dispatch_locations/{location_id}", json_data=location_data)

    async def get_forms(
        self,
        per_page: Optional[int] = None,
        page_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        List all dispatch stop forms.

        Args:
            per_page: Number of results per page
            page_no: Page number

        Returns:
            Response containing forms

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-all-the-dispatch-stop-forms
        """
        params: Dict[str, Any] = {}
        if per_page:
            params["per_page"] = per_page
        if page_no:
            params["page_no"] = page_no

        return await self._request("GET", "/v1/forms", params=params)

    async def get_form_entries(
        self,
        form_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        driver_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        per_page: Optional[int] = None,
        page_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        List form entries.

        Args:
            form_id: Optional form ID to filter by
            vehicle_id: Optional vehicle ID to filter by
            driver_id: Optional driver ID to filter by
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            per_page: Number of results per page
            page_no: Page number

        Returns:
            Response containing form entries

        Reference:
            https://developer.gomotive.com/reference/fetch-a-list-of-the-vehicle-form-entries
        """
        params: Dict[str, Any] = {}
        if form_id:
            params["form_id"] = form_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if driver_id:
            params["driver_id"] = driver_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if per_page:
            params["per_page"] = per_page
        if page_no:
            params["page_no"] = page_no

        return await self._request("GET", "/v1/form_entries", params=params)

    async def create_dispatch(
        self,
        dispatch_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new dispatch.

        Args:
            dispatch_data: Dispatch data

        Returns:
            Created dispatch

        Reference:
            https://developer.gomotive.com/reference/create-a-new-dispatch
        """
        return await self._request("POST", "/v1/dispatches", json_data=dispatch_data)

    async def update_dispatch(
        self,
        dispatch_id: str,
        dispatch_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing dispatch.

        Args:
            dispatch_id: Dispatch ID
            dispatch_data: Updated dispatch data

        Returns:
            Updated dispatch

        Reference:
            https://developer.gomotive.com/reference/update-an-existing-dispatch
        """
        return await self._request("PUT", f"/v1/dispatches/{dispatch_id}", json_data=dispatch_data)

    async def send_message_v2(
        self,
        message_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send bulk messages to users (v2).

        Args:
            message_data: Message data including recipients and content

        Returns:
            Response containing message status

        Reference:
            https://developer.gomotive.com/reference/send-a-a-bulk-message-to-your-users-v2
        """
        return await self._request("POST", "/v2/messages", json_data=message_data)

    async def update_inspection_report(
        self,
        report_id: str,
        report_data: Dict[str, Any],
        external_ids_attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update an inspection report.

        Args:
            report_id: Inspection report ID
            report_data: Updated inspection report data
            external_ids_attributes: Optional external IDs attributes

        Returns:
            Updated inspection report

        Reference:
            https://developer.gomotive.com/reference/update-an-existing-inspection-report
        """
        params: Dict[str, Any] = {}
        if external_ids_attributes:
            params["external_ids_attributes"] = external_ids_attributes

        return await self._request(
            "PUT", f"/v1/inspection_reports/{report_id}", params=params, json_data=report_data
        )

    async def test_connection(self) -> bool:
        """
        Test API connection by getting company info.

        Returns:
            True if connection is successful
        """
        try:
            await self.get_company_info()
            return True
        except Exception as e:
            logger.error(f"Motive connection test failed: {str(e)}")
            return False

