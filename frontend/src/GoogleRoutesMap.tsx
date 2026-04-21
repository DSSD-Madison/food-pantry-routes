import { useEffect, useMemo, useRef, useState } from "react";
import type { BackendBestRoutes, CardData } from "./DragDropDemo";
import {
  chunkStops,
  prepareRoutesForExport,
  type LatLngLiteral,
  type PreparedRoute,
  type RouteStop,
} from "./routeExport";

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

type RouteOverlay = {
  routeId: string;
  polylines: GooglePolyline[];
  markers: GoogleMarker[];
};

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const MAX_STOPS_PER_DIRECTIONS_REQUEST = 25;

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
    return prepareRoutesForExport(routes, bestRoutes);
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

            markerStops.forEach((stop: RouteStop, stopOffset: number) => {
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

        <div className="routes-list-section">
          <h4>Select a group</h4>
          <div className="routes-list-wrap">
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
          </div>
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
