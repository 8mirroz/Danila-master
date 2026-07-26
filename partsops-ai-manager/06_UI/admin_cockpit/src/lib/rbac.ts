export type Role = 'ADMIN' | 'OPERATOR' | 'FINANCIAL_CONTROLLER' | 'VIEWER';

export interface RBACMatrix {
  canApprove: boolean;
  canReject: boolean;
  canEdit: boolean;
  canViewCosts: boolean;
  canAccessSettings: boolean;
  canTriggerSync: boolean;
}

const rolePermissions: Record<Role, RBACMatrix> = {
  ADMIN: {
    canApprove: true,
    canReject: true,
    canEdit: true,
    canViewCosts: true,
    canAccessSettings: true,
    canTriggerSync: true,
  },
  FINANCIAL_CONTROLLER: {
    canApprove: true,
    canReject: true,
    canEdit: false,
    canViewCosts: true,
    canAccessSettings: false,
    canTriggerSync: false,
  },
  OPERATOR: {
    canApprove: false,
    canReject: false,
    canEdit: true,
    canViewCosts: false,
    canAccessSettings: false,
    canTriggerSync: true,
  },
  VIEWER: {
    canApprove: false,
    canReject: false,
    canEdit: false,
    canViewCosts: false,
    canAccessSettings: false,
    canTriggerSync: false,
  },
};

export const getPermissions = (role: Role): RBACMatrix => rolePermissions[role];
