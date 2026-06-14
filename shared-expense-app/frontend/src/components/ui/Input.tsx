import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', ...props }, ref) => {
    return (
      <div className="flex flex-col space-y-1 w-full">
        {label && (
          <label className="text-xs font-semibold text-slate-600 tracking-wide">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`w-full px-3 py-2 bg-white border rounded-lg text-sm text-slate-900 transition-all focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent ${
            error ? 'border-red-300 focus:ring-red-500' : 'border-slate-200'
          } ${className}`}
          {...props}
        />
        {error && (
          <span className="text-[11px] text-red-500 font-medium">
            {error}
          </span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
