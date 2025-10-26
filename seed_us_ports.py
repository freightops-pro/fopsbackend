#!/usr/bin/env python3
"""
Seed script for major US container ports

Populates the ports table with configuration for the 10 largest US container ports
including their UN/LOC codes, API endpoints, authentication requirements, and
compliance standards.

Usage:
    python seed_us_ports.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.config.db import get_db
from app.models.port import Port, PortAuthType, PortService
import uuid

def seed_ports():
    """Seed the ports table with major US container ports"""
    
    db = next(get_db())
    
    # Check if ports already exist
    existing_count = db.query(Port).count()
    if existing_count > 0:
        print(f"Ports already seeded ({existing_count} ports found). Skipping.")
        return
    
    # Major US Container Ports Configuration
    ports_data = [
        {
            "port_code": "USLAX",
            "port_name": "Port of Los Angeles",
            "unlocode": "USLAX",
            "region": "West Coast",
            "state": "CA",
            "api_endpoint": "https://api.portoflosangeles.org/v2",
            "api_version": "2.0",
            "auth_type": PortAuthType.OAUTH2,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.GATE_OPERATIONS.value,
                PortService.DOCUMENT_UPLOAD.value
            ],
            "rate_limits": {
                "requests_per_minute": 100,
                "burst_capacity": 50,
                "daily_limit": 10000
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": True,
                "isf_required": True,
                "ams_required": True
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": True
            },
            "priority": 1
        },
        {
            "port_code": "USLGB",
            "port_name": "Port of Long Beach",
            "unlocode": "USLGB",
            "region": "West Coast",
            "state": "CA",
            "api_endpoint": "https://api.polb.com/api/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.API_KEY,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.GATE_OPERATIONS.value
            ],
            "rate_limits": {
                "requests_per_minute": 80,
                "burst_capacity": 40,
                "daily_limit": 8000
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": True,
                "isf_required": True,
                "ams_required": False
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": False
            },
            "priority": 2
        },
        {
            "port_code": "USNYC",
            "port_name": "Port of New York & New Jersey",
            "unlocode": "USNYC",
            "region": "East Coast",
            "state": "NY",
            "api_endpoint": "https://api.panynj.gov/port/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.JWT,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.DOCUMENT_UPLOAD.value,
                PortService.BERTH_AVAILABILITY.value
            ],
            "rate_limits": {
                "requests_per_minute": 120,
                "burst_capacity": 60,
                "daily_limit": 12000
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": True,
                "isf_required": True,
                "ams_required": True,
                "c-tpat_tier_3": True
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": True,
                "bond_required": True
            },
            "priority": 3
        },
        {
            "port_code": "USSAV",
            "port_name": "Port of Savannah",
            "unlocode": "USSAV",
            "region": "East Coast",
            "state": "GA",
            "api_endpoint": "https://api.gaports.com/savannah/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.API_KEY,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.GATE_OPERATIONS.value,
                PortService.BERTH_AVAILABILITY.value
            ],
            "rate_limits": {
                "requests_per_minute": 90,
                "burst_capacity": 45,
                "daily_limit": 9000
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": False,
                "isf_required": True,
                "ams_required": False
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": False
            },
            "priority": 4
        },
        {
            "port_code": "USHOU",
            "port_name": "Port of Houston",
            "unlocode": "USHOU",
            "region": "Gulf Coast",
            "state": "TX",
            "api_endpoint": "https://api.portofhouston.com/container/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.CLIENT_CERT,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.BERTH_AVAILABILITY.value
            ],
            "rate_limits": {
                "requests_per_minute": 75,
                "burst_capacity": 35,
                "daily_limit": 7500
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": True,
                "isf_required": True,
                "ams_required": True
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": True,
                "petroleum_license": True
            },
            "priority": 5
        },
        {
            "port_code": "USSEA",
            "port_name": "Port of Seattle",
            "unlocode": "USSEA",
            "region": "West Coast",
            "state": "WA",
            "api_endpoint": "https://api.portseattle.org/api/v2",
            "api_version": "2.0",
            "auth_type": PortAuthType.OAUTH2,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.GATE_OPERATIONS.value
            ],
            "rate_limits": {
                "requests_per_minute": 70,
                "burst_capacity": 30,
                "daily_limit": 7000
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": False,
                "isf_required": True,
                "ams_required": False
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": False
            },
            "priority": 6
        },
        {
            "port_code": "USOAK",
            "port_name": "Port of Oakland",
            "unlocode": "USOAK",
            "region": "West Coast",
            "state": "CA",
            "api_endpoint": "https://api.portofoakland.com/api/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.API_KEY,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.GATE_OPERATIONS.value
            ],
            "rate_limits": {
                "requests_per_minute": 60,
                "burst_capacity": 25,
                "daily_limit": 6000
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": False,
                "isf_required": True,
                "ams_required": False
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": False
            },
            "priority": 7
        },
        {
            "port_code": "USCHS",
            "port_name": "Port of Charleston",
            "unlocode": "USCHS",
            "region": "East Coast",
            "state": "SC",
            "api_endpoint": "https://api.scspa.com/charleston/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.BASIC_AUTH,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.GATE_OPERATIONS.value
            ],
            "rate_limits": {
                "requests_per_minute": 55,
                "burst_capacity": 20,
                "daily_limit": 5500
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": False,
                "isf_required": True,
                "ams_required": False
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": False
            },
            "priority": 8
        },
        {
            "port_code": "USORF",
            "port_name": "Port of Virginia",
            "unlocode": "USORF",
            "region": "East Coast",
            "state": "VA",
            "api_endpoint": "https://api.portofvirginia.com/api/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.API_KEY,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.GATE_OPERATIONS.value
            ],
            "rate_limits": {
                "requests_per_minute": 50,
                "burst_capacity": 20,
                "daily_limit": 5000
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": False,
                "isf_required": True,
                "ams_required": False
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": False
            },
            "priority": 9
        },
        {
            "port_code": "USTIW",
            "port_name": "Port of Tacoma",
            "unlocode": "USTIW",
            "region": "West Coast",
            "state": "WA",
            "api_endpoint": "https://api.portoftacoma.com/api/v1",
            "api_version": "1.0",
            "auth_type": PortAuthType.OAUTH2,
            "services_supported": [
                PortService.VESSEL_SCHEDULING.value,
                PortService.CONTAINER_TRACKING.value,
                PortService.GATE_OPERATIONS.value
            ],
            "rate_limits": {
                "requests_per_minute": 45,
                "burst_capacity": 15,
                "daily_limit": 4500
            },
            "compliance_standards": {
                "twic_required": True,
                "ctpat_certified": False,
                "isf_required": True,
                "ams_required": False
            },
            "documentation_requirements": {
                "manifest_required": True,
                "customs_declaration": True,
                "safety_certificate": True,
                "insurance_document": False
            },
            "priority": 10
        }
    ]
    
    # Create port records
    created_count = 0
    for port_data in ports_data:
        port = Port(
            id=str(uuid.uuid4()),
            **port_data
        )
        db.add(port)
        created_count += 1
        print(f"Added port: {port_data['port_name']} ({port_data['port_code']})")
    
    # Commit to database
    db.commit()
    print(f"\nSuccessfully seeded {created_count} major US container ports!")
    print("\nPort Summary:")
    print("=" * 50)
    
    # Display summary
    for port_data in ports_data:
        print(f"{port_data['port_code']}: {port_data['port_name']} ({port_data['region']})")
    
    db.close()

if __name__ == "__main__":
    print("Seeding major US container ports...")
    seed_ports()
    print("Port seeding completed!")









