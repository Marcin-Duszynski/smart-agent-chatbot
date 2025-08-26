"""
Customer configuration router for managing selected customer persona
"""

import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()

CUSTOMER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'customer_config.json')

class CustomerSelection(BaseModel):
    customer_id: str

def load_customer_config() -> Dict[str, Any]:
    """Load customer configuration from JSON file"""
    try:
        with open(CUSTOMER_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default config if file doesn't exist
        return {
            "selected_customer_id": "CUST_001",
            "customers": {
                "CUST_001": {
                    "name": "John Smith",
                    "description": "Food Enthusiast - Urban professional who loves fine dining and travel",
                    "lifestyle": "food_enthusiast",
                    "active": True
                },
                "CUST_002": {
                    "name": "Sarah Johnson", 
                    "description": "Family-Focused - Suburban mom managing household and kids activities",
                    "lifestyle": "family_focused",
                    "active": False
                },
                "CUST_003": {
                    "name": "Michael Brown",
                    "description": "Sports Enthusiast - Golf lover with premium lifestyle preferences", 
                    "lifestyle": "sports_enthusiast",
                    "active": False
                }
            }
        }

def save_customer_config(config: Dict[str, Any]) -> None:
    """Save customer configuration to JSON file"""
    with open(CUSTOMER_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

@router.get("/customer/config")
async def get_customer_config():
    """Get current customer configuration"""
    try:
        config = load_customer_config()
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading customer config: {str(e)}")

@router.post("/customer/select")
async def select_customer(selection: CustomerSelection):
    """Select a customer persona"""
    try:
        config = load_customer_config()
        
        # Validate customer_id exists
        if selection.customer_id not in config["customers"]:
            raise HTTPException(status_code=400, detail=f"Customer ID {selection.customer_id} not found")
        
        # Update selected customer and active status
        config["selected_customer_id"] = selection.customer_id
        
        # Set all customers to inactive first
        for customer_id in config["customers"]:
            config["customers"][customer_id]["active"] = False
        
        # Set selected customer to active
        config["customers"][selection.customer_id]["active"] = True
        
        # Save updated config
        save_customer_config(config)
        
        return {
            "success": True,
            "selected_customer_id": selection.customer_id,
            "customer_name": config["customers"][selection.customer_id]["name"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting customer: {str(e)}")

@router.get("/customer/selected")
async def get_selected_customer():
    """Get currently selected customer"""
    try:
        config = load_customer_config()
        selected_id = config["selected_customer_id"]
        selected_customer = config["customers"][selected_id]
        
        return {
            "customer_id": selected_id,
            "name": selected_customer["name"],
            "description": selected_customer["description"],
            "lifestyle": selected_customer["lifestyle"],
            "active": selected_customer["active"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting selected customer: {str(e)}")
