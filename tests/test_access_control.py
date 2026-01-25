"""
Tests for the Role-Based Access Control System

Tests cover:
- Role management
- User management
- Authentication
- Permission checking
- Audit logging
"""

import pytest
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tap_station.access_control import (
    AccessControlManager,
    Role,
    Session,
    Permission,
    get_access_control_manager,
    load_roles_from_config,
)


@pytest.fixture
def manager():
    """Create an access control manager"""
    return AccessControlManager(require_authentication=False)


@pytest.fixture
def strict_manager():
    """Create a manager that requires authentication"""
    return AccessControlManager(require_authentication=True)


class TestRole:
    """Tests for Role dataclass"""

    def test_creation(self):
        """Test role creation"""
        role = Role(
            id="test_role",
            name="Test Role",
            description="A test role",
            permissions={Permission.DASHBOARD_VIEW, Permission.QUEUE_VIEW}
        )
        assert role.id == "test_role"
        assert Permission.DASHBOARD_VIEW in role.permissions

    def test_to_dict(self):
        """Test serialization"""
        role = Role(
            id="test",
            name="Test",
            description="Test role",
            permissions={Permission.TAP_READ}
        )
        result = role.to_dict()

        assert result["id"] == "test"
        assert "tap:read" in result["permissions"]


class TestAccessControlManager:
    """Tests for AccessControlManager"""

    def test_initialization(self, manager):
        """Test manager initialization with system roles"""
        assert "public" in [r["id"] for r in manager.list_roles()]
        assert "admin" in [r["id"] for r in manager.list_roles()]
        assert "coordinator" in [r["id"] for r in manager.list_roles()]

    def test_define_role(self, manager):
        """Test defining a custom role"""
        role = Role(
            id="custom_role",
            name="Custom Role",
            description="Test",
            permissions={Permission.DASHBOARD_VIEW}
        )
        manager.define_role(role)

        retrieved = manager.get_role("custom_role")
        assert retrieved is not None
        assert retrieved.name == "Custom Role"

    def test_define_role_from_dict(self, manager):
        """Test defining role from config dict"""
        config = {
            "id": "dict_role",
            "name": "Dict Role",
            "description": "From dict",
            "permissions": ["dashboard:view", "queue:view"]
        }
        role = manager.define_role_from_dict(config)

        assert role.id == "dict_role"
        assert Permission.DASHBOARD_VIEW in role.permissions

    def test_get_role_permissions_with_inheritance(self, manager):
        """Test permission inheritance"""
        # Coordinator inherits from peer_worker
        perms = manager.get_role_permissions("coordinator")

        # Should have coordinator's own permissions
        assert Permission.SESSION_START in perms
        # Should inherit from peer_worker
        assert Permission.TAP_SCAN in perms

    def test_create_user(self, manager):
        """Test user creation"""
        user = manager.create_user(
            username="testuser",
            display_name="Test User",
            roles=["peer_worker"],
            password="testpass123",
            email="test@example.com"
        )

        assert user.username == "testuser"
        assert "peer_worker" in user.roles
        assert user.password_hash is not None

    def test_get_user(self, manager):
        """Test getting user by ID"""
        user = manager.create_user(
            username="gettest",
            display_name="Get Test",
            roles=["public"]
        )

        retrieved = manager.get_user(user.id)
        assert retrieved is not None
        assert retrieved.username == "gettest"

    def test_get_user_by_username(self, manager):
        """Test getting user by username"""
        manager.create_user(
            username="findme",
            display_name="Find Me",
            roles=["public"]
        )

        user = manager.get_user_by_username("findme")
        assert user is not None
        assert user.display_name == "Find Me"

    def test_update_user(self, manager):
        """Test updating user"""
        user = manager.create_user(
            username="updateme",
            display_name="Update Me",
            roles=["public"]
        )

        manager.update_user(
            user.id,
            display_name="Updated Name",
            roles=["peer_worker"]
        )

        updated = manager.get_user(user.id)
        assert updated.display_name == "Updated Name"
        assert "peer_worker" in updated.roles

    def test_set_password(self, manager):
        """Test password setting"""
        user = manager.create_user(
            username="passtest",
            display_name="Pass Test",
            roles=["public"]
        )

        result = manager.set_password(user.id, "newpassword123")
        assert result is True

        updated = manager.get_user(user.id)
        assert updated.password_hash is not None

    def test_list_users(self, manager):
        """Test listing users"""
        manager.create_user("user1", "User 1", ["public"])
        manager.create_user("user2", "User 2", ["public"])

        users = manager.list_users()
        assert len(users) >= 2  # At least our 2 + default admin

    def test_get_user_permissions(self, manager):
        """Test getting all user permissions"""
        user = manager.create_user(
            username="permtest",
            display_name="Perm Test",
            roles=["coordinator"]
        )

        perms = manager.get_user_permissions(user.id)

        # Coordinator has these permissions
        assert Permission.SESSION_START in perms
        assert Permission.ALERTS_ACKNOWLEDGE in perms


