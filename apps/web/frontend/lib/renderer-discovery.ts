import {
  getPublicationContracts,
  getUiDescriptors,
} from "./backend";
import type { components } from "../generated/api";

export const WEB_RENDERER_NAME = "web";

export const WEB_RENDERER_SURFACES = {
  overview: "/",
  reports: "/reports",
  homelab: "/homelab",
} as const;

export type WebRendererSurface = keyof typeof WEB_RENDERER_SURFACES;
export type WebRendererMode = "detail" | "discovery";

type PublicationContractRecord =
  components["schemas"]["PublicationContractModel"];
type UiDescriptorRecord = components["schemas"]["UiDescriptorContractModel"];

export type WebRendererDescriptor = UiDescriptorRecord & {
  surface: WebRendererSurface;
  renderMode: WebRendererMode;
  anchor: string;
  href: string;
  navGroup: string;
  publications: PublicationContractRecord[];
};

export type WebRendererDiscovery = {
  overview: WebRendererDescriptor[];
  reports: WebRendererDescriptor[];
  homelab: WebRendererDescriptor[];
  publicationContracts: PublicationContractRecord[];
};

function normalizeSurface(value: string | undefined): WebRendererSurface | null {
  if (value === "overview" || value === "reports" || value === "homelab") {
    return value;
  }
  return null;
}

function surfaceForDescriptor(descriptor: UiDescriptorRecord): WebRendererSurface | null {
  const hintedSurface = normalizeSurface(descriptor.renderer_hints.web_surface);
  if (hintedSurface) {
    return hintedSurface;
  }
  if (descriptor.nav_path === "/") {
    return "overview";
  }
  if (descriptor.nav_path.startsWith("/reports")) {
    return "reports";
  }
  if (descriptor.nav_path.startsWith("/homelab")) {
    return "homelab";
  }
  return null;
}

function renderModeForDescriptor(descriptor: UiDescriptorRecord): WebRendererMode {
  return descriptor.renderer_hints.web_render_mode === "detail"
    ? "detail"
    : "discovery";
}

function anchorForDescriptor(descriptor: UiDescriptorRecord): string {
  return descriptor.renderer_hints.web_anchor || descriptor.key;
}

function hrefForDescriptor(
  surface: WebRendererSurface,
  anchor: string,
  renderMode: WebRendererMode
): string {
  const basePath = WEB_RENDERER_SURFACES[surface];
  const targetAnchor = renderMode === "detail" ? anchor : `discovery-${anchor}`;
  return basePath === "/" ? `/#${targetAnchor}` : `${basePath}#${targetAnchor}`;
}

function navGroupForDescriptor(
  descriptor: UiDescriptorRecord,
  surface: WebRendererSurface
): string {
  const explicitGroup = descriptor.renderer_hints.web_nav_group?.trim();
  if (explicitGroup) {
    return explicitGroup;
  }
  if (surface === "overview") {
    return "Overview";
  }
  if (surface === "homelab") {
    return "Operations";
  }
  return "Money";
}

export async function getWebRendererDiscovery(): Promise<WebRendererDiscovery> {
  const [publicationContracts, uiDescriptors] = await Promise.all([
    getPublicationContracts() as Promise<PublicationContractRecord[]>,
    getUiDescriptors() as Promise<UiDescriptorRecord[]>,
  ]);
  const publicationContractsByKey = new Map<string, PublicationContractRecord>(
    publicationContracts.map((contract) => [contract.publication_key, contract])
  );
  const descriptors = uiDescriptors
    .filter((descriptor) =>
      descriptor.supported_renderers.includes(WEB_RENDERER_NAME)
    )
    .map((descriptor) => {
      const surface = surfaceForDescriptor(descriptor);
      if (!surface) {
        return null;
      }
      const anchor = anchorForDescriptor(descriptor);
      const renderMode = renderModeForDescriptor(descriptor);
      return {
        ...descriptor,
        surface,
        renderMode,
        anchor,
        href: hrefForDescriptor(surface, anchor, renderMode),
        navGroup: navGroupForDescriptor(descriptor, surface),
        publications: descriptor.publication_keys
          .map((publicationKey) => publicationContractsByKey.get(publicationKey))
          .filter(
            (contract): contract is PublicationContractRecord => contract != null
          ),
      };
    })
    .filter(
      (descriptor): descriptor is WebRendererDescriptor => descriptor != null
    )
    .sort((left, right) => left.nav_label.localeCompare(right.nav_label));

  return {
    overview: descriptors.filter((descriptor) => descriptor.surface === "overview"),
    reports: descriptors.filter((descriptor) => descriptor.surface === "reports"),
    homelab: descriptors.filter((descriptor) => descriptor.surface === "homelab"),
    publicationContracts,
  };
}
