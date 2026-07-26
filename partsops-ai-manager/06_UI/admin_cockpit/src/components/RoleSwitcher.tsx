import React from 'react';
import type { Role } from '../lib/rbac';

interface RoleSwitcherProps {
  currentRole: Role;
  onRoleChange: (role: Role) => void;
}

const roleIcons: Record<Role, React.ReactNode> = {
  ADMIN: <i className="fas fa-shield w-4 h-4 text-center"></i>,
  FINANCIAL_CONTROLLER: <i className="fas fa-dollar-sign w-4 h-4 text-center"></i>,
  OPERATOR: <i className="fas fa-user w-4 h-4 text-center"></i>,
  VIEWER: <i className="fas fa-eye w-4 h-4 text-center"></i>,
};

const roleLabels: Record<Role, string> = {
  ADMIN: 'Admin',
  FINANCIAL_CONTROLLER: 'Finance',
  OPERATOR: 'Operator',
  VIEWER: 'Viewer',
};

export const RoleSwitcher: React.FC<RoleSwitcherProps> = ({ currentRole, onRoleChange }) => {
  return (
    <div className="flex items-center gap-2 bg-[#1C1C1E]/50 border border-white/5 p-1 rounded-lg">
      {(Object.keys(roleIcons) as Role[]).map((role) => (
        <button
          key={role}
          onClick={() => onRoleChange(role)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
            currentRole === role
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.2)]'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5 border border-transparent'
          }`}
          title={roleLabels[role]}
        >
          {roleIcons[role]}
          <span className="hidden sm:inline">{roleLabels[role]}</span>
        </button>
      ))}
    </div>
  );
};