class TestAuthentication:
    """Tests for authentication functionality"""

    def test_authenticate_success(self, manager):
        """Test successful authentication"""
        manager.create_user(
            username="authtest",
            display_name="Auth Test",
            roles=["peer_worker"],
            password="correctpassword"
        )

        session = manager.authenticate(
            username="authtest",
            password="correctpassword"
        )

        assert session is not None
        assert session.token is not None
        assert session.is_valid()

    def test_authenticate_wrong_password(self, manager):
        """Test authentication with wrong password"""
        manager.create_user(
            username="wrongpass",
            display_name="Wrong Pass",
            roles=["peer_worker"],
            password="correctpassword"
        )

        session = manager.authenticate(
            username="wrongpass",
            password="wrongpassword"
        )

        assert session is None

    def test_authenticate_nonexistent_user(self, manager):
        """Test authentication with non-existent user"""
        session = manager.authenticate(
            username="doesnotexist",
            password="anypassword"
        )
        assert session is None

    def test_validate_session(self, manager):
        """Test session validation"""
        manager.create_user(
            username="sessiontest",
            display_name="Session Test",
            roles=["peer_worker"],
            password="password123"
        )

        session = manager.authenticate("sessiontest", "password123")
        validated = manager.validate_session(session.token)

        assert validated is not None
        assert validated.id == session.id

    def test_validate_invalid_session(self, manager):
        """Test validating invalid session token"""
        result = manager.validate_session("invalid_token")
        assert result is None

    def test_logout(self, manager):
        """Test logout"""
        manager.create_user(
            username="logouttest",
            display_name="Logout Test",
            roles=["peer_worker"],
            password="password123"
        )

        session = manager.authenticate("logouttest", "password123")
        result = manager.logout(session.token)
        assert result is True

        # Session should no longer be valid
        validated = manager.validate_session(session.token)
        assert validated is None

    def test_get_user_from_session(self, manager):
        """Test getting user from session"""
        user = manager.create_user(
            username="fromsession",
            display_name="From Session",
            roles=["peer_worker"],
            password="password123"
        )

        session = manager.authenticate("fromsession", "password123")
        retrieved_user = manager.get_user_from_session(session.token)

        assert retrieved_user is not None
        assert retrieved_user.id == user.id


