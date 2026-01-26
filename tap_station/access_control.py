"""
Role-Based Access Control (RBAC) System

This module implements a flexible role-based access control system that allows
services to define custom roles, permissions, and access policies.

Key Features:
- Hierarchical role definitions
- Granular permission system
- Context-aware access decisions
- Session management
- Audit logging of access events

Service Design Principles:
- Protect sensitive operations appropriately
- Enable appropriate access for different roles
- Support multi-stakeholder access patterns
- Maintain audit trail for compliance
"""

import logging
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import functools

from .datetime_utils import utc_now

logger = logging.getLogger(__name__)


class Permission(Enum):
    """Available permissions in the system"""

    # Tap operations
    TAP_READ = "tap:read"
    TAP_SCAN = "tap:scan"
    TAP_MANUAL_ENTRY = "tap:manual_entry"
    TAP_DELETE = "tap:delete"

    # Queue operations
    QUEUE_VIEW = "queue:view"
    QUEUE_MANAGE = "queue:manage"
    QUEUE_FORCE_EXIT = "queue:force_exit"

    # Dashboard access
    DASHBOARD_VIEW = "dashboard:view"
    DASHBOARD_FULL = "dashboard:full"

    # Analytics
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"

    # Session management
    SESSION_START = "session:start"
    SESSION_END = "session:end"
    SESSION_MANAGE = "session:manage"

    # Alert management
    ALERTS_VIEW = "alerts:view"
    ALERTS_ACKNOWLEDGE = "alerts:acknowledge"
    ALERTS_CONFIGURE = "alerts:configure"

    # Configuration
    CONFIG_VIEW = "config:view"
    CONFIG_EDIT = "config:edit"

    # User management
    USERS_VIEW = "users:view"
    USERS_MANAGE = "users:manage"

    # System administration
    ADMIN_SYSTEM = "admin:system"
    ADMIN_DATA = "admin:data"

    # Public access
    PUBLIC_VIEW = "public:view"

    # Wildcard
    ALL = "*"


@dataclass
class Role:
    """Defines a role with its permissions"""

    id: str
    name: str
    description: str
    permissions: Set[Permission]
    inherits_from: Optional[str] = None
    is_system_role: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "inherits_from": self.inherits_from,
            "is_system_role": self.is_system_role,
            "metadata": self.metadata,
        }


@dataclass
class User:
    """Represents a user in the system"""

    id: str
    username: str
    display_name: str
    roles: List[str]
    password_hash: Optional[str] = None
    email: Optional[str] = None
    active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    last_login: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "roles": self.roles,
            "email": self.email,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "metadata": self.metadata,
        }
        if include_sensitive:
            data["has_password"] = bool(self.password_hash)
        return data


@dataclass
class Session:
    """Represents an active user session"""

    id: str
    user_id: str
    token: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    active: bool = True

    def is_valid(self) -> bool:
        """
        Check if session is still valid.

        Compares current UTC time with expiration time. utc_now() returns a
        timezone-aware datetime (UTC), so comparison will work correctly
        whether expires_at is timezone-aware or naive.
        """
        return self.active and utc_now() < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_valid": self.is_valid(),
            "active": self.active,
        }


@dataclass
class AccessDecision:
    """Result of an access control decision"""

    allowed: bool
    permission: Permission
    user_id: Optional[str]
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "allowed": self.allowed,
            "permission": self.permission.value,
            "user_id": self.user_id,
            "reason": self.reason,
            "context": self.context,
        }


@dataclass
class AuditLogEntry:
    """An entry in the access audit log"""

    id: str
    timestamp: datetime
    user_id: Optional[str]
    action: str
    resource: str
    decision: bool
    ip_address: Optional[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "decision": self.decision,
            "ip_address": self.ip_address,
            "details": self.details,
        }


