import { cn } from "@/lib/utils";
import { LogoMark } from "./LogoMark";

interface LogoFullProps {
  size?: number;
  variant?: "flat" | "neon" | "holographic";
  simplified?: boolean;
  className?: string;
}

export function LogoFull({ size = 32, variant = "holographic", simplified, className }: LogoFullProps) {
  const isGlowing = variant === "neon" || variant === "holographic";
  
  return (
    <div 
      className={cn(
        "flex items-center gap-2",
        isGlowing && "neon",
        className
      )}
    >
      <LogoMark size={size} variant={variant} simplified={simplified} />
      <span 
        className={cn(
          "font-heading font-bold tracking-tight",
          isGlowing ? "bg-gradient-to-r from-[#00f0ff] via-[#7c3aed] to-[#f0abfc] bg-clip-text text-transparent" : "text-foreground"
        )}
        style={{ fontSize: size * 0.75 }}
      >
        AN2B
      </span>
    </div>
  );
}
