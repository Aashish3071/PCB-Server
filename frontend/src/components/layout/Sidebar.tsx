import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Cpu, Activity, AlertTriangle, Users, HeartPulse, Settings } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, setIsOpen }) => {
  const { user } = useAuthStore();

  const navItems = [
    { name: 'Dashboard', to: '/', icon: LayoutDashboard, exact: true, adminOnly: false },
    { name: 'Devices', to: '/devices', icon: Cpu, exact: false, adminOnly: false },
    { name: 'Customers', to: '/customers', icon: Users, exact: false, adminOnly: true },
    { name: 'Alerts', to: '/alerts', icon: AlertTriangle, exact: false, adminOnly: false },
    { name: 'Telemetry', to: '/telemetry', icon: Activity, exact: false, adminOnly: false },
    { name: 'System Health', to: '/health', icon: HeartPulse, exact: false, adminOnly: true },
    { name: 'Settings', to: '/settings', icon: Settings, exact: false, adminOnly: true },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-gray-900/50 z-40 md:hidden transition-opacity"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar container */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 text-white flex flex-col h-full border-r border-gray-800
        transition-transform duration-300 ease-in-out md:relative md:translate-x-0
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="h-16 flex items-center px-6 border-b border-gray-800">
          <h1 className="text-xl font-bold tracking-wider text-primary-400">IoT DMS</h1>
        </div>
      <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
        {navItems.map((item) => {
          if (item.adminOnly && user?.role !== 'admin') {
            return null;
          }

          const Icon = item.icon;
          return (
            <NavLink
              key={item.name}
              to={item.to}
              end={item.exact}
              onClick={() => setIsOpen(false)}
              className={({ isActive }) =>
                `flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-900 text-primary-100'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <Icon className="mr-3 h-5 w-5 flex-shrink-0" />
              {item.name}
            </NavLink>
          );
        })}
      </nav>
      
      <div className="p-4 border-t border-gray-800">
        <div className="flex items-center">
          <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm font-medium">
            {user?.email?.charAt(0).toUpperCase()}
          </div>
          <div className="ml-3 overflow-hidden">
            <p className="text-sm font-medium truncate">{user?.email}</p>
            <p className="text-xs text-gray-400 capitalize">{user?.role}</p>
          </div>
        </div>
      </div>
    </div>
    </>
  );
};
