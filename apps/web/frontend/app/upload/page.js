import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { getCurrentUser, getSourceAssets } from "@/lib/backend";

function errorCopy(error) {
  switch (error) {
    case "account-upload-failed":
      return "Account-transaction upload failed.";
    case "subscription-upload-failed":
      return "Subscription upload failed.";
    case "contract-price-upload-failed":
      return "Contract-price upload failed.";
    case "configured-upload-failed":
      return "Configured upload failed.";
    default:
      return "";
  }
}

function UploadCard({ eyebrow, title, action, description, children }) {
  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h2>{title}</h2>
        </div>
      </div>
      <div className="muted">{description}</div>
      <form className="formGrid threeCol" action={action} method="post" encType="multipart/form-data">
        <div className="field spanTwo">
          <label htmlFor={`${action}-source-name`}>Source name</label>
          <input
            id={`${action}-source-name`}
            name="source_name"
            type="text"
            defaultValue="manual-upload"
            required
          />
        </div>
        <div className="field">
          <label htmlFor={`${action}-file`}>CSV file</label>
          <input id={`${action}-file`} name="file" type="file" accept=".csv,text/csv" required />
        </div>
        {children}
        <button className="primaryButton inlineButton" type="submit">
          Upload file
        </button>
      </form>
    </article>
  );
}

export default async function UploadPage({ searchParams }) {
  const user = await getCurrentUser();
  if (user.role === "reader") {
    redirect("/");
  }
  const sourceAssets = await getSourceAssets();
  const activeSourceAssets = sourceAssets.filter((record) => record.enabled);
  const error = errorCopy(searchParams?.error);

  return (
    <AppShell
      currentPath="/upload"
      user={user}
      title="Manual Uploads"
      eyebrow="Operator Access"
      lede="Browser uploads stay API-backed. Built-in datasets and configured source assets land through the same ingest contracts the worker and CLI already use."
    >
      <section className="stack">
        {error ? <div className="errorBanner">{error}</div> : null}

        <section className="cards uploadCards">
          <UploadCard
            eyebrow="Built-In Domain"
            title="Account transactions"
            action="/upload/account-transactions"
            description="Direct browser upload into the household account-transactions landing contract."
          />
          <UploadCard
            eyebrow="Built-In Domain"
            title="Subscriptions"
            action="/upload/subscriptions"
            description="Upload a subscription export and let the API validate and promote it."
          />
          <UploadCard
            eyebrow="Built-In Domain"
            title="Contract prices"
            action="/upload/contract-prices"
            description="Upload current contract-price snapshots through the built-in price contract."
          />
        </section>

        {activeSourceAssets.length === 0 ? (
          <div className="empty">
            No active source assets are available yet. Register a source asset under Control before
            using configured browser uploads.
          </div>
        ) : (
          <UploadCard
            eyebrow="Configured Asset"
            title="Configured CSV upload"
            action="/upload/configured-csv"
            description="Use a saved source asset binding so the browser upload lands with the same contract and mapping versions as your scheduled or file-drop ingestion path."
          >
            <div className="field">
              <label htmlFor="configured-source-asset">Source asset</label>
              <select id="configured-source-asset" name="source_asset_id" required defaultValue="">
                <option value="" disabled>
                  Select source asset
                </option>
                {activeSourceAssets.map((record) => (
                  <option key={record.source_asset_id} value={record.source_asset_id}>
                    {record.source_asset_id}
                  </option>
                ))}
              </select>
            </div>
          </UploadCard>
        )}
      </section>
    </AppShell>
  );
}
