import { useEffect, useMemo, useRef, useState } from "react";
import type { BackendBestRoutes, CardData, RouteItem } from "./DragDropDemo";

type GoogleMapInstance = {
  fitBounds: (bounds: GoogleLatLngBounds) => void;
  setZoom: (zoom: number) => void;
};

type GoogleLatLngBounds = {
  extend: (point: LatLngLiteral) => void;
};

type GooglePolyline = {
  addListener: (eventName: string, handler: () => void) => void;
  setMap: (map: GoogleMapInstance | null) => void;
  setOptions: (options: {
    strokeOpacity?: number;
    strokeWeight?: number;
    zIndex?: number;
  }) => void;
};

type GoogleMarker = {
  addListener: (eventName: string, handler: () => void) => void;
  setMap: (map: GoogleMapInstance | null) => void;
  setOpacity: (opacity: number) => void;
};

type GoogleDirectionsResult = {
  routes: Array<{
    overview_path?: LatLngLiteral[];
  }>;
};

type GoogleDirectionsService = {
  route: (
    request: {
      origin: LatLngLiteral;
      destination: LatLngLiteral;
      waypoints: Array<{ location: LatLngLiteral; stopover: boolean }>;
      optimizeWaypoints: boolean;
      travelMode: string;
    },
    callback: (result: GoogleDirectionsResult | null, status: string) => void
  ) => void;
};

type GoogleMapsApi = {
  maps: {
    Map: new (
      element: HTMLDivElement,
      options: {
        center: LatLngLiteral;
        zoom: number;
        mapTypeControl: boolean;
        streetViewControl: boolean;
        fullscreenControl: boolean;
      }
    ) => GoogleMapInstance;
    LatLngBounds: new () => GoogleLatLngBounds;
    DirectionsService: new () => GoogleDirectionsService;
    Polyline: new (options: {
      map: GoogleMapInstance;
      path: LatLngLiteral[];
      strokeColor: string;
      strokeOpacity: number;
      strokeWeight: number;
      clickable: boolean;
    }) => GooglePolyline;
    Marker: new (options: {
      map: GoogleMapInstance;
      position: LatLngLiteral;
      title: string;
      label: {
        text: string;
        color: string;
        fontSize: string;
        fontWeight: string;
      };
      icon: {
        path: number;
        fillColor: string;
        fillOpacity: number;
        strokeColor: string;
        strokeWeight: number;
        scale: number;
      };
    }) => GoogleMarker;
    SymbolPath: {
      CIRCLE: number;
    };
  };
};

declare global {
  interface Window {
    google?: GoogleMapsApi;
  }
}

type Props = {
  routes: CardData[];
  bestRoutes: BackendBestRoutes | null;
};

type LatLngLiteral = {
  lat: number;
  lng: number;
};

type RouteSegment = {
  id: string;
  stops: RouteStop[];
  googleMapsUrl: string;
};

type RouteStop = {
  id: string;
  name: string;
  address: string;
  position: LatLngLiteral;
};

type PreparedRoute = {
  id: string;
  title: string;
  color: string;
  stops: RouteStop[];
  exportSegments: RouteSegment[];
  skippedStops: RouteItem[];
};

type RouteOverlay = {
  routeId: string;
  polylines: GooglePolyline[];
  markers: GoogleMarker[];
};

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const MAX_STOPS_PER_DIRECTIONS_REQUEST = 25;
const MAX_WAYPOINTS_PER_EXPORT_URL = 9;
const ROUTE_COLORS = [
  "#d1495b",
  "#00798c",
  "#edae49",
  "#30638e",
  "#6a4c93",
  "#2a9d8f",
  "#ff7f11",
  "#3d348b",
];

let googleMapsApiPromise: Promise<GoogleMapsApi> | null = null;

