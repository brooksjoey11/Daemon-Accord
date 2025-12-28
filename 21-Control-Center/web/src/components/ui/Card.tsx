import { cn } from '@/lib/utils';

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-lg border bg-white p-6 shadow-sm', className)}>
      {children}
    </div>
  );
}
