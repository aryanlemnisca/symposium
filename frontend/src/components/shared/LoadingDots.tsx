interface Props {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  centered?: boolean;
  color?: string;
}

export default function LoadingDots({ size = 'md', label, centered = false, color }: Props) {
  const dotSize = size === 'sm' ? 'w-1.5 h-1.5' : size === 'lg' ? 'w-3 h-3' : 'w-2 h-2';
  const gap = size === 'sm' ? 'gap-1' : size === 'lg' ? 'gap-2' : 'gap-1.5';
  const dotColor = color || 'var(--color-teal)';

  const dots = (
    <div className={`flex items-center ${gap}`}>
      <div className={`${dotSize} rounded-full animate-bounce`} style={{ background: dotColor, animationDelay: '0ms' }} />
      <div className={`${dotSize} rounded-full animate-bounce`} style={{ background: dotColor, animationDelay: '150ms' }} />
      <div className={`${dotSize} rounded-full animate-bounce`} style={{ background: dotColor, animationDelay: '300ms' }} />
    </div>
  );

  const content = label ? (
    <div className="flex items-center gap-2">
      {dots}
      <span className="text-xs" style={{ color: 'var(--color-text-dim)' }}>{label}</span>
    </div>
  ) : dots;

  if (centered) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-navy)' }}>
        {content}
      </div>
    );
  }

  return content;
}
