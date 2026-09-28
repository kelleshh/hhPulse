import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "quiet" | "danger";
  size?: "small" | "medium";
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "medium",
  icon,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button className={`button button--${variant} button--${size} ${className}`.trim()} {...props}>
      {icon ? <span className="button__icon" aria-hidden="true">{icon}</span> : null}
      <span>{children}</span>
    </button>
  );
}
