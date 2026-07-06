import React from 'react';
import { useAuthStore } from '../../store/authStore';
import { LogOut, Wifi, Menu } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface HeaderProps {
  onMenuClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
  const { logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="bg-white shadow-sm h-16 flex items-center justify-between px-4 sm:px-6 border-b border-gray-200">
      <div className="flex items-center">
        <button
          onClick={onMenuClick}
          className="mr-4 text-gray-500 hover:text-gray-900 md:hidden"
          aria-label="Open sidebar"
        >
          <Menu className="w-6 h-6" />
        </button>
        {/* Placeholder for dynamic breadcrumbs or page title later */}
        <h2 className="text-lg font-semibold text-gray-800">Administration Portal</h2>
      </div>

      <div className="flex items-center space-x-4 sm:space-x-6">
        {/* Backend Connection Indicator */}
        <div className="hidden sm:flex items-center text-xs font-medium text-gray-500">
          <Wifi className="w-3.5 h-3.5 mr-1.5 text-green-500" />
          API Connected
        </div>

        {/* Environment Indicator */}
        <div className="hidden sm:flex items-center text-xs font-medium px-2.5 py-1 rounded-full bg-primary-50 text-primary-700 border border-primary-200">
          <span className="w-1.5 h-1.5 mr-1.5 bg-primary-500 rounded-full"></span>
          Development
        </div>

        {/* User Actions */}
        <div className="flex items-center sm:border-l sm:border-gray-200 sm:pl-6">
          <button
            onClick={handleLogout}
            className="flex items-center text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors"
          >
            <LogOut className="w-4 h-4 sm:mr-2" />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        </div>
      </div>
    </header>
  );
};
