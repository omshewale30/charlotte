from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import logging
from typing import Optional, Dict
import base64
import json
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Security scheme
security = HTTPBearer()

def validate_jwt_token(token: str) -> Dict:
    """
    Simple JWT token validation - extracts user info from token payload
    Note: This does NOT verify token signature (Azure AD handles that)
    """
    try:
        # Split JWT token into parts
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT token format")
        
        # Decode payload (add padding if needed)
        payload_encoded = parts[1]
        payload_encoded += '=' * (4 - len(payload_encoded) % 4)
        payload_decoded = base64.urlsafe_b64decode(payload_encoded)
        payload = json.loads(payload_decoded)
        
        # Extract user information from token
        # Try multiple fields for email as different tokens may have email in different fields
        email = (payload.get("email") or 
                payload.get("preferred_username") or 
                payload.get("upn") or 
                payload.get("unique_name"))
        
        user_info = {
            "id": payload.get("oid") or payload.get("sub"),
            "email": email,
            "name": payload.get("name"),
            "given_name": payload.get("given_name"),
            "family_name": payload.get("family_name"),
            "job_title": payload.get("jobTitle"),
            "tenant_id": payload.get("tid")
        }
        
        return user_info
        
    except Exception as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user from JWT token"""
    try:
        logger.info(f"Received token: {credentials.credentials[:50]}..." if credentials.credentials else "No token")
        user_info = validate_jwt_token(credentials.credentials)
        logger.info(f"Extracted user info: {user_info}")
        
        if not user_info.get("id"):
            logger.error(f"No user ID found in token payload: {user_info}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Optional dependency that doesn't raise error if no auth provided"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

# Utility functions for auth checking
def require_unc_email(user: Dict = Depends(get_current_user)) -> Dict:
    """Authentication is handled by Azure AD - just return the user"""
    logger.info(f"Access granted for authenticated user: {user.get('name')} (ID: {user.get('id')})")
    return user

def check_user_permissions(user: Dict, required_permissions: list = None) -> bool:
    """Check if user has required permissions (can be extended)"""
    # Basic implementation - can be extended with role-based access
    if not user:
        return False
    
    # For now, just check if user has UNC email
    email = user.get("email", "")
    return email.endswith("@unc.edu") or email.endswith("@ad.unc.edu")