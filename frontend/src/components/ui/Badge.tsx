import React from 'react';

type BadgeVariant = 'success' | 'warning' | 'error' | 'neutral' | 'primary';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'neutral', dot = false }) => {
  const variantStyles = {
    success: 'bg-green-50 text-green-700 border-green-200',
    warning: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    error: 'bg-red-50 text-red-700 border-red-200',
    neutral: 'bg-gray-100 text-gray-700 border-gray-200',
    primary: 'bg-primary-50 text-primary-700 border-primary-200',
  };

  const dotColors = {
    success: 'bg-green-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-500',
    neutral: 'bg-gray-500',
    primary: 'bg-primary-500',
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variantStyles[variant]}`}>
      {dot && (
        <span className={`w-1.5 h-1.5 mr-1.5 rounded-full ${dotColors[variant]}`} />
      )}
      {children}
    </span>
  );
};
