import React from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  badge?: {
    text: string;
    variant: 'success' | 'warning' | 'info' | 'neutral';
  };
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  badge,
}) => {
  const badgeClasses = {
    success: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
    info: 'bg-sky-500/10 text-sky-400 border border-sky-500/20',
    neutral: 'bg-slate-700/50 text-slate-300 border border-slate-600/30',
  };

  return (
    <div className="bg-[#111827] border border-slate-800/80 rounded-xl p-5 shadow-lg hover:border-slate-700 transition-all">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-400 tracking-wide uppercase text-[11px]">
          {title}
        </span>
        <div className="p-2.5 rounded-lg bg-slate-800/80 text-cyan-400 border border-slate-700/50">
          {icon}
        </div>
      </div>
      <div className="flex items-baseline justify-between mt-1">
        <div className="text-2xl font-bold tracking-tight text-white font-mono">
          {value}
        </div>
        {badge && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeClasses[badge.variant]}`}>
            {badge.text}
          </span>
        )}
      </div>
      {subtitle && (
        <p className="mt-2 text-xs text-slate-400 flex items-center gap-1.5">
          {subtitle}
        </p>
      )}
    </div>
  );
};

