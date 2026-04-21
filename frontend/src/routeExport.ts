export type ExportableRouteItem = {
  id: string;
  name: string;
  address: string;
  raw: Record<string, unknown>;
};

export type ExportableCardData = {
  id: string;
  title: string;
  items: ExportableRouteItem[];
};

export type ExportableBestRoutes = Record<
  string,
  Record<string, Array<Record<string, unknown>>> | "No Solution"
>;

export type LatLngLiteral = {
  lat: number;
  lng: number;
};

export type RouteStop = {
  id: string;
  name: string;
  address: string;
  position: LatLngLiteral;
};

export type RouteSegment = {
  id: string;
  stops: RouteStop[];
  googleMapsUrl: string;
};

export type PreparedRoute = {
  id: string;
  title: string;
  color: string;
  stops: RouteStop[];
  exportSegments: RouteSegment[];
  skippedStops: ExportableRouteItem[];
};

const MAX_WAYPOINTS_PER_EXPORT_URL = 9;

export const ROUTE_COLORS = [
  "#d1495b",
  "#00798c",
  "#edae49",
  "#30638e",
  "#6a4c93",
  "#2a9d8f",
  "#ff7f11",
  "#3d348b",
];

function normalizeKey(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function findNumericValue(
  row: Record<string, unknown>,
  candidateKeys: string[]
): number | null {
  const normalizedCandidates = new Set(candidateKeys.map(normalizeKey));

  for (const [key, value] of Object.entries(row)) {
    if (!normalizedCandidates.has(normalizeKey(key))) {
      continue;
    }

    const numericValue =
      typeof value === "number"
        ? value
        : typeof value === "string"
          ? Number.parseFloat(value)
          : Number.NaN;

    if (Number.isFinite(numericValue)) {
      return numericValue;
    }
  }

  return null;
}

export function extractLatLng(raw: Record<string, unknown>): LatLngLiteral | null {
  const lat = findNumericValue(raw, [
    "lat",
    "latitude",
    "y",
    "start_lat",
    "startLatitude",
  ]);
  const lng = findNumericValue(raw, [
    "lng",
    "lon",
    "long",
    "longitude",
    "x",
    "start_lng",
    "startLongitude",
  ]);

  if (lat === null || lng === null) {
    return null;
  }

  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    return null;
  }

  return { lat, lng };
}

function buildStopsFromBackendRoute(
  routeId: string,
  backendStops: Array<Record<string, unknown>>
): RouteStop[] {
  return backendStops
    .map((backendStop, index) => {
      const position = extractLatLng(backendStop);
      if (!position) {
        return null;
      }

      const name =
        typeof backendStop.name === "string"
          ? backendStop.name
          : typeof backendStop.Name === "string"
            ? backendStop.Name
            : `Stop ${index + 1}`;
      const address =
        typeof backendStop.Location === "string"
          ? backendStop.Location
          : typeof backendStop.Address === "string"
            ? backendStop.Address
            : typeof backendStop.address === "string"
              ? backendStop.address
              : "";

      return {
        id: `${routeId}-${index + 1}`,
        name,
        address,
        position,
      };
    })
    .filter((stop): stop is RouteStop => stop !== null);
}

export function chunkStops(stops: RouteStop[], maxStopsPerChunk: number) {
  if (stops.length <= maxStopsPerChunk) {
    return [stops];
  }

  const chunks: RouteStop[][] = [];
  const step = maxStopsPerChunk - 1;

  for (let startIndex = 0; startIndex < stops.length - 1; startIndex += step) {
    const chunk = stops.slice(startIndex, startIndex + maxStopsPerChunk);
    if (chunk.length >= 2) {
      chunks.push(chunk);
    }
  }

  return chunks;
}

export function buildGoogleMapsDirectionsUrl(stops: RouteStop[]) {
  const origin = `${stops[0].position.lat},${stops[0].position.lng}`;
  const destination = `${stops[stops.length - 1].position.lat},${
    stops[stops.length - 1].position.lng
  }`;
  const waypoints = stops
    .slice(1, -1)
    .map((stop) => `${stop.position.lat},${stop.position.lng}`)
    .join("|");

  const params = new URLSearchParams({
    api: "1",
    origin,
    destination,
    travelmode: "driving",
    dir_action: "navigate",
  });

  if (waypoints) {
    params.set("waypoints", waypoints);
  }

  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

export function prepareRoutesForExport(
  routes: ExportableCardData[],
  bestRoutes: ExportableBestRoutes | null
): PreparedRoute[] {
  return routes.map((route, routeIndex) => {
    const clusterRoutes = bestRoutes?.[String(routeIndex)];
    const backendStops =
      clusterRoutes && clusterRoutes !== "No Solution"
        ? Object.entries(clusterRoutes)
            .sort(([routeIdA], [routeIdB]) => Number(routeIdA) - Number(routeIdB))
            .flatMap(([backendRouteId, backendRouteStops]) =>
              buildStopsFromBackendRoute(`${route.id}-${backendRouteId}`, backendRouteStops)
            )
        : [];

    const skippedStops: ExportableRouteItem[] = [];
    const fallbackStops: RouteStop[] = [];

    route.items.forEach((item) => {
      const position = extractLatLng(item.raw);
      if (!position) {
        skippedStops.push(item);
        return;
      }

      fallbackStops.push({
        id: item.id,
        name: item.name,
        address: item.address,
        position,
      });
    });

    const stops = backendStops.length >= 2 ? backendStops : fallbackStops;
    const exportChunks = chunkStops(stops, MAX_WAYPOINTS_PER_EXPORT_URL + 2);

    return {
      id: route.id,
      title: route.title,
      color: ROUTE_COLORS[routeIndex % ROUTE_COLORS.length],
      stops,
      exportSegments: exportChunks.map((chunk, index) => ({
        id: `${route.id}-segment-${index + 1}`,
        stops: chunk,
        googleMapsUrl: buildGoogleMapsDirectionsUrl(chunk),
      })),
      skippedStops,
    };
  });
}
