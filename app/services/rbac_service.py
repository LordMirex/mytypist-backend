"""
Role-Based Access Control (RBAC) Service
Implements granular permissions, role hierarchies, and resource-based access control
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Union
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import json

from config import settings
from database import Base
from app.services.audit_service import AuditService


# Association tables for many-to-many relationships
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('rbac_roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('rbac_permissions.id'), primary_key=True)
)

user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('rbac_roles.id'), primary_key=True)
)

role_hierarchy = Table(
    'role_hierarchy',
    Base.metadata,
    Column('parent_role_id', Integer, ForeignKey('rbac_roles.id'), primary_key=True),
    Column('child_role_id', Integer, ForeignKey('rbac_roles.id'), primary_key=True)
)


class ResourceType(str, Enum):
    """Types of resources that can be protected"""
    DOCUMENT = "document"
    TEMPLATE = "template"
    SIGNATURE = "signature"
    PAYMENT = "payment"
    USER = "user"
    ANALYTICS = "analytics"
    ADMIN = "admin"
    SYSTEM = "system"
    API = "api"


class Action(str, Enum):
    """Actions that can be performed on resources"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    MANAGE = "manage"
    SHARE = "share"
    EXPORT = "export"
    IMPORT = "import"
    APPROVE = "approve"
    REJECT = "reject"


class RBACRole(Base):
    """RBAC Role definition"""
    __tablename__ = "rbac_roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Role properties
    is_system_role = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=0)  # Higher priority overrides lower

    # Role constraints
    max_users = Column(Integer, nullable=True)  # Maximum users that can have this role
    expires_at = Column(DateTime, nullable=True)  # Role expiration

    # Metadata
    role_metadata = Column(Text, nullable=True)  # JSON metadata

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, nullable=True)

    # Relationships
    permissions = relationship("RBACPermission", secondary=role_permissions, back_populates="roles")
    parent_roles = relationship(
        "RBACRole",
        secondary=role_hierarchy,
        primaryjoin=id == role_hierarchy.c.child_role_id,
        secondaryjoin=id == role_hierarchy.c.parent_role_id,
        back_populates="child_roles"
    )
    child_roles = relationship(
        "RBACRole",
        secondary=role_hierarchy,
        primaryjoin=id == role_hierarchy.c.parent_role_id,
        secondaryjoin=id == role_hierarchy.c.child_role_id,
        back_populates="parent_roles"
    )


class RBACPermission(Base):
    """RBAC Permission definition"""
    __tablename__ = "rbac_permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Permission properties
    resource_type = Column(String(50), nullable=False)  # ResourceType enum
    action = Column(String(50), nullable=False)  # Action enum
    scope = Column(String(50), nullable=False, default="own")  # own, team, organization, global

    # Permission constraints
    conditions = Column(Text, nullable=True)  # JSON conditions for dynamic permissions
    is_system_permission = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    roles = relationship("RBACRole", secondary=role_permissions, back_populates="permissions")


class UserRoleAssignment(Base):
    """User role assignments with additional metadata"""
    __tablename__ = "user_role_assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey('rbac_roles.id'), nullable=False, index=True)

    # Assignment properties
    assigned_by = Column(Integer, nullable=True)  # User who assigned the role
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Role assignment expiration
    is_active = Column(Boolean, nullable=False, default=True)

    # Context
    assignment_reason = Column(String(255), nullable=True)
    assignment_metadata = Column(Text, nullable=True)  # JSON metadata


class ResourceAccess(Base):
    """Resource-specific access control"""
    __tablename__ = "resource_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(100), nullable=False, index=True)

    # Access properties
    permissions = Column(Text, nullable=False)  # JSON array of permissions
    granted_by = Column(Integer, nullable=True)  # User who granted access
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Context
    access_reason = Column(String(255), nullable=True)
    access_metadata = Column(Text, nullable=True)


