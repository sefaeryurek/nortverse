"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { LiveHTMatch } from "./api";

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const publicUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");
  if (publicUrl) {
    const url = new URL(publicUrl);
    return `${url.protocol === "https:" ? "wss:" : "ws:"}//${url.host}/ws/live-ht`;
  }
  return `${proto}//${window.location.host}/ws/live-ht`;
}

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000];
const PING_INTERVAL = 30_000;

export type WsStatus = "connecting" | "connected" | "disconnected" | "fallback";

export interface UseLiveWsResult {
  matches: LiveHTMatch[];
  status: WsStatus;
  lastUpdate: Date | null;
}

export function useLiveWs(): UseLiveWsResult {
  const [matches, setMatches] = useState<LiveHTMatch[]>([]);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCount = useRef(0);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmounted = useRef(false);

  const cleanup = useCallback(() => {
    if (pingTimer.current) {
      clearInterval(pingTimer.current);
      pingTimer.current = null;
    }
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      if (wsRef.current.readyState <= WebSocket.OPEN) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (unmounted.current) return;
    cleanup();

    const url = getWsUrl();
    if (!url) {
      setStatus("fallback");
      return;
    }

    setStatus("connecting");

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmounted.current) return;
        retryCount.current = 0;
        setStatus("connected");
        pingTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, PING_INTERVAL);
      };

      ws.onmessage = (event) => {
        if (unmounted.current) return;
        if (event.data === "pong") return;
        try {
          const data = JSON.parse(event.data) as LiveHTMatch[];
          setMatches(data);
          setLastUpdate(new Date());
        } catch {
          // parse hatası — yoksay
        }
      };

      ws.onerror = () => {
        // onclose tetiklenecek
      };

      ws.onclose = () => {
        if (unmounted.current) return;
        if (pingTimer.current) {
          clearInterval(pingTimer.current);
          pingTimer.current = null;
        }
        const idx = Math.min(retryCount.current, RECONNECT_DELAYS.length - 1);
        const delay = RECONNECT_DELAYS[idx];
        retryCount.current++;

        if (retryCount.current > RECONNECT_DELAYS.length) {
          setStatus("fallback");
          return;
        }

        setStatus("disconnected");
        reconnectTimer.current = setTimeout(connect, delay);
      };
    } catch {
      setStatus("fallback");
    }
  }, [cleanup]);

  useEffect(() => {
    unmounted.current = false;
    connect();
    return () => {
      unmounted.current = true;
      cleanup();
    };
  }, [connect, cleanup]);

  return { matches, status, lastUpdate };
}