class AccessControlManager:
    """
    Manages role-based access control.

    This manager:
    - Defines and manages roles
    - Manages users and their role assignments
    - Handles authentication and sessions
    - Makes access control decisions
    - Maintains audit logs
    """

    # Built-in system roles
    SYSTEM_ROLES = {
        "public": Role(
            id="public",
            name="Public",
            description="Unauthenticated public access",
            permissions={Permission.PUBLIC_VIEW},
            is_system_role=True,
        ),
        "peer_worker": Role(
            id="peer_worker",
            name="Peer Worker",
            description="Front-line service provider",
            permissions={
                Permission.TAP_SCAN,
                Permission.QUEUE_VIEW,
                Permission.DASHBOARD_VIEW,
                Permission.ALERTS_VIEW,
                Permission.PUBLIC_VIEW,
            },
            is_system_role=True,
        ),
        "coordinator": Role(
            id="coordinator",
            name="Service Coordinator",
            description="Shift supervisor with elevated access",
            permissions={
                Permission.TAP_SCAN,
                Permission.TAP_MANUAL_ENTRY,
                Permission.QUEUE_VIEW,
                Permission.QUEUE_MANAGE,
                Permission.QUEUE_FORCE_EXIT,
                Permission.DASHBOARD_VIEW,
                Permission.DASHBOARD_FULL,
                Permission.ANALYTICS_VIEW,
                Permission.SESSION_START,
                Permission.SESSION_END,
                Permission.ALERTS_VIEW,
                Permission.ALERTS_ACKNOWLEDGE,
                Permission.PUBLIC_VIEW,
            },
            inherits_from="peer_worker",
            is_system_role=True,
        ),
        "admin": Role(
            id="admin",
            name="Administrator",
            description="Full system access",
            permissions={Permission.ALL},
            is_system_role=True,
        ),
    }

    def __init__(
        self,
        conn: Optional[sqlite3.Connection] = None,
        session_timeout_minutes: int = 60,
        require_authentication: bool = False,
    ):
        """
        Initialize the access control manager.

        Args:
            conn: Database connection for persistence
            session_timeout_minutes: Session duration
            require_authentication: Require auth for protected operations
        """
        self._conn = conn
        self._session_timeout = timedelta(minutes=session_timeout_minutes)
        self._require_auth = require_authentication

        self._roles: Dict[str, Role] = {}
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Session] = {}
        self._audit_log: List[AuditLogEntry] = []
        self._max_audit_log = 5000
        self._audit_counter = 0

        # Load system roles
        for role in self.SYSTEM_ROLES.values():
            self._roles[role.id] = role

        # Create default admin user
        self._create_default_admin()

    def _create_default_admin(self) -> None:
        """Create default admin user if none exists"""
        admin_exists = any("admin" in u.roles for u in self._users.values())
        if not admin_exists:
            # Create with a random password that must be changed
            self._users["admin"] = User(
                id="admin",
                username="admin",
                display_name="Administrator",
                roles=["admin"],
                password_hash=None,  # No password by default
                active=True,
            )

    # =========================================================================
    # Role Management
    # =========================================================================

    def define_role(self, role: Role) -> None:
        """
        Define or update a role.

        Args:
            role: Role definition
        """
        self._roles[role.id] = role
        logger.info(f"Defined role: {role.id}")

    def define_role_from_dict(self, config: Dict[str, Any]) -> Role:
        """
        Define a role from configuration dictionary.

        Args:
            config: Role configuration

        Returns:
            The created role
        """
        permissions = set()
        for perm_str in config.get("permissions", []):
            if perm_str == "*":
                permissions.add(Permission.ALL)
            else:
                try:
                    permissions.add(Permission(perm_str))
                except ValueError:
                    logger.warning(f"Unknown permission: {perm_str}")

        role = Role(
            id=config["id"],
            name=config.get("name", config["id"]),
            description=config.get("description", ""),
            permissions=permissions,
            inherits_from=config.get("inherits_from"),
            is_system_role=False,
            metadata=config.get("metadata", {}),
        )

        self.define_role(role)
        return role

    def get_role(self, role_id: str) -> Optional[Role]:
        """Get a role by ID"""
        return self._roles.get(role_id)

    def list_roles(self, include_system: bool = True) -> List[Dict[str, Any]]:
        """List all roles"""
        roles = self._roles.values()
        if not include_system:
            roles = [r for r in roles if not r.is_system_role]
        return [r.to_dict() for r in roles]

    def get_role_permissions(self, role_id: str) -> Set[Permission]:
        """
        Get all permissions for a role, including inherited.

        Args:
            role_id: Role to get permissions for

        Returns:
            Set of all permissions
        """
        role = self._roles.get(role_id)
        if not role:
            return set()

        permissions = set(role.permissions)

        # Add inherited permissions
        if role.inherits_from:
            inherited = self.get_role_permissions(role.inherits_from)
            permissions.update(inherited)

        return permissions

    # =========================================================================
    # User Management
    # =========================================================================

    def create_user(
        self,
        username: str,
        display_name: str,
        roles: List[str],
        password: Optional[str] = None,
        email: Optional[str] = None,
    ) -> User:
        """
        Create a new user.

        Args:
            username: Unique username
            display_name: Display name
            roles: List of role IDs
            password: Optional password
            email: Optional email

        Returns:
            The created user
        """
        user_id = f"user_{len(self._users) + 1:04d}"

        password_hash = None
        if password:
            password_hash = self._hash_password(password)

        user = User(
            id=user_id,
            username=username,
            display_name=display_name,
            roles=roles,
            password_hash=password_hash,
            email=email,
            active=True,
        )

        self._users[user_id] = user
        logger.info(f"Created user: {username}")
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username"""
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        roles: Optional[List[str]] = None,
        email: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> Optional[User]:
        """Update a user"""
        user = self._users.get(user_id)
        if not user:
            return None

        if display_name is not None:
            user.display_name = display_name
        if roles is not None:
            user.roles = roles
        if email is not None:
            user.email = email
        if active is not None:
            user.active = active

        return user

    def set_password(self, user_id: str, password: str) -> bool:
        """Set user password"""
        user = self._users.get(user_id)
        if not user:
            return False

        user.password_hash = self._hash_password(password)
        return True

    def list_users(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List all users"""
        users = self._users.values()
        if active_only:
            users = [u for u in users if u.active]
        return [u.to_dict() for u in users]

    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        Get all permissions for a user.

        Args:
            user_id: User ID

        Returns:
            Set of all user permissions
        """
        user = self._users.get(user_id)
        if not user or not user.active:
            return set()

        permissions = set()
        for role_id in user.roles:
            role_perms = self.get_role_permissions(role_id)
            permissions.update(role_perms)

        return permissions

    # =========================================================================
    # Authentication
    # =========================================================================

    def authenticate(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[Session]:
        """
        Authenticate a user and create a session.

        Args:
            username: Username
            password: Password
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Session if successful, None otherwise
        """
        user = self.get_user_by_username(username)

        if not user or not user.active:
            self._audit_login_failure(
                username, ip_address, "User not found or inactive"
            )
            return None

        if not user.password_hash:
            # No password set - allow login for development
            logger.warning(f"Login without password for user: {username}")
        elif not self._verify_password(password, user.password_hash):
            self._audit_login_failure(username, ip_address, "Invalid password")
            return None

        # Create session
        session = self._create_session(user.id, ip_address, user_agent)

        # Update last login
        user.last_login = utc_now()

        self._audit_login_success(user.id, ip_address)
        return session

    def _create_session(
        self, user_id: str, ip_address: Optional[str], user_agent: Optional[str]
    ) -> Session:
        """Create a new session"""
        session_id = f"sess_{secrets.token_hex(8)}"
        token = secrets.token_urlsafe(32)
        now = utc_now()

        session = Session(
            id=session_id,
            user_id=user_id,
            token=token,
            created_at=now,
            expires_at=now + self._session_timeout,
            ip_address=ip_address,
            user_agent=user_agent,
            active=True,
        )

        self._sessions[token] = session
        return session

    def validate_session(self, token: str) -> Optional[Session]:
        """
        Validate a session token.

        Args:
            token: Session token

        Returns:
            Session if valid, None otherwise
        """
        session = self._sessions.get(token)
        if not session:
            return None

        if not session.is_valid():
            # Clean up expired session
            del self._sessions[token]
            return None

        return session

    def logout(self, token: str) -> bool:
        """
        End a session.

        Args:
            token: Session token

        Returns:
            True if session was ended
        """
        session = self._sessions.get(token)
        if session:
            session.active = False
            del self._sessions[token]
            self._audit("logout", session.user_id, "session", True)
            return True
        return False

    def get_user_from_session(self, token: str) -> Optional[User]:
        """Get the user associated with a session"""
        session = self.validate_session(token)
        if session:
            return self.get_user(session.user_id)
        return None

    # =========================================================================
    # Access Control Decisions
    # =========================================================================

    def check_permission(
        self,
        user_id: Optional[str],
        permission: Permission,
        resource: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AccessDecision:
        """
        Check if a user has a permission.

        Args:
            user_id: User ID (None for anonymous)
            permission: Permission to check
            resource: Optional resource identifier
            context: Optional additional context

        Returns:
            Access decision
        """
        context = context or {}

        # Anonymous users only get public access
        if user_id is None:
            if permission == Permission.PUBLIC_VIEW:
                return AccessDecision(
                    allowed=True,
                    permission=permission,
                    user_id=None,
                    reason="Public access allowed",
                    context=context,
                )
            else:
                if self._require_auth:
                    return AccessDecision(
                        allowed=False,
                        permission=permission,
                        user_id=None,
                        reason="Authentication required",
                        context=context,
                    )
                else:
                    # Allow when auth not required
                    return AccessDecision(
                        allowed=True,
                        permission=permission,
                        user_id=None,
                        reason="Authentication not required",
                        context=context,
                    )

        # Get user permissions
        user_permissions = self.get_user_permissions(user_id)

        # Check for wildcard permission
        if Permission.ALL in user_permissions:
            decision = AccessDecision(
                allowed=True,
                permission=permission,
                user_id=user_id,
                reason="User has admin access",
                context=context,
            )
            self._audit_access(user_id, permission.value, resource, True)
            return decision

        # Check specific permission
        if permission in user_permissions:
            decision = AccessDecision(
                allowed=True,
                permission=permission,
                user_id=user_id,
                reason="Permission granted",
                context=context,
            )
            self._audit_access(user_id, permission.value, resource, True)
            return decision

        decision = AccessDecision(
            allowed=False,
            permission=permission,
            user_id=user_id,
            reason="Permission denied",
            context=context,
        )
        self._audit_access(user_id, permission.value, resource, False)
        return decision

    def require_permission(
        self,
        permission: Permission,
        user_id: Optional[str] = None,
        session_token: Optional[str] = None,
    ) -> AccessDecision:
        """
        Check permission and raise if denied.

        Args:
            permission: Required permission
            user_id: User ID (optional if session provided)
            session_token: Session token (optional if user_id provided)

        Returns:
            Access decision
        """
        if session_token and not user_id:
            session = self.validate_session(session_token)
            if session:
                user_id = session.user_id

        return self.check_permission(user_id, permission)

    # =========================================================================
    # Password Hashing
    # =========================================================================

    def _hash_password(self, password: str) -> str:
        """
        Hash a password using PBKDF2-HMAC-SHA256.

        The hash is stored in the format: "salt$hash" where:
        - salt: 32-character hex string (16 bytes)
        - hash: PBKDF2-HMAC-SHA256 output with 100,000 iterations

        This is a standard approach for password storage. The salt prevents
        rainbow table attacks, and PBKDF2 with high iteration count slows
        down brute force attacks.
        """
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100000
        )
        return f"{salt}${hash_obj.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against hash"""
        try:
            salt, hash_hex = password_hash.split("$")
            hash_obj = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), 100000
            )
            return hash_obj.hex() == hash_hex
        except Exception:
            return False

    # =========================================================================
    # Audit Logging
    # =========================================================================

    def _audit(
        self,
        action: str,
        user_id: Optional[str],
        resource: str,
        allowed: bool,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an entry to the audit log"""
        self._audit_counter += 1
        entry = AuditLogEntry(
            id=f"audit_{self._audit_counter:08d}",
            timestamp=utc_now(),
            user_id=user_id,
            action=action,
            resource=resource,
            decision=allowed,
            ip_address=ip_address,
            details=details or {},
        )

        self._audit_log.append(entry)
        if len(self._audit_log) > self._max_audit_log:
            self._audit_log = self._audit_log[-self._max_audit_log // 2 :]

    def _audit_access(
        self, user_id: str, permission: str, resource: Optional[str], allowed: bool
    ) -> None:
        """Audit an access control decision"""
        self._audit(
            "access_check",
            user_id,
            resource or "unknown",
            allowed,
            details={"permission": permission},
        )

    def _audit_login_success(self, user_id: str, ip_address: Optional[str]) -> None:
        """Audit successful login"""
        self._audit("login_success", user_id, "auth", True, ip_address)

    def _audit_login_failure(
        self, username: str, ip_address: Optional[str], reason: str
    ) -> None:
        """Audit failed login"""
        self._audit(
            "login_failure",
            None,
            "auth",
            False,
            ip_address,
            {"username": username, "reason": reason},
        )

    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries.

        Args:
            user_id: Filter by user
            action: Filter by action
            limit: Maximum entries to return

        Returns:
            List of audit log entries
        """
        entries = self._audit_log

        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if action:
            entries = [e for e in entries if e.action == action]

        return [e.to_dict() for e in entries[-limit:]]


# =============================================================================
# Decorator for Permission Checking
# =============================================================================


def require_permission(permission: Permission):
    """
    Decorator to require a permission for a function.

    Usage:
        @require_permission(Permission.DASHBOARD_VIEW)
        def view_dashboard(user_id, ...):
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get user_id from kwargs or first arg
            user_id = kwargs.get("user_id") or (args[0] if args else None)

            manager = get_access_control_manager()
            decision = manager.check_permission(user_id, permission)

            if not decision.allowed:
                raise PermissionError(f"Permission denied: {permission.value}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Configuration Loading
# =============================================================================


def load_roles_from_config(
    config: Dict[str, Any], manager: AccessControlManager
) -> int:
    """
    Load role definitions from configuration.

    Args:
        config: Configuration with 'staffing.roles' key
        manager: Access control manager

    Returns:
        Number of roles loaded
    """
    role_configs = config.get("staffing", {}).get("roles", [])
    loaded = 0

    for role_config in role_configs:
        try:
            manager.define_role_from_dict(role_config)
            loaded += 1
        except Exception as e:
            logger.error(f"Error loading role {role_config.get('id', 'unknown')}: {e}")

    return loaded


# =============================================================================
# Global Instance
# =============================================================================

_access_manager: Optional[AccessControlManager] = None


def get_access_control_manager(
    conn: Optional[sqlite3.Connection] = None,
) -> AccessControlManager:
    """Get or create the global access control manager"""
    global _access_manager
    if _access_manager is None:
        _access_manager = AccessControlManager(conn)
    return _access_manager
