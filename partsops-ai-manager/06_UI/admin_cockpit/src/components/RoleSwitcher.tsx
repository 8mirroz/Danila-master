import React from 'react';
import type { Role } from '../lib/rbac';
import { Icon } from './Primitives';

interface RoleSwitcherProps {
  currentRole: Role;
  onRoleChange: (role: Role) => void;
}

const roleIcons: Record<Role, string> = {
  ADMIN: 'user-shield',
  FINANCIAL_CONTROLLER: 'file-shield',
  OPERATOR: 'robot',
  VIEWER: 'magnifying-glass',
};

const roleLabels: Record<Role, string> = {
  ADMIN: 'Admin',
  FINANCIAL_CONTROLLER: 'Finance',
  OPERATOR: 'Operator',
  VIEWER: 'Viewer',
};

export const RoleSwitcher: React.FC<RoleSwitcherProps> = ({ currentRole, onRoleChange }) => {
  return (
    <div className="ds-segmented" role="group" aria-label="Переключение роли">
      {(Object.keys(roleIcons) as Role[]).map((role) => {
        const active = currentRole === role;
        return (
          <button
            key={role}
            type="button"
            onClick={() => onRoleChange(role)}
            className={`ds-segmented__item inline-flex items-center gap-1.5 ${
              active ? 'ds-segmented__item--active' : ''
            }`}
            title={roleLabels[role]}
            aria-pressed={active}
          >
            <Icon name={roleIcons[role]} size={12} />
            <span className="hidden sm:inline">{roleLabels[role]}</span>
          </button>
        );
      })}
    </div>
  );
};