class RBACService:
    """Role-Based Access Control Service"""

    @staticmethod
    def create_role(db: Session, name: str, display_name: str, description: str = None,
                   permissions: List[str] = None, created_by: int = None) -> RBACRole:
        """Create a new role"""
        role = RBACRole(
            name=name,
            display_name=display_name,
            description=description,
            created_by=created_by
        )

        db.add(role)
        db.flush()  # Get ID

        # Add permissions if provided
        if permissions:
            RBACService.assign_permissions_to_role(db, role.id, permissions)

        db.commit()
        db.refresh(role)

        # Log audit event
        AuditService.log_system_event(
            "ROLE_CREATED",
            {
                "role_id": role.id,
                "role_name": role.name,
                "created_by": created_by,
                "permissions_count": len(permissions) if permissions else 0
            }
        )

        return role

    @staticmethod
    def create_permission(db: Session, name: str, display_name: str, resource_type: str,
                         action: str, scope: str = "own", description: str = None,
                         conditions: Dict = None) -> RBACPermission:
        """Create a new permission"""
        permission = RBACPermission(
            name=name,
            display_name=display_name,
            description=description,
            resource_type=resource_type,
            action=action,
            scope=scope,
            conditions=json.dumps(conditions) if conditions else None
        )

        db.add(permission)
        db.commit()
        db.refresh(permission)

        # Log audit event
        AuditService.log_system_event(
            "PERMISSION_CREATED",
            {
                "permission_id": permission.id,
                "permission_name": permission.name,
                "resource_type": resource_type,
                "action": action,
                "scope": scope
            }
        )

        return permission

    @staticmethod
    def assign_role_to_user(db: Session, user_id: int, role_id: int, assigned_by: int = None,
                           expires_at: datetime = None, reason: str = None) -> bool:
        """Assign role to user"""
        # Check if assignment already exists
        existing = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id,
            UserRoleAssignment.is_active == True
        ).first()

        if existing:
            return False  # Already assigned

        # Check role constraints
        role = db.query(RBACRole).filter(RBACRole.id == role_id).first()
        if not role or not role.is_active:
            return False

        if role.max_users:
            current_assignments = db.query(UserRoleAssignment).filter(
                UserRoleAssignment.role_id == role_id,
                UserRoleAssignment.is_active == True
            ).count()
            if current_assignments >= role.max_users:
                return False

        # Create assignment
        assignment = UserRoleAssignment(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            expires_at=expires_at,
            assignment_reason=reason
        )

        db.add(assignment)
        db.commit()

        # Log audit event
        AuditService.log_system_event(
            "ROLE_ASSIGNED",
            {
                "user_id": user_id,
                "role_id": role_id,
                "role_name": role.name,
                "assigned_by": assigned_by,
                "expires_at": expires_at.isoformat() if expires_at else None
            }
        )

        return True

    @staticmethod
    def revoke_role_from_user(db: Session, user_id: int, role_id: int, revoked_by: int = None) -> bool:
        """Revoke role from user"""
        assignment = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id,
            UserRoleAssignment.is_active == True
        ).first()

        if not assignment:
            return False

        assignment.is_active = False
        db.commit()

        # Log audit event
        role = db.query(RBACRole).filter(RBACRole.id == role_id).first()
        AuditService.log_system_event(
            "ROLE_REVOKED",
            {
                "user_id": user_id,
                "role_id": role_id,
                "role_name": role.name if role else "Unknown",
                "revoked_by": revoked_by
            }
        )

        return True

    @staticmethod
    def assign_permissions_to_role(db: Session, role_id: int, permission_names: List[str]) -> bool:
        """Assign permissions to role"""
        role = db.query(RBACRole).filter(RBACRole.id == role_id).first()
        if not role:
            return False

        permissions = db.query(RBACPermission).filter(
            RBACPermission.name.in_(permission_names),
            RBACPermission.is_active == True
        ).all()

        # Clear existing permissions
        role.permissions.clear()

        # Add new permissions
        for permission in permissions:
            role.permissions.append(permission)

        db.commit()

        # Log audit event
        AuditService.log_system_event(
            "ROLE_PERMISSIONS_UPDATED",
            {
                "role_id": role_id,
                "role_name": role.name,
                "permissions": permission_names,
                "permissions_count": len(permissions)
            }
        )

        return True

    @staticmethod
    def check_permission(db: Session, user_id: int, resource_type: str, action: str,
                        resource_id: str = None, context: Dict = None) -> bool:
        """Check if user has permission for action on resource"""

        # Get user's active roles
        user_roles_query = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.is_active == True
        )

        # Check for expired assignments
        current_time = datetime.utcnow()
        user_roles_query = user_roles_query.filter(
            (UserRoleAssignment.expires_at.is_(None)) |
            (UserRoleAssignment.expires_at > current_time)
        )

        user_role_assignments = user_roles_query.all()

        if not user_role_assignments:
            return False

        # Get all role IDs including inherited roles
        all_role_ids = set()
        for assignment in user_role_assignments:
            all_role_ids.add(assignment.role_id)
            # Add parent roles (role hierarchy)
            parent_roles = RBACService._get_parent_roles(db, assignment.role_id)
            all_role_ids.update(parent_roles)

        # Check permissions for all roles
        permissions = db.query(RBACPermission).join(
            role_permissions, RBACPermission.id == role_permissions.c.permission_id
        ).filter(
            role_permissions.c.role_id.in_(all_role_ids),
            RBACPermission.resource_type == resource_type,
            RBACPermission.action == action,
            RBACPermission.is_active == True
        ).all()

        if not permissions:
            return False

        # Check scope and conditions
        for permission in permissions:
            if RBACService._check_permission_scope(permission, user_id, resource_id, context):
                if RBACService._check_permission_conditions(permission, context):
                    return True

        # Check resource-specific access
        if resource_id:
            resource_access = db.query(ResourceAccess).filter(
                ResourceAccess.user_id == user_id,
                ResourceAccess.resource_type == resource_type,
                ResourceAccess.resource_id == resource_id,
                ResourceAccess.is_active == True
            ).filter(
                (ResourceAccess.expires_at.is_(None)) |
                (ResourceAccess.expires_at > current_time)
            ).first()

            if resource_access:
                permissions_list = json.loads(resource_access.permissions)
                return action in permissions_list

        return False

    @staticmethod
    def get_user_permissions(db: Session, user_id: int) -> List[Dict[str, any]]:
        """Get all permissions for user"""
        # Get user's active roles
        user_role_assignments = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.is_active == True
        ).filter(
            (UserRoleAssignment.expires_at.is_(None)) |
            (UserRoleAssignment.expires_at > datetime.utcnow())
        ).all()

        if not user_role_assignments:
            return []

        # Get all role IDs including inherited roles
        all_role_ids = set()
        for assignment in user_role_assignments:
            all_role_ids.add(assignment.role_id)
            parent_roles = RBACService._get_parent_roles(db, assignment.role_id)
            all_role_ids.update(parent_roles)

        # Get permissions
        permissions = db.query(RBACPermission).join(
            role_permissions, RBACPermission.id == role_permissions.c.permission_id
        ).filter(
            role_permissions.c.role_id.in_(all_role_ids),
            RBACPermission.is_active == True
        ).all()

        return [
            {
                "id": perm.id,
                "name": perm.name,
                "display_name": perm.display_name,
                "resource_type": perm.resource_type,
                "action": perm.action,
                "scope": perm.scope,
                "conditions": json.loads(perm.conditions) if perm.conditions else None
            }
            for perm in permissions
        ]

    @staticmethod
    def get_user_roles(db: Session, user_id: int) -> List[Dict[str, any]]:
        """Get all roles for user"""
        assignments = db.query(UserRoleAssignment).join(
            RBACRole, UserRoleAssignment.role_id == RBACRole.id
        ).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.is_active == True,
            RBACRole.is_active == True
        ).filter(
            (UserRoleAssignment.expires_at.is_(None)) |
            (UserRoleAssignment.expires_at > datetime.utcnow())
        ).all()

        return [
            {
                "role_id": assignment.role_id,
                "role_name": assignment.role.name,
                "display_name": assignment.role.display_name,
                "assigned_at": assignment.assigned_at,
                "expires_at": assignment.expires_at,
                "assignment_reason": assignment.assignment_reason
            }
            for assignment in assignments
        ]

    @staticmethod
    def grant_resource_access(db: Session, user_id: int, resource_type: str, resource_id: str,
                             permissions: List[str], granted_by: int = None, expires_at: datetime = None,
                             reason: str = None) -> bool:
        """Grant specific access to a resource"""
        # Check if access already exists
        existing = db.query(ResourceAccess).filter(
            ResourceAccess.user_id == user_id,
            ResourceAccess.resource_type == resource_type,
            ResourceAccess.resource_id == resource_id,
            ResourceAccess.is_active == True
        ).first()

        if existing:
            # Update existing access
            existing.permissions = json.dumps(permissions)
            existing.expires_at = expires_at
            existing.access_reason = reason
        else:
            # Create new access
            access = ResourceAccess(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permissions=json.dumps(permissions),
                granted_by=granted_by,
                expires_at=expires_at,
                access_reason=reason
            )
            db.add(access)

        db.commit()

        # Log audit event
        AuditService.log_system_event(
            "RESOURCE_ACCESS_GRANTED",
            {
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "permissions": permissions,
                "granted_by": granted_by,
                "expires_at": expires_at.isoformat() if expires_at else None
            }
        )

        return True

    @staticmethod
    def revoke_resource_access(db: Session, user_id: int, resource_type: str, resource_id: str) -> bool:
        """Revoke access to a specific resource"""
        access = db.query(ResourceAccess).filter(
            ResourceAccess.user_id == user_id,
            ResourceAccess.resource_type == resource_type,
            ResourceAccess.resource_id == resource_id,
            ResourceAccess.is_active == True
        ).first()

        if not access:
            return False

        access.is_active = False
        db.commit()

        # Log audit event
        AuditService.log_system_event(
            "RESOURCE_ACCESS_REVOKED",
            {
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )

        return True

    @staticmethod
    def initialize_default_roles_and_permissions(db: Session):
        """Initialize default roles and permissions"""

        # Default permissions
        default_permissions = [
            # Document permissions
            ("document.create.own", "Create Own Documents", "document", "create", "own"),
            ("document.read.own", "Read Own Documents", "document", "read", "own"),
            ("document.update.own", "Update Own Documents", "document", "update", "own"),
            ("document.delete.own", "Delete Own Documents", "document", "delete", "own"),
            ("document.share.own", "Share Own Documents", "document", "share", "own"),
            ("document.read.all", "Read All Documents", "document", "read", "global"),
            ("document.manage.all", "Manage All Documents", "document", "manage", "global"),

            # Template permissions
            ("template.create.own", "Create Own Templates", "template", "create", "own"),
            ("template.read.own", "Read Own Templates", "template", "read", "own"),
            ("template.update.own", "Update Own Templates", "template", "update", "own"),
            ("template.delete.own", "Delete Own Templates", "template", "delete", "own"),
            ("template.read.public", "Read Public Templates", "template", "read", "organization"),
            ("template.manage.all", "Manage All Templates", "template", "manage", "global"),

            # User permissions
            ("user.read.own", "Read Own Profile", "user", "read", "own"),
            ("user.update.own", "Update Own Profile", "user", "update", "own"),
            ("user.read.all", "Read All Users", "user", "read", "global"),
            ("user.manage.all", "Manage All Users", "user", "manage", "global"),

            # Admin permissions
            ("admin.dashboard", "Access Admin Dashboard", "admin", "read", "global"),
            ("admin.users", "Manage Users", "admin", "manage", "global"),
            ("admin.roles", "Manage Roles", "admin", "manage", "global"),
            ("admin.permissions", "Manage Permissions", "admin", "manage", "global"),
            ("admin.system", "Manage System", "system", "manage", "global"),

            # API permissions
            ("api.access", "API Access", "api", "read", "own"),
            ("api.admin", "Admin API Access", "api", "manage", "global"),
        ]

        # Create permissions
        created_permissions = {}
        for perm_name, display_name, resource_type, action, scope in default_permissions:
            existing = db.query(RBACPermission).filter(RBACPermission.name == perm_name).first()
            if not existing:
                permission = RBACService.create_permission(
                    db, perm_name, display_name, resource_type, action, scope
                )
                created_permissions[perm_name] = permission

        # Default roles
        default_roles = [
            ("guest", "Guest", "Limited read-only access", [
                "document.read.own", "template.read.public"
            ]),
            ("user", "Standard User", "Standard user permissions", [
                "document.create.own", "document.read.own", "document.update.own",
                "document.delete.own", "document.share.own",
                "template.create.own", "template.read.own", "template.update.own",
                "template.delete.own", "template.read.public",
                "user.read.own", "user.update.own",
                "api.access"
            ]),
            ("premium_user", "Premium User", "Enhanced user permissions", [
                "document.create.own", "document.read.own", "document.update.own",
                "document.delete.own", "document.share.own",
                "template.create.own", "template.read.own", "template.update.own",
                "template.delete.own", "template.read.public",
                "user.read.own", "user.update.own",
                "api.access"
            ]),
            ("moderator", "Moderator", "Content moderation permissions", [
                "document.create.own", "document.read.own", "document.update.own",
                "document.delete.own", "document.share.own", "document.read.all",
                "template.create.own", "template.read.own", "template.update.own",
                "template.delete.own", "template.read.public",
                "user.read.own", "user.update.own", "user.read.all",
                "api.access"
            ]),
            ("admin", "Administrator", "Full system access", [
                "document.create.own", "document.read.own", "document.update.own",
                "document.delete.own", "document.share.own", "document.read.all", "document.manage.all",
                "template.create.own", "template.read.own", "template.update.own",
                "template.delete.own", "template.read.public", "template.manage.all",
                "user.read.own", "user.update.own", "user.read.all", "user.manage.all",
                "admin.dashboard", "admin.users", "admin.roles", "admin.permissions", "admin.system",
                "api.access", "api.admin"
            ])
        ]

        # Create roles
        for role_name, display_name, description, permissions in default_roles:
            existing = db.query(RBACRole).filter(RBACRole.name == role_name).first()
            if not existing:
                RBACService.create_role(
                    db, role_name, display_name, description, permissions
                )

        db.commit()

    @staticmethod
    def _get_parent_roles(db: Session, role_id: int) -> Set[int]:
        """Get all parent roles in hierarchy"""
        parent_roles = set()

        # Direct parents
        direct_parents = db.query(role_hierarchy).filter(
            role_hierarchy.c.child_role_id == role_id
        ).all()

        for parent in direct_parents:
            parent_id = parent.parent_role_id
            parent_roles.add(parent_id)
            # Recursive call for grandparents
            grandparents = RBACService._get_parent_roles(db, parent_id)
            parent_roles.update(grandparents)

        return parent_roles

    @staticmethod
    def _check_permission_scope(permission: RBACPermission, user_id: int, resource_id: str = None,
                               context: Dict = None) -> bool:
        """Check if permission scope allows access"""
        if permission.scope == "global":
            return True
        elif permission.scope == "own":
            if not context:
                return True  # Allow if no context to check ownership
            return context.get("owner_id") == user_id
        elif permission.scope == "organization":
            # In a multi-tenant system, check organization membership
            return True  # Simplified for now
        elif permission.scope == "team":
            # Check team membership
            return True  # Simplified for now

        return False

    @staticmethod
    def _check_permission_conditions(permission: RBACPermission, context: Dict = None) -> bool:
        """Check if permission conditions are met"""
        if not permission.conditions:
            return True

        if not context:
            return True  # Allow if no context to check conditions

        try:
            conditions = json.loads(permission.conditions)
            # Implement condition checking logic here
            # For example: time-based conditions, IP restrictions, etc.
            return True  # Simplified for now
        except json.JSONDecodeError:
            return True  # Invalid conditions, allow access

    @staticmethod
    def cleanup_expired_assignments(db: Session):
        """Cleanup expired role assignments and resource access"""
        current_time = datetime.utcnow()

        # Expire role assignments
        expired_assignments = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.expires_at < current_time,
            UserRoleAssignment.is_active == True
        ).update({UserRoleAssignment.is_active: False})

        # Expire resource access
        expired_access = db.query(ResourceAccess).filter(
            ResourceAccess.expires_at < current_time,
            ResourceAccess.is_active == True
        ).update({ResourceAccess.is_active: False})

        db.commit()

        return {
            "expired_role_assignments": expired_assignments,
            "expired_resource_access": expired_access
        }
