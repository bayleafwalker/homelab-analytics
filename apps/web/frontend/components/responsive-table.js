import React from "react";

// <ResponsiveTable> — one table that reads at phone width.
//
// Wide screens get an ordinary <table> inside a focusable scroll region.
// Under 600px each row becomes a ledger slip: the primary column is the slip's
// title and every other cell is a "label ..... value" line, the label taken
// from the column header (data-label). The markup stays a real table, so
// screen readers keep row and column semantics at every width.
//
// columns: [{
//   key: string,
//   header: string,             column header and phone-width label
//   cell?: (row, index) => node defaults to row[key]
//   primary?: boolean           title of the phone-width slip (one column)
//   align?: "start" | "end"     "end" for figures
//   hideLabel?: boolean         no phone-width label (actions, status dots)
//   width?: string              optional CSS width hint for wide layout
// }]
export function ResponsiveTable({ columns, rows, rowKey, label, caption, empty = null, dense = false }) {
  if (!rows || rows.length === 0) return empty;
  const keyOf = typeof rowKey === "function" ? rowKey : (row, index) => (rowKey ? row[rowKey] : index);
  return (
    <div className="rtable" role="region" aria-label={label} tabIndex={0} data-dense={dense ? "true" : "false"}>
      <table>
        {caption ? <caption className="srOnly">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                data-align={column.align || "start"}
                style={column.width ? { width: column.width } : undefined}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={keyOf(row, index)}>
              {columns.map((column) => {
                const content = column.cell ? column.cell(row, index) : row[column.key];
                return (
                  <td
                    key={column.key}
                    data-label={column.hideLabel || column.primary ? undefined : column.header}
                    data-primary={column.primary ? "true" : undefined}
                    data-align={column.align || "start"}
                  >
                    <span className="rtableValue">{content ?? <span className="muted">—</span>}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
