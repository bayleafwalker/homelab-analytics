import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getMonthlyCashflow } from "@/lib/backend";

export default async function ReportsPage() {
  const user = await getCurrentUser();
  const rows = await getMonthlyCashflow();

  return (
    <AppShell
      currentPath="/reports"
      user={user}
      title="Published Reports"
      eyebrow="Published Access"
      lede="This shell is intentionally narrow. It renders published reporting models without embedding source-specific logic."
    >
      <section className="stack">
        <article className="panel section">
          <div className="sectionHeader">
            <div>
              <div className="eyebrow">Built-In Mart</div>
              <h2>Monthly cashflow</h2>
            </div>
          </div>
          {rows.length === 0 ? (
            <div className="empty">No published rows yet.</div>
          ) : (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Booking month</th>
                    <th>Income</th>
                    <th>Expense</th>
                    <th>Net</th>
                    <th>Transactions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.booking_month}>
                      <td>{row.booking_month}</td>
                      <td>{row.income}</td>
                      <td>{row.expense}</td>
                      <td>{row.net}</td>
                      <td>{row.transaction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </AppShell>
  );
}
