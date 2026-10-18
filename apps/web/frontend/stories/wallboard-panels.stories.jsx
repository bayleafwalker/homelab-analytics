import React from "react";
import { expect, within } from "@storybook/test";

import { DevicePanel, EventFeed, PowerChart, ServiceTile, ServicesPanel } from "../components/wallboard-panels";
import { devicesData, eventsData, powerAmbiguous, powerData, servicesData } from "./wallboard-fixtures";

// Panels render inside .wall so they pick up the wallboard tokens and type.
function WallFrame({ children, compact = false }) {
  return (
    <main aria-label="Wallboard panel">
      <div className="wall" data-compact={compact} style={{ minHeight: "auto" }}>
        <div className="wallGrid" style={{ gridTemplateAreas: "none", gridTemplateColumns: "minmax(0, 1fr)" }}>
          {children}
        </div>
      </div>
    </main>
  );
}

const meta = {
  title: "Wallboard/Panels",
  parameters: { layout: "fullscreen" },
};

export default meta;

export const ServiceTileUp = {
  name: "ServiceTile",
  render: () => (
    <WallFrame>
      <section className="wallPanel" aria-label="Service">
        <ul className="wallServices">
          <ServiceTile service={servicesData.services[1]} />
          <ServiceTile service={servicesData.services[0]} />
          <ServiceTile service={servicesData.services[3]} />
        </ul>
      </section>
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("cpu 6.4% · mem 1.2 GB (7d avg)")).toBeInTheDocument();
    await expect(canvas.getByText("Degraded")).toBeInTheDocument();
    // A stale "up" is not shown as up.
    await expect(canvas.getAllByText("cpu/mem unknown").length).toBe(2);
    await expect(canvas.getByText("Unknown")).toBeInTheDocument();
  },
};

export const Services = {
  render: () => (
    <WallFrame>
      <ServicesPanel data={servicesData} />
    </WallFrame>
  ),
};

export const ServicesNotConnected = {
  render: () => (
    <WallFrame>
      <ServicesPanel data={null} />
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByText("Not connected")).toBeInTheDocument();
  },
};

export const Devices = {
  name: "DevicePanel",
  render: () => (
    <WallFrame>
      <DevicePanel data={devicesData} />
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Living room")).toBeInTheDocument();
    await expect(canvas.getByText("temp unknown")).toBeInTheDocument();
  },
};

export const DevicesCompact = {
  name: "DevicePanel compact",
  render: () => (
    <WallFrame compact>
      <DevicePanel data={devicesData} />
    </WallFrame>
  ),
};

export const DevicesEmpty = {
  name: "DevicePanel empty",
  render: () => (
    <WallFrame>
      <DevicePanel data={{ available: true, rooms: [] }} />
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByText("No room sensors")).toBeInTheDocument();
  },
};

export const Events = {
  name: "EventFeed",
  render: () => (
    <WallFrame>
      <EventFeed data={eventsData} />
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    const items = within(canvasElement).getAllByRole("listitem");
    await expect(items[0]).toHaveTextContent("Alert: Budget (breach)");
  },
};

export const EventsQuiet = {
  name: "EventFeed quiet, alerts not wired",
  render: () => (
    <WallFrame>
      <EventFeed data={{ ...eventsData, events: [], sources: { runs: true, proposals: true, alerts: false } }} />
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("Quiet")).toBeInTheDocument();
    await expect(canvas.getByText("(no alerts)")).toBeInTheDocument();
  },
};

export const Power = {
  name: "PowerChart",
  render: () => (
    <WallFrame>
      <PowerChart data={powerData} />
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    const chart = within(canvasElement).getByRole("img");
    await expect(chart.getAttribute("aria-label")).toContain("2 hours unknown");
    await expect(canvasElement.querySelectorAll("rect").length).toBe(24);
  },
};

export const PowerAmbiguous = {
  name: "PowerChart ambiguous meter",
  render: () => (
    <WallFrame>
      <PowerChart data={powerAmbiguous} />
    </WallFrame>
  ),
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByText("Choose a meter")).toBeInTheDocument();
  },
};