function loadGoogleMapsApi(apiKey: string): Promise<GoogleMapsApi> {
  if (window.google?.maps) {
    return Promise.resolve(window.google);
  }

  if (googleMapsApiPromise) {
    return googleMapsApiPromise;
  }

  googleMapsApiPromise = new Promise((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[data-google-maps-loader="true"]'
    );

    if (existingScript) {
      existingScript.addEventListener("load", () => {
        if (window.google?.maps) {
          resolve(window.google);
        } else {
          reject(new Error("Google Maps failed to initialize."));
        }
      });
      existingScript.addEventListener("error", () => {
        reject(new Error("Failed to load Google Maps."));
      });
      return;
    }

    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
      apiKey
    )}&v=weekly`;
    script.async = true;
    script.defer = true;
    script.dataset.googleMapsLoader = "true";
    script.onload = () => {
      if (window.google?.maps) {
        resolve(window.google);
      } else {
        reject(new Error("Google Maps failed to initialize."));
      }
    };
    script.onerror = () => reject(new Error("Failed to load Google Maps."));
    document.head.appendChild(script);
  });

  return googleMapsApiPromise;
}

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

function extractLatLng(raw: Record<string, unknown>): LatLngLiteral | null {
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

function chunkStops(stops: RouteStop[], maxStopsPerChunk: number) {
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

function buildGoogleMapsDirectionsUrl(stops: RouteStop[]) {
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

function buildDirectionsRequest(stops: RouteStop[]) {
  return {
    origin: stops[0].position,
    destination: stops[stops.length - 1].position,
    waypoints: stops.slice(1, -1).map((stop) => ({
      location: stop.position,
      stopover: true,
    })),
    optimizeWaypoints: false,
    travelMode: "DRIVING",
  };
}

function routeDirections(service: GoogleDirectionsService, stops: RouteStop[]) {
  return new Promise<GoogleDirectionsResult>((resolve, reject) => {
    service.route(buildDirectionsRequest(stops), (result, status) => {
      if (status === "OK" && result) {
        resolve(result);
        return;
      }

      reject(new Error(`Directions request failed with status ${status}`));
    });
  });
}

export default function GoogleRoutesMap({ routes, bestRoutes }: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const overlaysRef = useRef<RouteOverlay[]>([]);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);

  const preparedRoutes = useMemo<PreparedRoute[]>(() => {
    return routes.map((route, routeIndex) => {
      const clusterRoutes = bestRoutes?.[String(routeIndex)];
      const backendStops =
        clusterRoutes && clusterRoutes !== "No Solution"
          ? Object.entries(clusterRoutes)
              .sort(([routeIdA], [routeIdB]) => Number(routeIdA) - Number(routeIdB))
              .flatMap(([backendRouteId, backendRouteStops]) =>
                buildStopsFromBackendRoute(
                  `${route.id}-${backendRouteId}`,
                  backendRouteStops
                )
              )
          : [];

      const skippedStops: RouteItem[] = [];
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
  }, [bestRoutes, routes]);

  const selectedRoute =
    preparedRoutes.find((route) => route.id === selectedRouteId) ?? null;

  useEffect(() => {
    const matchingRouteExists = preparedRoutes.some(
      (route) => route.id === selectedRouteId && route.stops.length >= 2
    );

    if (!matchingRouteExists) {
      const nextRoute =
        preparedRoutes.find((route) => route.stops.length >= 2) ?? null;
      setSelectedRouteId(nextRoute?.id ?? null);
    }
  }, [preparedRoutes, selectedRouteId]);

  useEffect(() => {
    const overlays = overlaysRef.current;

    overlays.forEach((overlay) => {
      const isSelected = overlay.routeId === selectedRouteId;
      overlay.polylines.forEach((polyline) => {
        polyline.setOptions({
          strokeOpacity: isSelected ? 0.95 : 0.45,
          strokeWeight: isSelected ? 6 : 4,
          zIndex: isSelected ? 10 : 1,
        });
      });

      overlay.markers.forEach((marker) => {
        marker.setOpacity(isSelected ? 1 : 0.72);
      });
    });
  }, [selectedRouteId]);

  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY) {
      setMapError(
        "Set VITE_GOOGLE_MAPS_API_KEY in your frontend environment to render routes."
      );
      return;
    }

    if (!mapRef.current) {
      return;
    }

    const routableRoutes = preparedRoutes.filter((route) => route.stops.length >= 2);

    if (routableRoutes.length === 0) {
      setMapError("No routes have at least two stops with latitude and longitude.");
      return;
    }

    let isCancelled = false;
    setIsRendering(true);
    setMapError(null);

    loadGoogleMapsApi(GOOGLE_MAPS_API_KEY)
      .then(async (googleApi) => {
        if (isCancelled || !mapRef.current) {
          return;
        }

        const map = new googleApi.maps.Map(mapRef.current, {
          center: routableRoutes[0].stops[0].position,
          zoom: 11,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: true,
        });

        const bounds = new googleApi.maps.LatLngBounds();
        const directionsService = new googleApi.maps.DirectionsService();
        const nextOverlays: RouteOverlay[] = [];

        for (const route of routableRoutes) {
          const polylines: GooglePolyline[] = [];
          const markers: GoogleMarker[] = [];
          const chunks = chunkStops(route.stops, MAX_STOPS_PER_DIRECTIONS_REQUEST);

          for (const [chunkIndex, chunk] of chunks.entries()) {
            const directions = await routeDirections(directionsService, chunk);
            const overviewPath = directions.routes[0]?.overview_path ?? [];

            if (overviewPath.length > 0) {
              const polyline = new googleApi.maps.Polyline({
                map,
                path: overviewPath,
                strokeColor: route.color,
                strokeOpacity: 0.45,
                strokeWeight: 4,
                clickable: true,
              });

              polyline.addListener("click", () => {
                setSelectedRouteId(route.id);
              });

              polylines.push(polyline);
              overviewPath.forEach((point: LatLngLiteral) => bounds.extend(point));
            }

            const markerStops =
              chunkIndex === 0 ? chunk : chunk.slice(1);

            markerStops.forEach((stop, stopOffset) => {
              const marker = new googleApi.maps.Marker({
                map,
                position: stop.position,
                title: `${route.title}: ${stop.name}`,
                label: {
                  text: String(chunkIndex * (MAX_STOPS_PER_DIRECTIONS_REQUEST - 1) + stopOffset + 1),
                  color: "#ffffff",
                  fontSize: "11px",
                  fontWeight: "700",
                },
                icon: {
                  path: googleApi.maps.SymbolPath.CIRCLE,
                  fillColor: route.color,
                  fillOpacity: 1,
                  strokeColor: "#ffffff",
                  strokeWeight: 2,
                  scale: 11,
                },
              });

              marker.addListener("click", () => {
                setSelectedRouteId(route.id);
              });

              markers.push(marker);
              bounds.extend(stop.position);
            });
          }

          nextOverlays.push({
            routeId: route.id,
            polylines,
            markers,
          });
        }

        if (isCancelled) {
          nextOverlays.forEach((overlay) => {
            overlay.polylines.forEach((polyline) => polyline.setMap(null));
            overlay.markers.forEach((marker) => marker.setMap(null));
          });
          return;
        }

        overlaysRef.current = nextOverlays;
        map.fitBounds(bounds);

        if (routableRoutes.length === 1) {
          map.setZoom(12);
        }
      })
      .catch((error: unknown) => {
        if (!isCancelled) {
          setMapError(
            error instanceof Error ? error.message : "Failed to render Google Map."
          );
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setIsRendering(false);
        }
      });

    return () => {
      isCancelled = true;
      overlaysRef.current.forEach((overlay) => {
        overlay.polylines.forEach((polyline) => polyline.setMap(null));
        overlay.markers.forEach((marker) => marker.setMap(null));
      });
      overlaysRef.current = [];
    };
  }, [preparedRoutes]);

  return (
    <div className="routes-map-layout">
      <div className="routes-map-frame">
        {mapError ? (
          <div className="map-status">{mapError}</div>
        ) : (
          <>
            {isRendering && <div className="map-loading">Rendering routes...</div>}
            <div ref={mapRef} className="routes-map-canvas" />
          </>
        )}
      </div>

      <aside className="routes-sidebar">
        <h3>Google Maps Export</h3>
        <p className="routes-sidebar-copy">
          Click a route line or a stop marker to view its export links.
        </p>

        <div className="routes-list">
          {preparedRoutes.map((route) => {
            const isSelected = route.id === selectedRouteId;
            const canRender = route.stops.length >= 2;

            return (
              <button
                key={route.id}
                type="button"
                className={`route-list-item${isSelected ? " selected" : ""}`}
                onClick={() => setSelectedRouteId(route.id)}
                disabled={!canRender}
              >
                <span
                  className="route-swatch"
                  style={{ backgroundColor: route.color }}
                />
                <span className="route-list-text">
                  {route.title} ({route.stops.length} mapped)
                  {route.skippedStops.length > 0
                    ? `, ${route.skippedStops.length} skipped`
                    : ""}
                </span>
              </button>
            );
          })}
        </div>

        {selectedRoute && (
          <div className="route-detail-card">
            <h4>{selectedRoute.title}</h4>
            <p>
              {selectedRoute.stops.length} mapped stops
              {selectedRoute.skippedStops.length > 0
                ? `, ${selectedRoute.skippedStops.length} skipped because they do not have lat/lng`
                : ""}
            </p>

            {selectedRoute.exportSegments.length > 0 ? (
              <div className="route-links">
                {selectedRoute.exportSegments.map((segment, index) => (
                  <a
                    key={segment.id}
                    href={segment.googleMapsUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="route-link-button"
                  >
                    Open in Google Maps
                    {selectedRoute.exportSegments.length > 1
                      ? ` (Part ${index + 1})`
                      : ""}
                  </a>
                ))}
              </div>
            ) : (
              <p>At least two mapped stops are required to export directions.</p>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
