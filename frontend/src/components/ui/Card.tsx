import React from 'react';
import { Link } from 'react-router-dom';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  to?: string;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick, to }) => {
  const baseClasses = 'bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden';
  const interactiveClasses = (onClick || to) ? 'hover:shadow-md hover:border-primary-300 transition-all cursor-pointer' : '';
  const combinedClasses = `${baseClasses} ${interactiveClasses} ${className}`;

  if (to) {
    return (
      <Link to={to} className={`block ${combinedClasses}`}>
        {children}
      </Link>
    );
  }

  return (
    <div className={combinedClasses} onClick={onClick}>
      {children}
    </div>
  );
};
