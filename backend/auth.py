from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
import logging
from typing import Optional, Dict
import requests
from msal import ConfidentialClientApplication
import uuid
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Security scheme
security = HTTPBearer()

class MSALAuth:
    def __init__(self):
        self.client_id = os.getenv("AZURE_AD_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_AD_CLIENT_SECRET") 
        self.tenant_id = os.getenv("AZURE_AD_TENANT_ID")
        self.redirect_uri = os.getenv("AZURE_AD_REDIRECT_URI", "http://localhost:8000/auth/callback")
        
        if not all([self.client_id, self.client_secret, self.tenant_id]):
            raise ValueError("Missing required Azure AD configuration")
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = [ "User.Read"]
        
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )
        
        # In-memory session store (use Redis in production)
        self.sessions = {}
    
    def get_auth_url(self, state: str = None) -> str:
        """Generate authorization URL for OAuth flow"""
        if not state:
            state = str(uuid.uuid4())
        
        auth_url = self.app.get_authorization_request_url(
            scopes=self.scopes,
            redirect_uri=self.redirect_uri,
            state=state
        )
        
        return auth_url, state
    
    def handle_callback(self, code: str, state: str) -> Dict:
        """Handle OAuth callback and exchange code for tokens"""
        try:
            result = self.app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri
            )
            
            if "error" in result:
                logger.error(f"Token acquisition error: {result.get('error_description')}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Authentication failed: {result.get('error_description')}"
                )
            
            # Extract user info
            access_token = result["access_token"]
            id_token = result.get("id_token")
            
            # Get user profile from Microsoft Graph
            user_info = self.get_user_profile(access_token)
            
            # Create session
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {
                "user_info": user_info,
                "access_token": access_token,
                "id_token": id_token,
                "expires_at": datetime.utcnow() + timedelta(hours=1),
                "state": state
            }
            
            return {
                "session_id": session_id,
                "user": user_info,
                "expires_at": self.sessions[session_id]["expires_at"].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Callback handling error: {e}")
            raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
    
    def get_user_profile(self, access_token: str) -> Dict:
        """Fetch user profile from Microsoft Graph API"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            'https://graph.microsoft.com/v1.0/me',
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch user profile: {response.text}")
            raise HTTPException(status_code=400, detail="Failed to fetch user profile")
        
        user_data = response.json()
        
        # Extract relevant user information
        return {
            "id": user_data.get("id"),
            "email": user_data.get("mail") or user_data.get("userPrincipalName"),
            "name": user_data.get("displayName"),
            "given_name": user_data.get("givenName"),
            "family_name": user_data.get("surname"),
            "job_title": user_data.get("jobTitle"),
            "department": user_data.get("department"),
            "office_location": user_data.get("officeLocation")
        }
    
    def verify_session(self, session_id: str) -> Optional[Dict]:
        """Verify if session is valid and not expired"""
        session = self.sessions.get(session_id)
        
        if not session:
            return None
        
        if datetime.utcnow() > session["expires_at"]:
            # Session expired, remove it
            del self.sessions[session_id]
            return None
        
        return session
    
    def logout(self, session_id: str) -> bool:
        """Logout user and invalidate session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

# Initialize MSAL auth
msal_auth = MSALAuth()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    
    # Verify session
    session = msal_auth.verify_session(token)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return session["user_info"]

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
    """Require user to have UNC email domain"""
    email = user.get("email", "")
    
    # Accept various UNC email domains
    valid_domains = [
        "@unc.edu", 
        "@email.unc.edu", 
        "@charlotte.edu", 
        "@email.charlotte.edu",
        "@uncc.edu",
        "@email.uncc.edu"
    ]
    
    is_valid = any(email.endswith(domain) for domain in valid_domains)
    
    if not is_valid:
        logger.warning(f"Access denied for email: {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access restricted to UNC email addresses. Your email domain is not authorized."
        )
    
    logger.info(f"Access granted for UNC user: {email}")
    return user

def check_user_permissions(user: Dict, required_permissions: list = None) -> bool:
    """Check if user has required permissions (can be extended)"""
    # Basic implementation - can be extended with role-based access
    if not user:
        return False
    
    # For now, just check if user has UNC email
    email = user.get("email", "")
    return email.endswith("@unc.edu") or email.endswith("@charlotte.edu")