class TestPermissionChecking:
    """Tests for permission checking"""

    def test_check_permission_allowed(self, manager):
        """Test permission check when allowed"""
        user = manager.create_user(
            username="permcheck",
            display_name="Perm Check",
            roles=["coordinator"]
        )

        decision = manager.check_permission(
            user.id,
            Permission.SESSION_START
        )

        assert decision.allowed is True

    def test_check_permission_denied(self, manager):
        """Test permission check when denied"""
        user = manager.create_user(
            username="denied",
            display_name="Denied",
            roles=["public"]
        )

        decision = manager.check_permission(
            user.id,
            Permission.ADMIN_SYSTEM
        )

        assert decision.allowed is False

    def test_check_permission_admin_wildcard(self, manager):
        """Test admin has all permissions via wildcard"""
        user = manager.create_user(
            username="adminuser",
            display_name="Admin User",
            roles=["admin"]
        )

        # Admin should have any permission
        decision = manager.check_permission(
            user.id,
            Permission.ADMIN_SYSTEM
        )
        assert decision.allowed is True

        decision2 = manager.check_permission(
            user.id,
            Permission.CONFIG_EDIT
        )
        assert decision2.allowed is True

    def test_check_permission_anonymous_strict(self, strict_manager):
        """Test anonymous access with strict auth"""
        decision = strict_manager.check_permission(
            None,
            Permission.DASHBOARD_VIEW
        )
        assert decision.allowed is False
        assert "Authentication required" in decision.reason

    def test_check_permission_anonymous_public(self, manager):
        """Test anonymous can access public"""
        decision = manager.check_permission(
            None,
            Permission.PUBLIC_VIEW
        )
        assert decision.allowed is True

    def test_require_permission(self, manager):
        """Test require_permission method"""
        user = manager.create_user(
            username="require",
            display_name="Require",
            roles=["coordinator"]
        )

        decision = manager.require_permission(
            Permission.SESSION_START,
            user_id=user.id
        )
        assert decision.allowed is True


class TestAuditLogging:
    """Tests for audit logging"""

    def test_audit_log_access(self, manager):
        """Test access decisions are logged"""
        user = manager.create_user(
            username="audituser",
            display_name="Audit User",
            roles=["peer_worker"]
        )

        manager.check_permission(user.id, Permission.DASHBOARD_VIEW)

        log = manager.get_audit_log(user_id=user.id)
        assert len(log) > 0

    def test_audit_log_login(self, manager):
        """Test login attempts are logged"""
        manager.create_user(
            username="loginaudit",
            display_name="Login Audit",
            roles=["peer_worker"],
            password="password123"
        )

        manager.authenticate("loginaudit", "password123")
        manager.authenticate("loginaudit", "wrongpassword")

        log = manager.get_audit_log(action="login_success")
        assert any(e["user_id"] is not None for e in log)

        fail_log = manager.get_audit_log(action="login_failure")
        assert len(fail_log) > 0

    def test_audit_log_limit(self, manager):
        """Test audit log respects limit"""
        log = manager.get_audit_log(limit=5)
        assert len(log) <= 5


class TestSession:
    """Tests for Session dataclass"""

    def test_is_valid_active(self):
        """Test valid active session"""
        now = datetime.now(timezone.utc)
        session = Session(
            id="test",
            user_id="user1",
            token="token123",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            active=True
        )
        assert session.is_valid() is True

    def test_is_valid_expired(self):
        """Test expired session"""
        now = datetime.now(timezone.utc)
        session = Session(
            id="test",
            user_id="user1",
            token="token123",
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
            active=True
        )
        assert session.is_valid() is False

    def test_is_valid_inactive(self):
        """Test inactive session"""
        now = datetime.now(timezone.utc)
        session = Session(
            id="test",
            user_id="user1",
            token="token123",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            active=False
        )
        assert session.is_valid() is False


class TestConfigurationLoading:
    """Tests for configuration loading"""

    def test_load_roles_from_config(self, manager):
        """Test loading roles from config"""
        config = {
            "staffing": {
                "roles": [
                    {
                        "id": "config_role",
                        "name": "Config Role",
                        "permissions": ["dashboard:view", "queue:view"]
                    }
                ]
            }
        }

        loaded = load_roles_from_config(config, manager)
        assert loaded == 1

        role = manager.get_role("config_role")
        assert role is not None


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_access_control_manager(self):
        """Test global manager retrieval"""
        module = sys.modules["tap_station.access_control"]
        module._access_manager = None

        manager = get_access_control_manager()
        assert manager is not None

        manager2 = get_access_control_manager()
        assert manager is manager2
