import React from "react";

// <NumMono>{value}</NumMono>
//
// Tabular-numerals span. Use anywhere a money value, ratio, or count
// renders so columns of numbers stay aligned.
export function NumMono({ children, style, className = "" }) {
  return (
    <span className={`numMono ${className}`.trim()} style={style}>
      {children}
    </span>
  );
}
