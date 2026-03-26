
import logging
import os
from typing import Optional, Dict, Any

from agentic_brain.auth.providers import AuthProvider
from agentic_brain.auth.models import Credentials, User, AuthenticationResult, AuthMethod
from agentic_brain.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials as firebase_credentials
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    firebase_auth = None

class FirebaseAuthProvider(AuthProvider):
    """
    Firebase Authentication Provider.
    
    Validates Firebase ID tokens and extracts user information.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Firebase provider.
        
        Args:
            config: Configuration dictionary containing:
                - firebase_credentials_file: Path to service account JSON (optional)
                - firebase_project_id: Project ID (optional)
        """
        self.config = config
        self._app = None
        
        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase Admin SDK not installed. Firebase auth will not work.")
            return

        self._initialize_app()
            
    def _initialize_app(self):
        """Initialize Firebase Admin app if not already initialized."""
        try:
            # Check if app already exists
            try:
                self._app = firebase_admin.get_app()
                return
            except ValueError:
                pass  # App not initialized

            cred_path = self.config.get("firebase_credentials_file")
            options = {}
            if self.config.get("firebase_project_id"):
                options["projectId"] = self.config.get("firebase_project_id")

            if cred_path and os.path.exists(cred_path):
                cred = firebase_credentials.Certificate(cred_path)
                self._app = firebase_admin.initialize_app(cred, options)
            else:
                # Use default credentials (Google Application Default Credentials)
                self._app = firebase_admin.initialize_app(options=options)
                
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin: {e}")

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """
        Authenticate using Firebase ID token.
        
        Args:
            credentials: Must be TokenCredentials containing the Firebase ID token.
            
        Returns:
            AuthenticationResult with user info.
        """
        if not FIREBASE_AVAILABLE:
            raise AuthenticationError("Firebase Admin SDK not installed")

        if not hasattr(credentials, "token"):
            raise AuthenticationError("Invalid credentials type. Expected TokenCredentials.")

        token = credentials.token
        
        try:
            # Verify the ID token
            decoded_token = firebase_auth.verify_id_token(token, app=self._app)
            
            # Extract user info
            uid = decoded_token.get("uid")
            email = decoded_token.get("email")
            name = decoded_token.get("name")
            picture = decoded_token.get("picture")
            
            user = User(
                id=uid,
                login=email or uid,
                first_name=name.split(" ")[0] if name else None,
                last_name=" ".join(name.split(" ")[1:]) if name and " " in name else None,
                email=email,
                image_url=picture,
                authorities=["ROLE_USER"]  # Default role
            )
            
            return AuthenticationResult(
                success=True,
                user=user,
                method=AuthMethod.OAUTH2  # Firebase is essentially OAuth2/OIDC
            )
            
        except ValueError as e:
             # Invalid token
             logger.warning(f"Invalid Firebase token: {e}")
             raise AuthenticationError("Invalid authentication token")
        except Exception as e:
            logger.error(f"Firebase authentication failed: {e}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validate a Firebase ID token and return the user.
        
        Args:
            token: The Firebase ID token.
            
        Returns:
            User object if valid, None otherwise.
        """
        # Create dummy credentials wrapper to reuse authenticate logic
        from agentic_brain.auth.models import TokenCredentials
        try:
            result = await self.authenticate(TokenCredentials(token=token))
            if result.success and result.user:
                return result.user
        except AuthenticationError:
            pass
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            
        return None
